import json, copy

SRC = r"C:\Users\olietz\AppData\Local\Temp\claude\c--Users-olietz-Downloads\37a0efa2-3efb-49cb-9543-b23e8f160afd\scratchpad\wf09b_live.json"
OUT = r"C:\Users\olietz\Documents\finanz\09c – Lernagent Handelsstrategien (Simulation).json"

with open(SRC, encoding="utf-8") as f:
    src = json.load(f)

by_name = {n["name"]: copy.deepcopy(n) for n in src["nodes"]}

# ---------------------------------------------------------------------------
# 1. Trigger ersetzen: 3 Trigger (Manuell/Schedule/ExecuteWorkflow) -> 1 Webhook
#    + Validierung + Laden des Quell-Laufs (fuer den Out-of-Sample-Datum-Vergleich).
# ---------------------------------------------------------------------------
webhook = {
    "id": "sim09c-webhook",
    "name": "Webhook GET (Ausloesen)",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 2,
    "position": [-2400, 320],
    "parameters": {"httpMethod": "GET", "path": "lernagent-simulation", "responseMode": "responseNode", "options": {}}
}

validiere = {
    "id": "sim09c-validiere",
    "name": "Validiere simulation_run_id",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2280, 320],
    "parameters": {
        "jsCode": (
            "const runId = Number((($json.query) || {}).simulation_run_id);\n"
            "if (!Number.isInteger(runId) || runId <= 0) {\n"
            "  return [{ json: { _error: 'Ungueltige oder fehlende simulation_run_id.' } }];\n"
            "}\n"
            "return [{ json: { simulation_run_id: runId, _error: null } }];\n"
        )
    }
}

db_quelllauf = {
    "id": "sim09c-db-quelllauf",
    "name": "DB: Quell-Lauf laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2160, 320],
    "alwaysOutputData": True,
    "credentials": {"postgres": {"id": "NWckNyl8ZfwVVJCd", "name": "Postgres account"}},
    "parameters": {
        "operation": "executeQuery",
        "query": (
            "=SELECT id, name, start_date, end_date, status FROM trading.backtest_runs "
            "WHERE id = {{ $json.simulation_run_id || 0 }} AND run_type = 'walk_forward' "
            "AND status IN ('completed','completed_with_warnings');"
        ),
        "options": {}
    }
}

pruefe_quelllauf = {
    "id": "sim09c-pruefe-quelllauf",
    "name": "Pruefe Quell-Lauf",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2040, 320],
    "parameters": {
        "jsCode": (
            "// Nur ein ABGESCHLOSSENER Walk-Forward-Lauf ist als Explorationsgrundlage sinnvoll -\n"
            "// ein laufender Lauf hat unvollstaendige Trades, ein Out-of-Sample-Lauf selbst als\n"
            "// Quelle zu nehmen waere methodisch zirkulaer (er soll ja etwas ANDERES bestaetigen).\n"
            "const ctx = $('Validiere simulation_run_id').all()[0].json;\n"
            "if (ctx._error) return [{ json: { _error: ctx._error } }];\n"
            "const rows = $input.all().map(i => i.json).filter(r => r && r.id !== undefined);\n"
            "if (rows.length === 0) {\n"
            "  return [{ json: { _error: 'Lauf ' + ctx.simulation_run_id + ' nicht gefunden oder nicht als abgeschlossener Walk-Forward-Lauf verfuegbar.' } }];\n"
            "}\n"
            "const run = rows[0];\n"
            "return [{ json: { simulation_run_id: run.id, source_run_name: run.name, source_end_date: run.end_date, _error: null } }];\n"
        )
    }
}

# ---------------------------------------------------------------------------
# 2. Datenquellen-Queries: paper_trades -> simulation_trades WHERE simulation_run_id = X.
#    ambiguous_execution / status='blocked' existieren auf simulation_trades nicht (siehe
#    sql/057) - bewusst als 0 dokumentiert statt erfunden, s.u.
# ---------------------------------------------------------------------------
AMBIGUOUS_HINWEIS = (
    "-- HINWEIS: simulation_trades fuehrt (anders als paper_trades) keine ambiguous_execution-\n"
    "-- Spalte und keinen status='blocked' (Portfoliorisiko-Ablehnung vor Ausfuehrung wird in\n"
    "-- WF17 nicht als eigene Zeile persistiert) - beide bewusst als 0 statt erfunden/NULL, damit\n"
    "-- nachgelagerte Gates (MAX_AMBIGUOUS_PCT) numerisch stabil bleiben. Siehe sql/057.\n"
)

