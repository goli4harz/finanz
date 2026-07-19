# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED

OUT = r"C:\Users\olietz\Documents\finanz\07 – Status-Uebersicht – Agent V1.json"
ORIG = r"C:\Users\olietz\Downloads\Aktien\07 – Status-Uebersicht.json"

with open(ORIG, encoding="utf-8") as f:
    orig = json.load(f)
orig_nodes = {n["name"]: n for n in orig["nodes"]}

b = Builder("07 – Status-Uebersicht – Agent V1")

# ---------------------------------------------------------------------------
# 1. Webhook jetzt mit Header-Token-Schutz (Bestand-Pruefpunkt: "Status-
#    WebHook ist moeglicherweise nicht ausreichend geschuetzt" -- behoben).
#    httpHeaderAuth ist dieselbe, bereits produktiv genutzte n8n-Credential-
#    Art wie bei allen Matrix-Sends in diesem Projekt, hier aber als NEUE,
#    eigene Credential fuer eingehende Webhook-Absicherung (kein Zugangsdaten-
#    Wert im Workflow selbst).
# ---------------------------------------------------------------------------
n_webhook = b.add({
    "parameters": {
        "path": "aktien-status",
        "authentication": "headerAuth",
        "responseMode": "responseNode",
        "options": {}
    },
    "name": "Webhook Status-Uebersicht",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 2,
    "position": [-3600, 0],
    "webhookId": "eeeeeeee-0000-4000-8000-100000000001",
    "credentials": {"httpHeaderAuth": {"id": "PLACEHOLDER_STATUS_WEBHOOK_TOKEN", "name": "Status-Webhook Token (TODO Credential zuweisen)"}}
})

def dt_read(name, table_id, table_cached, position):
    node = b.add({
        "parameters": {
            "operation": "get",
            "dataTableId": {"__rl": True, "value": table_id, "mode": "list", "cachedResultName": table_cached},
            "returnAll": True
        },
        "name": name,
        "type": "n8n-nodes-base.dataTable",
        "typeVersion": 1,
        "position": position,
        "onError": "continueRegularOutput"
    })
    return node

n_fund = dt_read("DB: Fundamentaldaten laden", "Le3FJQ6pctb6qtGi", "stock_fundamentals", [-3400, -320])
b.link(n_webhook, n_fund)
n_markt = dt_read("DB: Marktumfeld laden", "dzUOoGnfASjaaVhn", "stock_market_context", [-3400, -160])
b.link(n_webhook, n_markt)
n_tech = dt_read("DB: Technische Signale laden", "GDMAKrvQovPcBItA", "stock_technical_signals", [-3400, 0])
b.link(n_webhook, n_tech)
n_empf = dt_read("DB: Empfehlungen laden", "TJgigfIfzXm7c7Ob", "stock_empfehlungen", [-3400, 160])
b.link(n_webhook, n_empf)
n_kurse = dt_read("DB: Kursverlauf laden", "Mc3Pem5RGio6bqXt", "stock_price_history", [-3400, 320])
b.link(n_webhook, n_kurse)

# News jetzt aus trading.* statt stock_news_evaluated (wird seit Phase 4
# nicht mehr befuellt).
n_news = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT ni.published_at, ni.created_at, na.wirkung_staerke, na.relevant\n"
                 "FROM trading.news_assessments na JOIN trading.news_items ni ON ni.id = na.news_id;",
        "options": {}
    },
    "name": "DB: News laden (trading.*)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 480],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_news)

# ---------------------------------------------------------------------------
# 2. Neue Kennzahlenquellen (Phase 13: Orchestrator/Agenten/Lernprozess)
# ---------------------------------------------------------------------------
n_pipeline = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT DISTINCT ON (workflow_name, stage_name) workflow_name, stage_name, status, started_at, finished_at,\n"
                 "       duration_ms, retry_count, error_message, warning_count, error_count\n"
                 "FROM trading.pipeline_runs ORDER BY workflow_name, stage_name, started_at DESC;",
        "options": {}
    },
    "name": "DB: Letzte Pipeline-Laeufe je Stufe",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 640],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_pipeline)

n_pipeline_success = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT DISTINCT ON (workflow_name) workflow_name, finished_at\n"
                 "FROM trading.pipeline_runs WHERE status = 'success' ORDER BY workflow_name, finished_at DESC;",
        "options": {}
    },
    "name": "DB: Letzter erfolgreicher Lauf je Workflow",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 800],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_pipeline_success)

n_agent_runs = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT DISTINCT ON (agent_name) agent_name, model_name, prompt_version, status, started_at, confidence\n"
                 "FROM trading.agent_runs ORDER BY agent_name, started_at DESC;",
        "options": {}
    },
    "name": "DB: Letzter Lauf je Agent",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 960],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_agent_runs)

