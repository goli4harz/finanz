import json

OUT = r"C:\Users\olietz\Documents\finanz\Simulation-Steuerzentrale.json"
PG_CRED = {"id": "NWckNyl8ZfwVVJCd", "name": "Postgres account"}

def pg(name, node_id, query, position, always_output=True, execute_once=False):
    n = {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": position,
        "credentials": {"postgres": PG_CRED},
        "parameters": {"operation": "executeQuery", "query": query, "options": {}}
    }
    if always_output:
        n["alwaysOutputData"] = True
    if execute_once:
        n["executeOnce"] = True
    return n

def code(name, node_id, js, position, mode=None):
    n = {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "parameters": {"jsCode": js}
    }
    if mode:
        n["parameters"]["mode"] = mode
    return n

def webhook(name, node_id, path, position):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": position,
        "parameters": {"httpMethod": "GET", "path": path, "responseMode": "responseNode", "options": {}}
    }

def respond_html(name, node_id, position):
    return {
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": position,
        "parameters": {
            "respondWith": "text",
            "responseBody": "={{ $json.html }}",
            "options": {"responseHeaders": {"entries": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}]}}
        }
    }

NAV = (
    "function nav(active) {\n"
    "  const items = [\n"
    "    ['simulation-uebersicht', 'Uebersicht'],\n"
    "    ['simulation-vergleich', 'Vergleich'],\n"
    "    ['historische-marktdaten', 'Marktdaten-Import (WF15)'],\n"
    "    ['historische-nachrichten', 'Nachrichten-Import (WF16)'],\n"
    "    ['historische-simulation', 'Laeufe verwalten (WF17)']\n"
    "  ];\n"
    "  return '<nav>' + items.map(([path, label]) =>\n"
    "    '<a href=\"/webhook/' + path + '\" class=\"' + (path === active ? 'active' : '') + '\">' + label + '</a>'\n"
    "  ).join('') + '</nav>';\n"
    "}\n"
    "function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;'); }\n"
    "function fmtNum(v, digits) { return (v === null || v === undefined) ? '-' : Number(v).toFixed(digits === undefined ? 2 : digits); }\n"
    "function fmtDateOnly(v) {\n"
    "  if (!v) return '-';\n"
    "  const d = new Date(v);\n"
    "  if (isNaN(d.getTime())) return String(v).slice(0, 10);\n"
    "  return d.toISOString().slice(0, 10);\n"
    "}\n"
    "const CSS = 'body{font-family:sans-serif;background:#1a1a1a;color:#e0e0e0;padding:24px;max-width:1100px;margin:0 auto;}'\n"
    "  + 'h1{color:#fff;} h2{color:#fff;margin-top:28px;} table{border-collapse:collapse;width:100%;margin-top:12px;}'\n"
    "  + 'th,td{border:1px solid #444;padding:6px 10px;text-align:left;font-size:13px;}'\n"
    "  + 'th{background:#2a2a2a;} .badge{background:#333;padding:2px 8px;border-radius:4px;}'\n"
    "  + '.pos{color:#7fd88f;} .neg{color:#e08080;}'\n"
    "  + 'nav{margin-bottom:20px;} nav a{color:#8ab4f8;text-decoration:none;margin-right:16px;padding:4px 0;}'\n"
    "  + 'nav a.active{color:#fff;border-bottom:2px solid #2d6cdf;} nav a:hover{text-decoration:underline;}'\n"
    "  + '.kpi-row{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;}'\n"
    "  + '.kpi{background:#232323;padding:12px 18px;border-radius:8px;min-width:140px;}'\n"
    "  + '.kpi .label{font-size:11px;color:#999;text-transform:uppercase;} .kpi .value{font-size:22px;color:#fff;margin-top:4px;}'\n"
    "  + '.bar-wrap{display:flex;align-items:flex-end;gap:1px;height:80px;background:#151515;padding:4px;border-radius:4px;}'\n"
    "  + '.bar{background:#2d6cdf;flex:1;min-width:1px;}'\n"
    "  + '.hint{font-size:12px;color:#888;margin-top:4px;}';\n"
)

# ---------------------------------------------------------------------------
# Bereich 1: Uebersicht (Dashboard)
# ---------------------------------------------------------------------------