gesamtkennzahlen = by_name["SQL: Gesamtkennzahlen (Trades)"]
gesamtkennzahlen["parameters"]["query"] = (
    "=" + AMBIGUOUS_HINWEIS +
    "SELECT\n"
    "  count(*) FILTER (WHERE status = 'closed') AS closed_trades,\n"
    "  0 AS blocked_trades,\n"
    "  0 AS ambiguous_trades,\n"
    "  0::numeric AS ambiguous_pct,\n"
    "  round(avg(realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS expectancy_r,\n"
    "  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS median_r,\n"
    "  round(100.0 * count(*) FILTER (WHERE status = 'closed' AND net_pnl > 0) / NULLIF(count(*) FILTER (WHERE status = 'closed'), 0), 1) AS win_rate_pct,\n"
    "  round(sum(net_pnl) FILTER (WHERE status = 'closed' AND net_pnl > 0)::numeric / NULLIF(ABS(sum(net_pnl) FILTER (WHERE status = 'closed' AND net_pnl < 0)), 0), 3) AS profit_factor,\n"
    "  round(avg(holding_period_days) FILTER (WHERE status = 'closed')::numeric, 2) AS avg_holding_days\n"
    "FROM trading.simulation_trades\n"
    "WHERE simulation_run_id = {{ $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id || 0 }};"
)

je_dimension = by_name["SQL: Je Dimension (Trades)"]
je_dimension["parameters"]["query"] = (
    "=" + AMBIGUOUS_HINWEIS +
    "SELECT 'strategy' AS dimension, strategy AS value, NULL::text AS sub_value,\n"
    "  count(*) FILTER (WHERE status = 'closed') AS sample_size,\n"
    "  round(avg(realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS expectancy_r,\n"
    "  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS median_r,\n"
    "  round(100.0 * count(*) FILTER (WHERE status = 'closed' AND net_pnl > 0) / NULLIF(count(*) FILTER (WHERE status = 'closed'), 0), 1) AS win_rate_pct,\n"
    "  round(sum(net_pnl) FILTER (WHERE status = 'closed' AND net_pnl > 0)::numeric / NULLIF(ABS(sum(net_pnl) FILTER (WHERE status = 'closed' AND net_pnl < 0)), 0), 3) AS profit_factor,\n"
    "  count(DISTINCT ticker) FILTER (WHERE status = 'closed') AS distinct_tickers,\n"
    "  0::numeric AS ambiguous_pct\n"
    "FROM trading.simulation_trades\n"
    "WHERE simulation_run_id = {{ $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id || 0 }}\n"
    "GROUP BY strategy\n"
    "\n"
    "UNION ALL\n"
    "\n"
    "SELECT 'strategy_regime' AS dimension, strategy AS value, market_regime_at_entry AS sub_value,\n"
    "  count(*) FILTER (WHERE status = 'closed') AS sample_size,\n"
    "  round(avg(realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS expectancy_r,\n"
    "  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS median_r,\n"
    "  round(100.0 * count(*) FILTER (WHERE status = 'closed' AND net_pnl > 0) / NULLIF(count(*) FILTER (WHERE status = 'closed'), 0), 1) AS win_rate_pct,\n"
    "  round(sum(net_pnl) FILTER (WHERE status = 'closed' AND net_pnl > 0)::numeric / NULLIF(ABS(sum(net_pnl) FILTER (WHERE status = 'closed' AND net_pnl < 0)), 0), 3) AS profit_factor,\n"
    "  count(DISTINCT ticker) FILTER (WHERE status = 'closed') AS distinct_tickers,\n"
    "  0::numeric AS ambiguous_pct\n"
    "FROM trading.simulation_trades\n"
    "WHERE simulation_run_id = {{ $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id || 0 }} AND market_regime_at_entry IS NOT NULL\n"
    "GROUP BY strategy, market_regime_at_entry\n"
    "\n"
    "UNION ALL\n"
    "\n"
    "SELECT 'strategy_ticker' AS dimension, strategy AS value, ticker AS sub_value,\n"
    "  count(*) FILTER (WHERE status = 'closed') AS sample_size,\n"
    "  round(avg(realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS expectancy_r,\n"
    "  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY realized_r_multiple) FILTER (WHERE status = 'closed')::numeric, 3) AS median_r,\n"
    "  round(100.0 * count(*) FILTER (WHERE status = 'closed' AND net_pnl > 0) / NULLIF(count(*) FILTER (WHERE status = 'closed'), 0), 1) AS win_rate_pct,\n"
    "  NULL::numeric AS profit_factor,\n"
    "  1 AS distinct_tickers,\n"
    "  0::numeric AS ambiguous_pct\n"
    "FROM trading.simulation_trades\n"
    "WHERE simulation_run_id = {{ $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id || 0 }}\n"
    "GROUP BY strategy, ticker\n"
    "\n"
    "ORDER BY dimension, value;"
)

