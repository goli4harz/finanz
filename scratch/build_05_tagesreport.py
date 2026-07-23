# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED, MATRIX_CRED

OUT = r"C:\Users\olietz\Documents\finanz\05 – Tagesreport – Agent V1.json"
ORIG = r"C:\Users\olietz\Downloads\Aktien\05 – Tagesreport.json"

with open(ORIG, encoding="utf-8") as f:
    orig = json.load(f)
orig_nodes = {n["name"]: n for n in orig["nodes"]}

WF_10 = "CONFIGURE_WORKFLOW_10_ID"  # echte n8n-id nach Erstellung 2026-07-19

b = Builder("05 – Tagesreport – Agent V1")

# ---------------------------------------------------------------------------
# 1. Zwei Einstiege: eigener Zeitplan (ruft 10 selbst auf -> voll
#    eigenstaendig lauffaehig ohne Orchestrator) und Execute Workflow Trigger
#    (bekommt das Ergebnis von 10 direkt vom Orchestrator mitgegeben, kein
#    zweiter Report-Agent-Aufruf noetig).
# ---------------------------------------------------------------------------
n_trig_schedule = b.add(dict(orig_nodes["Trigger: Tagesreport (18:30)"], position=[-3600, -200]))

n_trig_exec = b.add({
    "parameters": {"workflowInputs": {"values": [
        {"name": "run_id"}, {"name": "report_markdown"}, {"name": "approved"}, {"name": "DRY_RUN"}
    ]}},
    "name": "Execute Workflow Trigger",
    "type": "n8n-nodes-base.executeWorkflowTrigger",
    "typeVersion": 1.1,
    "position": [-3600, 200]
})

n_call_10 = b.add({
    "parameters": {
        "source": "database",
        "workflowId": {"__rl": True, "value": WF_10, "mode": "list", "cachedResultName": "10 – Report- und Prüfagent (TODO: id nach Import korrigieren)"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {
            "run_id": "={{ 'standalone-' + Date.now() }}",
            "business_date": ""
        }},
        "options": {"waitForSubWorkflow": True}
    },
    "name": "Ausfuehren: Report- und Pruefagent (10, standalone)",
    "type": "n8n-nodes-base.executeWorkflow",
    "typeVersion": 1.2,
    "position": [-3400, -200],
    "onError": "continueErrorOutput"
})
b.link(n_trig_schedule, n_call_10)

n_normalize = b.add({
    "parameters": {
        "jsCode": "// Vereinheitlicht beide Einstiegspfade auf ein gemeinsames Item.\n"
                  "const j = $json || {};\n"
                  "return [{ json: {\n"
                  "  run_id: j.run_id || 'unbekannt',\n"
                  "  report_markdown: j.report_markdown || '',\n"
                  "  approved: j.approved === true || j.approved === 'true',\n"
                  "  quality_score: j.quality_score,\n"
                  "  required_corrections: j.required_corrections || [],\n"
                  "  missing_warnings: j.missing_warnings || [],\n"
                  "  technische_signale: j.technische_signale || [],\n"
                  "  empfehlungswatchlist: j.empfehlungswatchlist || {},\n"
                  "  datenqualitaet: j.datenqualitaet || {},\n"
                  "  DRY_RUN: j.DRY_RUN === true || j.DRY_RUN === 'true'\n"
                  "} }];"
    },
    "name": "Eingabe normalisieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-3200, 0]
})
b.link(n_call_10, n_normalize, src_index=0)
b.link(n_call_10, n_normalize, src_index=1)
b.link(n_trig_exec, n_normalize)

n_if_approved = b.add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ $json.approved }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "name": "IF: Freigegeben?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-3000, 0]
})
b.link(n_normalize, n_if_approved)