Q_UEBERSICHT_JOBS = (
    "SELECT job_type, status, count(*) AS anzahl FROM trading.import_jobs "
    "GROUP BY job_type, status;"
)
Q_UEBERSICHT_RUNS = (
    "SELECT br.id, br.name, br.status, br.start_date, br.end_date, br.progress_total, "
    "br.progress_completed, br.news_enabled, br.last_heartbeat, sm.total_return_pct, "
    "sm.trade_count, sm.max_drawdown_pct "
    "FROM trading.backtest_runs br "
    "LEFT JOIN trading.simulation_metrics sm ON sm.simulation_run_id = br.id "
    "WHERE br.created_by = 'simulation-steuerzentrale' OR br.created_by IS NOT NULL "
    "ORDER BY br.started_at DESC NULLS LAST, br.id DESC LIMIT 10;"
)
Q_UEBERSICHT_DATENUMFANG = (
    "SELECT "
    "(SELECT count(*) FROM trading.historical_price_data) AS preis_zeilen, "
    "(SELECT count(DISTINCT ticker) FROM trading.historical_price_data) AS preis_ticker, "
    "(SELECT min(trading_date) FROM trading.historical_price_data) AS preis_von, "
    "(SELECT max(trading_date) FROM trading.historical_price_data) AS preis_bis, "
    "(SELECT count(*) FROM trading.historical_news) AS news_zeilen, "
    "(SELECT count(*) FROM trading.historical_news_assessments) AS news_bewertet;"
)

JS_UEBERSICHT_HTML = NAV + (
    "const jobs = $('DB: Jobs-Status').all().map(i => i.json).filter(j => j && j.job_type);\n"
    "const runs = $('DB: Laeufe').all().map(i => i.json).filter(j => j && j.id !== undefined);\n"
    "const umfangRows = $('DB: Datenumfang').all().map(i => i.json).filter(j => j && j.preis_zeilen !== undefined);\n"
    "const umfang = umfangRows[0] || {};\n"
    "\n"
    "const STATUS_LABEL = {\n"
    "  draft: 'Entwurf', queued: 'wartet', running: 'laeuft', pausing: 'pausiert (wird beendet)',\n"
    "  paused: 'pausiert', completed: 'abgeschlossen', completed_with_warnings: 'abgeschlossen (mit Warnungen)',\n"
    "  failed: 'fehlgeschlagen', cancelled: 'abgebrochen'\n"
    "};\n"
    "\n"
    "function jobCount(type, statuses) {\n"
    "  return jobs.filter(j => j.job_type === type && statuses.includes(j.status)).reduce((a, j) => a + Number(j.anzahl), 0);\n"
    "}\n"
    "const marktAktiv = jobCount('market_data', ['queued', 'running', 'pausing']);\n"
    "const newsAktiv = jobCount('news', ['queued', 'running', 'pausing']);\n"
    "const laufeAktiv = runs.filter(r => ['queued', 'running', 'pausing'].includes(r.status)).length;\n"
    "\n"
    "const runsHtml = runs.map(r => {\n"
    "  const prog = r.progress_total > 0 ? Math.round(100 * (r.progress_completed || 0) / r.progress_total) : 0;\n"
    "  const retKlass = r.total_return_pct > 0 ? 'pos' : (r.total_return_pct < 0 ? 'neg' : '');\n"
    "  return '<tr>' +\n"
    "    '<td><a href=\"/webhook/simulation-lauf?run_id=' + esc(r.id) + '\" style=\"color:#8ab4f8;\">' + esc(r.name || ('Lauf ' + r.id)) + '</a></td>' +\n"
    "    '<td>' + esc(fmtDateOnly(r.start_date)) + ' - ' + esc(fmtDateOnly(r.end_date)) + '</td>' +\n"
    "    '<td><span class=\"badge\">' + (STATUS_LABEL[r.status] || esc(r.status)) + '</span>' + (r.news_enabled ? ' <span class=\"badge\" title=\"Nachrichten aktiv\">News</span>' : '') + '</td>' +\n"
    "    '<td>' + prog + '%</td>' +\n"
    "    '<td class=\"' + retKlass + '\">' + (r.total_return_pct !== null ? fmtNum(r.total_return_pct) + '%' : '-') + '</td>' +\n"
    "    '<td>' + (r.trade_count ?? '-') + '</td>' +\n"
    "  '</tr>';\n"
    "}).join('');\n"
    "\n"
    "const html = '<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\">' +\n"
    "  '<title>Historische Simulation - Uebersicht</title><style>' + CSS + '</style></head><body>' +\n"
    "  nav('simulation-uebersicht') +\n"
    "  '<h1>Historische Simulation - Uebersicht</h1>' +\n"
    "  '<div class=\"kpi-row\">' +\n"
    "    '<div class=\"kpi\"><div class=\"label\">Aktive Marktdaten-Importe</div><div class=\"value\">' + marktAktiv + '</div></div>' +\n"
    "    '<div class=\"kpi\"><div class=\"label\">Aktive Nachrichten-Importe</div><div class=\"value\">' + newsAktiv + '</div></div>' +\n"
    "    '<div class=\"kpi\"><div class=\"label\">Aktive Simulationslaeufe</div><div class=\"value\">' + laufeAktiv + '</div></div>' +\n"
    "    '<div class=\"kpi\"><div class=\"label\">Kurs-Zeilen</div><div class=\"value\">' + Number(umfang.preis_zeilen || 0).toLocaleString('de-DE') + '</div></div>' +\n"
    "    '<div class=\"kpi\"><div class=\"label\">Nachrichten (bewertet)</div><div class=\"value\">' + Number(umfang.news_zeilen || 0).toLocaleString('de-DE') + ' (' + Number(umfang.news_bewertet || 0).toLocaleString('de-DE') + ')</div></div>' +\n"
    "  '</div>' +\n"
    "  '<div class=\"hint\">Kursdaten: ' + esc(umfang.preis_ticker || 0) + ' Ticker, ' + esc(fmtDateOnly(umfang.preis_von)) + ' bis ' + esc(fmtDateOnly(umfang.preis_bis)) + '</div>' +\n"
    "  '<h2>Letzte Simulationslaeufe</h2>' +\n"
    "  '<table><tr><th>Name</th><th>Zeitraum</th><th>Status</th><th>Fortschritt</th><th>Rendite</th><th>Trades</th></tr>' +\n"
    "  (runsHtml || '<tr><td colspan=\"6\">Noch keine Laeufe.</td></tr>') +\n"
    "  '</table>' +\n"
    "  '<p class=\"hint\">Import-/Lauf-Verwaltung (starten/pausieren/abbrechen) weiterhin ueber die jeweiligen eigenen Seiten (siehe Navigation oben).</p>' +\n"
    "  '</body></html>';\n"
    "\n"
    "return [{ json: { html } }];\n"
)

