import json, os

OUT = r"C:\Users\olietz\Documents\finanz\00 – Tagesabschluss-Orchestrator.json"

WF_02B = "EKxWwrP4SPLVUpNB"
WF_02 = "W6Mko3fAJEyJudoD"
WF_06_V1 = "zmedV73DsUArNquX"
WF_10 = "PLACEHOLDER_10_REPORT_PRUEF_AGENT"
WF_05_V1 = "7cbWfj6qlx0YmvIS"

PG_CRED = {"id": "PLACEHOLDER_POSTGRES_CRED", "name": "Postgres – Trading (TODO Credential zuweisen)"}
MATRIX_CRED = {"id": "od1pN1F5wy2irSDs", "name": "Header Auth account"}
MATRIX_ROOM = "!uDpcMuCWUvcwXMKJAP:matrix.org"

GET_BUSINESS_DATE_JS = """function getBusinessDate(date = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Berlin',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}
function getBerlinTimeParts(date = new Date()) {
  const fmt = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Berlin',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }).formatToParts(date);
  const p = Object.fromEntries(fmt.map(x => [x.type, x.value]));
  return `${p.hour}${p.minute}${p.second}`;
}"""

# Wiederverwendbarer SQL-Escaping-Helfer fuer alle Code-Nodes, die eine
# executeQuery-SQL-Zeichenkette fuer den Postgres-Node bauen. Bewusst NUR
# executeQuery verwendet (nicht insert/update-Operationen des Postgres-Nodes),
# da deren genaues Parameter-Schema in dieser n8n-Version nicht durch ein
# lokales Beispiel bestaetigt ist -- executeQuery (reiner SQL-String) ist
# die einzige Operation, deren Schema durch den bereits gebauten
# Migrations-Runner-Workflow real verifiziert ist.
PG_HELPERS_JS = """function pgStr(v) { return v === null || v === undefined ? 'NULL' : `'` + String(v).replace(/'/g, `''`) + `'`; }
function pgNum(v) { return v === null || v === undefined || v === '' || isNaN(Number(v)) ? 'NULL' : Number(v); }
function pgBool(v) { return v === null || v === undefined ? 'NULL' : (v ? 'TRUE' : 'FALSE'); }
function pgJson(v) { return `'` + JSON.stringify(v === undefined ? null : v).replace(/'/g, `''`) + `'::jsonb`; }"""

nodes = []
conns = {}

def add(node):
    nodes.append(node)
    return node["name"]

def link(src, dst, src_index=0, dst_index=0):
    conns.setdefault(src, {"main": []})
    while len(conns[src]["main"]) <= src_index:
        conns[src]["main"].append([])
    conns[src]["main"][src_index].append({"node": dst, "type": "main", "index": dst_index})

