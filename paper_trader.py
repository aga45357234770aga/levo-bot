"""
KriptoLevo (Kripto Levent) — 7/24 Test (Paper Trading) Motoru
- Binance & MEXC borsalarından en yüksek volatiliteli 300 coini çeker
- Paralel tarama ile Kripto Levent Özel Fibonacci, Mavi Kutu, OB, FVG ve 14 Koşul Tablosunu hesaplar
- Aynı anda maksimum 5 açık pozisyon (Max 5 Concurrent Positions) sınırı uygular
- TP1'de %75 kâr alıp stopu girişe (Breakeven) çeker, TP2'de kalan %25'i kapatır
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

from exchange_connector import BinanceMEXCConnector
from strategy_engine import KriptoLevoStrategyEngine

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")


class PaperTradingBot:
    def __init__(
        self,
        initial_balance: float = 100.0,
        max_positions: int = 5,
        risk_per_trade_pct: float = 2.0,
        leverage: int = 10,
        top_volatile_count: int = 300,
    ):
        self.connector = BinanceMEXCConnector(live_trading=False)
        self.engine = KriptoLevoStrategyEngine()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.max_positions = max_positions
        self.risk_per_trade_pct = risk_per_trade_pct
        self.leverage = leverage
        self.top_volatile_count = top_volatile_count

        self.is_running = True
        self.last_scan_time: Optional[str] = None
        self.volatile_300: List[Dict] = []
        self.open_positions: Dict[str, Dict] = {}
        self.closed_trades: List[Dict] = []
        self.signals_feed: List[Dict] = []
        self.webhook_alerts: List[Dict] = []
        self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.balance = data.get("balance", self.initial_balance)
                self.is_running = data.get("is_running", True)
                self.last_scan_time = data.get("last_scan_time")
                self.volatile_300 = data.get("volatile_300", [])
                self.open_positions = data.get("open_positions", {})
                self.closed_trades = data.get("closed_trades", [])
                self.signals_feed = data.get("signals_feed", [])
                self.webhook_alerts = data.get("webhook_alerts", [])
            except Exception:
                pass

    def save_state(self):
        data = {
            "mode": "TEST (SANAL BAKİYE)",
            "initial_balance": self.initial_balance,
            "balance": round(self.balance, 2),
            "max_positions": self.max_positions,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "leverage": self.leverage,
            "top_volatile_count": self.top_volatile_count,
            "is_running": self.is_running,
            "last_scan_time": self.last_scan_time,
            "volatile_300": self.volatile_300,
            "open_positions": self.open_positions,
            "closed_trades": self.closed_trades[-100:],
            "signals_feed": self.signals_feed[:60],
            "webhook_alerts": self.webhook_alerts[:30],
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _analyze_single_coin(self, coin_info: Dict, timeframe: str = "15m", htf: str = "1h") -> Optional[Dict]:
        sym = coin_info["symbol"]
        try:
            candles = self.connector.fetch_klines(coin_info, interval=timeframe, limit=180)
            if len(candles) < 65:
                return None
            htf_candles = self.connector.fetch_klines(coin_info, interval=htf, limit=80)
            plan = self.engine.build_fib_plan(sym, timeframe, candles, htf_candles)
            if not plan:
                return None
            last_price = candles[-1].close
            return {
                "symbol": sym,
                "exchange": coin_info["exchange"],
                "sources": coin_info["sources"],
                "volatility_score": coin_info["volatility_score"],
                "range_volatility_pct": coin_info["range_volatility_pct"],
                "change_24h_pct": coin_info["change_24h_pct"],
                "quote_volume_usdt": coin_info["quote_volume_usdt"],
                "last_price": last_price,
                "timeframe": timeframe,
                "direction": plan.direction,
                "status": plan.status,
                "grade": plan.grade,
                "score_14": plan.score_14,
                "entry_method": plan.entry_method,
                "entry_price": round(plan.entry_price, 6),
                "stop_price": round(plan.stop_price, 6),
                "tp1": round(plan.tp1, 6),
                "tp2": round(plan.tp2, 6),
                "tp3": round(plan.tp3, 6),
                "tp4": round(plan.tp4, 6),
                "gross_r": plan.gross_r,
                "net_r": plan.net_r,
                "fib_levels": {k: round(v, 6) for k, v in plan.fib_levels.items()},
                "confluences": plan.confluences,
            }
        except Exception:
            return None

    def update_open_positions(self, price_map: Dict[str, float]):
        to_close = []
        for sym, pos in self.open_positions.items():
            cur_price = price_map.get(sym)
            if cur_price is None:
                continue
            pos["current_price"] = cur_price
            entry = pos["entry_price"]
            direction = pos["direction"]
            pnl_pct = ((cur_price - entry) / entry) if direction == "LONG" else ((entry - cur_price) / entry)
            pos["unrealized_pnl_usdt"] = round(pos["remaining_notional"] * pnl_pct, 2)

            # Stop kontrolü
            hit_stop = (cur_price <= pos["stop_price"]) if direction == "LONG" else (cur_price >= pos["stop_price"])
            if hit_stop:
                realized = pos.get("realized_pnl_usdt", 0.0) + pos["unrealized_pnl_usdt"]
                self.balance += pos["unrealized_pnl_usdt"]
                pos["exit_price"] = cur_price
                pos["realized_pnl_usdt"] = round(realized, 2)
                pos["close_reason"] = "BREAKEVEN_STOP" if pos["tp1_hit"] else "STOP_LOSS"
                pos["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                to_close.append(sym)
                continue

            # TP1 (%75 Çıkış + Giriş-Stop)
            if not pos["tp1_hit"]:
                hit_tp1 = (cur_price >= pos["tp1"]) if direction == "LONG" else (cur_price <= pos["tp1"])
                if hit_tp1:
                    close_notional = pos["initial_notional"] * 0.75
                    tp1_pnl = close_notional * (abs(pos["tp1"] - entry) / entry)
                    self.balance += tp1_pnl
                    pos["realized_pnl_usdt"] = round(pos.get("realized_pnl_usdt", 0.0) + tp1_pnl, 2)
                    pos["remaining_notional"] = round(pos["initial_notional"] * 0.25, 2)
                    pos["tp1_hit"] = True
                    pos["stop_price"] = entry  # TP1 sonrası Giriş-Stop (Breakeven)!
                    pos["status_note"] = "TP1 (%75) Alındı • Stop Girişte"

            # TP2 (%25 Çıkış)
            if pos["tp1_hit"]:
                hit_tp2 = (cur_price >= pos["tp2"]) if direction == "LONG" else (cur_price <= pos["tp2"])
                if hit_tp2:
                    tp2_pnl = pos["remaining_notional"] * (abs(pos["tp2"] - entry) / entry)
                    self.balance += tp2_pnl
                    pos["realized_pnl_usdt"] = round(pos.get("realized_pnl_usdt", 0.0) + tp2_pnl, 2)
                    pos["exit_price"] = cur_price
                    pos["close_reason"] = "TP2_TARGET"
                    pos["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    to_close.append(sym)

        for sym in to_close:
            self.closed_trades.insert(0, self.open_positions.pop(sym))

    def manual_close_position(self, symbol: str) -> Optional[Dict]:
        """Kullanıcının arayüzden tek tuşla açık pozisyonu manuel kapatmasını sağlar."""
        sym = symbol.upper().strip()
        pos = self.open_positions.get(sym)
        if not pos:
            return None
        cur_price = pos.get("current_price", pos["entry_price"])
        entry = pos["entry_price"]
        direction = pos["direction"]
        pnl_pct = ((cur_price - entry) / entry) if direction == "LONG" else ((entry - cur_price) / entry)
        unrl = round(pos["remaining_notional"] * pnl_pct, 2)
        self.balance += unrl
        pos["exit_price"] = cur_price
        pos["realized_pnl_usdt"] = round(pos.get("realized_pnl_usdt", 0.0) + unrl, 2)
        pos["close_reason"] = "MANUEL_KAPATMA"
        pos["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        closed = self.open_positions.pop(sym)
        self.closed_trades.insert(0, closed)
        self.save_state()
        return closed

    def run_cycle(self, scan_limit: int = 80) -> Dict:
        """
        1) Binance + MEXC'den en yüksek volatiliteli 300 coini çeker
        2) Açık pozisyonların güncel fiyatlarını ve TP1/TP2/Stop durumlarını günceller
        3) İlk `scan_limit` yüksek volatiliteli coin üzerinde paralel Kripto Levent strateji taraması yapar
        4) Aynı anda max 5 açık pozisyon sınırını koruyarak uygun A/B derece sinyalleri test işlemine alır
        """
        top300 = self.connector.fetch_top_volatile_coins(top_n=self.top_volatile_count)
        self.volatile_300 = top300
        price_map = {c["symbol"]: c["last_price"] for c in top300}

        # Açık pozisyonları güncelle
        self.update_open_positions(price_map)

        signals: List[Dict] = []
        candidates = top300[:scan_limit]
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [pool.submit(self._analyze_single_coin, c) for c in candidates]
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    signals.append(res)

        # Derece (A önce) ve Net R + Volatiliteye göre sırala
        grade_rank = {"A": 0, "B": 1, "C": 2}
        signals.sort(key=lambda x: (grade_rank.get(x["grade"], 2), -x["score_14"], -x["volatility_score"]))
        self.signals_feed = signals

        # Yeni Test İşlemi Aç (Aynı anda max 5 pozisyon!)
        if self.is_running:
            for sig in signals:
                if len(self.open_positions) >= self.max_positions:
                    break
                sym = sig["symbol"]
                if sym in self.open_positions:
                    continue
                if sig["grade"] not in ("A", "B"):
                    continue
                if sig["status"] not in ("ACTIVE", "WAITING_ENTRY"):
                    continue
                if sig["net_r"] < 0.8:
                    continue

                entry = sig["entry_price"]
                stop = sig["stop_price"]
                stop_dist = abs(entry - stop) / max(entry, 1e-12)
                if stop_dist <= 0.001:
                    continue
                risk_usdt = self.balance * (self.risk_per_trade_pct / 100.0)
                notional = min(risk_usdt / stop_dist, (self.balance / self.max_positions) * self.leverage)
                margin = notional / self.leverage

                self.open_positions[sym] = {
                    "id": f"{sym}_{int(time.time())}",
                    "symbol": sym,
                    "exchange": sig["exchange"],
                    "direction": sig["direction"],
                    "grade": sig["grade"],
                    "score_14": sig["score_14"],
                    "entry_price": entry,
                    "current_price": sig["last_price"],
                    "stop_price": stop,
                    "initial_stop": stop,
                    "tp1": sig["tp1"],
                    "tp2": sig["tp2"],
                    "tp3": sig["tp3"],
                    "tp4": sig["tp4"],
                    "tp1_hit": False,
                    "initial_notional": round(notional, 2),
                    "remaining_notional": round(notional, 2),
                    "leverage": self.leverage,
                    "margin_usdt": round(margin, 2),
                    "margin_pct": round((margin / max(self.balance, 1e-12)) * 100.0, 2),
                    "risk_usdt": round(risk_usdt, 2),
                    "unrealized_pnl_usdt": 0.0,
                    "realized_pnl_usdt": 0.0,
                    "net_r": sig["net_r"],
                    "volatility_score": sig["volatility_score"],
                    "confluences": sig["confluences"],
                    "fib_levels": sig["fib_levels"],
                    "status_note": "Açık (TP1 %75 Bekleniyor)",
                    "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

        self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_state()
        return {
            "top300_count": len(self.volatile_300),
            "signals_found": len(self.signals_feed),
            "open_positions": len(self.open_positions),
            "balance": round(self.balance, 2),
        }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    bot = PaperTradingBot()
    summary = bot.run_cycle(scan_limit=60)
    print("Tarama Tamamlandı:", summary)
