import json

OUT = r"C:\Users\olietz\Documents\finanz\98 – Einmalig – Postgres-Verbindungstest.json"

PG_CRED = {"id": "PLACEHOLDER_POSTGRES_CRED", "name": "Postgres – Trading (TODO Credential zuweisen)"}

workflow = {
    "name": "98 – Einmalig – Postgres-Verbindungstest",
    "nodes": [
        {
            "parameters": {},
            "id": "20000000-0000-4000-8000-000000000001",
            "name": "Manueller Start",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-400, 0]
        },
        {
            "parameters": {
                "operation": "executeQuery",
                "query": "SELECT 1 AS ok, now() AS server_zeit, current_database() AS datenbank;",
                "options": {}
            },
            "id": "20000000-0000-4000-8000-000000000002",
            "name": "Postgres: Verbindung testen",
            "type": "n8n-nodes-base.postgres",
            "typeVersion": 2.5,
            "position": [-176, 0],
            "credentials": {"postgres": PG_CRED}
        },
        {
            "parameters": {
                "operation": "executeQuery",
                "query": "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'trading';",
                "options": {}
            },
            "id": "20000000-0000-4000-8000-000000000003",
            "name": "Postgres: Prueft ob Schema trading existiert",
            "type": "n8n-nodes-base.postgres",
            "typeVersion": 2.5,
            "position": [48, 0],
            "onError": "continueRegularOutput",
            "credentials": {"postgres": PG_CRED}
        }
    ],
    "connections": {
        "Manueller Start": {"main": [[{"node": "Postgres: Verbindung testen", "type": "main", "index": 0}]]},
        "Postgres: Verbindung testen": {"main": [[{"node": "Postgres: Prueft ob Schema trading existiert", "type": "main", "index": 0}]]}
    },
    "pinData": {},
    "settings": {"executionOrder": "v1"}
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

with open(OUT, encoding="utf-8") as f:
    check = json.load(f)
print("nodes:", len(check["nodes"]))