def pg_exec_pair(id_prefix, label, position, sql_js_body):
    """Baut ein (Code: SQL bauen) -> (Postgres: executeQuery) Nodepaar.
    Gibt (entry_node_name, exit_node_name) zurueck."""
    code_name = f"{label} (SQL bauen)"
    pg_name = f"{label} (ausfuehren)"
    add({
        "parameters": {"jsCode": PG_HELPERS_JS + "\n\n" + sql_js_body},
        "id": f"{id_prefix}a",
        "name": code_name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [position[0], position[1]]
    })
    add({
        "parameters": {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
        "id": f"{id_prefix}b",
        "name": pg_name,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": [position[0] + 176, position[1]],
        "onError": "continueRegularOutput",
        "credentials": {"postgres": PG_CRED}
    })
    link(code_name, pg_name)
    return code_name, pg_name

def pipeline_run_log(id_prefix, label, position, status_expr, stage_name, workflow_name, extra_json_expr="{}"):
    """SQL-Body fuer einen INSERT in trading.pipeline_runs."""
    body = f"""const runId = $('Run-ID erzeugen').item.json.run_id;
const startedAt = $('Run-ID erzeugen').item.json.started_at;
const status = {status_expr};
const errorMessage = {status_expr} === 'failed' ? String(($json.error && ($json.error.message || $json.error)) || '') : '';
const metadata = {extra_json_expr};

const sql = `INSERT INTO trading.pipeline_runs
  (run_id, workflow_name, stage_name, status, started_at, finished_at, error_message, metadata_json)
  VALUES (${{pgStr(runId)}}, ${{pgStr('{workflow_name}')}}, ${{pgStr('{stage_name}')}}, ${{pgStr(status)}},
          ${{pgStr(startedAt)}}, ${{pgStr(new Date().toISOString())}}, ${{pgStr(errorMessage)}}, ${{pgJson(metadata)}});`;

return {{ json: {{ ...$json, sql }} }};
"""
    return pg_exec_pair(id_prefix, label, position, body)

# ---------------------------------------------------------------------------
# 1. Trigger
# ---------------------------------------------------------------------------
n_trigger = add({
    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 50 17 * * 1-5"}]}},
    "id": "00000000-0000-4000-8000-000000000001",
    "name": "Trigger: Tagesabschluss (17:50 Werktage)",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.1,
    "position": [-2400, 0]
})

# ---------------------------------------------------------------------------
# 2. Run-ID erzeugen
# ---------------------------------------------------------------------------
n_runid = add({
    "parameters": {
        "jsCode": GET_BUSINESS_DATE_JS + """

function randHex(n) {
  let s = '';
  for (let i = 0; i < n; i++) s += Math.floor(Math.random() * 16).toString(16);
  return s;
}

const businessDate = getBusinessDate();
const timePart = getBerlinTimeParts();
const runId = `daily-${businessDate}-${timePart}-${randHex(6)}`;
const startedAt = new Date().toISOString();

return { json: {
  run_id: runId,
  business_date: businessDate,
  started_at: startedAt,
  DRY_RUN: false
} };
"""
    },
    "id": "00000000-0000-4000-8000-000000000002",
    "name": "Run-ID erzeugen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2176, 0]
})
link(n_trigger, n_runid)

# ---------------------------------------------------------------------------
# 3. Marktumfeld (02b) ausfuehren + pruefen
# ---------------------------------------------------------------------------
n_ex_marktumfeld = add({
    "parameters": {
        "source": "database",
        "workflowId": {"__rl": True, "value": WF_02B, "mode": "list", "cachedResultName": "02b – Marktumfeld täglich"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {"run_id": "={{ $json.run_id }}"}},
        "options": {"waitForSubWorkflow": True}
    },
    "id": "00000000-0000-4000-8000-000000000003",
    "name": "Ausfuehren: Marktumfeld (02b)",
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [-1952, 0],
    "onError": "continueErrorOutput"
})
link(n_runid, n_ex_marktumfeld)

log_markt_in, log_markt_out = pipeline_run_log(
    "00000004-0000-4000-8000-00000000000", "Log Marktumfeld", [-1728, -80],
    "$json.error ? 'failed' : 'success'", "marktumfeld", "02b – Marktumfeld täglich"
)
link(n_ex_marktumfeld, log_markt_in, src_index=0)
link(n_ex_marktumfeld, log_markt_in, src_index=1)

n_if_markt = add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ $('Ausfuehren: Marktumfeld (02b)').item.json.error }}",
                "rightValue": "",
                "operator": {"type": "string", "operation": "empty", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "id": "00000000-0000-4000-8000-000000000005",
    "name": "IF: Marktumfeld ok?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-1504, 0]
})
link(log_markt_out, n_if_markt)

# ---------------------------------------------------------------------------
# 4. Technische Signale (02) ausfuehren + pruefen
# ---------------------------------------------------------------------------
n_ex_signale = add({
    "parameters": {
        "source": "database",
        "workflowId": {"__rl": True, "value": WF_02, "mode": "list", "cachedResultName": "02 – Technische Signale täglich"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {"run_id": "={{ $('Run-ID erzeugen').item.json.run_id }}"}},
        "options": {"waitForSubWorkflow": True}
    },
    "id": "00000000-0000-4000-8000-000000000006",
    "name": "Ausfuehren: Technische Signale (02)",
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [-1280, 0],
    "onError": "continueErrorOutput"
})
link(n_if_markt, n_ex_signale, src_index=0)

log_signale_in, log_signale_out = pipeline_run_log(
    "00000007-0000-4000-8000-00000000000", "Log Technische Signale", [-1056, -80],
    "$json.error ? 'failed' : 'success'", "technische_signale", "02 – Technische Signale täglich"
)
link(n_ex_signale, log_signale_in, src_index=0)
link(n_ex_signale, log_signale_in, src_index=1)

n_if_signale = add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ $('Ausfuehren: Technische Signale (02)').item.json.error }}",
                "rightValue": "",
                "operator": {"type": "string", "operation": "empty", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "id": "00000000-0000-4000-8000-000000000008",
    "name": "IF: Technische Signale ok?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-832, 0]
})
link(log_signale_out, n_if_signale)