# ---------------------------------------------------------------------------
# Bereich: Lauf-Detail
# ---------------------------------------------------------------------------

Q_LAUF_INFO = (
    "=SELECT br.*, sm.final_equity, sm.total_return_pct, sm.annualized_return_pct, "
    "sm.max_drawdown_pct, sm.volatility_pct, sm.sharpe_ratio, sm.win_rate_pct, sm.profit_factor, "
    "sm.average_win, sm.average_loss, sm.trade_count, sm.average_holding_period_days, "
    "sm.total_commission, sm.total_slippage, sm.unfilled_order_pct "
    "FROM trading.backtest_runs br "
    "LEFT JOIN trading.simulation_metrics sm ON sm.simulation_run_id = br.id "
    "WHERE br.id = {{ $('Validiere run_id').all()[0].json.run_id || 0 }};"
)
Q_LAUF_EQUITY = (
    "=SELECT simulated_date, total_equity, drawdown_pct FROM trading.simulation_daily_portfolio "
    "WHERE simulation_run_id = {{ $('Validiere run_id').all()[0].json.run_id || 0 }} ORDER BY simulated_date;"
)
Q_LAUF_TRADES = (
    "=SELECT trade_id, ticker, strategy, direction, as_of_date, simulated_entry_price, "
    "exit_price, exit_reason, net_pnl, realized_r_multiple, status, holding_period_days "
    "FROM trading.simulation_trades WHERE simulation_run_id = {{ $('Validiere run_id').all()[0].json.run_id || 0 }} "
    "ORDER BY as_of_date DESC LIMIT 200;"
)
Q_LAUF_FEHLER = (
    "=SELECT occurred_at, ticker, simulated_date, error_class, message, retryable "
    "FROM trading.simulation_errors WHERE simulation_run_id = {{ $('Validiere run_id').all()[0].json.run_id || 0 }} "
    "ORDER BY occurred_at DESC LIMIT 50;"
)

