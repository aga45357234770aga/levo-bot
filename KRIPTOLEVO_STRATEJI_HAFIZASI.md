# KriptoLevo (Kripto Levent) — Tüm Kanal Hafızası ve Strateji Dokümantasyonu

**Kanal:** `https://www.youtube.com/@KriptoLevo` (**Kripto Levent**)  
**TradingView Profili:** `darkorbitcenneti`  
**Ana İndikatör:** `Kripto Levent - Fibonacci & Market Structure (KL Modüler v6.8.4)` (`tr.tradingview.com/script/cf50bopR/`)  
**Kullanılan Borsa:** Ağırlıklı olarak **Bitget** (Vadeli İşlemler / USDT-M Futures) ve **Binance**, ayrıca Forex/Altın için **MT5 (XM)**.

---

## 1. Kanaldaki Videoların ve Serilerin Özeti (108+ Video/Yayın/Shorts Taraması)

Kanaldaki tüm videolar, canlı yayınlar ve Shorts içerikleri incelendiğinde Kripto Levent'in sistemi **6 ana sütun** üzerine kuruludur:

### A. Kripto Levent Özel Fibonacci & Plan Takip Stratejisi
- **Özel Fibonacci (`Kripto Levent Özel Fib` Modu):**
  - Standart tepe-dip çekmek yerine, **hacimli/gövdesi büyük impuls (referans) mumlarını** tespit eder.
  - **Mum Büyüklük Hassasiyeti:** Varsayılan `1.8x` (Mum gövdesi, ortalama mum gövdesinin en az `1.8` katı olmalı).
  - **Trend Filtresi:** `EMA 50` ve `EMA 144–169` (Vegas Tüneli / Bulutu) ile mevcut zaman dilimi ve Üst Zaman Dilimi (`HTF`) trend yönü kontrol edilir.
  - **Giriş Yöntemleri (4 Seçenek):**
    1. `Sinyal kapanışı` (Mum kapanır kapanmaz işleme giriş)
    2. `Fib 0.382 dönüşü` (Düzeltmede 0.382 seviyesinden limit emirle giriş)
    3. `Fib 0.500 dönüşü` (**Varsayılan / Ana Strateji** — Referans mumun %50 orta noktasından dönüşte giriş)
    4. `Fib 0.618 dönüşü` (Altın oran 0.618 geri çekilmesinde giriş)
  - **Bekleme Süresi ve Geçersizleşme:**
    - Giriş için en fazla **20 mum** beklenir (`in_80 = 20`). 20 mum içinde giriş seviyesine gelmeden hedefe giderse ("Fiyat hedefe gitti ama giriş vermedi") plan iptal edilir, peşinden koşulmaz (FOMO yapılmaz).
  - **Hedefler (TP1 – TP4) ve Kademeli Çıkış Planı:**
    - Seviyeler: `0.0`, `0.382`, `0.500`, `0.618`, `0.786`, `1.0`, `1.272 (TP1)`, `1.414 (TP2)`, `1.618 (TP3)`, `2.0 / 2.618 (TP4)`.
    - **Kademeli Kar Al (Shorts & Video Kuralı):**
      - **TP1'de pozisyonun %75'i kapatılır** (veya ana sermaye garantiye alınır) ve **Stop-Loss (SL) giriş seviyesine (Başabaş / Breakeven)** çekilir! ("TP1 sonrası Giriş-Stop").
      - **TP2 / TP3 / TP4'te kalan %25** ile kâr sürülür.
  - **Stop-Loss (SL) Kuralı:**
    - İki mod vardır: `Fitil` (varsayılan) veya `Kapanış`.
    - Referans mumun/yapının diğer ucu (`1.0` / `0.0` altı/üstü) stop seviyesidir.

