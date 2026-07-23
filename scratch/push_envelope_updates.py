import json, os, sys, urllib.request, urllib.error, datetime

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://172.16.1.14:5678/api/v1"
REPO = r"C:\Users\olietz\Documents\finanz"
BACKUP_DIR = os.path.join(REPO, "n8n_live_backup")

FILES_TO_IDS = {
    "10 – Report- und Prüfagent.json": "BFlxfLyarzR2xbBT",
    "06 – Empfehlungswatchlist – Agent V1.json": "aguWZUolRizBnsj4",
    "05 – Tagesreport – Agent V1.json": "VRr5jIHj7G7dsMwi",
    "00 – Tagesabschluss-Orchestrator.json": "ncMZzkqDHpSiDGPm",
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


def push_one(fname):
    wid = FILES_TO_IDS[fname]
    with open(os.path.join(REPO, fname), encoding="utf-8") as f:
        local = json.load(f)

    live = api("GET", f"/workflows/{wid}")
    if live.get("__error__"):
        print(fname, wid, "GET FEHLER", live["status"], live["body"][:300])
        return False

    live_names = sorted(n["name"] for n in live["nodes"])
    local_names = sorted(n["name"] for n in local["nodes"])
    print(fname, "-> live nodes:", len(live_names), "local nodes:", len(local_names))
    only_live = set(live_names) - set(local_names)
    only_local = set(local_names) - set(live_names)
    if only_live:
        print("  nur live:", only_live)
    if only_local:
        print("  nur lokal (neu):", only_local)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = live["name"].replace(" ", "_").replace("–", "-")
    backup_path = os.path.join(BACKUP_DIR, f"{safe_name}_LIVE_BACKUP_PRE_ENVELOPE_{stamp}.json")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(live, f, ensure_ascii=False)
    print("  backup:", backup_path)

    payload = {
        "name": live["name"],
        "nodes": sanitize_nodes(local["nodes"]),
        "connections": local["connections"],
        "settings": {"executionOrder": "v1"},
    }
    result = api("PUT", f"/workflows/{wid}", payload)
    if result.get("__error__"):
        print("  PUT FEHLER", result["status"], result["body"][:500])
        return False
    print("  -> PUT ok, live nodes now:", len(result.get("nodes", [])))
    return True


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(FILES_TO_IDS.keys())
    for t in targets:
        push_one(t)
        print()
