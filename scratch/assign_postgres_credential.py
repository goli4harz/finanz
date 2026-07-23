import json, os, urllib.request, urllib.error

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://market-data.internal.example:5678/api/v1"
REAL_CRED = {"id": "CONFIGURE_POSTGRES_CREDENTIAL_ID", "name": "Postgres account"}
STATUS_WEBHOOK_CRED = {"id": "CONFIGURE_STATUS_CREDENTIAL_ID", "name": "Status-Webhook Token"}

WORKFLOW_IDS = {
    "00 Orchestrator": "CONFIGURE_WORKFLOW_00_ID",
    "02b Orchestriert": "CONFIGURE_WORKFLOW_02B_ID",
    "02 Orchestriert": "CONFIGURE_WORKFLOW_02_ID",
    "03 Agent V1": "CONFIGURE_WORKFLOW_03_ID",
    "03a": "CONFIGURE_WORKFLOW_03A_ID",
    "04 Agent V1": "CONFIGURE_WORKFLOW_04_ID",
    "05 Agent V1": "CONFIGURE_WORKFLOW_05_ID",
    "06 Agent V1": "CONFIGURE_WORKFLOW_06_ID",
    "07 Agent V1": "CONFIGURE_WORKFLOW_07_ID",
    "08": "CONFIGURE_WORKFLOW_08_ID",
    "09": "CONFIGURE_WORKFLOW_09_ID",
    "10": "CONFIGURE_WORKFLOW_10_ID",
    "99": "CONFIGURE_WORKFLOW_99_ID",
    "11 Error-Handler": "CONFIGURE_ERROR_WORKFLOW_ID",
}

def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-N8N-API-KEY", API_KEY)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__error__": True, "status": e.code, "body": e.read().decode("utf-8")}

def sanitize_nodes(nodes):
    out = []
    for n in nodes:
        n2 = dict(n)
        n2.pop("settings", None)
        out.append(n2)
    return out

for label, wid in WORKFLOW_IDS.items():
    d = api("GET", f"/workflows/{wid}")
    if d.get("__error__"):
        print(label, wid, "GET FEHLER", d["status"])
        continue
    changed = 0
    for n in d["nodes"]:
        if n["type"] == "n8n-nodes-base.postgres":
            n["credentials"] = {"postgres": REAL_CRED}
            changed += 1
        elif n["type"] == "n8n-nodes-base.webhook" and "httpHeaderAuth" in (n.get("credentials") or {}):
            n["credentials"] = {"httpHeaderAuth": STATUS_WEBHOOK_CRED}
            changed += 1
    if changed == 0:
        print(label, wid, "-> keine Postgres-Nodes, uebersprungen")
        continue
    payload = {
        "name": d["name"],
        "nodes": sanitize_nodes(d["nodes"]),
        "connections": d["connections"],
        "settings": {"executionOrder": "v1"},
    }
    result = api("PUT", f"/workflows/{wid}", payload)
    if result.get("__error__"):
        print(label, wid, f"-> PUT FEHLER ({changed} Postgres-Nodes)", result["status"], result["body"][:300])
    else:
        print(label, wid, f"-> {changed} Postgres-Node(s) aktualisiert, ok")