### B. Mavi Kutular (Major / Minor Kutular) Stratejisi
- **Mavi Kutuların 3 Seviyesi:** Üst sınır, Orta çizgi (%50 denge) ve Alt sınır.
- **Sıralı Hareket Takibi (`BEKLİYOR` -> `✓ YAPTI`):**
  - Fiyat bir Major kutuyu ilk kez kapanışla kırdığında takip başlar:
    - **Aşağı kırılımda:** Fiyatın kutunun **üst sınırına** (%3 temas toleransı ile) retest yapması ve ardından **alt sınıra** ulaşması beklenir.
    - **Yukarı kırılımda:** Fiyatın kutunun **alt sınırına** dönmesi ve ardından **üst sınıra** ulaşması izlenir.
  - Kutu sınırına temaslarda (%3 tolerans, `in_99 = 3.0`) dönüş mumu kapanışıyla işleme girilir.

### C. Piyasa Yapısı (SMC / ICT): Emir Blokları (OB), FVG, GAP ve Likidite
- **Emir Blokları (Order Blocks - OB):**
  - İçsel (Internal, periyot 20) ve Dışsal (External, periyot 50) emir blokları.
  - Hacim ve yüzde dengesizliği yüksek olan OB'lerin **Orta Çizgisi (%50)** ve sınırları destek/direnç olarak kullanılır.
- **FVG (Fair Value Gap - Adil Değer Boşluğu) ve Normal GAP:**
  - 3 mumluk dengesizlik boşlukları (FVG, maks genişlik 1.5 ATR filtresiyle) ve 2 mum arası fitil boşlukları (Normal Gap).
  - **"Her FVG Dolar mı?" Kuralı:** Yalnızca trend yönündeki ve OB / Fibonacci 0.500–0.618 ile kesişen (confluence) FVG bölgelerinden işlem alınır. Boşluğun %50 orta seviyesi ana tepki noktasıdır.
- **Likidite Süpürülmesi (Liquidity Sweep / Turtle Soup):**
  - Onaylı tepe/dip (sağ ve solda 5 mum, `in_60 = 5`, veya likidite pivot uzunluğu `8`).
  - Fiyat onaylı tepeyi en az 1 tick aşıp **aynı mumda seviyenin altında kapanırsa** -> **SHORT Sinyali (Üst Likidite Süpürüldü)**.
  - Fiyat onaylı dibi aşıp **aynı mumda seviyenin üstünde kapanırsa** -> **LONG Sinyali (Alt Likidite Süpürüldü)**.
- **Yapı Kırılımları (BOS / MSS / CHoCH):**
  - 10 periyotluk Swing noktalarının kırılımıyla trend dönüşü (MSS/CHoCH) veya trend devamı (BOS) onayı alınır.

### D. 14 Koşullu Teknik Analiz & Filtre Tablosu (A/B/C Derecelendirmesi ve "Kör Giriş" Önleme)
Kripto Levent'in *"Körlemesine İşlem Açmayın: Telegram Sistemimde Filtre Böyle Çalışıyor"* ve *"211 İşlem, 1 Stop"* videolarındaki ana filtre mekanizmasıdır:
- **14 Koşul:** Momentum (RSI, Stokastik, MACD, CCI, Momentum), Trend (EMA 50, EMA 144/169 bulutu, SuperTrend/ADX, VWAP), Hacim (OBV / Hacim ortalaması), Volatilite (ATR / Bollinger) ve Sinyal Yaşı.
- **Derecelendirme (Grade):**
  - **A Derecesi (Grade A):** 14 koşulun **en az 10 tanesi** onay veriyor (Yüksek Güven — Otomatik Bot için birincil giriş şartı).
  - **B Derecesi (Grade B):** **7 ile 9 arası** koşul onay veriyor (Orta Güven).
  - **C Derecesi (Grade C):** **7'den az** koşul sağlıyor (**İşlem Açılmaz / Filtrelenir**).
- **10 Gösterge Uyumsuzluğu (Divergence):**
  - RSI, MACD, Momentum, CCI, OBV, Stokastik vb. 10 osilatörde fiyat ile pozitif/negatif uyumsuzluk taraması.
