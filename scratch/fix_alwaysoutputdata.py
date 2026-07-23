import json, os, urllib.request, urllib.error

API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://market-data.internal.example:5678/api/v1"
REPO = r"C:\Users\olietz\Documents\finanz"
REAL_CRED = {"id": "CONFIGURE_POSTGRES_CREDENTIAL_ID", "name": "Postgres account"}

# Quelle: die LOKALEN Repo-Dateien (haben noch die vollstaendigen, original-
# treuen node.settings.alwaysOutputData-Werte) -- NICHT der aktuelle Live-
# Stand in n8n, der durch fruehere Pushes bereits das ungeprueft gestrippte
# "settings" verloren hat.
FILES_TO_IDS = {
    "00 – Tagesabschluss-Orchestrator.json": "CONFIGURE_WORKFLOW_00_ID",
    "02b – Marktumfeld täglich – Orchestriert.json": "CONFIGURE_WORKFLOW_02B_ID",
    "02 – Technische Signale täglich – Orchestriert.json": "CONFIGURE_WORKFLOW_02_ID",
    "03 – News Ingestion stündlich – Agent V1.json": "CONFIGURE_WORKFLOW_03_ID",
    "03a – News-Recherche-Agent.json": "CONFIGURE_WORKFLOW_03A_ID",
    "04 – Cleanup News-Tabellen – Agent V1.json": "CONFIGURE_WORKFLOW_04_ID",
    "05 – Tagesreport – Agent V1.json": "CONFIGURE_WORKFLOW_05_ID",
    "06 – Empfehlungswatchlist – Agent V1.json": "CONFIGURE_WORKFLOW_06_ID",
    "07 – Status-Uebersicht – Agent V1.json": "CONFIGURE_WORKFLOW_07_ID",
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

def fix_node(n):
    n2 = dict(n)
    settings = n2.get("settings")
    promoted = False
    if isinstance(settings, dict):
        if settings.get("alwaysOutputData") and not n2.get("alwaysOutputData"):
            n2["alwaysOutputData"] = True
            promoted = True
    n2.pop("settings", None)
    if n2.get("type") == "n8n-nodes-base.postgres":
        n2["credentials"] = {"postgres": REAL_CRED}
    return n2, promoted

for fname, wid in FILES_TO_IDS.items():
    with open(os.path.join(REPO, fname), encoding="utf-8") as f:
        d = json.load(f)
    new_nodes = []
    promoted_names = []
    for n in d["nodes"]:
        n2, promoted = fix_node(n)
        new_nodes.append(n2)
        if promoted:
            promoted_names.append(n["name"])
    payload = {
        "name": d["name"],
        "nodes": new_nodes,
        "connections": d["connections"],
        "settings": {"executionOrder": "v1"},
    }
    result = api("PUT", f"/workflows/{wid}", payload)
    if result.get("__error__"):
        print(fname, wid, "PUT FEHLER", result["status"], result["body"][:300])
    else:
        print(fname, wid, f"-> ok, alwaysOutputData nachgetragen bei:", promoted_names)