JS_LAUF_VALIDIERE = (
    "const runId = Number(($json.query || {}).run_id);\n"
    "if (!Number.isInteger(runId) || runId <= 0) {\n"
    "  return [{ json: { _invalid: true } }];\n"
    "}\n"
    "return [{ json: { run_id: runId, _invalid: false } }];\n"
)

JS_LAUF_HTML = NAV + (
    "const ctx = $('Validiere run_id').all()[0].json;\n"
    "if (ctx._invalid) {\n"
    "  const html = '<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\"><title>Ungueltiger Lauf</title>' +\n"
    "    '<style>' + CSS + '</style></head><body>' + nav('simulation-uebersicht') +\n"
    "    '<h1>Ungueltige Lauf-ID</h1><p>Bitte ueber die <a href=\"/webhook/simulation-uebersicht\" style=\"color:#8ab4f8;\">Uebersicht</a> einen Lauf auswaehlen.</p></body></html>';\n"
    "  return [{ json: { html } }];\n"
    "}\n"
    "\n"
    "const infoRows = $('DB: Lauf-Info').all().map(i => i.json).filter(j => j && j.id !== undefined);\n"
    "const equity = $('DB: Equity-Kurve').all().map(i => i.json).filter(j => j && j.simulated_date);\n"
    "const trades = $('DB: Trades').all().map(i => i.json).filter(j => j && j.trade_id);\n"
    "const fehler = $('DB: Fehler').all().map(i => i.json).filter(j => j && j.occurred_at);\n"
    "const info = infoRows[0];\n"
    "\n"
    "if (!info) {\n"
    "  const html = '<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\"><title>Lauf nicht gefunden</title>' +\n"
    "    '<style>' + CSS + '</style></head><body>' + nav('simulation-uebersicht') +\n"
    "    '<h1>Lauf ' + ctx.run_id + ' nicht gefunden</h1></body></html>';\n"
    "  return [{ json: { html } }];\n"
    "}\n"
    "\n"
    "const STATUS_LABEL = {\n"
    "  draft: 'Entwurf', queued: 'wartet', running: 'laeuft', pausing: 'pausiert (wird beendet)',\n"
    "  paused: 'pausiert', completed: 'abgeschlossen', completed_with_warnings: 'abgeschlossen (mit Warnungen)',\n"
    "  failed: 'fehlgeschlagen', cancelled: 'abgebrochen'\n"
    "};\n"
    "\n"
    "// Equity-Kurve als einfaches Balkendiagramm (relative Hoehe zwischen Min/Max der Reihe) -\n"
    "// gleiches Stilprinzip wie 07s bestehendes Balkendiagramm, kein externes Chart-JS noetig.\n"
    "let barsHtml = '<div class=\"hint\">Noch keine Equity-Daten.</div>';\n"
    "if (equity.length > 0) {\n"
    "  const values = equity.map(e => Number(e.total_equity));\n"
    "  const min = Math.min(...values), max = Math.max(...values);\n"
    "  const range = (max - min) || 1;\n"
    "  const bars = equity.map(e => {\n"
    "    const v = Number(e.total_equity);\n"
    "    const pct = 10 + 90 * (v - min) / range;\n"
    "    const title = esc(fmtDateOnly(e.simulated_date)) + ': ' + fmtNum(v, 0) + ' EUR';\n"
    "    return '<div class=\"bar\" style=\"height:' + pct.toFixed(1) + '%;\" title=\"' + title + '\"></div>';\n"
    "  }).join('');\n"
    "  barsHtml = '<div class=\"bar-wrap\">' + bars + '</div>' +\n"
    "    '<div class=\"hint\">' + esc(fmtDateOnly(equity[0].simulated_date)) + ' bis ' + esc(fmtDateOnly(equity[equity.length - 1].simulated_date)) +\n"
    "    ' - Min ' + fmtNum(min, 0) + ' EUR / Max ' + fmtNum(max, 0) + ' EUR</div>';\n"
    "}\n"
    "\n"
    "const tradesHtml = trades.map(t => {\n"
    "  const pnlKlass = t.net_pnl > 0 ? 'pos' : (t.net_pnl < 0 ? 'neg' : '');\n"
    "  return '<tr>' +\n"
    "    '<td>' + esc(fmtDateOnly(t.as_of_date)) + '</td>' +\n"
    "    '<td>' + esc(t.ticker) + '</td>' +\n"
    "    '<td>' + esc(t.strategy) + '</td>' +\n"
    "    '<td>' + esc(t.direction) + '</td>' +\n"
    "    '<td>' + (t.simulated_entry_price !== null ? fmtNum(t.simulated_entry_price) : '-') + '</td>' +\n"
    "    '<td>' + (t.exit_price !== null ? fmtNum(t.exit_price) : '-') + '</td>' +\n"
    "    '<td>' + esc(t.exit_reason || '-') + '</td>' +\n"
    "    '<td class=\"' + pnlKlass + '\">' + (t.net_pnl !== null ? fmtNum(t.net_pnl) : '-') + '</td>' +\n"
    "    '<td>' + (t.realized_r_multiple !== null ? fmtNum(t.realized_r_multiple) + 'R' : '-') + '</td>' +\n"
    "    '<td><span class=\"badge\">' + esc(t.status) + '</span></td>' +\n"
    "  '</tr>';\n"
    "}).join('');\n"
    "\n"
    "const fehlerHtml = fehler.map(f => '<tr>' +\n"
    "  '<td>' + esc(fmtDateOnly(f.simulated_date)) + '</td>' +\n"
    "  '<td>' + esc(f.ticker || '-') + '</td>' +\n"
    "  '<td>' + esc(f.error_class) + '</td>' +\n"
    "  '<td>' + esc(f.message) + '</td>' +\n"
    "  '<td>' + (f.retryable ? 'ja' : 'nein') + '</td>' +\n"
    "'</tr>').join('');\n"
    "\n"
    "function kpi(label, value) {\n"
    "  return '<div class=\"kpi\"><div class=\"label\">' + esc(label) + '</div><div class=\"value\">' + esc(value) + '</div></div>';\n"
    "}\n"
    "\n"
    "const html = '<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\">' +\n"
    "  '<title>Lauf: ' + esc(info.name || info.id) + '</title><style>' + CSS + '</style></head><body>' +\n"
    "  nav('simulation-uebersicht') +\n"
    "  '<h1>' + esc(info.name || ('Lauf ' + info.id)) + '</h1>' +\n"
    "  '<div class=\"hint\">' + esc(fmtDateOnly(info.start_date)) + ' - ' + esc(fmtDateOnly(info.end_date)) +\n"
    "  ' | Status: <span class=\"badge\">' + (STATUS_LABEL[info.status] || esc(info.status)) + '</span>' +\n"
    "  (info.news_enabled ? ' <span class=\"badge\">News aktiv</span>' : '') + '</div>' +\n"
    "  '<div class=\"kpi-row\">' +\n"
    "    kpi('Endkapital', info.final_equity !== null ? fmtNum(info.final_equity, 0) + ' EUR' : '-') +\n"
    "    kpi('Gesamtrendite', info.total_return_pct !== null ? fmtNum(info.total_return_pct) + '%' : '-') +\n"
    "    kpi('Max Drawdown', info.max_drawdown_pct !== null ? fmtNum(info.max_drawdown_pct) + '%' : '-') +\n"
    "    kpi('Sharpe Ratio', info.sharpe_ratio !== null ? fmtNum(info.sharpe_ratio, 2) : '-') +\n"
    "    kpi('Trefferquote', info.win_rate_pct !== null ? fmtNum(info.win_rate_pct) + '%' : '-') +\n"
    "    kpi('Trades', info.trade_count ?? '-') +\n"
    "  '</div>' +\n"
    "  '<h2>Equity-Kurve</h2>' + barsHtml +\n"
    "  '<h2>Trades (max. 200, neueste zuerst)</h2>' +\n"
    "  '<table><tr><th>Datum</th><th>Ticker</th><th>Strategie</th><th>Richtung</th><th>Einstieg</th><th>Ausstieg</th><th>Grund</th><th>Netto-P&amp;L</th><th>R-Multiple</th><th>Status</th></tr>' +\n"
    "  (tradesHtml || '<tr><td colspan=\"10\">Noch keine Trades.</td></tr>') +\n"
    "  '</table>' +\n"
    "  '<h2>Fehler (max. 50, neueste zuerst)</h2>' +\n"
    "  '<table><tr><th>Datum</th><th>Ticker</th><th>Klasse</th><th>Meldung</th><th>Wiederholbar</th></tr>' +\n"
    "  (fehlerHtml || '<tr><td colspan=\"5\">Keine Fehler.</td></tr>') +\n"
    "  '</table>' +\n"
    "  '</body></html>';\n"
    "\n"
    "return [{ json: { html } }];\n"
)