oos_backtests = by_name["DB: OOS-Backtests laden"]
oos_backtests["parameters"]["query"] = (
    "SELECT backtest_id, strategy_filter, rule_version, configuration_version, start_date, end_date "
    "FROM trading.backtest_runs "
    "WHERE run_type = 'out_of_sample' AND status IN ('completed','completed_with_warnings');"
)

# ---------------------------------------------------------------------------
# 3. Klassifizierung: OOS-Gate verschaerft (muss NACH dem Explorationszeitraum liegen -
#    echtes Train->Confirm statt reiner Existenzpruefung, sonst Ueberanpassung an dieselben
#    Daten, die den Vorschlag erzeugt haben).
# ---------------------------------------------------------------------------
klass = by_name["Mindestfallzahlen klassifizieren (Trades)"]
old_gate = (
    "const oosRuns = $('DB: OOS-Backtests laden').all().map(i => i.json);\n"
    "const oosConfirmedStrategies = new Set(oosRuns.filter(r => r.strategy_filter).map(r => r.strategy_filter));\n"
    "function oosConfirmedFor(strategy) { return oosConfirmedStrategies.has(strategy); }"
)
new_gate = (
    "// Verschaerft gegenueber 09b (Live-Variante): bei simulationsbasierten Vorschlaegen muss der\n"
    "// Out-of-Sample-Lauf ZEITLICH NACH dem Explorationszeitraum liegen (start_date > Quelllauf-\n"
    "// end_date) - eine blosse Existenzpruefung wuerde erlauben, denselben oder einen frueheren\n"
    "// Zeitraum als \"Bestaetigung\" zu missbrauchen, was keine echte Out-of-Sample-Validierung waere.\n"
    "const sourceRun = $('Pruefe Quell-Lauf').all()[0].json;\n"
    "const oosRuns = $('DB: OOS-Backtests laden').all().map(i => i.json);\n"
    "const oosConfirmedStrategies = new Set(\n"
    "  oosRuns.filter(r => r.strategy_filter && r.start_date && sourceRun.source_end_date && r.start_date > sourceRun.source_end_date)\n"
    "    .map(r => r.strategy_filter)\n"
    ");\n"
    "function oosConfirmedFor(strategy) { return oosConfirmedStrategies.has(strategy); }"
)
assert old_gate in klass["parameters"]["jsCode"], "OOS-Gate-Text nicht gefunden - 09b hat sich vermutlich geaendert"
klass["parameters"]["jsCode"] = klass["parameters"]["jsCode"].replace(old_gate, new_gate)

