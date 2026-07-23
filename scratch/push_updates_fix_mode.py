import json, os, urllib.request, urllib.error

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://market-data.internal.example:5678/api/v1"
REPO = r"C:\Users\olietz\Documents\finanz"

FILES_TO_IDS = {
    "00 – Tagesabschluss-Orchestrator.json": "CONFIGURE_WORKFLOW_00_ID",
    "03 – News Ingestion stündlich – Agent V1.json": "CONFIGURE_WORKFLOW_03_ID",
    "03a – News-Recherche-Agent.json": "CONFIGURE_WORKFLOW_03A_ID",
    "04 – Cleanup News-Tabellen – Agent V1.json": "CONFIGURE_WORKFLOW_04_ID",
    "08 – News-Wirkungsanalyse.json": "CONFIGURE_WORKFLOW_08_ID",
    "09 – Lernagent Newswirkung.json": "CONFIGURE_WORKFLOW_09_ID",
    "10 – Report- und Prüfagent.json": "CONFIGURE_WORKFLOW_10_ID",
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

for fname, wid in FILES_TO_IDS.items():
    with open(os.path.join(REPO, fname), encoding="utf-8") as f:
        d = json.load(f)
    payload = {
        "name": d["name"],
        "nodes": sanitize_nodes(d["nodes"]),
        "connections": d["connections"],
        "settings": {"executionOrder": "v1"},
    }
    result = api("PUT", f"/workflows/{wid}", payload)
    if result.get("__error__"):
        print(fname, wid, "FEHLER", result["status"], result["body"][:300])
    else:
        print(fname, wid, "-> ok, nodes:", len(result.get("nodes", [])))
