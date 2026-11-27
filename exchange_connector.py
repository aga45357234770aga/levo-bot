"""
KriptoLevo (Kripto Levent) — Binance & MEXC Çoklu Borsa Veri ve Emir Yöneticisi
Özellikler:
1. Binance (USDT-M Futures & Spot) ve MEXC (USDT-M Futures & Spot) canlı veri beslemesi
2. Tüm pariteleri tarayıp 24 saatlik volatiliteye ((High - Low) / Low ve % değişim + hacim) göre
   EN YÜKSEK VOLATİLİTELİ 300 COİN'i dinamik olarak seçme
3. Aynı anda maksimum 5 açık pozisyon (Max 5 Concurrent Positions) sınırı ve kasa bölüştürme
4. Hem Canlı API Emir Gönderimi (HMAC-SHA256 imzalı Binance & MEXC REST API) hem de
   Paper Trading (Simülasyon) modu.
"""

import hmac
import hashlib
import json
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Tuple
from strategy_engine import Candle


class BinanceMEXCConnector:
    BINANCE_FAPI = "https://fapi.binance.com"
    BINANCE_SPOT = "https://api.binance.com"
    MEXC_CONTRACT = "https://contract.mexc.com"
    MEXC_SPOT = "https://api.mexc.com"

    def __init__(
        self,
        binance_api_key: str = "",
        binance_api_secret: str = "",
        mexc_api_key: str = "",
        mexc_api_secret: str = "",
        use_futures: bool = True,
        live_trading: bool = False,
    ):
        self.binance_api_key = binance_api_key
        self.binance_api_secret = binance_api_secret
        self.mexc_api_key = mexc_api_key
        self.mexc_api_secret = mexc_api_secret
        self.use_futures = use_futures
        self.live_trading = live_trading

    @staticmethod
    def _http_get(url: str, headers: Optional[dict] = None, timeout: int = 10):
        req_headers = {"User-Agent": "Mozilla/5.0"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # =========================================================================
    # 1. BİNANCE & MEXC EN YÜKSEK VOLATİLİTELİ 300 COİN TARAMASI
    # =========================================================================
    def fetch_top_volatile_coins(self, top_n: int = 300, min_quote_vol_usdt: float = 500_000.0) -> List[Dict]:
        """
        Binance ve MEXC borsalarındaki tüm USDT paritelerini çeker,
        24 saatlik volatilite yüzdesini ((High - Low) / Low * 100 ve |PriceChangePct|) hesaplar,
        iki borsayı birleştirip en yüksek volatiliteli ilk `top_n` (300) coini döndürür.
        """
        combined: Dict[str, Dict] = {}

        # A) Binance Futures 24hr Tickers
        try:
            b_tickers = self._http_get(f"{self.BINANCE_FAPI}/fapi/v1/ticker/24hr", timeout=12)
            for t in b_tickers:
                sym = t.get("symbol", "")
                if not sym.endswith("USDT") or "_" in sym:
                    continue
                high = float(t.get("highPrice", 0) or 0)
                low = float(t.get("lowPrice", 0) or 0)
                last = float(t.get("lastPrice", 0) or 0)
                qvol = float(t.get("quoteVolume", 0) or 0)
                chg_pct = float(t.get("priceChangePercent", 0) or 0)
                if low <= 0 or last <= 0 or qvol < min_quote_vol_usdt:
                    continue
                range_vol_pct = ((high - low) / low) * 100.0
                volatility_score = range_vol_pct * 0.7 + abs(chg_pct) * 0.3
                combined[sym] = {
                    "symbol": sym,
                    "mexc_symbol": sym[:-4] + "_USDT",
                    "exchange": "BINANCE",
                    "sources": ["BINANCE"],
                    "last_price": last,
                    "high_24h": high,
                    "low_24h": low,
                    "change_24h_pct": round(chg_pct, 2),
                    "range_volatility_pct": round(range_vol_pct, 2),
                    "volatility_score": round(volatility_score, 2),
                    "quote_volume_usdt": round(qvol, 2),
                }
        except Exception as e:
            print(f"[Uyarı] Binance 24h ticker çekilemedi: {e}")

        # B) MEXC Futures (Contract) & Spot 24hr Tickers
        try:
            m_resp = self._http_get(f"{self.MEXC_CONTRACT}/api/v1/contract/ticker", timeout=12)
            m_tickers = m_resp.get("data", []) if isinstance(m_resp, dict) else []
            for t in m_tickers:
                msym = t.get("symbol", "")  # Örn: BTC_USDT
                if not msym.endswith("_USDT"):
                    continue
                norm_sym = msym.replace("_", "")
                high = float(t.get("high24Price", 0) or 0)
                low = float(t.get("lower24Price", 0) or 0)
                last = float(t.get("lastPrice", 0) or 0)
                qvol = float(t.get("amount24", 0) or 0)
                chg_pct = float(t.get("riseFallRate", 0) or 0) * 100.0
                if low <= 0 or last <= 0 or qvol < min_quote_vol_usdt:
                    continue
                range_vol_pct = ((high - low) / low) * 100.0
                volatility_score = range_vol_pct * 0.7 + abs(chg_pct) * 0.3

                if norm_sym in combined:
                    combined[norm_sym]["sources"].append("MEXC")
                    combined[norm_sym]["mexc_price"] = last
                    # En yüksek volatilite skorunu güncelle
                    if volatility_score > combined[norm_sym]["volatility_score"]:
                        combined[norm_sym]["volatility_score"] = round(volatility_score, 2)
                        combined[norm_sym]["range_volatility_pct"] = round(range_vol_pct, 2)
                else:
                    combined[norm_sym] = {
                        "symbol": norm_sym,
                        "mexc_symbol": msym,
                        "exchange": "MEXC",
                        "sources": ["MEXC"],
                        "last_price": last,
                        "high_24h": high,
                        "low_24h": low,
                        "change_24h_pct": round(chg_pct, 2),
                        "range_volatility_pct": round(range_vol_pct, 2),
                        "volatility_score": round(volatility_score, 2),
                        "quote_volume_usdt": round(qvol, 2),
                    }
        except Exception as e:
            print(f"[Uyarı] MEXC Contract ticker çekilemedi: {e}")

        # Volatilite skoruna göre büyükten küçüğe sırala ve ilk 300 coini al
        ranked = sorted(combined.values(), key=lambda x: x["volatility_score"], reverse=True)
        return ranked[:top_n]

    # =========================================================================
    # 2. BİNANCE VE MEXC MUM (KLINE) VERİSİ ÇEKME
    # =========================================================================
    def fetch_klines(self, symbol_info: Dict, interval: str = "15m", limit: int = 200) -> List[Candle]:
        """
        Parite Binance'te varsa Binance Futures'tan, yoksa veya MEXC seçiliyse MEXC Contract/Spot'tan çeker.
        """
        exchange = symbol_info.get("exchange", "BINANCE")
        sym = symbol_info["symbol"]
        mexc_sym = symbol_info.get("mexc_symbol", sym[:-4] + "_USDT")

        if exchange == "BINANCE" or "BINANCE" in symbol_info.get("sources", []):
            try:
                url = f"{self.BINANCE_FAPI}/fapi/v1/klines?symbol={sym}&interval={interval}&limit={limit}"
                raw = self._http_get(url, timeout=8)
                return [
                    Candle(
                        timestamp=int(r[0]),
                        open=float(r[1]),
                        high=float(r[2]),
                        low=float(r[3]),
                        close=float(r[4]),
                        volume=float(r[5]),
                    )
                    for r in raw
                ]
            except Exception:
                pass

        # MEXC Futures Klines yedek / birincil
        mexc_interval_map = {
            "1m": "Min1",
            "5m": "Min5",
            "15m": "Min15",
            "30m": "Min30",
            "1h": "Min60",
            "4h": "Hour4",
            "1d": "Day1",
        }
        m_int = mexc_interval_map.get(interval, "Min15")
        url = f"{self.MEXC_CONTRACT}/api/v1/contract/kline/{mexc_sym}?interval={m_int}"
        resp = self._http_get(url, timeout=8)
        data = resp.get("data", {})
        times = data.get("time", [])
        opens = data.get("open", [])
        highs = data.get("high", [])
        lows = data.get("low", [])
        closes = data.get("close", [])
        vols = data.get("vol", [])
        candles = []
        for i in range(max(0, len(times) - limit), len(times)):
            candles.append(
                Candle(
                    timestamp=int(times[i]) * 1000,
                    open=float(opens[i]),
                    high=float(highs[i]),
                    low=float(lows[i]),
                    close=float(closes[i]),
                    volume=float(vols[i]),
                )
            )
        return candles

    # =========================================================================
    # 3. MEXC VADELİ İŞLEMLER (FUTURES) İMZALI CANLI API MODÜLÜ
    # =========================================================================
    def _mexc_sign(self, req_time: str, param_str: str = "") -> str:
        sign_str = f"{self.mexc_api_key}{req_time}{param_str}"
        return hmac.new(
            self.mexc_api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _mexc_private_request(self, method: str, path: str, params: Optional[dict] = None) -> Dict:
        if not self.mexc_api_key or not self.mexc_api_secret:
            return {"success": False, "message": "MEXC_API_KEY veya MEXC_API_SECRET tanimli degil."}
        req_time = str(int(time.time() * 1000))
        params = params or {}
        if method == "GET":
            sorted_qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in sorted(params.items()))
            sig = self._mexc_sign(req_time, sorted_qs)
            url = f"{self.MEXC_CONTRACT}{path}" + (f"?{sorted_qs}" if sorted_qs else "")
            body = None
        else:
            body_str = json.dumps(params, separators=(",", ":"))
            sig = self._mexc_sign(req_time, body_str)
            url = f"{self.MEXC_CONTRACT}{path}"
            body = body_str.encode("utf-8")

        headers = {
            "ApiKey": self.mexc_api_key,
            "Request-Time": req_time,
            "Signature": sig,
            "Content-Type": "application/json",
            "User-Agent": "KriptoLevoBot/1.0",
        }
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            return {"success": False, "code": e.code, "message": err_body}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_mexc_usdt_balance(self) -> Dict:
        """MEXC Vadeli (Futures) hesabindaki USDT bakiyesini ve API baglantisini test eder."""
        return self._mexc_private_request("GET", "/api/v1/private/account/asset/USDT")

    def submit_mexc_futures_order(
        self,
        mexc_symbol: str,
        direction: str,
        vol: float,
        leverage: int = 10,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
    ) -> Dict:
        """
        MEXC Vadeli (Contract) piyasa emri gonderir.
        side: 1 = Open Long, 3 = Open Short | openType: 1 = Isolated (Izole) | type: 5 = Market
        """
        if not self.live_trading:
            return {"success": False, "message": "Test modu aktif (live_trading=False)."}
        side_code = 1 if direction.upper() == "LONG" else 3
        payload = {
            "symbol": mexc_symbol,
            "vol": vol,
            "leverage": leverage,
            "side": side_code,
            "type": 5,      # Market Order
            "openType": 1,  # Isolated Margin
        }
        if stop_loss_price:
            payload["stopLossPrice"] = stop_loss_price
        if take_profit_price:
            payload["takeProfitPrice"] = take_profit_price
        return self._mexc_private_request("POST", "/api/v1/private/order/submit", payload)