# ---------------------------------------------------------------------------
# 4. Vorschlag speichern: data_source/source_run_id ergaenzen (sql/061).
# ---------------------------------------------------------------------------
speichern = by_name["Vorschlag speichern (SQL bauen, Trades)"]
old_sql_head = (
    "const sql = `INSERT INTO trading.learning_rule_proposals\n"
    "  (proposal_type, target_type, target_value, current_value, proposed_value, sample_size, metric_name, metric_value, reason, confidence_level, status, metadata_json, rule_version, configuration_version, data_schema_version, learning_model_version)\n"
    "SELECT ${pgStr(j.proposal_type)}, ${pgStr(j.target_type)}, ${pgStr(j.target_value)}, ${pgStr(j.current_value)}, ${pgStr(j.proposed_value)},\n"
    "          ${pgNum(j.sample_size)}, ${pgStr(j.metric_name)}, ${pgNum(j.metric_value)}, ${pgStr(j.reason)}, ${pgStr(j.confidence_level)},\n"
    "          'proposed', ${pgJson(j.evidence || {})},\n"
    "          ${pgStr('welle3-lernagent-trades-rules-v1')}, ${pgStr('welle3-lernagent-trades-config-v1')}, ${pgStr('sql-001-v1')}, ${pgStr('09b-handelsstrategien-v1')}\n"
    "WHERE NOT EXISTS ("
)
new_sql_head = (
    "const sourceRunId = $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id;\n"
    "const sql = `INSERT INTO trading.learning_rule_proposals\n"
    "  (proposal_type, target_type, target_value, current_value, proposed_value, sample_size, metric_name, metric_value, reason, confidence_level, status, metadata_json, rule_version, configuration_version, data_schema_version, learning_model_version, data_source, source_run_id)\n"
    "SELECT ${pgStr(j.proposal_type)}, ${pgStr(j.target_type)}, ${pgStr(j.target_value)}, ${pgStr(j.current_value)}, ${pgStr(j.proposed_value)},\n"
    "          ${pgNum(j.sample_size)}, ${pgStr(j.metric_name)}, ${pgNum(j.metric_value)}, ${pgStr(j.reason)}, ${pgStr(j.confidence_level)},\n"
    "          'proposed', ${pgJson(j.evidence || {})},\n"
    "          ${pgStr('welle3-lernagent-trades-rules-v1')}, ${pgStr('welle3-lernagent-trades-config-v1')}, ${pgStr('sql-001-v1')}, ${pgStr('09c-handelsstrategien-simulation-v1')},\n"
    "          'simulation', ${pgNum(sourceRunId)}\n"
    "WHERE NOT EXISTS ("
)
assert old_sql_head in speichern["parameters"]["jsCode"], "Vorschlag-INSERT-Text nicht gefunden"
speichern["parameters"]["jsCode"] = speichern["parameters"]["jsCode"].replace(old_sql_head, new_sql_head)

# ---------------------------------------------------------------------------
# 5. Agentenlauf-Protokoll: eigener agent_name/run_id-Praefix.
# ---------------------------------------------------------------------------
protokoll = by_name["Agentenlauf protokollieren (Trades, SQL bauen)"]
protokoll["parameters"]["jsCode"] = protokoll["parameters"]["jsCode"].replace(
    "'lernagent-handel-' + getBusinessDate()", "'lernagent-handel-sim-' + getBusinessDate() + '-' + $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id"
).replace(
    "'lernagent-handelsstrategien'", "'lernagent-handelsstrategien-simulation'"
)

# ---------------------------------------------------------------------------
# 6. Lernbericht-Text: klarstellen, dass es sich um eine Simulation handelt.
# ---------------------------------------------------------------------------
bericht = by_name["Lernbericht aufbereiten (Trades)"]
bericht["parameters"]["jsCode"] = bericht["parameters"]["jsCode"].replace(
    "'\U0001F4C8 Lernagent Handelsstrategien \u2013 Stand ' + j.analysis_to",
    "'\U0001F4C8 Lernagent Handelsstrategien (SIMULATION, Lauf ' + $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id + ') \u2013 Stand ' + j.analysis_to"
).replace(
    "'Geschlossene Paper Trades: '", "'Geschlossene Simulations-Trades: '"
)

# Matrix-Send defensiv absichern (09b hat kein onError - fehlender Credential darf den
# eigentlichen Speichervorgang, der davor bereits gelaufen ist, nicht als Gesamtfehler zeigen).
matrix = by_name["Matrix: Lernbericht senden (Trades)"]
matrix["onError"] = "continueRegularOutput"
matrix["alwaysOutputData"] = True