# ---------------------------------------------------------------------------
# 5. Datenqualitaetspruefung
# ---------------------------------------------------------------------------
n_dq_signale = add({
    "parameters": {
        "operation": "get",
        "dataTableId": {"__rl": True, "value": "GDMAKrvQovPcBItA", "mode": "list", "cachedResultName": "stock_technical_signals"},
        "filters": {"conditions": [{"keyName": "datum", "keyValue": "={{ $('Run-ID erzeugen').item.json.business_date }}"}]},
        "returnAll": True
    },
    "id": "00000000-0000-4000-8000-000000000009",
    "name": "DB: Heutige Signale zaehlen",
    "type": "n8n-nodes-base.dataTable",
    "typeVersion": 1,
    "position": [-608, -80],
    "onError": "continueRegularOutput"
})
link(n_if_signale, n_dq_signale, src_index=0)

n_dq_news = add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT id FROM trading.news_items WHERE (created_at AT TIME ZONE 'Europe/Berlin')::date = '{{ $('Run-ID erzeugen').item.json.business_date }}'::date;",
        "options": {}
    },
    "id": "0000000a-0000-4000-8000-00000000000a",
    "name": "DB: Heutige News zaehlen",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-608, 80],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
link(n_if_signale, n_dq_news, src_index=0)

n_dq_merge = add({
    "parameters": {"mode": "combine", "combineBy": "combineAll", "options": {}},
    "id": "0000000b-0000-4000-8000-00000000000b",
    "name": "Merge: Datenqualitaet",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3.1,
    "position": [-384, 0]
})
link(n_dq_signale, n_dq_merge, dst_index=0)
link(n_dq_news, n_dq_merge, dst_index=1)

n_dq_check = add({
    "parameters": {
        "jsCode": """// Datenqualitaetspruefung: mindestens 1 aktuelles technisches Signal muss
// vorliegen, sonst gilt der Geschaeftstag als unvollstaendig (harte Abbruchregel).
// Fehlende News-Aktivitaet ist nur eine Warnung (an ruhigen Tagen kann News=0
// legitim sein), kein harter Abbruch.
const signale = $('DB: Heutige Signale zaehlen').all();
const news = $('DB: Heutige News zaehlen').all();

const signaleOk = signale.length > 0;
const newsOk = news.length > 0;

return { json: {
  run_id: $('Run-ID erzeugen').item.json.run_id,
  business_date: $('Run-ID erzeugen').item.json.business_date,
  signale_count: signale.length,
  news_count: news.length,
  signale_ok: signaleOk,
  news_ok: newsOk,
  datenqualitaet_ok: signaleOk
} };
"""
    },
    "id": "0000000c-0000-4000-8000-00000000000c",
    "name": "Pruefe Datenqualitaet",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-160, 0]
})
link(n_dq_merge, n_dq_check)

log_dq_in, log_dq_out = pipeline_run_log(
    "0000000d-0000-4000-8000-00000000000", "Log Datenqualitaet", [64, 0],
    "$json.datenqualitaet_ok ? 'success' : 'failed'", "datenqualitaet", "00 – Tagesabschluss-Orchestrator",
    extra_json_expr="{ signale_count: $json.signale_count, news_count: $json.news_count, news_ok: $json.news_ok }"
)
link(n_dq_check, log_dq_in)

n_if_dq = add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ $('Pruefe Datenqualitaet').item.json.datenqualitaet_ok }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "id": "0000000e-0000-4000-8000-00000000000e",
    "name": "IF: Datenqualitaet ok?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [288, 0]
})
link(log_dq_out, n_if_dq)

# ---------------------------------------------------------------------------
# 6. Empfehlungswatchlist (06) ausfuehren
# ---------------------------------------------------------------------------
n_ex_empf = add({
    "parameters": {
        "source": "database",
        "workflowId": {"__rl": True, "value": WF_06_V1, "mode": "list", "cachedResultName": "06 – Empfehlungswatchlist"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {
            "run_id": "={{ $('Run-ID erzeugen').item.json.run_id }}",
            "DRY_RUN": "={{ $('Run-ID erzeugen').item.json.DRY_RUN }}"
        }},
        "options": {"waitForSubWorkflow": True}
    },
    "id": "0000000f-0000-4000-8000-00000000000f",
    "name": "Ausfuehren: Empfehlungswatchlist (06)",
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [512, 0],
    "onError": "continueErrorOutput"
})
link(n_if_dq, n_ex_empf, src_index=0)

