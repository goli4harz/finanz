function safeStr(v) { return v === null || v === undefined ? '' : String(v).trim(); }
function esc(s) {
  return safeStr(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function num(v) {
  const n = Number(v);
  return isNaN(n) ? null : n;
}
function rows(nodeName) {
  try { return $(nodeName).all().map(i => i.json || {}); } catch (e) { return []; }
}

const heute = new Date().toISOString().substring(0, 10);
const now = new Date().toLocaleString('de-DE', { timeZone: 'Europe/Berlin' });

const fundamentaldaten = rows('DB: Fundamentaldaten laden');
const marktKontext     = rows('DB: Marktumfeld laden');
const techSignale      = rows('DB: Technische Signale laden');
const news             = rows('DB: News laden');
const empfehlungen     = rows('DB: Empfehlungen laden');
const kursHistorie     = rows('DB: Kursverlauf laden');

function letzterStand(list, getFeld) {
  const daten = list.map(r => safeStr(getFeld(r))).filter(Boolean).sort();
  return daten.length > 0 ? daten[daten.length - 1] : null;
}

function quelleZeile(name, list, getFeld) {
  const stand = letzterStand(list, getFeld);
  const standDatum = stand ? stand.substring(0, 10) : null;
  const aktuell = standDatum === heute;
  const badge = list.length === 0
    ? '<span class="badge warn">leer</span>'
    : aktuell
      ? '<span class="badge ok">aktuell</span>'
      : '<span class="badge warn">veraltet (' + esc(standDatum || 'unbekannt') + ')</span>';
  return '<tr><td>' + esc(name) + '</td><td class="num">' + list.length + '</td><td>' + (stand ? esc(stand) : '—') + '</td><td>' + badge + '</td></tr>';
}

const quellenHtml =
  quelleZeile('stock_fundamentals', fundamentaldaten, r => r.datum) +
  quelleZeile('stock_market_context', marktKontext, r => r.datum) +
  quelleZeile('stock_technical_signals', techSignale, r => r.datum) +
  quelleZeile('stock_news_evaluated', news, r => r.datum_iso || r.datum) +
  quelleZeile('stock_empfehlungen', empfehlungen, r => r.letzte_aktualisierung) +
  quelleZeile('stock_price_history', kursHistorie, r => r.datum);

// Technische Signale heute
const techHeute = techSignale.filter(s => safeStr(s.datum).startsWith(heute));
const handelskandidaten = techHeute.filter(s => s.handels_status === 'handelskandidat');
const beobachten = techHeute.filter(s => s.handels_status === 'beobachten');

function signalZeile(s) {
  return '<tr><td>' + esc(s.ticker) + '</td><td>' + esc(s.name) + '</td><td>' + esc(s.handels_status_text || s.handels_status) + '</td>' +
    '<td class="num">' + esc(s.rsi) + '</td><td>' + esc(s.macd_signal) + '</td><td>' + esc(s.richtung) + '</td></tr>';
}
const kandidatenHtml = handelskandidaten.length > 0 ? handelskandidaten.map(signalZeile).join('') : '<tr><td colspan="6" class="empty">keine heute</td></tr>';
const beobachtenHtml = beobachten.length > 0 ? beobachten.map(signalZeile).join('') : '<tr><td colspan="6" class="empty">keine heute</td></tr>';

// Empfehlungs-Watchlist
const offen = empfehlungen.filter(e => e.status === 'offen');
const geschlossen = empfehlungen.filter(e => e.status === 'geschlossen');
const perfWerte = geschlossen.map(e => num(e.performance_pct)).filter(v => v !== null);
const avgPerf = perfWerte.length > 0 ? (perfWerte.reduce((a, b) => a + b, 0) / perfWerte.length).toFixed(2) : null;
const hitRate = perfWerte.length > 0 ? Math.round((perfWerte.filter(v => v > 0).length / perfWerte.length) * 100) : null;

function empfehlungZeile(e) {
  return '<tr><td>' + esc(e.ticker) + '</td><td>' + esc(e.richtung) + '</td><td>' + esc(e.entry_datum) + '</td>' +
    '<td class="num">' + esc(e.entry_kurs) + '</td><td>' + esc(e.status) + '</td></tr>';
}
const offenHtml = offen.length > 0 ? offen.map(empfehlungZeile).join('') : '<tr><td colspan="5" class="empty">keine offenen Positionen</td></tr>';

// News heute
const newsHeute = news.filter(n => safeStr(n.datum_iso || n.datum).startsWith(heute));
const newsHoch = newsHeute.filter(n => n.relevanz === 'hoch').length;
const newsMittel = newsHeute.filter(n => n.relevanz === 'mittel').length;

const html = '<!DOCTYPE html>' +
'<html lang="de">' +
'<head>' +
'<meta charset="utf-8">' +
'<title>Aktien-Pipeline Status-Uebersicht</title>' +
'<style>' +
'  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#0f1115; color:#e6e6e6; margin:0; padding:32px; }' +
'  h1 { font-size:20px; margin-bottom:4px; }' +
'  .meta { color:#9aa0a6; font-size:13px; margin-bottom:24px; }' +
'  table { border-collapse: collapse; width:100%; margin-bottom:32px; }' +
'  th, td { text-align:left; padding:8px 12px; border-bottom:1px solid #2a2d34; font-size:14px; font-variant-numeric: tabular-nums; }' +
'  th { color:#9aa0a6; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:0.04em; }' +
'  td.num { text-align:right; }' +
'  .empty { color:#5f6368; font-style:italic; }' +
'  h2 { font-size:15px; margin-top:8px; margin-bottom:8px; color:#e6e6e6; }' +
'  .hint { color:#9aa0a6; font-size:12px; margin-bottom:12px; }' +
'  .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }' +
'  .badge.ok { background:#1c3a2a; color:#6bcf8e; }' +
'  .badge.warn { background:#3a2c1c; color:#e0a854; }' +
'  .summary { display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }' +
'  .stat { background:#181b21; border:1px solid #2a2d34; border-radius:8px; padding:12px 16px; min-width:140px; }' +
'  .stat .label { color:#9aa0a6; font-size:11px; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:4px; }' +
'  .stat .value { font-size:22px; font-weight:700; font-variant-numeric: tabular-nums; }' +
'  .stat .value.good { color:#6bcf8e; }' +
'  .stat .value.bad { color:#e0665a; }' +
'</style>' +
'</head>' +
'<body>' +
'  <h1>Aktien-Report-Pipeline &mdash; Status-Uebersicht</h1>' +
'  <div class="meta">Stand: ' + esc(now) + '</div>' +
'  <h2>Datenquellen</h2>' +
'  <table>' +
'    <thead><tr><th>Tabelle</th><th>Zeilen</th><th>Letzter Stand</th><th></th></tr></thead>' +
'    <tbody>' + quellenHtml + '</tbody>' +
'  </table>' +
'  <h2>Kennzahlen heute</h2>' +
'  <div class="summary">' +
'    <div class="stat"><div class="label">Handelskandidaten</div><div class="value">' + handelskandidaten.length + '</div></div>' +
'    <div class="stat"><div class="label">Beobachten</div><div class="value">' + beobachten.length + '</div></div>' +
'    <div class="stat"><div class="label">News hoch/mittel</div><div class="value">' + newsHoch + ' / ' + newsMittel + '</div></div>' +
'    <div class="stat"><div class="label">Offene Empfehlungen</div><div class="value">' + offen.length + '</div></div>' +
'    <div class="stat"><div class="label">Ø Performance geschlossen</div><div class="value ' + (avgPerf !== null && avgPerf >= 0 ? 'good' : avgPerf !== null ? 'bad' : '') + '">' + (avgPerf !== null ? avgPerf + '%' : '—') + '</div></div>' +
'    <div class="stat"><div class="label">Trefferquote</div><div class="value">' + (hitRate !== null ? hitRate + '%' : '—') + '</div></div>' +
'  </div>' +
'  <h2>Handelskandidaten heute</h2>' +
'  <table>' +
'    <thead><tr><th>Ticker</th><th>Name</th><th>Status</th><th>RSI</th><th>MACD</th><th>Richtung</th></tr></thead>' +
'    <tbody>' + kandidatenHtml + '</tbody>' +
'  </table>' +
'  <h2>Beobachten heute</h2>' +
'  <table>' +
'    <thead><tr><th>Ticker</th><th>Name</th><th>Status</th><th>RSI</th><th>MACD</th><th>Richtung</th></tr></thead>' +
'    <tbody>' + beobachtenHtml + '</tbody>' +
'  </table>' +
'  <h2>Offene Empfehlungs-Positionen</h2>' +
'  <div class="hint">Hypothetische Watchlist aus News+Signal-Treffern, keine echten Trades.</div>' +
'  <table>' +
'    <thead><tr><th>Ticker</th><th>Richtung</th><th>Entry-Datum</th><th>Entry-Kurs</th><th>Status</th></tr></thead>' +
'    <tbody>' + offenHtml + '</tbody>' +
'  </table>' +
'</body>' +
'</html>';

return [{ json: { html: html } }];