n_news_state = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT status, count(*) AS anzahl FROM trading.news_items GROUP BY status;",
        "options": {}
    },
    "name": "DB: News-Zustandsverteilung",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 1120],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_news_state)

n_impact = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT status, count(*) AS anzahl,\n"
                 "       count(*) FILTER (WHERE confounded) AS confounded_anzahl,\n"
                 "       round(100.0 * count(*) FILTER (WHERE direction_correct = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct IS NOT NULL), 0), 1) AS trefferquote\n"
                 "FROM trading.news_impact_tracking GROUP BY status;",
        "options": {}
    },
    "name": "DB: Wirkungsanalyse-Fortschritt",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 1280],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_impact)

n_learn_open = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT count(*) AS offene_vorschlaege, max(created_at) AS letzter_vorschlag_am\n"
                 "FROM trading.learning_rule_proposals WHERE status = 'proposed';",
        "options": {}
    },
    "name": "DB: Offene Lernvorschlaege",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3400, 1440],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_webhook, n_learn_open)

# ---------------------------------------------------------------------------
# 3. Alles zusammenfuehren (append-Merge-Kette wie im Original)
# ---------------------------------------------------------------------------
sources = [n_fund, n_markt, n_tech, n_empf, n_kurse, n_news, n_pipeline, n_pipeline_success, n_agent_runs, n_news_state, n_impact, n_learn_open]
prev = sources[0]
for i, src in enumerate(sources[1:], start=1):
    m = b.add({"parameters": {}, "name": f"Merge Status {i}", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-3200 + i * 40, i * 30]})
    b.link(prev, m, dst_index=0)
    b.link(src, m, dst_index=1)
    prev = m

# ---------------------------------------------------------------------------
# 4. HTML bauen -- Original-Logik fast unveraendert, News-Feldnamen an
#    trading.* angepasst, neue Abschnitte fuer Orchestrator/Agenten/Lernagent
#    angehaengt (Phase 13, alle im Auftrag genannten Kennzahlen).
# ---------------------------------------------------------------------------
orig_code = orig_nodes["Baue Uebersicht"]["parameters"]["jsCode"]
new_code = orig_code.replace(
    "const heute = new Date().toISOString().substring(0, 10);",
    GET_BUSINESS_DATE_JS + "\nconst heute = getBusinessDate();"
)
new_code = new_code.replace(
    "const news             = rows('DB: News laden');",
    "const news             = rows('DB: News laden (trading.*)').map(r => ({ datum_iso: r.published_at || r.created_at, relevanz: r.wirkung_staerke === 'hoch' ? 'hoch' : (r.wirkung_staerke === 'mittel' ? 'mittel' : '') }));"
)
# Die urspruengliche Return-Zeile wird entfernt (nicht nur ueberschrieben) --
# sonst wuerde sie den Node vor dem neuen, erweiterten Return-Statement
# beenden.
ORIG_RETURN = "return [{ json: { html: html } }];"
assert new_code.rstrip().endswith(ORIG_RETURN), "unerwartetes Zeilenende in Baue Uebersicht"
new_code = new_code.rstrip()[: -len(ORIG_RETURN)].rstrip()