# ---------------------------------------------------------------------------
# 2a. Freigegeben: aufbereiten + versenden (Original-Logik von "Report
#    aufbereiten" uebernommen, aber report_markdown direkt statt aus einem
#    rohen KI-Objekt extrahiert -- der Report-Agent-Aufruf liefert bereits
#    fertigen Markdown-Text).
# ---------------------------------------------------------------------------
orig_aufbereiten = orig_nodes["Report aufbereiten"]["parameters"]["jsCode"]
new_aufbereiten = orig_aufbereiten.replace(
    "const ki = $input.item.json;\n",
    "const ki = $input.item.json;\n"
)
new_aufbereiten = new_aufbereiten.replace(
    "const report_text = buildSignalUebersicht() + extractReportText(ki) + buildEmpfehlungsMarkdown();",
    "const report_text = buildSignalUebersicht() + (ki.report_markdown || extractReportText(ki)) + buildEmpfehlungsMarkdown();"
)
new_aufbereiten = new_aufbereiten.replace(
    "$('Report: Datenqualität prüfen').item.json.empfehlungswatchlist;",
    "$('Eingabe normalisieren').item.json.empfehlungswatchlist;"
)
new_aufbereiten = new_aufbereiten.replace(
    "daten = $('Report: Datenqualität prüfen').item.json;",
    "daten = $('Eingabe normalisieren').item.json;"
)
assert "ki.report_markdown" in new_aufbereiten and "Eingabe normalisieren" in new_aufbereiten

n_aufbereiten = b.add({
    "parameters": {"jsCode": new_aufbereiten},
    "name": "Report aufbereiten",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2800, -120]
})
b.link(n_if_approved, n_aufbereiten, src_index=0)

n_if_dry_run_send = b.add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ !$('Eingabe normalisieren').item.json.DRY_RUN }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "name": "IF: DRY_RUN? (Versand)",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-2600, -120]
})
b.link(n_aufbereiten, n_if_dry_run_send)

n_matrix_send = b.add(dict(orig_nodes["Matrix: Tagesreport senden"], position=[-2400, -200]))
b.link(n_if_dry_run_send, n_matrix_send, src_index=0)

n_email_send = b.add(dict(orig_nodes["E-Mail Report senden"], position=[-2400, -40]))
b.link(n_if_dry_run_send, n_email_send, src_index=0)

n_dry_run_log = b.add({
    "parameters": {
        "jsCode": "// DRY_RUN=true: kein produktiver Versand, nur Protokollierung.\n"
                  "return [{ json: { ...$json, _dry_run_skip: 'Versand uebersprungen (DRY_RUN)' } }];"
    },
    "name": "DRY_RUN: Versand uebersprungen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2400, 40]
})
b.link(n_if_dry_run_send, n_dry_run_log, src_index=1)

# ---------------------------------------------------------------------------
# 2b. Nicht freigegeben: technische Warnung statt Normalversand (Pruef-Agent-
#    Ablehnung wird explizit genannt, nicht nur allgemeine Datenqualitaet).
# ---------------------------------------------------------------------------
n_build_warning = b.add({
    "parameters": {
        "jsCode": """const j = $json;
const warns = [
  ...(j.missing_warnings || []),
  ...(j.required_corrections || []).map(c => 'Pruef-Agent-Korrektur: ' + c)
];
if (warns.length === 0) warns.push('Pruef-Agent hat den Bericht abgelehnt (quality_score ' + j.quality_score + '), keine Details verfuegbar.');

const body = '⚠️ Tagesreport NICHT versendet (run_id ' + j.run_id + ', quality_score ' + j.quality_score + ')\\n\\n• ' + warns.join('\\n• ');
const formatted_body = '<b>⚠️ Tagesreport NICHT versendet</b> (run_id ' + j.run_id + ', quality_score ' + j.quality_score + ')<br><ul>' + warns.map(w => '<li>' + w + '</li>').join('') + '</ul>';

return [{ json: { ...j, _warn_body: body, _warn_formatted_body: formatted_body } }];
"""
    },
    "name": "Ablehnungs-Warnung bauen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2800, 160]
})
b.link(n_if_approved, n_build_warning, src_index=1)

n_matrix_fehler_orig = orig_nodes["Matrix: Fehler-Alert"]
new_fehler_params = json.loads(json.dumps(n_matrix_fehler_orig["parameters"]))
for p in new_fehler_params["bodyParameters"]["parameters"]:
    if p["name"] == "body":
        p["value"] = "={{ $json._warn_body }}"
    if p["name"] == "formatted_body":
        p["value"] = "={{ $json._warn_formatted_body }}"

n_matrix_fehler = b.add({
    "parameters": new_fehler_params,
    "name": "Matrix: Fehler-Alert",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.1,
    "position": [-2600, 160],
    "credentials": {"httpHeaderAuth": MATRIX_CRED}
})
b.link(n_build_warning, n_matrix_fehler)

b.write_and_validate(OUT)