# ---------------------------------------------------------------------------
# Bereich 5: Vergleich
# ---------------------------------------------------------------------------

Q_VERGLEICH = (
    "SELECT br.id, br.name, br.start_date, br.end_date, br.news_enabled, br.status, "
    "sm.total_return_pct, sm.annualized_return_pct, sm.max_drawdown_pct, sm.sharpe_ratio, "
    "sm.win_rate_pct, sm.profit_factor, sm.trade_count "
    "FROM trading.backtest_runs br "
    "JOIN trading.simulation_metrics sm ON sm.simulation_run_id = br.id "
    "ORDER BY sm.computed_at DESC LIMIT 50;"
)

JS_VERGLEICH_HTML = NAV + (
    "const runs = $('DB: Vergleich').all().map(i => i.json).filter(j => j && j.id !== undefined);\n"
    "\n"
    "const rowsHtml = runs.map(r => {\n"
    "  const retKlass = r.total_return_pct > 0 ? 'pos' : (r.total_return_pct < 0 ? 'neg' : '');\n"
    "  return '<tr>' +\n"
    "    '<td><a href=\"/webhook/simulation-lauf?run_id=' + esc(r.id) + '\" style=\"color:#8ab4f8;\">' + esc(r.name || ('Lauf ' + r.id)) + '</a></td>' +\n"
    "    '<td>' + esc(fmtDateOnly(r.start_date)) + ' - ' + esc(fmtDateOnly(r.end_date)) + '</td>' +\n"
    "    '<td>' + (r.news_enabled ? 'ja' : 'nein') + '</td>' +\n"
    "    '<td class=\"' + retKlass + '\">' + fmtNum(r.total_return_pct) + '%</td>' +\n"
    "    '<td>' + fmtNum(r.annualized_return_pct) + '%</td>' +\n"
    "    '<td>' + fmtNum(r.max_drawdown_pct) + '%</td>' +\n"
    "    '<td>' + fmtNum(r.sharpe_ratio, 2) + '</td>' +\n"
    "    '<td>' + fmtNum(r.win_rate_pct) + '%</td>' +\n"
    "    '<td>' + (r.trade_count ?? '-') + '</td>' +\n"
    "  '</tr>';\n"
    "}).join('');\n"
    "\n"
    "const html = '<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\">' +\n"
    "  '<title>Simulationslaeufe vergleichen</title><style>' + CSS + '</style></head><body>' +\n"
    "  nav('simulation-vergleich') +\n"
    "  '<h1>Simulationslaeufe vergleichen</h1>' +\n"
    "  '<div class=\"hint\">Nur Laeufe mit bereits berechneten Kennzahlen (abgeschlossen oder mit Zwischenstand).</div>' +\n"
    "  '<table><tr><th>Name</th><th>Zeitraum</th><th>News</th><th>Rendite</th><th>Rendite p.a.</th><th>Max Drawdown</th><th>Sharpe</th><th>Trefferquote</th><th>Trades</th></tr>' +\n"
    "  (rowsHtml || '<tr><td colspan=\"9\">Noch keine ausgewerteten Laeufe.</td></tr>') +\n"
    "  '</table>' +\n"
    "  '</body></html>';\n"
    "\n"
    "return [{ json: { html } }];\n"
)