# ---------------------------------------------------------------------------
# 7. KI-Node durch Platzhalter ersetzen (Absturzrisiko frisch importierter LangChain-Nodes,
#    gleiches Muster wie Workflow 16b) - vollstaendiger Prompt bleibt als Kommentar erhalten,
#    damit ein spaeterer manueller Ersatz (wie bei 16b) direkt den richtigen Text hat.
# ---------------------------------------------------------------------------
ki_placeholder = {
    "id": "sim09c-ki-platzhalter",
    "name": "KI: Lernbericht interpretieren (Trades) [PLATZHALTER]",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": list(by_name["KI: Lernbericht interpretieren (Trades)"]["position"]),
    "parameters": {
        "jsCode": (
            "// PLATZHALTER statt echtem KI-Node (Absturzrisiko frisch importierter LangChain-\n"
            "// Nodes ueber die API, gleiches Muster wie Workflow 16b - siehe dortigen Commit-\n"
            "// Kommentar). Der vollstaendige Prompt liegt in $json.systemPrompt/$json.userPrompt\n"
            "// (von 'Baue Lernagent-Prompt (Trades)' unveraendert uebernommen).\n"
            "//\n"
            "// SPAETER MANUELL ERSETZEN: echten 'Message a model'-Node (n8n-nodes-langchain.openAi,\n"
            "// gleiche Konfiguration wie im Live-Workflow 09b, Credential 'OpenAI account') einfuegen,\n"
            "// System-Message = {{ $json.systemPrompt }}, User-Message = {{ $json.userPrompt }}.\n"
            "//\n"
            "// Bis dahin: konservativer deterministischer Platzhalter-Entscheid - jeder Kandidat mit\n"
            "// candidate_proposal wird MIT einer generischen Begruendung uebernommen (include=true),\n"
            "// NICHTS wird erfunden/bewertet, was nicht schon deterministisch vorlag (Grundregel 9\n"
            "// bleibt gewahrt - der Platzhalter ersetzt nur die redaktionelle Formulierung/das\n"
            "// fachliche Ermessen der KI, nicht die Zahlen-Gates selbst).\n"
            "const d = $json;\n"
            "const decisions = (d.findings || []).filter(f => f.proposal_eligible).map(f => ({\n"
            "  dimension: f.dimension, value: f.value, sub_value: f.sub_value, include: true,\n"
            "  reason: '[Platzhalter, keine KI-Bewertung] Automatisch uebernommen, da alle deterministischen Gates (Fallzahl/OOS/Konzentration/Erwartungswert) erfuellt sind.'\n"
            "}));\n"
            "return { json: { output: [{ type: 'message', content: [{ type: 'output_text', text: JSON.stringify({ decisions }) }] }] } };\n"
        )
    }
}

# ---------------------------------------------------------------------------
# 8. Abschluss-Antwort fuer den Webhook-Aufrufer (Steuerzentrale-Button).
# ---------------------------------------------------------------------------
antwort = {
    "id": "sim09c-antwort",
    "name": "Baue Antwort (JSON)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [200, 400],
    "parameters": {
        "jsCode": (
            "const j = $('Lernbericht aufbereiten (Trades)').all()[0].json;\n"
            "const runId = $('Pruefe Quell-Lauf').all()[0].json.simulation_run_id;\n"
            "return { json: { ok: true, simulation_run_id: runId, proposals_count: (j.proposals_final || []).length, report_text: j.report_text } };\n"
        )
    }
}
respond = {
    "id": "sim09c-respond",
    "name": "Antwort senden",
    "type": "n8n-nodes-base.respondToWebhook",
    "typeVersion": 1.1,
    "position": [400, 400],
    "parameters": {"respondWith": "json", "responseBody": "={{ $json }}", "options": {}}
}