new_code += """

// ─── Phase 13: Orchestrator-/Agenten-/Lernprozess-Kennzahlen ──────────────────
const pipelineLaeufe = rows('DB: Letzte Pipeline-Laeufe je Stufe');
const letzterErfolg = rows('DB: Letzter erfolgreicher Lauf je Workflow');
const agentLaeufe = rows('DB: Letzter Lauf je Agent');
const newsZustand = rows('DB: News-Zustandsverteilung');
const wirkungsFortschritt = rows('DB: Wirkungsanalyse-Fortschritt');
const lernVorschlaege = rows('DB: Offene Lernvorschlaege')[0] || {};

function pipelineZeile(p) {
  const erfolgTreffer = letzterErfolg.find(e => e.workflow_name === p.workflow_name);
  const badge = p.status === 'success' ? '<span class="badge ok">success</span>'
    : p.status === 'failed' ? '<span class="badge warn">failed</span>'
    : '<span class="badge warn">' + esc(p.status) + '</span>';
  return '<tr><td>' + esc(p.workflow_name) + '</td><td>' + esc(p.stage_name) + '</td><td>' + badge + '</td>' +
    '<td>' + esc(p.finished_at) + '</td><td>' + esc(erfolgTreffer ? erfolgTreffer.finished_at : '—') + '</td>' +
    '<td class="num">' + esc(p.duration_ms) + '</td><td class="num">' + esc(p.retry_count || 0) + '</td>' +
    '<td class="num">' + esc(p.warning_count || 0) + '</td><td class="num">' + esc(p.error_count || 0) + '</td></tr>';
}
const pipelineHtml = pipelineLaeufe.length > 0 ? pipelineLaeufe.map(pipelineZeile).join('') : '<tr><td colspan="9" class="empty">noch keine Orchestrator-Laeufe protokolliert</td></tr>';

function agentZeile(a) {
  const badge = a.status === 'success' ? '<span class="badge ok">success</span>' : '<span class="badge warn">' + esc(a.status) + '</span>';
  return '<tr><td>' + esc(a.agent_name) + '</td><td>' + esc(a.model_name) + '</td><td>' + esc(a.prompt_version) + '</td>' +
    '<td>' + badge + '</td><td>' + esc(a.started_at) + '</td><td class="num">' + esc(a.confidence ?? '') + '</td></tr>';
}
const agentHtml = agentLaeufe.length > 0 ? agentLaeufe.map(agentZeile).join('') : '<tr><td colspan="6" class="empty">noch keine Agentenlaeufe protokolliert</td></tr>';

const newsZustandMap = {};
for (const z of newsZustand) newsZustandMap[z.status] = Number(z.anzahl);
const newsOffenRetry = (newsZustandMap.pending || 0) + (newsZustandMap.retry || 0);
const newsFailed = newsZustandMap.failed || 0;

const impactMap = {};
for (const w of wirkungsFortschritt) impactMap[w.status] = w;
const impactCompleted = impactMap.completed || { anzahl: 0, trefferquote: null };
const impactConfounded = wirkungsFortschritt.reduce((sum, w) => sum + Number(w.confounded_anzahl || 0), 0);
const impactOffen = wirkungsFortschritt.filter(w => String(w.status).startsWith('waiting_')).reduce((sum, w) => sum + Number(w.anzahl || 0), 0);

const zusatzHtml =
'  <h2>Orchestrator-Laeufe (letzter Lauf je Stufe)</h2>' +
'  <table><thead><tr><th>Workflow</th><th>Stufe</th><th>Status</th><th>Beendet</th><th>Letzter Erfolg</th><th>Dauer (ms)</th><th>Retries</th><th>Warnungen</th><th>Fehler</th></tr></thead>' +
'    <tbody>' + pipelineHtml + '</tbody></table>' +
'  <h2>Agentenlaeufe (letzter Lauf je Agent)</h2>' +
'  <table><thead><tr><th>Agent</th><th>Modell</th><th>Prompt-Version</th><th>Status</th><th>Gestartet</th><th>Konfidenz</th></tr></thead>' +
'    <tbody>' + agentHtml + '</tbody></table>' +
'  <h2>News-Verarbeitung &amp; Wirkungsanalyse</h2>' +
'  <div class="summary">' +
'    <div class="stat"><div class="label">Offene News-Retries</div><div class="value ' + (newsOffenRetry > 20 ? 'bad' : '') + '">' + newsOffenRetry + '</div></div>' +
'    <div class="stat"><div class="label">Fehlgeschlagene News</div><div class="value ' + (newsFailed > 0 ? 'bad' : '') + '">' + newsFailed + '</div></div>' +
'    <div class="stat"><div class="label">Offene Wirkungsanalysen</div><div class="value">' + impactOffen + '</div></div>' +
'    <div class="stat"><div class="label">Abgeschlossene D+1..D+20</div><div class="value">' + impactCompleted.anzahl + '</div></div>' +
'    <div class="stat"><div class="label">Trefferquote (sauber)</div><div class="value">' + (impactCompleted.trefferquote !== null && impactCompleted.trefferquote !== undefined ? impactCompleted.trefferquote + '%' : '—') + '</div></div>' +
'    <div class="stat"><div class="label">Konfundierte Faelle</div><div class="value">' + impactConfounded + '</div></div>' +
'  </div>' +
'  <h2>Lernagent</h2>' +
'  <div class="summary">' +
'    <div class="stat"><div class="label">Offene Lernvorschlaege</div><div class="value">' + (lernVorschlaege.offene_vorschlaege || 0) + '</div></div>' +
'    <div class="stat"><div class="label">Letzter Vorschlag am</div><div class="value" style="font-size:14px">' + esc(lernVorschlaege.letzter_vorschlag_am || '—') + '</div></div>' +
'  </div>';

// In den bestehenden HTML-String VOR dem schliessenden </body> einfuegen,
// ohne die restliche Original-Struktur zu veraendern.
const htmlErweitert = html.replace('</body>', zusatzHtml + '</body>');

return [{ json: { html: htmlErweitert } }];
"""

n_build_html = b.add({
    "parameters": {"jsCode": new_code},
    "name": "Baue Uebersicht",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2800, 500]
})
b.link(prev, n_build_html)

n_respond = b.add(dict(orig_nodes["Antwort mit HTML"], position=[-2600, 500]))
b.link(n_build_html, n_respond)

b.write_and_validate(OUT)
