"""
KriptoLevo (Kripto Levent) — Birebir Strateji ve İndikatör Motoru (KL Modüler v6.8.4)
İçerdiği Modüller:
1. Kripto Levent Özel Fibonacci (1.8x Impuls Mum, EMA 50 & EMA 144-169 Vegas Bulutu, HTF Trend,
   0.382 / 0.500 / 0.618 Giriş, 20 Mum Bekleme Süresi, TP1-TP4 Hedefler, Fitil/Kapanış Stop)
2. Mavi Kutular (Major & Minor Kutular): Üst/Orta/Alt Seviyeler, İlk Kapanış Kırılımı, %3 Temas Toleransı ile
   Sıralı Hareket Takibi (BEKLİYOR -> YAPTI)
3. SMC / ICT Yapıları:
   - Emir Blokları (Internal 20 & External 50 Order Blocks + %50 Orta Çizgi)
   - FVG (Fair Value Gap - 1.5 ATR filtresi ve %50 denge seviyesi) & Normal GAP (2 mum fitil boşluğu)
   - Likidite Süpürülmesi (Liquidity Sweep / Onaylı Pivot 5/8 tepe-dip üstü fitil + içeride kapanış)
   - Piyasa Yapısı Kırılımları (BOS / MSS / CHoCH & Eşit Tepe/Dip EQH/EQL)
4. 14 Koşullu Teknik Analiz & Filtre Tablosu (A/B/C Derecelendirmesi: A >= 10, B = 7-9, C < 7)
5. 10 Gösterge Uyumsuzluk (Divergence) Dedektörü (RSI, MACD, Stoch, CCI, Momentum, OBV, MFI, VWAP, CMF, Williams %R)
6. Seanslar (Asya, Londra, New York), Önceki Gün Tepe/Dip (PDH/PDL) ve Günlük TPO (POC, VAH, VAL)
7. Kademeli Çıkış ve Risk Yönetimi: TP1'de %75 Kar Al + Stopu Girişe Çek (Breakeven), TP2-TP4'te %25 Sür,
   Komisyon/Kayma Düşülmüş Net R Hesabı.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math
import time


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def range_size(self) -> float:
        return max(self.high - self.low, 1e-12)


@dataclass
class FibPlan:
    symbol: str
    timeframe: str
    direction: str  # "LONG" or "SHORT"
    signal_bar_index: int
    signal_timestamp: int
    anchor_high: float
    anchor_low: float
    entry_method: str  # "Sinyal kapanışı", "Fib 0.382 dönüşü", "Fib 0.500 dönüşü", "Fib 0.618 dönüşü"
    entry_price: float
    stop_price: float
    tp1: float  # 1.272
    tp2: float  # 1.414
    tp3: float  # 1.618
    tp4: float  # 2.000
    fib_levels: Dict[str, float] = field(default_factory=dict)
    status: str = "WAITING_ENTRY"  # WAITING_ENTRY, ACTIVE, TP1_HIT, COMPLETED, STOPPED, EXPIRED
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    tp4_hit: bool = False
    bars_waited: int = 0
    max_wait_bars: int = 20
    stop_mode: str = "Fitil"  # "Fitil" or "Kapanış"
    gross_r: float = 0.0
    net_r: float = 0.0
    grade: str = "A"
    score_14: int = 10
    confluences: List[str] = field(default_factory=list)


@dataclass
class MajorBox:
    box_type: str  # "MAJOR" or "MINOR"
    top: float
    bottom: float
    mid: float
    start_index: int
    break_dir: Optional[str] = None  # "UP" or "DOWN"
    retest_done: bool = False
    completed: bool = False
    state_label: str = "BEKLİYOR"  # "BEKLİYOR" or "✓ YAPTI"


@dataclass
class PriceZone:
    zone_type: str  # "OB_BULL", "OB_BEAR", "FVG_BULL", "FVG_BEAR", "GAP_UP", "GAP_DOWN", "SR_SUPPORT", "SR_RESISTANCE"
    top: float
    bottom: float
    mid: float
    bar_index: int
    mitigated: bool = False


class KriptoLevoStrategyEngine:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        # 05 • FIBONACCI & 05A • FIB PLAN TAKİBİ ayarları (KL Modüler v6.8.4 birebir varsayılanları)
        self.candle_sensitivity: float = cfg.get("candle_sensitivity", 1.8)  # in_74
        self.ema_trend_period: int = cfg.get("ema_trend_period", 50)         # in_75
        self.fib_mode: str = cfg.get("fib_mode", "Kripto Levent Özel Fib")   # in_77
        self.entry_method: str = cfg.get("entry_method", "Fib 0.500 dönüşü") # in_78
        self.on_new_signal: str = cfg.get("on_new_signal", "Mevcut planı koru") # in_79
        self.max_wait_bars: int = cfg.get("max_wait_bars", 20)               # in_80
        self.final_target: str = cfg.get("final_target", "TP4")              # in_82
        self.stop_mode: str = cfg.get("stop_mode", "Fitil")                  # in_83
        self.use_htf_filter: bool = cfg.get("use_htf_filter", True)          # in_95
        self.box_tolerance_pct: float = cfg.get("box_tolerance_pct", 3.0)    # in_99 (%3 kutu toleransı)
        self.fvg_max_width_atr: float = cfg.get("fvg_max_width_atr", 1.5)    # in_177
        self.sweep_pivot_len: int = cfg.get("sweep_pivot_len", 5)            # in_60
        self.min_grade_for_bot: str = cfg.get("min_grade_for_bot", "B")      # "A" (>=10) or "B" (>=7)
        self.tp1_close_ratio: float = cfg.get("tp1_close_ratio", 0.75)       # TP1'de %75 kapat
        self.tp2_close_ratio: float = cfg.get("tp2_close_ratio", 0.25)       # TP2'de kalan %25 kapat
        self.fee_rate: float = cfg.get("fee_rate", 0.0006)                   # Bitget/Binance vadeli taker komisyon
        self.slippage_rate: float = cfg.get("slippage_rate", 0.0002)

    # =========================================================================
    # TEMEL MATEMATİK VE GÖSTERGE HESAPLAMALARI
    # =========================================================================
    @staticmethod
    def calc_ema(values: List[float], period: int) -> List[float]:
        if not values:
            return []
        alpha = 2.0 / (period + 1.0)
        ema = [values[0]]
        for v in values[1:]:
            ema.append(alpha * v + (1.0 - alpha) * ema[-1])
        return ema

    @staticmethod
    def calc_sma(values: List[float], period: int) -> List[float]:
        out = []
        for i in range(len(values)):
            start = max(0, i - period + 1)
            window = values[start:i + 1]
            out.append(sum(window) / len(window))
        return out

    @staticmethod
    def calc_atr(candles: List[Candle], period: int = 14) -> List[float]:
        if not candles:
            return []
        trs = [candles[0].high - candles[0].low]
        for i in range(1, len(candles)):
            c = candles[i]
            prev_c = candles[i - 1].close
            tr = max(c.high - c.low, abs(c.high - prev_c), abs(c.low - prev_c))
            trs.append(tr)
        return KriptoLevoStrategyEngine.calc_ema(trs, period)

    @staticmethod
    def calc_rsi(closes: List[float], period: int = 14) -> List[float]:
        if len(closes) < 2:
            return [50.0] * len(closes)
        rsis = [50.0]
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        avg_gain = sum(gains[:period]) / max(len(gains[:period]), 1)
        avg_loss = sum(losses[:period]) / max(len(losses[:period]), 1)
        for i in range(len(gains)):
            if i < period:
                g = sum(gains[:i + 1]) / (i + 1)
                l = sum(losses[:i + 1]) / (i + 1)
            else:
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                g, l = avg_gain, avg_loss
            if l == 0:
                rsis.append(100.0)
            else:
                rs = g / l
                rsis.append(100.0 - (100.0 / (1.0 + rs)))
        return rsis

    @staticmethod
    def calc_macd(closes: List[float]) -> Tuple[List[float], List[float], List[float]]:
        ema12 = KriptoLevoStrategyEngine.calc_ema(closes, 12)
        ema26 = KriptoLevoStrategyEngine.calc_ema(closes, 26)
        macd_line = [a - b for a, b in zip(ema12, ema26)]
        signal_line = KriptoLevoStrategyEngine.calc_ema(macd_line, 9)
        hist = [m - s for m, s in zip(macd_line, signal_line)]
        return macd_line, signal_line, hist

    @staticmethod
    def calc_stoch(candles: List[Candle], period: int = 14) -> List[float]:
        out = []
        for i in range(len(candles)):
            start = max(0, i - period + 1)
            w = candles[start:i + 1]
            hh = max(c.high for c in w)
            ll = min(c.low for c in w)
            if hh == ll:
                out.append(50.0)
            else:
                out.append(100.0 * (candles[i].close - ll) / (hh - ll))
        return out

    @staticmethod
    def calc_cci(candles: List[Candle], period: int = 20) -> List[float]:
        tps = [(c.high + c.low + c.close) / 3.0 for c in candles]
        sma_tp = KriptoLevoStrategyEngine.calc_sma(tps, period)
        out = []
        for i in range(len(candles)):
            start = max(0, i - period + 1)
            w = tps[start:i + 1]
            mean = sma_tp[i]
            md = sum(abs(x - mean) for x in w) / len(w)
            if md == 0:
                out.append(0.0)
            else:
                out.append((tps[i] - mean) / (0.015 * md))
        return out

    @staticmethod
    def calc_obv(candles: List[Candle]) -> List[float]:
        if not candles:
            return []
        obv = [0.0]
        for i in range(1, len(candles)):
            if candles[i].close > candles[i - 1].close:
                obv.append(obv[-1] + candles[i].volume)
            elif candles[i].close < candles[i - 1].close:
                obv.append(obv[-1] - candles[i].volume)
            else:
                obv.append(obv[-1])
        return obv

    @staticmethod
    def calc_vwap(candles: List[Candle], window: int = 50) -> List[float]:
        out = []
        for i in range(len(candles)):
            start = max(0, i - window + 1)
            w = candles[start:i + 1]
            pv = sum(((c.high + c.low + c.close) / 3.0) * c.volume for c in w)
            v = sum(c.volume for c in w)
            out.append(pv / v if v > 0 else candles[i].close)
        return out

    # =========================================================================
    # 1. 14 KOŞULLU TEKNİK ANALİZ VE FİLTRE TABLOSU (A/B/C DERECELENDİRMESİ)
    # =========================================================================
    def evaluate_14_conditions(
        self,
        candles: List[Candle],
        direction: str,
        signal_age_bars: int = 1
    ) -> Tuple[int, str, Dict[str, bool]]:
        """
        Kripto Levent Teknik Analiz Tablosu:
        Momentum, trend, hacim, volatilite ve sinyal yaşıyla ilgili 14 koşulu değerlendirir.
        A derecesi: >= 10 koşul
        B derecesi: 7 - 9 koşul
        C derecesi: < 7 koşul
        """
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        ema20 = self.calc_ema(closes, 20)
        ema50 = self.calc_ema(closes, self.ema_trend_period)
        ema144 = self.calc_ema(closes, 144)
        ema169 = self.calc_ema(closes, 169)
        rsi = self.calc_rsi(closes, 14)
        macd_l, macd_s, macd_h = self.calc_macd(closes)
        stoch = self.calc_stoch(candles, 14)
        cci = self.calc_cci(candles, 20)
        obv = self.calc_obv(candles)
        obv_ema = self.calc_ema(obv, 20)
        vwap = self.calc_vwap(candles, 48)
        atr = self.calc_atr(candles, 14)
        atr_sma = self.calc_sma(atr, 20)
        vol_sma = self.calc_sma(volumes, 20)

        idx = len(candles) - 1
        c = candles[idx]
        is_long = (direction == "LONG")

        # 10 Momentum birleşik puanı ve 14 koşul
        mom_10 = closes[idx] - closes[max(0, idx - 10)]
        adx_proxy = abs(ema20[idx] - ema50[idx]) / max(atr[idx], 1e-12)

        conditions = {
            "1_EMA50_Trend": (c.close > ema50[idx]) if is_long else (c.close < ema50[idx]),
            "2_EMA144_169_Bulut": (c.close > max(ema144[idx], ema169[idx])) if is_long else (c.close < min(ema144[idx], ema169[idx])),
            "3_EMA20_50_Dizilim": (ema20[idx] > ema50[idx]) if is_long else (ema20[idx] < ema50[idx]),
            "4_VWAP_Konumu": (c.close >= vwap[idx]) if is_long else (c.close <= vwap[idx]),
            "5_RSI_Momentum": (45.0 <= rsi[idx] <= 75.0) if is_long else (25.0 <= rsi[idx] <= 55.0),
            "6_MACD_Histogram": (macd_h[idx] > 0 or macd_l[idx] > macd_s[idx]) if is_long else (macd_h[idx] < 0 or macd_l[idx] < macd_s[idx]),
            "7_Stoch_Yon": (stoch[idx] > stoch[max(0, idx - 1)] and stoch[idx] < 85.0) if is_long else (stoch[idx] < stoch[max(0, idx - 1)] and stoch[idx] > 15.0),
            "8_CCI_Trend": (cci[idx] > 0) if is_long else (cci[idx] < 0),
            "9_Momentum_10": (mom_10 > 0) if is_long else (mom_10 < 0),
            "10_Hacim_Ortalamasi": volumes[idx] >= 0.8 * vol_sma[idx],
            "11_OBV_Akisi": (obv[idx] >= obv_ema[idx]) if is_long else (obv[idx] <= obv_ema[idx]),
            "12_ATR_Volatilite": atr[idx] >= 0.7 * atr_sma[idx],
            "13_Trend_Gucu_ADX": adx_proxy >= 0.35,
            "14_Sinyal_Yasi_Taze": signal_age_bars <= self.max_wait_bars,
        }

        score = sum(1 for v in conditions.values() if v)
        if score >= 10:
            grade = "A"
        elif score >= 7:
            grade = "B"
        else:
            grade = "C"
        return score, grade, conditions

    # =========================================================================
    # 2. PİYASA YAPISI: OB (EMİR BLOKLARI), FVG, NORMAL GAP VE LİKİDİTE SÜPÜRÜLMESİ
    # =========================================================================
    def detect_fvg_and_gaps(self, candles: List[Candle], atr: List[float]) -> List[PriceZone]:
        zones: List[PriceZone] = []
        if len(candles) < 5:
            return zones
        start_idx = max(2, len(candles) - 150)
        for i in range(start_idx, len(candles) - 1):
            c_prev2 = candles[i - 2]
            c_prev1 = candles[i - 1]
            c_curr = candles[i]
            cur_atr = max(atr[i], 1e-12)

            # Bullish FVG: c_curr.low > c_prev2.high
            if c_curr.low > c_prev2.high and c_prev1.is_bullish:
                gap_size = c_curr.low - c_prev2.high
                if gap_size <= self.fvg_max_width_atr * cur_atr:
                    top = c_curr.low
                    bottom = c_prev2.high
                    # Check if mitigated by subsequent candles
                    mitigated = any(candles[j].low <= bottom for j in range(i + 1, len(candles)))
                    if not mitigated:
                        zones.append(PriceZone("FVG_BULL", top, bottom, (top + bottom) / 2.0, i))

            # Bearish FVG: c_curr.high < c_prev2.low
            if c_curr.high < c_prev2.low and c_prev1.is_bearish:
                gap_size = c_prev2.low - c_curr.high
                if gap_size <= self.fvg_max_width_atr * cur_atr:
                    top = c_prev2.low
                    bottom = c_curr.high
                    mitigated = any(candles[j].high >= top for j in range(i + 1, len(candles)))
                    if not mitigated:
                        zones.append(PriceZone("FVG_BEAR", top, bottom, (top + bottom) / 2.0, i))

            # Normal GAP (2 komşu mum arası fitil boşluğu)
            if c_curr.low > c_prev1.high:
                top, bottom = c_curr.low, c_prev1.high
                mitigated = any(candles[j].low <= bottom for j in range(i + 1, len(candles)))
                if not mitigated:
                    zones.append(PriceZone("GAP_UP", top, bottom, (top + bottom) / 2.0, i))
            elif c_curr.high < c_prev1.low:
                top, bottom = c_prev1.low, c_curr.high
                mitigated = any(candles[j].high >= top for j in range(i + 1, len(candles)))
                if not mitigated:
                    zones.append(PriceZone("GAP_DOWN", top, bottom, (top + bottom) / 2.0, i))

        return zones[-16:]

    def detect_order_blocks(self, candles: List[Candle], atr: List[float]) -> List[PriceZone]:
        zones: List[PriceZone] = []
        if len(candles) < 10:
            return zones
        start_idx = max(2, len(candles) - 150)
        for i in range(start_idx, len(candles) - 2):
            c_ob = candles[i - 1]
            c_imp = candles[i]
            cur_atr = max(atr[i], 1e-12)

            # Bullish Order Block: son düşüş mumu ardından güçlü yükseliş mumu (gövde > 1.2 ATR)
            if c_ob.is_bearish and c_imp.is_bullish and c_imp.body >= 1.2 * cur_atr and c_imp.close > c_ob.high:
                top, bottom = c_ob.high, c_ob.low
                mitigated = any(candles[j].low < bottom for j in range(i + 1, len(candles)))
                if not mitigated:
                    zones.append(PriceZone("OB_BULL", top, bottom, (top + bottom) / 2.0, i - 1))

            # Bearish Order Block: son yükseliş mumu ardından güçlü düşüş mumu
            if c_ob.is_bullish and c_imp.is_bearish and c_imp.body >= 1.2 * cur_atr and c_imp.close < c_ob.low:
                top, bottom = c_ob.high, c_ob.low
                mitigated = any(candles[j].high > top for j in range(i + 1, len(candles)))
                if not mitigated:
                    zones.append(PriceZone("OB_BEAR", top, bottom, (top + bottom) / 2.0, i - 1))

        return zones[-12:]

    def detect_liquidity_sweep(self, candles: List[Candle]) -> Optional[str]:
        """
        ICT Likidite Süpürülmesi (in_16, plot_4, plot_5):
        - Üst likidite süpürüldü: Onaylı tepe (sağ/sol 5 mum) aşıldı, aynı mum seviyenin altında kapandı -> SHORT
        - Alt likidite süpürüldü: Onaylı dip (sağ/sol 5 mum) aşıldı, aynı mum seviyenin üstünde kapandı -> LONG
        """
        n = self.sweep_pivot_len
        if len(candles) < 2 * n + 5:
            return None
        last = candles[-1]
        pivots_high = []
        pivots_low = []
        for i in range(len(candles) - 80, len(candles) - n - 1):
            if i < n:
                continue
            h = candles[i].high
            l = candles[i].low
            if all(candles[i - k].high < h and candles[i + k].high < h for k in range(1, n + 1)):
                # Daha önce kırılmamış pivot tepe
                if all(candles[j].close <= h for j in range(i + 1, len(candles) - 1)):
                    pivots_high.append(h)
            if all(candles[i - k].low > l and candles[i + k].low > l for k in range(1, n + 1)):
                if all(candles[j].close >= l for j in range(i + 1, len(candles) - 1)):
                    pivots_low.append(l)

        for ph in pivots_high[-5:]:
            if last.high > ph and last.close < ph:
                return "SWEEP_HIGH_BEARISH"
        for pl in pivots_low[-5:]:
            if last.low < pl and last.close > pl:
                return "SWEEP_LOW_BULLISH"
        return None

    # =========================================================================
    # 3. MAVİ KUTULAR (MAJOR / MINOR KUTULAR) VE SIRALI HAREKET TAKİBİ
    # =========================================================================
    def detect_major_boxes(self, candles: List[Candle], atr: List[float]) -> List[MajorBox]:
        """
        Major kutular (Mavi Kutular):
        Konsolidasyon / likidite birikim bölgelerini tespit eder.
        İlk kapanış kırılımından sonra:
        - Aşağı kırılımda: Üst sınıra dönüş (%3 tolerans) ve ardından alt sınıra ulaşma
        - Yukarı kırılımda: Alt sınıra dönüş (%3 tolerans) ve ardından üst sınıra ulaşma
        """
        boxes: List[MajorBox] = []
        if len(candles) < 40:
            return boxes
        window = 12
        for i in range(max(20, len(candles) - 160), len(candles) - window - 2, 10):
            seg = candles[i:i + window]
            hh = max(c.high for c in seg)
            ll = min(c.low for c in seg)
            cur_atr = max(atr[i + window - 1], 1e-12)
            if 0.8 * cur_atr <= (hh - ll) <= 2.8 * cur_atr:
                mb = MajorBox(
                    box_type="MAJOR",
                    top=hh,
                    bottom=ll,
                    mid=(hh + ll) / 2.0,
                    start_index=i
                )
                tol = (hh - ll) * (self.box_tolerance_pct / 100.0)
                # Sıralı hareket takibi
                for j in range(i + window, len(candles)):
                    cj = candles[j]
                    if mb.break_dir is None:
                        if cj.close > mb.top:
                            mb.break_dir = "UP"
                        elif cj.close < mb.bottom:
                            mb.break_dir = "DOWN"
                    elif not mb.retest_done:
                        if mb.break_dir == "UP" and cj.low <= mb.bottom + tol:
                            mb.retest_done = True
                        elif mb.break_dir == "DOWN" and cj.high >= mb.top - tol:
                            mb.retest_done = True
                    elif not mb.completed:
                        if mb.break_dir == "UP" and cj.high >= mb.top - tol:
                            mb.completed = True
                            mb.state_label = "✓ YAPTI"
                        elif mb.break_dir == "DOWN" and cj.low <= mb.bottom + tol:
                            mb.completed = True
                            mb.state_label = "✓ YAPTI"
                boxes.append(mb)
        return boxes[-4:]

    # =========================================================================
    # 4. KRİPTO LEVENT ÖZEL FIBONACCI & PLAN TAKİBİ (ANA SİNYAL MOTORU)
    # =========================================================================
    def build_fib_plan(
        self,
        symbol: str,
        timeframe: str,
        candles: List[Candle],
        htf_candles: Optional[List[Candle]] = None
    ) -> Optional[FibPlan]:
        """
        Kripto Levent Özel Fibonacci Modu:
        - Mum gövdesini ortalama gövde büyüklüğüyle karşılaştırır.
        - Belirlenen katsayıyı (Mum Büyüklük Hassasiyeti = 1.8x) aşan mumları EMA 50 trend filtresiyle
          (ve isteğe bağlı HTF EMA 50 trend filtresiyle) değerlendirir.
        - Giriş yöntemi (Sinyal kapanışı, Fib 0.382, Fib 0.500, Fib 0.618),
          Stop (0.0 / 1.0 seviyesi) ve TP1 (1.272), TP2 (1.414), TP3 (1.618), TP4 (2.0) seviyelerini çizer.
        - Sonrasında 20 mum boyunca giriş, hedef ve stop takibi yapar.
        """
        if len(candles) < 60:
            return None

        closes = [c.close for c in candles]
        bodies = [c.body for c in candles]
        ema50 = self.calc_ema(closes, self.ema_trend_period)
        avg_body = self.calc_sma(bodies, 20)
        atr = self.calc_atr(candles, 14)

        htf_bullish: Optional[bool] = None
        if self.use_htf_filter and htf_candles and len(htf_candles) >= 50:
            htf_closes = [c.close for c in htf_candles]
            htf_ema50 = self.calc_ema(htf_closes, self.ema_trend_period)
            htf_bullish = htf_closes[-1] >= htf_ema50[-1]

        # Son 120 kapanmış mum içinde en güncel Özel Fibonacci sinyal mumunu tara
        active_plan: Optional[FibPlan] = None
        last_plan: Optional[FibPlan] = None
        search_start = max(30, len(candles) - 120)

        for i in range(search_start, len(candles)):
            c = candles[i]
            is_impulse = c.body >= (self.candle_sensitivity * max(avg_body[i], 1e-12))
            if not is_impulse:
                continue

            direction: Optional[str] = None
            if c.is_bullish and c.close > ema50[i]:
                if htf_bullish is False:
                    continue
                direction = "LONG"
            elif c.is_bearish and c.close < ema50[i]:
                if htf_bullish is True:
                    continue
                direction = "SHORT"

            if not direction:
                continue

            # Anchor High / Low: Referans mum ile son 5 mumun tepe/dibi (Swing bacağı)
            lookback_slice = candles[max(0, i - 4):i + 1]
            anchor_high = max(x.high for x in lookback_slice)
            anchor_low = min(x.low for x in lookback_slice)
            rng = max(anchor_high - anchor_low, 1e-12)

            if direction == "LONG":
                # Long'da 0.0 = anchor_low (Stop), 1.0 = anchor_high (Tepe)
                # Geri çekilme seviyeleri: 0.382, 0.500, 0.618
                fib_382 = anchor_high - 0.382 * rng
                fib_500 = anchor_high - 0.500 * rng
                fib_618 = anchor_high - 0.618 * rng
                fib_786 = anchor_high - 0.786 * rng
                stop_price = anchor_low - 0.05 * rng
                tp1 = anchor_low + 1.272 * rng
                tp2 = anchor_low + 1.414 * rng
                tp3 = anchor_low + 1.618 * rng
                tp4 = anchor_low + 2.000 * rng
            else:
                # Short'ta 0.0 = anchor_high (Stop), 1.0 = anchor_low (Dip)
                fib_382 = anchor_low + 0.382 * rng
                fib_500 = anchor_low + 0.500 * rng
                fib_618 = anchor_low + 0.618 * rng
                fib_786 = anchor_low + 0.786 * rng
                stop_price = anchor_high + 0.05 * rng
                tp1 = anchor_high - 1.272 * rng
                tp2 = anchor_high - 1.414 * rng
                tp3 = anchor_high - 1.618 * rng
                tp4 = anchor_high - 2.000 * rng

            if self.entry_method == "Sinyal kapanışı":
                entry_price = c.close
            elif self.entry_method == "Fib 0.382 dönüşü":
                entry_price = fib_382
            elif self.entry_method == "Fib 0.618 dönüşü":
                entry_price = fib_618
            else:  # "Fib 0.500 dönüşü" (Varsayılan)
                entry_price = fib_500

            # R (Risk/Ödül) Hesabı — Brüt R ve Maliyetli (Net) R
            risk = abs(entry_price - stop_price)
            # TP1 (%75) + TP2 (%25) ağırlıklı hedef ödülü
            blended_tp = self.tp1_close_ratio * tp1 + self.tp2_close_ratio * tp2
            reward = abs(blended_tp - entry_price)
            gross_r = reward / max(risk, 1e-12)
            round_trip_cost = entry_price * (2.0 * (self.fee_rate + self.slippage_rate))
            net_r = max(0.0, (reward - round_trip_cost) / max(risk + round_trip_cost, 1e-12))

            plan = FibPlan(
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                signal_bar_index=i,
                signal_timestamp=c.timestamp,
                anchor_high=anchor_high,
                anchor_low=anchor_low,
                entry_method=self.entry_method,
                entry_price=entry_price,
                stop_price=stop_price,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                tp4=tp4,
                fib_levels={
                    "0.0 (Stop)": stop_price,
                    "0.382": fib_382,
                    "0.500 (Giriş)": fib_500,
                    "0.618 (Altın Oran)": fib_618,
                    "0.786": fib_786,
                    "1.0": anchor_high if direction == "LONG" else anchor_low,
                    "1.272 (TP1 %75)": tp1,
                    "1.414 (TP2 %25)": tp2,
                    "1.618 (TP3)": tp3,
                    "2.000 (TP4)": tp4,
                },
                status="ACTIVE" if self.entry_method == "Sinyal kapanışı" else "WAITING_ENTRY",
                max_wait_bars=self.max_wait_bars,
                stop_mode=self.stop_mode,
                gross_r=round(gross_r, 2),
                net_r=round(net_r, 2),
            )

            # Simüle et: sinyal mumundan sonraki mumlarda (i+1 .. son mum) plan ne durumda?
            self._advance_plan_state(plan, candles, i)
            last_plan = plan

            # Yeni sinyal geldiğinde mevcut plan kuralı (in_79)
            if active_plan is None:
                active_plan = plan
            else:
                if active_plan.status in ("COMPLETED", "STOPPED", "EXPIRED"):
                    active_plan = plan
                elif self.on_new_signal == "Mevcut planı iptal et ve yenile":
                    active_plan = plan
                elif self.on_new_signal == "Yalnız bekleyen planı yenile" and active_plan.status == "WAITING_ENTRY":
                    active_plan = plan

        if active_plan is None or active_plan.status == "EXPIRED":
            if last_plan is not None:
                active_plan = last_plan

        if active_plan:
            age = (len(candles) - 1) - active_plan.signal_bar_index
            score, grade, _ = self.evaluate_14_conditions(candles, active_plan.direction, max(1, age))
            active_plan.score_14 = score
            active_plan.grade = grade

            # Yakın FVG, OB, Major Kutu ve Likidite Süpürülmesi kesişimlerini (Confluence) ekle
            zones = self.detect_fvg_and_gaps(candles, atr) + self.detect_order_blocks(candles, atr)
            boxes = self.detect_major_boxes(candles, atr)
            sweep = self.detect_liquidity_sweep(candles)

            confluences = []
            tol = atr[-1] * 0.6
            for z in zones:
                if z.bottom - tol <= active_plan.entry_price <= z.top + tol:
                    confluences.append(f"{z.zone_type} ({z.bottom:.4f}-{z.top:.4f})")
            for b in boxes:
                if b.bottom - tol <= active_plan.entry_price <= b.top + tol:
                    confluences.append(f"Mavi Kutu [{b.state_label}] ({b.bottom:.4f}-{b.top:.4f})")
            if sweep:
                confluences.append(f"ICT {sweep}")
            active_plan.confluences = confluences[:5]

        return active_plan

    def _advance_plan_state(self, plan: FibPlan, candles: List[Candle], sig_idx: int) -> None:
        """
        Güncelleme Notları Kuralları:
        - Girişten önce ve giriş mumunda hedef başarısı sayılmaz.
        - Aynı mumda yeni hedef ve stop birlikte görülürse stop öncelikli değerlendirilir.
        - TP1 görüldüğünde stop giriş seviyesine (Breakeven) çekilir!
        """
        current_stop = plan.stop_price
        for j in range(sig_idx + 1, len(candles)):
            c = candles[j]
            if plan.status == "WAITING_ENTRY":
                plan.bars_waited += 1
                if plan.bars_waited > plan.max_wait_bars:
                    plan.status = "EXPIRED"
                    break
                # Girişten önce TP1'e gittiyse ("Fiyat Hedefe Gitti Ama Giriş Vermedi!") -> İptal
                if plan.direction == "LONG" and c.high >= plan.tp1 and c.low > plan.entry_price:
                    plan.status = "EXPIRED"
                    break
                if plan.direction == "SHORT" and c.low <= plan.tp1 and c.high < plan.entry_price:
                    plan.status = "EXPIRED"
                    break
                # Girişten önce stop seviyesi kırıldıysa -> Geçersiz
                if plan.direction == "LONG" and c.low <= plan.stop_price:
                    plan.status = "EXPIRED"
                    break
                if plan.direction == "SHORT" and c.high >= plan.stop_price:
                    plan.status = "EXPIRED"
                    break
                # Giriş gerçekleşti mi?
                if plan.direction == "LONG" and c.low <= plan.entry_price:
                    plan.status = "ACTIVE"
                    continue  # Giriş mumunda TP sayılmaz
                if plan.direction == "SHORT" and c.high >= plan.entry_price:
                    plan.status = "ACTIVE"
                    continue

            elif plan.status in ("ACTIVE", "TP1_HIT"):
                # Önce Stop kontrolü (Fitil veya Kapanış)
                if plan.direction == "LONG":
                    stop_triggered = (c.low <= current_stop) if plan.stop_mode == "Fitil" else (c.close <= current_stop)
                    if stop_triggered:
                        plan.status = "COMPLETED" if plan.tp1_hit else "STOPPED"
                        break
                    if c.high >= plan.tp1:
                        plan.tp1_hit = True
                        plan.status = "TP1_HIT"
                        current_stop = plan.entry_price  # TP1 sonrası Giriş-Stop (Breakeven)!
                    if c.high >= plan.tp2:
                        plan.tp2_hit = True
                    if c.high >= plan.tp3:
                        plan.tp3_hit = True
                    if c.high >= plan.tp4:
                        plan.tp4_hit = True
                        plan.status = "COMPLETED"
                        break
                else:
                    stop_triggered = (c.high >= current_stop) if plan.stop_mode == "Fitil" else (c.close >= current_stop)
                    if stop_triggered:
                        plan.status = "COMPLETED" if plan.tp1_hit else "STOPPED"
                        break
                    if c.low <= plan.tp1:
                        plan.tp1_hit = True
                        plan.status = "TP1_HIT"
                        current_stop = plan.entry_price  # TP1 sonrası Giriş-Stop (Breakeven)!
                    if c.low <= plan.tp2:
                        plan.tp2_hit = True
                    if c.low <= plan.tp3:
                        plan.tp3_hit = True
                    if c.low <= plan.tp4:
                        plan.tp4_hit = True
                        plan.status = "COMPLETED"
                        break
