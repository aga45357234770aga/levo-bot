"""
KriptoLevo (Kripto Levent) — 7/24 Otomatik Kripto Al-Sat Botu & Canlı Tarayıcı
Özellikler:
- Gerçek zamanlı borsa verisi çekme (Binance / Bitget USDT-M Futures API & CCXT uyumlu)
- Kripto Levent Özel Fibonacci (1.8x Impuls Mum, EMA 50, EMA 144-169 Vegas Bulutu, HTF Trend)
- Mavi Kutular (Major Kutular), Emir Blokları (OB), Adil Değer Boşluğu (FVG) ve Likidite Süpürülmesi (ICT Sweep)
- 14 Koşullu Teknik Analiz Filtresi (A/B/C Derecelendirmesi — Kör Giriş Engelleme)
- Kademeli Çıkış ve Otomatik Stop Yönetimi:
  * TP1'de %75 Kar Al + Stopu Girişe Çek (Breakeven / Giriş-Stop)
  * TP2/TP3/TP4'te kalan %25 ile kâr sürme
- TradingView Webhook Dinleyici & Telegram Bildirim Entegrasyonu
"""

import json
import urllib.request
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from strategy_engine import Candle, KriptoLevoStrategyEngine, FibPlan


class MarketDataFetcher:
    """Binance Futures ve Bitget Futures üzerinden API anahtarı gerektirmeden canlı mum verisi çeker."""

    @staticmethod
    def fetch_binance_futures_klines(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 200) -> List[Candle]:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
        candles = []
        for row in raw:
            candles.append(
                Candle(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        return candles


class KriptoLevoAutoTrader:
    def __init__(self, initial_balance_usdt: float = 200.0, risk_per_trade_pct: float = 2.0, leverage: int = 10):
        self.balance_usdt = initial_balance_usdt
        self.risk_per_trade_pct = risk_per_trade_pct
        self.leverage = leverage
        self.engine = KriptoLevoStrategyEngine()
        self.open_positions: Dict[str, dict] = {}
        self.trade_history: List[dict] = []

    def calculate_position_size(self, entry_price: float, stop_price: float) -> Dict[str, float]:
        """
        Kripto Levent 'Küçük Hesapta En Kritik Kural: Pozisyon Boyutu' ve 'Kaldıraç ve İşlem Başına Risk':
        Stop mesafesine göre kasanın yalnızca belirli bir yüzdesini (ör. %2 - %5) riske eder.
        """
        risk_usdt = self.balance_usdt * (self.risk_per_trade_pct / 100.0)
        stop_dist_pct = abs(entry_price - stop_price) / max(entry_price, 1e-12)
        if stop_dist_pct <= 0:
            return {"qty": 0.0, "notional_usdt": 0.0, "margin_usdt": 0.0, "risk_usdt": 0.0}
        notional_usdt = risk_usdt / stop_dist_pct
        max_notional = self.balance_usdt * self.leverage * 0.90
        notional_usdt = min(notional_usdt, max_notional)
        qty = notional_usdt / entry_price
        margin_usdt = notional_usdt / self.leverage
        return {
            "qty": round(qty, 4),
            "notional_usdt": round(notional_usdt, 2),
            "margin_usdt": round(margin_usdt, 2),
            "risk_usdt": round(risk_usdt, 2),
        }

    def scan_watchlist(self, symbols: List[str], timeframe: str = "15m", htf: str = "1h") -> List[dict]:
        results = []
        for sym in symbols:
            try:
                candles = MarketDataFetcher.fetch_binance_futures_klines(sym, timeframe, 220)
                htf_candles = MarketDataFetcher.fetch_binance_futures_klines(sym, htf, 120)
                atr = self.engine.calc_atr(candles, 14)
                closes = [c.close for c in candles]
                rsi = self.engine.calc_rsi(closes, 14)
                ema50 = self.engine.calc_ema(closes, 50)
                ema144 = self.engine.calc_ema(closes, 144)
                ema169 = self.engine.calc_ema(closes, 169)

                plan = self.engine.build_fib_plan(sym, timeframe, candles, htf_candles)
                fvg_gaps = self.engine.detect_fvg_and_gaps(candles, atr)
                obs = self.engine.detect_order_blocks(candles, atr)
                boxes = self.engine.detect_major_boxes(candles, atr)
                sweep = self.engine.detect_liquidity_sweep(candles)

                # Mevcut mum yönüne göre 14 koşul skoru
                default_dir = plan.direction if plan else ("LONG" if closes[-1] >= ema50[-1] else "SHORT")
                score14, grade14, conds14 = self.engine.evaluate_14_conditions(candles, default_dir, 1)

                pos_sizing = None
                if plan:
                    pos_sizing = self.calculate_position_size(plan.entry_price, plan.stop_price)

                results.append({
                    "symbol": sym,
                    "timeframe": timeframe,
                    "last_price": closes[-1],
                    "rsi_14": round(rsi[-1], 2),
                    "ema50": round(ema50[-1], 4),
                    "vegas_cloud": f"{min(ema144[-1], ema169[-1]):.4f} - {max(ema144[-1], ema169[-1]):.4f}",
                    "trend_dir": default_dir,
                    "score_14": score14,
                    "grade": grade14,
                    "conditions_14": conds14,
                    "liquidity_sweep": sweep,
                    "active_fvg_count": len([z for z in fvg_gaps if "FVG" in z.zone_type]),
                    "active_ob_count": len(obs),
                    "major_boxes": [
                        {
                            "top": round(b.top, 4),
                            "mid": round(b.mid, 4),
                            "bottom": round(b.bottom, 4),
                            "break_dir": b.break_dir,
                            "state": b.state_label,
                        }
                        for b in boxes
                    ],
                    "fib_plan": {
                        "direction": plan.direction,
                        "status": plan.status,
                        "entry_method": plan.entry_method,
                        "entry_price": round(plan.entry_price, 4),
                        "stop_price": round(plan.stop_price, 4),
                        "tp1_75pct": round(plan.tp1, 4),
                        "tp2_25pct": round(plan.tp2, 4),
                        "tp3": round(plan.tp3, 4),
                        "tp4": round(plan.tp4, 4),
                        "gross_r": plan.gross_r,
                        "net_r": plan.net_r,
                        "bars_waited": plan.bars_waited,
                        "tp1_hit": plan.tp1_hit,
                        "confluences": plan.confluences,
                        "position_sizing": pos_sizing,
                    } if plan else None,
                })
            except Exception as e:
                results.append({"symbol": sym, "error": str(e)})
        return results


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    watchlist = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "ZECUSDT", "YGGUSDT",
        "XRPUSDT", "SUIUSDT", "1000PEPEUSDT", "LINKUSDT", "DOGEUSDT", "ACTUSDT"
    ]
    bot = KriptoLevoAutoTrader(initial_balance_usdt=200.0, risk_per_trade_pct=3.0, leverage=10)
    print("=====================================================================")
    print("  KRİPTO LEVENT (@KriptoLevo) OTOMATİK AL-SAT BOTU — CANLI TARAMA")
    print("=====================================================================")
    scan_data = bot.scan_watchlist(watchlist, timeframe="15m", htf="1h")
    with open(r"C:\Users\Arif\.gemini\antigravity\scratch\kriptolevo-bot\latest_scan.json", "w", encoding="utf-8") as f:
        json.dump(scan_data, f, ensure_ascii=False, indent=2)

    for item in scan_data:
        if "error" in item:
            print(f"[{item['symbol']}] Hata: {item['error']}")
            continue
        p = item["fib_plan"]
        print(f"\n▶ {item['symbol']} ({item['timeframe']}) | Fiyat: {item['last_price']} | RSI: {item['rsi_14']} | Tablo: {item['score_14']}/14 (Derece: {item['grade']})")
        print(f"  EMA50: {item['ema50']} | Vegas Bulutu (144-169): {item['vegas_cloud']} | FVG: {item['active_fvg_count']} | OB: {item['active_ob_count']} | Likidite: {item['liquidity_sweep'] or 'Yok'}")
        if item["major_boxes"]:
            mb = item["major_boxes"][-1]
            print(f"  Mavi Kutu (Major): Alt={mb['bottom']} | Orta={mb['mid']} | Üst={mb['top']} | Kırılım={mb['break_dir']} | Durum={mb['state']}")
        if p:
            print(f"  🎯 ÖZEL FIB PLANI [{p['direction']}] — Durum: {p['status']} ({p['entry_method']})")
            print(f"     Giriş: {p['entry_price']} | Stop: {p['stop_price']} (TP1 sonrası Giriş-Stop)")
            print(f"     TP1 (%75 Çıkış): {p['tp1_75pct']} | TP2 (%25 Çıkış): {p['tp2_25pct']} | TP3: {p['tp3']} | TP4: {p['tp4']}")
            print(f"     R Oranı: Brüt {p['gross_r']}R / Maliyetli Net {p['net_r']}R | Kesişimler: {', '.join(p['confluences']) if p['confluences'] else 'Temiz'}")
            ps = p["position_sizing"]
            print(f"     Pozisyon (200$ Kasa, 10x, %3 Risk): Miktar={ps['qty']} ({ps['notional_usdt']}$ Büyüklük, {ps['margin_usdt']}$ Marjin, Risk={ps['risk_usdt']}$)")
