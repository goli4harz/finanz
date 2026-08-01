"""Wiederverwendbarer Push-Helfer fuer diese Haertungs-Session: GET Live-Stand -> Backup nach
n8n_live_backup/ -> Node-Namensabgleich -> PUT. Aufruf: python push_with_backup.py "<Dateiname ohne Pfad>" [tag]
"""
import json, os, sys, urllib.request, urllib.error, datetime

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://172.16.1.14:5678/api/v1"
REPO = r"C:\Users\olietz\Documents\finanz"

ALLOWED_SETTINGS = {
    "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
    "saveDataSuccessExecution", "executionTimeout", "errorWorkflow", "timezone",
    "executionOrder"
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

def push(fname, tag="fix"):
    local_path = os.path.join(REPO, fname)
    with open(local_path, encoding="utf-8") as f:
        local = json.load(f)

    listing = api("GET", "/workflows?limit=250")
    if listing.get("__error__"):
        print("LIST FEHLER", listing); return False
    match = [w for w in listing["data"] if w["name"] == local["name"]]
    if len(match) != 1:
        print(f"FEHLER: {len(match)} Treffer fuer Name '{local['name']}' statt genau 1"); return False
    wid = match[0]["id"]

    live = api("GET", f"/workflows/{wid}")
    if live.get("__error__"):
        print("GET FEHLER", live); return False

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = local["name"].replace(" ", "_").replace("–", "-")
    backup_path = os.path.join(REPO, "n8n_live_backup", f"{safe_name}_PRE_{tag}_{ts}.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(live, f, ensure_ascii=False, indent=2)
    print("backup:", backup_path)

    live_names = sorted(n["name"] for n in live["nodes"])
    local_names = sorted(n["name"] for n in local["nodes"])
    if live_names != local_names:
        print("WARNUNG node-name-sets differ:", set(live_names) ^ set(local_names))

    settings = {k: v for k, v in live.get("settings", {}).items() if k in ALLOWED_SETTINGS}
    if not settings:
        settings = {"executionOrder": "v1"}

    body = {
        "name": local["name"],
        "nodes": sanitize_nodes(local["nodes"]),
        "connections": local["connections"],
        "settings": settings,
    }
    result = api("PUT", f"/workflows/{wid}", body)
    if result.get("__error__"):
        print("PUT FEHLER", result["status"], result["body"][:500]); return False
    print(f"OK: {fname} (id {wid}) -> {len(result.get('nodes', []))} Nodes, active={result.get('active')}")
    return True

if __name__ == "__main__":
    fname = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else "fix"
    ok = push(fname, tag)
    sys.exit(0 if ok else 1)