workflow = {
    "name": "Simulation-Steuerzentrale",
    "nodes": [
        webhook("Webhook GET Uebersicht", "sz-wh-uebersicht", "simulation-uebersicht", [-1200, -200]),
        pg("DB: Jobs-Status", "sz-db-jobs", Q_UEBERSICHT_JOBS, [-960, -280], execute_once=True),
        pg("DB: Laeufe", "sz-db-laeufe", Q_UEBERSICHT_RUNS, [-960, -200], execute_once=True),
        pg("DB: Datenumfang", "sz-db-datenumfang", Q_UEBERSICHT_DATENUMFANG, [-960, -120], execute_once=True),
        code("Baue Uebersicht HTML", "sz-code-uebersicht", JS_UEBERSICHT_HTML, [-720, -200]),
        respond_html("Antwort Uebersicht", "sz-resp-uebersicht", [-480, -200]),

        webhook("Webhook GET Lauf-Detail", "sz-wh-lauf", "simulation-lauf", [-1200, 200]),
        code("Validiere run_id", "sz-code-validiere", JS_LAUF_VALIDIERE, [-960, 200]),
        pg("DB: Lauf-Info", "sz-db-lauf-info", Q_LAUF_INFO, [-720, 80]),
        pg("DB: Equity-Kurve", "sz-db-equity", Q_LAUF_EQUITY, [-720, 160]),
        pg("DB: Trades", "sz-db-trades", Q_LAUF_TRADES, [-720, 240]),
        pg("DB: Fehler", "sz-db-fehler", Q_LAUF_FEHLER, [-720, 320]),
        code("Baue Lauf-Detail HTML", "sz-code-lauf", JS_LAUF_HTML, [-480, 200]),
        respond_html("Antwort Lauf-Detail", "sz-resp-lauf", [-240, 200]),

        webhook("Webhook GET Vergleich", "sz-wh-vergleich", "simulation-vergleich", [-1200, 600]),
        pg("DB: Vergleich", "sz-db-vergleich", Q_VERGLEICH, [-960, 600], execute_once=True),
        code("Baue Vergleich HTML", "sz-code-vergleich", JS_VERGLEICH_HTML, [-720, 600]),
        respond_html("Antwort Vergleich", "sz-resp-vergleich", [-480, 600]),
    ],
    "connections": {
        # Sequentielle Kette statt paralleler Fan-in-Verbindungen (etabliertes Muster aus
        # WF15/16/17s eigenen HTML-Seiten) - mehrere parallele Verbindungen auf denselben
        # Zielnode fuehren in n8n NICHT zu einem "warte auf alle"-Merge, sondern lassen den
        # Zielnode bei jedem einzelnen Trigger mit nur EINER der Quellen laufen -
        # "Node 'X' hasn't been executed" live am 2026-08-04 bestaetigt.
        "Webhook GET Uebersicht": {"main": [[{"node": "DB: Jobs-Status", "type": "main", "index": 0}]]},
        "DB: Jobs-Status": {"main": [[{"node": "DB: Laeufe", "type": "main", "index": 0}]]},
        "DB: Laeufe": {"main": [[{"node": "DB: Datenumfang", "type": "main", "index": 0}]]},
        "DB: Datenumfang": {"main": [[{"node": "Baue Uebersicht HTML", "type": "main", "index": 0}]]},
        "Baue Uebersicht HTML": {"main": [[{"node": "Antwort Uebersicht", "type": "main", "index": 0}]]},

        "Webhook GET Lauf-Detail": {"main": [[{"node": "Validiere run_id", "type": "main", "index": 0}]]},
        "Validiere run_id": {"main": [[{"node": "DB: Lauf-Info", "type": "main", "index": 0}]]},
        "DB: Lauf-Info": {"main": [[{"node": "DB: Equity-Kurve", "type": "main", "index": 0}]]},
        "DB: Equity-Kurve": {"main": [[{"node": "DB: Trades", "type": "main", "index": 0}]]},
        "DB: Trades": {"main": [[{"node": "DB: Fehler", "type": "main", "index": 0}]]},
        "DB: Fehler": {"main": [[{"node": "Baue Lauf-Detail HTML", "type": "main", "index": 0}]]},
        "Baue Lauf-Detail HTML": {"main": [[{"node": "Antwort Lauf-Detail", "type": "main", "index": 0}]]},

        "Webhook GET Vergleich": {"main": [[{"node": "DB: Vergleich", "type": "main", "index": 0}]]},
        "DB: Vergleich": {"main": [[{"node": "Baue Vergleich HTML", "type": "main", "index": 0}]]},
        "Baue Vergleich HTML": {"main": [[{"node": "Antwort Vergleich", "type": "main", "index": 0}]]},
    },
    "pinData": {},
    "settings": {"executionOrder": "v1"}
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)
print("written", OUT)
