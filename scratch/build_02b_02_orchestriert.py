# -*- coding: utf-8 -*-
import json

# Fuegt beiden Workflows additiv einen Execute Workflow Trigger als
# ALTERNATIVEN Einstiegspunkt hinzu (neben dem bestehenden Schedule Trigger,
# der unveraendert weiterlaeuft solange der Nutzer ihn nicht deaktiviert --
# siehe README/Abschlussbericht fuer den Hinweis, beide nicht dauerhaft
# parallel aktiv zu lassen). Keine bestehende Logik/kein bestehender Node
# wird veraendert, nur ein neuer Node + eine neue Verbindung ergaenzt.

JOBS = [
    (r"C:\Users\olietz\Downloads\Aktien\02b – Marktumfeld täglich (1).json",
     r"C:\Users\olietz\Documents\finanz\02b – Marktumfeld täglich – Orchestriert.json",
     "Markt-Watchlist laden"),
    (r"C:\Users\olietz\Downloads\Aktien\02 – Technische Signale täglich.json",
     r"C:\Users\olietz\Documents\finanz\02 – Technische Signale täglich – Orchestriert.json",
     "Watchlist laden (Kurse)"),
]

for src, dst, first_real_node in JOBS:
    with open(src, encoding="utf-8") as f:
        d = json.load(f)

    trigger_node = {
        "parameters": {"workflowInputs": {"values": [{"name": "run_id"}]}},
        "id": "eeeeeeee-0000-4000-8000-000000000001",
        "name": "Execute Workflow Trigger",
        "type": "n8n-nodes-base.executeWorkflowTrigger",
        "typeVersion": 1.1,
        "position": [-1568, -160]
    }
    assert first_real_node in {n["name"] for n in d["nodes"]}, f"{first_real_node} not found in {src}"
    d["nodes"].append(trigger_node)
    d["connections"].setdefault("Execute Workflow Trigger", {"main": [[]]})
    d["connections"]["Execute Workflow Trigger"]["main"][0].append(
        {"node": first_real_node, "type": "main", "index": 0}
    )

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    with open(dst, encoding="utf-8") as f:
        check = json.load(f)
    names = {n["name"] for n in check["nodes"]}
    dangling = []
    for s, o in check["connections"].items():
        if s not in names:
            dangling.append(("SRC_MISSING", s))
        for branch in o.get("main", []):
            for c in branch:
                if c["node"] not in names:
                    dangling.append(("DST_MISSING", c["node"]))
    print(dst.split(chr(92))[-1], "-> nodes:", len(check["nodes"]), "dangling:", dangling)