log_empf_in, log_empf_out = pipeline_run_log(
    "00000010-0000-4000-8000-000000000", "Log Empfehlungswatchlist", [736, -80],
    "$json.error ? 'failed' : 'success'", "empfehlungswatchlist", "06 – Empfehlungswatchlist"
)
link(n_ex_empf, log_empf_in, src_index=0)
link(n_ex_empf, log_empf_in, src_index=1)

# ---------------------------------------------------------------------------
# 7. Report- und Pruefagent (10) ausfuehren
# ---------------------------------------------------------------------------
n_ex_report = add({
    "parameters": {
        "source": "database",
        "workflowId": {"__rl": True, "value": WF_10, "mode": "list", "cachedResultName": "10 – Report- und Prüfagent (TODO: id nach Import korrigieren)"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {
            "run_id": "={{ $('Run-ID erzeugen').item.json.run_id }}",
            "business_date": "={{ $('Run-ID erzeugen').item.json.business_date }}"
        }},
        "options": {"waitForSubWorkflow": True}
    },
    "id": "00000011-0000-4000-8000-000000000011",
    "name": "Ausfuehren: Report- und Pruefagent (10)",
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [960, 0],
    "onError": "continueErrorOutput"
})
link(log_empf_out, n_ex_report)

log_report_in, log_report_out = pipeline_run_log(
    "00000012-0000-4000-8000-000000000", "Log Report-Pruef-Agent", [1184, -80],
    "$json.error ? 'failed' : ($json.approved ? 'success' : 'warning')", "report_pruef_agent", "10 – Report- und Prüfagent"
)
link(n_ex_report, log_report_in, src_index=0)
link(n_ex_report, log_report_in, src_index=1)

n_if_freigabe = add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ $('Ausfuehren: Report- und Pruefagent (10)').item.json.approved }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "id": "00000013-0000-4000-8000-000000000013",
    "name": "IF: Freigegeben?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [1408, 0]
})
link(log_report_out, n_if_freigabe)

# ---------------------------------------------------------------------------
# 8a. Freigegeben -> Versand (05)
# ---------------------------------------------------------------------------
n_ex_versand = add({
    "parameters": {
        "source": "database",
        "workflowId": {"__rl": True, "value": WF_05_V1, "mode": "list", "cachedResultName": "05 – Tagesreport"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {
            "run_id": "={{ $('Run-ID erzeugen').item.json.run_id }}",
            "report_markdown": "={{ $('Ausfuehren: Report- und Pruefagent (10)').item.json.report_markdown }}",
            "approved": True,
            "DRY_RUN": "={{ $('Run-ID erzeugen').item.json.DRY_RUN }}"
        }},
        "options": {"waitForSubWorkflow": True}
    },
    "id": "00000014-0000-4000-8000-000000000014",
    "name": "Ausfuehren: Tagesreport-Versand (05)",
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [1632, -120],
    "onError": "continueErrorOutput"
})
link(n_if_freigabe, n_ex_versand, src_index=0)

log_versand_in, log_versand_out = pipeline_run_log(
    "00000015-0000-4000-8000-000000000", "Log Versand", [1856, -120],
    "$json.error ? 'failed' : 'success'", "tagesreport_versand", "05 – Tagesreport"
)
link(n_ex_versand, log_versand_in, src_index=0)
link(n_ex_versand, log_versand_in, src_index=1)

n_finish_success = add({
    "parameters": {"jsCode": "return { json: { ...$json, final_status: 'success' } };"},
    "id": "00000016-0000-4000-8000-000000000016",
    "name": "Lauf abschliessen (Erfolg)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [2080, -120]
})
link(log_versand_out, n_finish_success)

