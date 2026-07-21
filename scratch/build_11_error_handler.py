# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, PG_CRED, MATRIX_CRED, MATRIX_ROOM

OUT = r"C:\Users\olietz\Documents\finanz\11 – Zentraler Error-Handler.json"

b = Builder("11 – Zentraler Error-Handler")

n_trigger = b.add({
    "parameters": {},
    "name": "Error Trigger",
    "type": "n8n-nodes-base.errorTrigger",
    "typeVersion": 1,
    "position": [-800, 0]
})

n_extract = b.add({
    "parameters": {
        "mode": "runOnceForEachItem",
        "jsCode": PG_HELPERS_JS + """

const exec = $json.execution || {};
const wf = $json.workflow || {};
const err = exec.error || {};

const workflowName = wf.name || 'unbekannt';
const workflowId = wf.id || '';
const executionId = exec.id || '';
const executionUrl = exec.url || '';
const failedNodeName = exec.lastNodeExecuted || '';
const failedNodeType = (err.node && err.node.type) || '';
const errorMessage = err.message || (typeof err === 'string' ? err : '') || '';
const errorName = err.name || '';
const errorStack = err.stack || '';
const executionMode = exec.mode || '';

const sql = `INSERT INTO trading.workflow_errors
  (workflow_name, workflow_id, execution_id, execution_url, failed_node_name, failed_node_type, error_message, error_name, error_stack, execution_mode, raw_payload_json)
  VALUES (${pgStr(workflowName)}, ${pgStr(workflowId)}, ${pgStr(executionId)}, ${pgStr(executionUrl)}, ${pgStr(failedNodeName)}, ${pgStr(failedNodeType)}, ${pgStr(errorMessage)}, ${pgStr(errorName)}, ${pgStr(errorStack)}, ${pgStr(executionMode)}, ${pgJson($json)});`;

const matrixText = `⚠️ Workflow-Fehler: ${workflowName}\\n\\nNode: ${failedNodeName || '(unbekannt)'}\\nFehler: ${errorMessage || '(keine Meldung)'}\\nExecution: ${executionUrl || '(keine URL)'}`;

return { json: { workflowName, workflowId, executionId, executionUrl, failedNodeName, failedNodeType, errorMessage, errorName, errorStack, executionMode, sql, matrixText } };
"""
    },
    "name": "Fehlerdaten aufbereiten",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-576, 0]
})
b.link(n_trigger, n_extract)

n_pg = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "={{ $json.sql }}",
        "options": {}
    },
    "name": "Fehler protokollieren (ausfuehren)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-352, -120],
    "credentials": {"postgres": PG_CRED}
})
b.link(n_extract, n_pg)

n_matrix = b.add({
    "parameters": {
        "method": "PUT",
        "url": "=https://matrix.org/_matrix/client/v3/rooms/" + MATRIX_ROOM + "/send/m.room.message/{{ 'error_' + ($json.executionId || Date.now()) }}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "Content-Type", "value": "application/json"}
            ]
        },
        "sendBody": True,
        "contentType": "raw",
        "rawContentType": "application/json",
        "body": "={{ JSON.stringify({ msgtype: 'm.text', body: $json.matrixText }) }}",
        "options": {"timeout": 30000}
    },
    "name": "Matrix: Fehler-Alert senden",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [-352, 120],
    "onError": "continueRegularOutput",
    "credentials": {"httpHeaderAuth": MATRIX_CRED}
})
b.link(n_extract, n_matrix)

check = b.write_and_validate(OUT)
print(json.dumps({"nodes": len(check["nodes"])}, indent=2))
