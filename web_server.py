"""
KriptoLevo (Kripto Levent) — Web Arayüzü & TradingView Webhook Sunucusu
- http://localhost:8501 adresinde çalışır (harici paket gerektirmez)
- Ana sayfada Açık İşlemler (Max 5), En Yüksek Volatiliteli 300 Coin ve Sinyal Akışı
- Herhangi bir işleme veya sinyale tıklayınca YENİ SEKMEDE (/trade?symbol=...) detay + canlı TradingView grafiği açılır
- POST /webhook üzerinden TradingView alarmlarını kabul eder
"""

import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime

from paper_trader import PaperTradingBot, STATE_FILE

PORT = int(os.environ.get("PORT", 8501))
BOT = PaperTradingBot()
BOT_LOCK = threading.Lock()


def background_scanner():
    tick = 0
    while True:
        time.sleep(5)
        tick += 1
        with BOT_LOCK:
            if not BOT.is_running:
                continue
            try:
                if tick % 12 == 0:
                    # Her 60 saniyede bir tam 300 coin taramasi
                    BOT.run_cycle(scan_limit=60)
                else:
                    # Her 5 saniyede bir acik pozisyonlarin canli fiyat & PnL guncellemesi
                    if BOT.open_positions:
                        top300 = BOT.connector.fetch_top_volatile_coins(top_n=BOT.top_volatile_count)
                        price_map = {c["symbol"]: c["last_price"] for c in top300}
                        BOT.update_open_positions(price_map)
                        BOT.save_state()
            except Exception as e:
                print(f"[Arka Plan Tarama Hatası] {e}")


HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KriptoLevo Bot • Otomatik Al-Sat Paneli (Test Modu)</title>
<style>
  :root {
    --bg: #0b0f19; --card: #131a2a; --card2: #192236; --border: #25314d;
    --text: #e6edf7; --muted: #8b9bb4; --green: #10b981; --red: #ef4444;
    --blue: #3b82f6; --amber: #f59e0b; --purple: #8b5cf6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 20px; }
  .header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
  .title-wrap h1 { font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 10px; }
  .badge { font-size: 12px; padding: 4px 10px; border-radius: 999px; font-weight: 600; }
  .badge-test { background: rgba(245,158,11,.15); color: var(--amber); border: 1px solid rgba(245,158,11,.4); }
  .badge-run { background: rgba(16,185,129,.15); color: var(--green); border: 1px solid rgba(16,185,129,.4); }
  .badge-stop { background: rgba(239,68,68,.15); color: var(--red); border: 1px solid rgba(239,68,68,.4); }
  .actions { display: flex; gap: 10px; align-items: center; }
  button { cursor: pointer; border: none; padding: 10px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; transition: .15s; }
  .btn-primary { background: var(--blue); color: #fff; }
  .btn-primary:hover { filter: brightness(1.15); }
  .btn-danger { background: var(--red); color: #fff; }
  .btn-success { background: var(--green); color: #fff; }
  .btn-tv { background: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; text-decoration: none; padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; }

  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 22px; }
  .kpi { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
  .kpi .label { color: var(--muted); font-size: 12px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }
  .kpi .val { font-size: 24px; font-weight: 700; }
  .kpi .sub { font-size: 12px; color: var(--muted); margin-top: 4px; }

  .section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; margin-bottom: 20px; }
  .section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 10px; }
  .section-head h2 { font-size: 16px; font-weight: 600; }
  .hint { font-size: 12px; color: var(--muted); }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; color: var(--muted); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  td { padding: 11px 12px; border-bottom: 1px solid rgba(37,49,77,.5); white-space: nowrap; }
  tr.clickable { cursor: pointer; transition: background .12s; }
  tr.clickable:hover { background: var(--card2); }

  .pill { padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; display: inline-block; }
  .long { background: rgba(16,185,129,.15); color: var(--green); }
  .short { background: rgba(239,68,68,.15); color: var(--red); }
  .grade-A { background: rgba(16,185,129,.2); color: #34d399; }
  .grade-B { background: rgba(59,130,246,.2); color: #60a5fa; }
  .grade-C { background: rgba(139,155,180,.2); color: var(--muted); }
  .pos { color: var(--green); font-weight: 600; }
  .neg { color: var(--red); font-weight: 600; }

  .tabs { display: flex; gap: 8px; margin-bottom: 14px; }
  .tab { background: var(--card2); color: var(--muted); padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }
  .tab.active { background: var(--blue); color: #fff; }
  .search { background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 8px; font-size: 13px; width: 240px; }
  .webhook-box { background: var(--bg); border: 1px dashed var(--border); padding: 10px 14px; border-radius: 8px; font-size: 12px; color: var(--muted); }
  code { color: #38bdf8; }
</style>
</head>
<body>

<div class="header">
  <div class="title-wrap">
    <h1>🤖 KriptoLevo (@KriptoLevo) Otomatik Al-Sat Botu
      <span class="badge badge-test">TEST MODU (SANAL BAKİYE)</span>
      <span id="runBadge" class="badge badge-run">ÇALIŞIYOR</span>
    </h1>
    <div class="hint" id="lastScan">Son Tarama: Yükleniyor... | Strateji: Özel Fibonacci (1.8x) + Mavi Kutular + OB/FVG + 14 Koşul Tablosu</div>
  </div>
  <div class="actions">
    <button class="btn-primary" style="background:#8b5cf6;" onclick="goToHistory()">📜 Geçmiş İşlemler (<span id="closedCountBtn">0</span>)</button>
    <a class="btn-tv" href="https://tr.tradingview.com/chart/" target="_blank">📈 TradingView'ı Aç</a>
    <button class="btn-primary" id="scanBtn" onclick="triggerScan()">🔄 Şimdi Tara (300 Coin)</button>
    <button class="btn-danger" id="toggleBtn" onclick="toggleBot()">🛑 Acil Durdur</button>
  </div>
</div>

<div class="kpis">
  <div class="kpi">
    <div class="label">Anlık Toplam Kasa (Özsermaye)</div>
    <div class="val" id="kpiBalance">$100.00</div>
    <div class="sub" id="kpiPnl">Bakiye: $100.00 | Açık PnL: $0.00</div>
  </div>
  <div class="kpi">
    <div class="label">Açık Pozisyonlar</div>
    <div class="val" id="kpiOpen">0 / 5</div>
    <div class="sub">Aynı anda maksimum 5 işlem</div>
  </div>
  <div class="kpi">
    <div class="label">Volatilite Havuzu</div>
    <div class="val" id="kpiVol300">300 Coin</div>
    <div class="sub">Binance + MEXC En Yüksek Volatilite</div>
  </div>
  <div class="kpi">
    <div class="label">Strateji Sinyalleri</div>
    <div class="val" id="kpiSignals">0</div>
    <div class="sub">14 Koşul A/B Derece Filtreli</div>
  </div>
</div>

<div class="section">
  <div class="section-head">
    <h2>🔥 Açık Pozisyonlar (Detay ve TradingView Grafiği İçin Satıra Tıklayın ↗)</h2>
    <span class="hint">TP1'de %75 kâr alınır ve Stop otomatik giriş fiyatına (Breakeven) çekilir</span>
  </div>
  <div style="overflow-x:auto;">
    <table>
      <thead>
        <tr>
          <th>Parite</th><th>Borsa</th><th>Yön</th><th>Kaldıraç</th><th>Marjin ($ / %)</th><th>Büyüklük ($)</th><th>Derece</th><th>Giriş</th>
          <th>Anlık Fiyat</th><th>Stop (SL)</th><th>TP1 (%75)</th><th>TP2 (%25)</th>
          <th>Anlık Kâr/Zarar</th><th>Durum</th><th>İşlem</th>
        </tr>
      </thead>
      <tbody id="openBody"></tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="section-head">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('signals', this)">🎯 Strateji Sinyalleri</div>
      <div class="tab" onclick="switchTab('vol300', this)">⚡ En Yüksek Volatiliteli 300 Coin</div>
      <div class="tab" onclick="switchTab('history', this)">📜 Kapanan İşlemler</div>
      <div class="tab" onclick="switchTab('webhooks', this)">🔔 TradingView Webhook</div>
    </div>
    <input class="search" id="searchBox" placeholder="Coin ara (ör: BTC, SOL)..." oninput="renderTables()">
  </div>

  <div id="tab-signals" style="overflow-x:auto;">
    <table>
      <thead>
        <tr><th>Parite</th><th>Borsa</th><th>Yön</th><th>Durum</th><th>Derece</th><th>Fiyat</th><th>Giriş (Fib 0.5)</th><th>Stop</th><th>TP1</th><th>Net R</th><th>Volatilite</th></tr>
      </thead>
      <tbody id="signalsBody"></tbody>
    </table>
  </div>

  <div id="tab-vol300" style="display:none; overflow-x:auto; max-height: 480px;">
    <table>
      <thead>
        <tr><th>#</th><th>Parite</th><th>Kaynaklar</th><th>Son Fiyat</th><th>24s Değişim %</th><th>24s Aralık Volatilite %</th><th>Volatilite Skoru</th><th>24s Hacim (USDT)</th></tr>
      </thead>
      <tbody id="vol300Body"></tbody>
    </table>
  </div>

  <div id="tab-history" style="display:none; overflow-x:auto;">
    <div id="historySummary" class="webhook-box" style="margin-bottom:10px;"></div>
    <table>
      <thead>
        <tr><th>Parite</th><th>Yön</th><th>Giriş</th><th>Çıkış</th><th>Sonuç</th><th>Kapanış Nedeni</th><th>Net PnL ($)</th><th>Kapanış Zamanı</th></tr>
      </thead>
      <tbody id="historyBody"></tbody>
    </table>
  </div>

  <div id="tab-webhooks" style="display:none;">
    <div class="webhook-box" style="margin-bottom:12px;">
      <strong>TradingView Alarm Webhook Adresi:</strong> <code>http://localhost:8501/webhook</code><br>
      TradingView'da Kripto Levent indikatörüne alarm kurarken Webhook URL alanına bu adresi yazabilirsiniz. Gelen alarmlar aşağıda listelenir.
    </div>
    <div id="webhookList" class="hint">Henüz TradingView webhook alarmı gelmedi.</div>
  </div>
</div>

<script>
let STATE = null;
let ACTIVE_TAB = 'signals';

function switchTab(name, el) {
  ACTIVE_TAB = name;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  if (el) el.classList.add('active');
  ['signals','vol300','history','webhooks'].forEach(id => {
    document.getElementById('tab-' + id).style.display = (id === name) ? 'block' : 'none';
  });
}

function goToHistory() {
  const tabs = document.querySelectorAll('.tab');
  switchTab('history', tabs[2]);
  document.getElementById('tab-history').scrollIntoView({ behavior: 'smooth' });
}

function openTradeTab(symbol) {
  window.open('/trade?symbol=' + encodeURIComponent(symbol), '_blank');
}

async function fetchState() {
  const res = await fetch('/api/state');
  STATE = await res.json();
  renderAll();
}

async function triggerScan() {
  const btn = document.getElementById('scanBtn');
  btn.disabled = true; btn.innerText = '⏳ Taranıyor...';
  try {
    await fetch('/api/scan', { method: 'POST' });
    await fetchState();
  } finally {
    btn.disabled = false; btn.innerText = '🔄 Şimdi Tara (300 Coin)';
  }
}

async function toggleBot() {
  await fetch('/api/toggle', { method: 'POST' });
  await fetchState();
}

async function closePosition(ev, symbol) {
  ev.stopPropagation();
  if (!confirm(symbol + ' pozisyonunu anlık fiyattan kapatmak istiyor musunuz?')) return;
  await fetch('/api/close?symbol=' + encodeURIComponent(symbol), { method: 'POST' });
  await fetchState();
}

function renderAll() {
  if (!STATE) return;
  document.getElementById('lastScan').innerText = 'Son Tarama: ' + (STATE.last_scan_time || '-') + ' | Binance & MEXC Canlı Akış (5 sn Fiyat Güncellemesi)';
  const openList = Object.values(STATE.open_positions || {});
  const unrealizedSum = openList.reduce((acc, p) => acc + Number(p.unrealized_pnl_usdt || 0), 0);
  const equity = Number(STATE.balance) + unrealizedSum;
  const totalDiff = equity - Number(STATE.initial_balance);
  const balEl = document.getElementById('kpiBalance');
  balEl.innerText = '$' + equity.toFixed(2);
  balEl.className = 'val ' + (totalDiff > 0 ? 'pos' : (totalDiff < 0 ? 'neg' : ''));
  document.getElementById('kpiPnl').innerHTML = `Bakiye: $${Number(STATE.balance).toFixed(2)} | Açık PnL: <span class="${unrealizedSum>=0?'pos':'neg'}">${unrealizedSum>=0?'+':''}$${unrealizedSum.toFixed(2)}</span> | Toplam: <span class="${totalDiff>=0?'pos':'neg'}">${totalDiff>=0?'+':''}$${totalDiff.toFixed(2)}</span>`;
  document.getElementById('kpiOpen').innerText = `${openList.length} / ${STATE.max_positions}`;
  document.getElementById('kpiVol300').innerText = `${(STATE.volatile_300 || []).length} Coin`;
  document.getElementById('kpiSignals').innerText = (STATE.signals_feed || []).length;
  document.getElementById('closedCountBtn').innerText = (STATE.closed_trades || []).length;

  const rb = document.getElementById('runBadge');
  const tb = document.getElementById('toggleBtn');
  if (STATE.is_running) {
    rb.className = 'badge badge-run'; rb.innerText = 'ÇALIŞIYOR';
    tb.className = 'btn-danger'; tb.innerText = '🛑 Acil Durdur';
  } else {
    rb.className = 'badge badge-stop'; rb.innerText = 'DURDURULDU';
    tb.className = 'btn-success'; tb.innerText = '▶️ Botu Başlat';
  }

  // Open Positions
  const ob = document.getElementById('openBody');
  ob.innerHTML = openList.length ? openList.map(p => {
    const lev = p.leverage || STATE.leverage || 10;
    const mUsd = Number(p.margin_usdt || 0);
    const mPct = p.margin_pct !== undefined ? Number(p.margin_pct) : ((mUsd / Math.max(Number(STATE.balance || 100), 1)) * 100);
    const notional = Number(p.initial_notional || (mUsd * lev));
    return `
    <tr class="clickable" onclick="openTradeTab('${p.symbol}')">
      <td><strong>${p.symbol}</strong> ↗</td>
      <td>${p.exchange}</td>
      <td><span class="pill ${p.direction==='LONG'?'long':'short'}">${p.direction}</span></td>
      <td><span class="pill grade-B">${lev}x</span></td>
      <td><strong>$${mUsd.toFixed(2)}</strong> <span style="color:#8b9bb4;">(%${mPct.toFixed(1)})</span></td>
      <td>$${notional.toFixed(2)}</td>
      <td><span class="pill grade-${p.grade}">${p.grade} (${p.score_14}/14)</span></td>
      <td>${p.entry_price}</td>
      <td>${p.current_price}</td>
      <td>${p.stop_price}</td>
      <td>${p.tp1}</td>
      <td>${p.tp2}</td>
      <td class="${p.unrealized_pnl_usdt>=0?'pos':'neg'}">${p.unrealized_pnl_usdt>=0?'+':''}$${p.unrealized_pnl_usdt}</td>
      <td>${p.status_note}</td>
      <td><button class="btn-danger" style="padding:5px 10px;font-size:12px;" onclick="closePosition(event, '${p.symbol}')">❌ Kapat</button></td>
    </tr>
  `}).join('') : '<tr><td colspan="15" style="color:#8b9bb4;text-align:center;">Şu anda açık pozisyon yok.</td></tr>';

  renderTables();
}

function renderTables() {
  if (!STATE) return;
  const q = (document.getElementById('searchBox').value || '').toUpperCase().trim();

  // Signals
  const sigs = (STATE.signals_feed || []).filter(s => !q || s.symbol.includes(q));
  document.getElementById('signalsBody').innerHTML = sigs.map(s => `
    <tr class="clickable" onclick="openTradeTab('${s.symbol}')">
      <td><strong>${s.symbol}</strong> ↗</td>
      <td>${s.exchange}</td>
      <td><span class="pill ${s.direction==='LONG'?'long':'short'}">${s.direction}</span></td>
      <td>${s.status}</td>
      <td><span class="pill grade-${s.grade}">${s.grade} (${s.score_14}/14)</span></td>
      <td>${s.last_price}</td>
      <td>${s.entry_price}</td>
      <td>${s.stop_price}</td>
      <td>${s.tp1}</td>
      <td>${s.net_r}R</td>
      <td>${s.volatility_score}%</td>
    </tr>
  `).join('');

  // Top 300 Volatile
  const v300 = (STATE.volatile_300 || []).filter(c => !q || c.symbol.includes(q));
  document.getElementById('vol300Body').innerHTML = v300.map((c, idx) => `
    <tr class="clickable" onclick="openTradeTab('${c.symbol}')">
      <td>${idx + 1}</td>
      <td><strong>${c.symbol}</strong> ↗</td>
      <td>${(c.sources || []).join(' + ')}</td>
      <td>${c.last_price}</td>
      <td class="${c.change_24h_pct>=0?'pos':'neg'}">${c.change_24h_pct}%</td>
      <td>${c.range_volatility_pct}%</td>
      <td><strong>${c.volatility_score}</strong></td>
      <td>$${Number(c.quote_volume_usdt).toLocaleString('en-US')}</td>
    </tr>
  `).join('');

  // Closed History
  const allHist = STATE.closed_trades || [];
  const winCount = allHist.filter(h => Number(h.realized_pnl_usdt || 0) > 0).length;
  const lossCount = allHist.filter(h => Number(h.realized_pnl_usdt || 0) < 0).length;
  const netHistPnl = allHist.reduce((acc, h) => acc + Number(h.realized_pnl_usdt || 0), 0);
  document.getElementById('historySummary').innerHTML = `<strong>Toplam Kapanan:</strong> ${allHist.length} | <span class="pos">Kârda Kapanan: ${winCount}</span> | <span class="neg">Zararda Kapanan: ${lossCount}</span> | <strong>Net Gerçekleşen PnL:</strong> <span class="${netHistPnl>=0?'pos':'neg'}">${netHistPnl>=0?'+':''}$${netHistPnl.toFixed(2)}</span>`;
  const hist = allHist.filter(h => !q || h.symbol.includes(q));
  document.getElementById('historyBody').innerHTML = hist.length ? hist.map(h => {
    const pnl = Number(h.realized_pnl_usdt || 0);
    const resBadge = pnl > 0 ? '<span class="pill long">KÂR</span>' : (pnl < 0 ? '<span class="pill short">ZARAR</span>' : '<span class="pill grade-C">BAŞABAŞ</span>');
    return `
    <tr class="clickable" onclick="openTradeTab('${h.symbol}')">
      <td><strong>${h.symbol}</strong> ↗</td>
      <td><span class="pill ${h.direction==='LONG'?'long':'short'}">${h.direction}</span></td>
      <td>${h.entry_price}</td>
      <td>${h.exit_price}</td>
      <td>${resBadge}</td>
      <td>${h.close_reason}</td>
      <td class="${pnl>=0?'pos':'neg'}">${pnl>=0?'+':''}$${pnl.toFixed(2)}</td>
      <td>${h.closed_at}</td>
    </tr>
  `}).join('') : '<tr><td colspan="8" style="color:#8b9bb4;text-align:center;">Henüz kapanan test işlemi yok. Açık işlemler TP1/TP2 veya Stop olduğunda burada kâr/zarar durumuyla listelenir.</td></tr>';

  // Webhooks
  const wh = STATE.webhook_alerts || [];
  if (wh.length) {
    document.getElementById('webhookList').innerHTML = wh.map(w => `<div style="padding:8px;border-bottom:1px solid #25314d;">[${w.time}] <code>${JSON.stringify(w.payload)}</code></div>`).join('');
  }
}

fetchState();
setInterval(fetchState, 3000);
</script>
</body>
</html>
"""

HTML_TRADE_DETAIL = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__SYMBOL__ • İşlem Detayı & TradingView</title>
<style>
  body { background:#0b0f19; color:#e6edf7; font-family:'Segoe UI',system-ui,sans-serif; margin:0; padding:18px; }
  .top { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:10px; }
  .grid { display:grid; grid-template-columns: 360px 1fr; gap:16px; height: calc(100vh - 90px); }
  .card { background:#131a2a; border:1px solid #25314d; border-radius:12px; padding:16px; overflow-y:auto; }
  .row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(37,49,77,.5); font-size:13px; }
  .lbl { color:#8b9bb4; }
  .btn { background:#3b82f6; color:#fff; text-decoration:none; padding:8px 14px; border-radius:8px; font-size:13px; font-weight:600; }
  .tag { display:inline-block; background:#1e293b; border:1px solid #334155; padding:4px 8px; border-radius:6px; font-size:12px; margin:3px 3px 0 0; }
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; height:auto; } }
</style>
</head>
<body>
  <div class="top">
    <h2 style="margin:0;">📊 __SYMBOL__ — Kripto Levent Strateji & TradingView Görünümü</h2>
    <div>
      <a class="btn" href="__TV_LINK__" target="_blank">TradingView Tam Ekranda Aç ↗</a>
    </div>
  </div>
  <div class="grid">
    <div class="card" id="detailsCard">Yükleniyor...</div>
    <div class="card" style="padding:0; overflow:hidden;">
      <div id="tv_chart" style="width:100%; height:100%; min-height:540px;"></div>
    </div>
  </div>

<script src="https://s3.tradingview.com/tv.js"></script>
<script>
const SYM = "__SYMBOL__";
new TradingView.widget({
  "autosize": true,
  "symbol": "__TV_SYMBOL__",
  "interval": "15",
  "timezone": "Europe/Istanbul",
  "theme": "dark",
  "style": "1",
  "locale": "tr",
  "enable_publishing": false,
  "allow_symbol_change": true,
  "container_id": "tv_chart"
});

fetch('/api/trade?symbol=' + encodeURIComponent(SYM)).then(r => r.json()).then(d => {
  const pos = d.position || d.signal || {};
  const coin = d.coin || {};
  const box = document.getElementById('detailsCard');
  if (!pos.symbol && !coin.symbol) {
    box.innerHTML = '<p>Bu parite için aktif sinyal bulunamadı.</p>';
    return;
  }
  const fibs = pos.fib_levels ? Object.entries(pos.fib_levels).map(([k,v]) => `<div class="row"><span class="lbl">${k}</span><strong>${v}</strong></div>`).join('') : '';
  const confs = (pos.confluences || []).map(c => `<span class="tag">${c}</span>`).join('') || '<span class="lbl">Yok</span>';
  box.innerHTML = `
    <h3 style="margin-top:0;">${SYM} (${pos.direction || '-'})</h3>
    <div class="row"><span class="lbl">Borsa</span><strong>${pos.exchange || coin.exchange || 'BINANCE'}</strong></div>
    <div class="row"><span class="lbl">Kaldıraç</span><strong>${pos.leverage || 10}x</strong></div>
    <div class="row"><span class="lbl">Marjin ($ / %)</span><strong>$${Number(pos.margin_usdt || 0).toFixed(2)} (%${Number(pos.margin_pct || 0).toFixed(1)})</strong></div>
    <div class="row"><span class="lbl">İşlem Büyüklüğü</span><strong>$${Number(pos.initial_notional || 0).toFixed(2)}</strong></div>
    <div class="row"><span class="lbl">14 Koşul Tablosu</span><strong>${pos.grade || '-'} (${pos.score_14 || 0}/14)</strong></div>
    <div class="row"><span class="lbl">Giriş Fiyatı</span><strong>${pos.entry_price || coin.last_price || '-'}</strong></div>
    <div class="row"><span class="lbl">Stop-Loss</span><strong style="color:#ef4444;">${pos.stop_price || '-'}</strong></div>
    <div class="row"><span class="lbl">TP1 (%75 Çıkış + Giriş-Stop)</span><strong style="color:#10b981;">${pos.tp1 || '-'}</strong></div>
    <div class="row"><span class="lbl">TP2 (%25 Çıkış)</span><strong style="color:#10b981;">${pos.tp2 || '-'}</strong></div>
    <div class="row"><span class="lbl">Net R Oranı</span><strong>${pos.net_r || '-'}R</strong></div>
    <div class="row"><span class="lbl">24s Volatilite Skoru</span><strong>${coin.volatility_score || pos.volatility_score || '-'}%</strong></div>
    <div class="row"><span class="lbl">Durum</span><strong>${pos.status_note || pos.status || 'İzleniyor'}</strong></div>
    <h4 style="margin:14px 0 6px;">📐 Özel Fibonacci Seviyeleri</h4>
    ${fibs}
    <h4 style="margin:14px 0 6px;">🧱 Kesişimler (Mavi Kutu / OB / FVG)</h4>
    <div>${confs}</div>
  `;
});
</script>
</body>
</html>
"""


class BotRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, obj, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_DASHBOARD)
        elif parsed.path == "/trade":
            qs = urllib.parse.parse_qs(parsed.query)
            sym = qs.get("symbol", ["BTCUSDT"])[0].upper()
            tv_sym = f"BINANCE:{sym}.P"
            tv_link = f"https://tr.tradingview.com/chart/?symbol={urllib.parse.quote(tv_sym)}"
            html = (
                HTML_TRADE_DETAIL
                .replace("__SYMBOL__", sym)
                .replace("__TV_SYMBOL__", tv_sym)
                .replace("__TV_LINK__", tv_link)
            )
            self._send_html(html)
        elif parsed.path == "/api/state":
            with BOT_LOCK:
                if os.path.exists(STATE_FILE):
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        self._send_json(json.load(f))
                else:
                    self._send_json({"balance": BOT.balance, "open_positions": {}, "volatile_300": [], "signals_feed": []})
        elif parsed.path == "/api/trade":
            qs = urllib.parse.parse_qs(parsed.query)
            sym = qs.get("symbol", [""])[0].upper()
            with BOT_LOCK:
                pos = BOT.open_positions.get(sym)
                sig = next((s for s in BOT.signals_feed if s["symbol"] == sym), None)
                coin = next((c for c in BOT.volatile_300 if c["symbol"] == sym), None)
            self._send_json({"position": pos, "signal": sig, "coin": coin})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/scan":
            with BOT_LOCK:
                res = BOT.run_cycle(scan_limit=60)
            self._send_json(res)
        elif parsed.path == "/api/toggle":
            with BOT_LOCK:
                BOT.is_running = not BOT.is_running
                BOT.save_state()
                state = BOT.is_running
            self._send_json({"is_running": state})
        elif parsed.path == "/api/close":
            qs = urllib.parse.parse_qs(parsed.query)
            sym = qs.get("symbol", [""])[0].upper()
            with BOT_LOCK:
                closed = BOT.manual_close_position(sym)
            self._send_json({"ok": closed is not None, "closed": closed})
        elif parsed.path == "/webhook":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length).decode("utf-8", errors="ignore")
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"raw": raw}
            with BOT_LOCK:
                BOT.webhook_alerts.insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "payload": payload})
                BOT.save_state()
            self._send_json({"ok": True})
        else:
            self.send_error(404)


if __name__ == "__main__":
    t = threading.Thread(target=background_scanner, daemon=True)
    t.start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), BotRequestHandler)
    print(f"KriptoLevo Web Arayuzu http://0.0.0.0:{PORT} adresinde baslatildi.")
    server.serve_forever()