- **4 Saatlik RSI Haritası & Kanal/Omuz Baş Omuz Taraması:**
  - Aşırı alım (`RSI > 70`) ve aşırı satım (`RSI < 30`) bildirimleri geldiğinde doğrudan kör giriş yapılmaz; düşen kanal kırılımı + retest veya OBO/TOBO boyun çizgisi kırılımı + FVG/OB onayı beklenir.

### E. Seans (Asya, Londra, New York), Günlük TPO ve Zaman Filtresi
- **Seans Kutuları:**
  - Asya (Tokyo `09:00-15:00` yerel), Londra (`08:00-17:00` yerel), New York (`08:00-17:00` yerel).
  - Asya seansının tepe ve dibi (Asian Range) likidite bölgesi olarak izlenir; Londra ve New York açılışlarında Asya likiditesi süpürüldüğünde ters yönde işleme girilir.
- **Günlük TPO (Market Profile):**
  - `POC` (Point of Control), `VAH` (Value Area High - %70 değer alanı üstü), `VAL` (Value Area Low - %70 değer alanı altı) ve Önceki Gün/Hafta Tepe-Dip (`PDH / PDL / PWH / PWL`) seviyeleri.

### F. Otomatik Al-Sat Botu Mimarisi ve Risk / Kasa Yönetimi
- **Otomatik Bot Çalışma Mantığı:**
  1. **Çoklu Zaman Dilimi (Scalp / Gün İçi / Swing Profilleri):**
     - `Scalping` (1m - 5m - 15m, Maks uzaklık 4 ATR)
     - `Gün içi / Intraday` (15m - 1h, Maks uzaklık 8 ATR)
     - `Swing` (4h - 1d, Maks uzaklık 16 ATR)
  2. **Maliyet ve R Hesabı:**
     - Komisyon, spread, kayma (slippage) ve funding düşüldükten sonra **Net R (Risk/Ödül)** oranı hesaplanır. Net R oranı düşük olan işlemlere girilmez.
  3. **Borsa & Webhook / API Otomasyonu:**
     - Hem TradingView Webhook sinyallerini dinleyebilen hem de **bilgisayar/tarayıcı bağımsız 7/24 Python üzerinden doğrudan borsa verisini (CCXT ile Binance / Bitget / Bybit) tarayıp** tüm bu stratejileri kendi içinde hesaplayarak otomatik emir (Market/Limit Giriş, Kademeli TP1 %75 + TP2 %25 ve Otomatik Breakeven Stop-Loss) gönderen mimari.
- **Başಮುข Video Referansları:**
  - [6 Günde Kasa 96.238 USDT’ye Nasıl Çıktı?](https://www.youtube.com/watch?v=XOFydc_ME0w)
  - [200 Dolardan 1.200 Dolara Nasıl Çıktım?](https://www.youtube.com/watch?v=vuIc-d06qBw)
  - [Siz İstediniz, Güncelledim! Fibonacci’de Giriş, Hedef ve Stop Takibi](https://www.youtube.com/watch?v=5LxYngIydG8)
  - [Sonunda Paylaşıyorum! Canlı Yayında Kullandığım İndikatör](https://www.youtube.com/watch?v=v_iD4z55tC8)
  - [Tek Ekranda Fibonacci, FVG ve Emir Blokları! Ücretsiz İndikatör](https://www.youtube.com/watch?v=1IpkWAkijTo)
  - [Ücretsiz Otomatik Al-Sat Botu ile 1 Ayda +1.500$ Kazandım!](https://www.youtube.com/watch?v=NfRZgyEVqkM)
  - [Kripto Botu Nasıl Kurulur? PC Açık Olmadan Otomatik İşlem](https://www.youtube.com/watch?v=G6HOxPL1CfE)
  - [Kripto'da Tarayıcıdan Otomatik İşlem Açan Bot! Kurulum, Ayarlar ve Strateji](https://www.youtube.com/watch?v=XnZF-DfVDwM)