# ---------------------------------------------------------------------------
# 8b. Nicht freigegeben / Datenqualitaet fehlgeschlagen / Marktumfeld|Signale
#     fehlgeschlagen -> technische Matrix-Warnung statt Normalversand
# ---------------------------------------------------------------------------
n_build_warning = add({
    "parameters": {
        "jsCode": """const runId = $('Run-ID erzeugen').item.json.run_id;
const businessDate = $('Run-ID erzeugen').item.json.business_date;

let gruende = [];
try { if ($('Ausfuehren: Marktumfeld (02b)').item.json.error) gruende.push('Marktumfeld fehlgeschlagen: ' + $('Ausfuehren: Marktumfeld (02b)').item.json.error); } catch(e) {}
try { if ($('Ausfuehren: Technische Signale (02)').item.json.error) gruende.push('Technische Signale fehlgeschlagen: ' + $('Ausfuehren: Technische Signale (02)').item.json.error); } catch(e) {}
try { if ($('Pruefe Datenqualitaet').item.json.datenqualitaet_ok === false) gruende.push('Datenqualitaet unzureichend (Signale: ' + $('Pruefe Datenqualitaet').item.json.signale_count + ', News: ' + $('Pruefe Datenqualitaet').item.json.news_count + ')'); } catch(e) {}
try { if ($('Ausfuehren: Report- und Pruefagent (10)').item.json.approved === false) gruende.push('Pruef-Agent hat den Bericht abgelehnt: ' + JSON.stringify($('Ausfuehren: Report- und Pruefagent (10)').item.json.required_corrections || [])); } catch(e) {}
if (gruende.length === 0) gruende.push('Unbekannter Abbruchgrund - siehe trading.pipeline_runs fuer run_id ' + runId);

const text = '⚠️ Tagesabschluss ' + businessDate + ' (run_id ' + runId + ') wurde NICHT automatisch versendet:\\n\\n- ' + gruende.join('\\n- ');

return { json: { run_id: runId, business_date: businessDate, warnung_text: text, final_status: 'warning' } };
"""
    },
    "id": "00000017-0000-4000-8000-000000000017",
    "name": "Baue technische Warnung",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1632, 120]
})
link(n_if_freigabe, n_build_warning, src_index=1)
link(n_if_signale, n_build_warning, src_index=1)
link(n_if_markt, n_build_warning, src_index=1)
link(n_if_dq, n_build_warning, src_index=1)

n_send_warning = add({
    "parameters": {
        "method": "PUT",
        "url": f"=https://matrix.org/_matrix/client/v3/rooms/{MATRIX_ROOM}/send/m.room.message/{{{{ 'orchestrator_warn_' + $json.run_id }}}}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "contentType": "raw",
        "rawContentType": "application/json",
        "body": "={{ JSON.stringify({ msgtype: 'm.text', body: $json.warnung_text }) }}",
        "options": {"timeout": 30000}
    },
    "id": "00000018-0000-4000-8000-000000000018",
    "name": "Matrix: Technische Warnung senden",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1856, 120],
    "onError": "continueRegularOutput",
    "credentials": {"httpHeaderAuth": MATRIX_CRED}
})
link(n_build_warning, n_send_warning)

n_finish_warning = add({
    "parameters": {"jsCode": "return { json: { ...$json, final_status: $json.final_status || 'warning' } };"},
    "id": "00000019-0000-4000-8000-000000000019",
    "name": "Lauf abschliessen (Warnung/Fehler)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [2080, 120]
})
link(n_send_warning, n_finish_warning)

# ---------------------------------------------------------------------------
# Finaler Log-Eintrag (aus beiden Abschluss-Pfaden)
# ---------------------------------------------------------------------------
log_final_in, log_final_out = pipeline_run_log(
    "0000001a-0000-4000-8000-00000000", "Log Gesamtlauf abgeschlossen", [2304, 0],
    "$json.final_status", "orchestrator_ende", "00 – Tagesabschluss-Orchestrator"
)
link(n_finish_success, log_final_in)
link(n_finish_warning, log_final_in)

workflow = {
    "name": "00 – Tagesabschluss-Orchestrator",
    "nodes": nodes,
    "connections": conns,
    "pinData": {},
    "settings": {"executionOrder": "v1"}
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

with open(OUT, encoding="utf-8") as f:
    check = json.load(f)
names = {n["name"] for n in check["nodes"]}
dangling = []
for src, o in check["connections"].items():
    if src not in names:
        dangling.append(("SRC_MISSING", src))
    for branch in o.get("main", []):
        for c in branch:
            if c["node"] not in names:
                dangling.append(("DST_MISSING", c["node"]))
print("nodes:", len(check["nodes"]))
print("dangling:", dangling)
ids = [n["id"] for n in check["nodes"]]
print("duplicate ids:", len(ids) != len(set(ids)), "count:", len(ids), "unique:", len(set(ids)))
