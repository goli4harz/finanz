import json, os, urllib.request, urllib.error

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://172.16.1.14:5678/api/v1"
REPO = r"C:\Users\olietz\Documents\finanz"

FILES_TO_IDS = {
    "00 – Tagesabschluss-Orchestrator.json": "ncMZzkqDHpSiDGPm",
    "03 – News Ingestion stündlich – Agent V1.json": "kXfFAy97N6xgRgQ5",
    "03a – News-Recherche-Agent.json": "SUNb1rfSUTQGUTPN",
    "04 – Cleanup News-Tabellen – Agent V1.json": "3aeFh4tfDrCi4dUm",
    "08 – News-Wirkungsanalyse.json": "EvJKlqkuSIu9CHmR",
    "09 – Lernagent Newswirkung.json": "LjZHC5g7thqcCElo",
    "10 – Report- und Prüfagent.json": "BFlxfLyarzR2xbBT",
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
