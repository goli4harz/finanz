import json

OUT = r"C:\Users\olietz\Documents\finanz\97 – Einmalig – Beliebige Query ausfuehren.json"

PG_CRED = {"id": "NWckNyl8ZfwVVJCd", "name": "Postgres account"}

workflow = {
    "name": "97 – Einmalig – Beliebige Query ausfuehren",
    "nodes": [
        {
            "parameters": {},
            "id": "30000000-0000-4000-8000-000000000001",
            "name": "Manueller Start",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-400, 0]
        },
        {
            "parameters": {
                "operation": "executeQuery",
                "query": "SELECT 1 AS platzhalter;",
                "options": {}
            },
            "id": "30000000-0000-4000-8000-000000000002",
            "name": "Query ausfuehren",
            "type": "n8n-nodes-base.postgres",
            "typeVersion": 2.5,
            "position": [-176, 0],
            "credentials": {"postgres": PG_CRED}
        }
    ],
    "connections": {
        "Manueller Start": {"main": [[{"node": "Query ausfuehren", "type": "main", "index": 0}]]}
    },
    "pinData": {},
    "settings": {"executionOrder": "v1"}
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)
print("written")
