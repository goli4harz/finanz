import json, os, subprocess, sys

REPO = r"C:\Users\olietz\Documents\finanz"
SCRATCH = r"C:\Users\olietz\AppData\Local\Temp\claude\c--Users-olietz-Downloads\9e5863c2-f27c-40ea-ad25-5cc547749c68\scratchpad"
API_KEY = os.environ["N8N_API_KEY"]
BASE = "http://market-data.internal.example:5678/api/v1"

import urllib.request

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

def load(fname):
    with open(os.path.join(REPO, fname), encoding="utf-8") as f:
        return json.load(f)

def sanitize_nodes(nodes):
    # Die strikte create-Workflow-API akzeptiert kein node-level "settings"
    # (z.B. retryOnFail/maxTries an httpRequest-Nodes), obwohl das UI-Export-
    # Format es enthaelt -- nur fuer den API-Push entfernt, Dateien im Repo
    # bleiben unveraendert (dort ist es fuer einen manuellen UI-Import evtl.
    # relevant/gueltig).
    out = []
    for n in nodes:
        n2 = dict(n)
        n2.pop("settings", None)
        out.append(n2)
    return out

def create_payload(d):
    payload = {
        "name": d["name"],
        "nodes": sanitize_nodes(d["nodes"]),
        "connections": d["connections"],
        "settings": {"executionOrder": "v1"},
    }
    return payload

def create(fname, force_inactive_note=None):
    d = load(fname)
    payload = create_payload(d)
    result = api("POST", "/workflows", payload)
    if result.get("__error__"):
        print(f"FEHLER bei {fname}: {result['status']} {result['body'][:300]}")
        return None
    wid = result["id"]
    print(f"{fname} -> id={wid} active={result.get('active')}")
    return wid

# Nur die zuvor fehlgeschlagenen erneut versuchen (Rest bereits erfolgreich erstellt).
ids = {}
for fname in [
    "02b – Marktumfeld täglich – Orchestriert.json",
    "02 – Technische Signale täglich – Orchestriert.json",
    "03a – News-Recherche-Agent.json",
    "06 – Empfehlungswatchlist – Agent V1.json",
]:
    ids[fname] = create(fname)

with open(os.path.join(SCRATCH, "pushed_ids.json"), "w", encoding="utf-8") as f:
    json.dump(ids, f, ensure_ascii=False, indent=2)

print()
print("=== IDs gesammelt ===")
for k, v in ids.items():
    print(k, "->", v)
