import json, os, urllib.request, urllib.error

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://172.16.1.14:5678/api/v1"
REAL_CRED = {"id": "NWckNyl8ZfwVVJCd", "name": "Postgres account"}
STATUS_WEBHOOK_CRED = {"id": "5lPS4iU0YNbMcjWR", "name": "Status-Webhook Token"}

WORKFLOW_IDS = {
    "00 Orchestrator": "ncMZzkqDHpSiDGPm",
    "02b Orchestriert": "9zO3uZeZeakTnLnX",
    "02 Orchestriert": "vgT6IrPp3ATaJg8s",
    "03 Agent V1": "kXfFAy97N6xgRgQ5",
    "03a": "SUNb1rfSUTQGUTPN",
    "04 Agent V1": "3aeFh4tfDrCi4dUm",
    "05 Agent V1": "VRr5jIHj7G7dsMwi",
    "06 Agent V1": "aguWZUolRizBnsj4",
    "07 Agent V1": "7hQ3t6KrSo9uDNML",
    "08": "EvJKlqkuSIu9CHmR",
    "09": "LjZHC5g7thqcCElo",
    "10": "BFlxfLyarzR2xbBT",
    "99": "8PHV9RfaXjfTo3ZK",
    "11 Error-Handler": "VTBfUuzQfMZNGYDM",
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
