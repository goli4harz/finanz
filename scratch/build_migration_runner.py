import json, os

SQL_PATH = r"C:\Users\olietz\Documents\finanz\sql\001_agenten_architektur.sql"
OUT = r"C:\Users\olietz\Documents\finanz\99 – Einmalig – SQL-Migration ausfuehren.json"

with open(SQL_PATH, encoding="utf-8") as f:
    sql_text = f.read()

PG_CRED = {"id": "PLACEHOLDER_POSTGRES_CRED", "name": "Postgres – Trading (TODO Credential zuweisen)"}

workflow = {
    "name": "99 – Einmalig – SQL-Migration ausfuehren",
    "nodes": [
        {
            "parameters": {},
            "id": "10000000-0000-4000-8000-000000000001",
            "name": "Manueller Start",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-400, 0]
        },
        {
            "parameters": {
                "operation": "executeQuery",
                "query": sql_text,
                "options": {}
            },
            "id": "10000000-0000-4000-8000-000000000002",
            "name": "Fuehre 001_agenten_architektur.sql aus",
            "type": "n8n-nodes-base.postgres",
            "typeVersion": 2.5,
            "position": [-176, 0],
            "credentials": {"postgres": PG_CRED}
        }
    ],
    "connections": {
        "Manueller Start": {"main": [[{"node": "Fuehre 001_agenten_architektur.sql aus", "type": "main", "index": 0}]]}
    },
    "pinData": {},
    "settings": {"executionOrder": "v1"}
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

with open(OUT, encoding="utf-8") as f:
    check = json.load(f)
print("nodes:", len(check["nodes"]))
print("query length:", len(check["nodes"][1]["parameters"]["query"]))