fehler_antwort = {
    "id": "sim09c-fehler-antwort",
    "name": "Baue Fehler-Antwort (JSON)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1920, 480],
    "parameters": {"jsCode": "return { json: { ok: false, error: $json._error } };"}
}
respond_fehler = {
    "id": "sim09c-respond-fehler",
    "name": "Fehler-Antwort senden",
    "type": "n8n-nodes-base.respondToWebhook",
    "typeVersion": 1.1,
    "position": [-1800, 480],
    "parameters": {"respondWith": "json", "responseBody": "={{ $json }}", "options": {}}
}
if_fehler = {
    "id": "sim09c-if-fehler",
    "name": "IF: Quell-Lauf ungueltig?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [-1920, 320],
    "parameters": {
        "conditions": {
            "conditions": [{"id": "c1", "leftValue": "={{ !!$json._error }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
            "combinator": "and", "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1}
        },
        "options": {}
    }
}

# ---------------------------------------------------------------------------
# Zusammenbau
# ---------------------------------------------------------------------------
keep_names = [
    "DB: Lern-Konfiguration laden", "DB: OOS-Backtests laden", "SQL: Gesamtkennzahlen (Trades)",
    "SQL: Je Dimension (Trades)", "Mindestfallzahlen klassifizieren (Trades)",
    "Baue Lernagent-Prompt (Trades)", "Vorschlaege gegen Fallzahlen validieren (Trades)",
    "Vorschlaege auffaechern (Trades)", "Vorschlag speichern (SQL bauen, Trades)",
    "Vorschlag speichern (ausfuehren, Trades)", "Agentenlauf protokollieren (Trades, SQL bauen)",
    "Agentenlauf protokollieren (Trades, ausfuehren)", "Lernbericht aufbereiten (Trades)",
    "Matrix: Lernbericht senden (Trades)", "Fehlerpruefung (Vorschlag speichern, Trades)"
]
nodes = [webhook, validiere, db_quelllauf, if_fehler, fehler_antwort, respond_fehler, pruefe_quelllauf]
nodes += [by_name[n] for n in keep_names]
nodes += [ki_placeholder, antwort, respond]

connections = {
    "Webhook GET (Ausloesen)": {"main": [[{"node": "Validiere simulation_run_id", "type": "main", "index": 0}]]},
    "Validiere simulation_run_id": {"main": [[{"node": "DB: Quell-Lauf laden", "type": "main", "index": 0}]]},
    "DB: Quell-Lauf laden": {"main": [[{"node": "Pruefe Quell-Lauf", "type": "main", "index": 0}]]},
    "Pruefe Quell-Lauf": {"main": [[{"node": "IF: Quell-Lauf ungueltig?", "type": "main", "index": 0}]]},
    "IF: Quell-Lauf ungueltig?": {"main": [
        [{"node": "Baue Fehler-Antwort (JSON)", "type": "main", "index": 0}],
        [{"node": "DB: Lern-Konfiguration laden", "type": "main", "index": 0}]
    ]},
    "Baue Fehler-Antwort (JSON)": {"main": [[{"node": "Fehler-Antwort senden", "type": "main", "index": 0}]]},
    "DB: Lern-Konfiguration laden": {"main": [[{"node": "DB: OOS-Backtests laden", "type": "main", "index": 0}]]},
    "DB: OOS-Backtests laden": {"main": [[{"node": "SQL: Gesamtkennzahlen (Trades)", "type": "main", "index": 0}]]},
    "SQL: Gesamtkennzahlen (Trades)": {"main": [[{"node": "SQL: Je Dimension (Trades)", "type": "main", "index": 0}]]},
    "SQL: Je Dimension (Trades)": {"main": [[{"node": "Mindestfallzahlen klassifizieren (Trades)", "type": "main", "index": 0}]]},
    "Mindestfallzahlen klassifizieren (Trades)": {"main": [[{"node": "Baue Lernagent-Prompt (Trades)", "type": "main", "index": 0}]]},
    "Baue Lernagent-Prompt (Trades)": {"main": [[{"node": "KI: Lernbericht interpretieren (Trades) [PLATZHALTER]", "type": "main", "index": 0}]]},
    "KI: Lernbericht interpretieren (Trades) [PLATZHALTER]": {"main": [[{"node": "Vorschlaege gegen Fallzahlen validieren (Trades)", "type": "main", "index": 0}]]},
    "Vorschlaege gegen Fallzahlen validieren (Trades)": {"main": [[
        {"node": "Vorschlaege auffaechern (Trades)", "type": "main", "index": 0},
        {"node": "Agentenlauf protokollieren (Trades, SQL bauen)", "type": "main", "index": 0}
    ]]},
    "Vorschlaege auffaechern (Trades)": {"main": [[{"node": "Vorschlag speichern (SQL bauen, Trades)", "type": "main", "index": 0}]]},
    "Vorschlag speichern (SQL bauen, Trades)": {"main": [[{"node": "Vorschlag speichern (ausfuehren, Trades)", "type": "main", "index": 0}]]},
    "Vorschlag speichern (ausfuehren, Trades)": {"main": [[{"node": "Fehlerpruefung (Vorschlag speichern, Trades)", "type": "main", "index": 0}]]},
    "Agentenlauf protokollieren (Trades, SQL bauen)": {"main": [[{"node": "Agentenlauf protokollieren (Trades, ausfuehren)", "type": "main", "index": 0}]]},
    "Agentenlauf protokollieren (Trades, ausfuehren)": {"main": [[{"node": "Lernbericht aufbereiten (Trades)", "type": "main", "index": 0}]]},
    "Lernbericht aufbereiten (Trades)": {"main": [[
        {"node": "Matrix: Lernbericht senden (Trades)", "type": "main", "index": 0},
        {"node": "Baue Antwort (JSON)", "type": "main", "index": 0}
    ]]},
    "Baue Antwort (JSON)": {"main": [[{"node": "Antwort senden", "type": "main", "index": 0}]]},
}

workflow = {
    "name": "09c – Lernagent Handelsstrategien (Simulation)",
    "nodes": nodes,
    "connections": connections,
    "pinData": {},
    "settings": {"executionOrder": "v1"}
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)
print("written", OUT, "-", len(nodes), "nodes")
