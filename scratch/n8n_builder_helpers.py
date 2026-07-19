"""Wiederverwendbare Bausteine fuer die generierten n8n-Workflow-JSONs dieser
Migration. Kein n8n-Feature wird hier erfunden -- alle Node-Typen/Parameter-
Formen sind entweder aus den bestehenden 8 Original-Workflows uebernommen
(scheduleTrigger, code, if, filter, merge, dataTable, httpRequest,
langchain.openAi) oder aus dem real getesteten Migrations-Runner
(postgres executeQuery)."""
import json

PG_CRED = {"id": "PLACEHOLDER_POSTGRES_CRED", "name": "Postgres – Trading (TODO Credential zuweisen)"}
MATRIX_CRED = {"id": "od1pN1F5wy2irSDs", "name": "Header Auth account"}
OPENAI_CRED = {"id": "RiT1gwJpQWzSo6NO", "name": "OpenAI account"}
MATRIX_ROOM = "!uDpcMuCWUvcwXMKJAP:matrix.org"

GET_BUSINESS_DATE_JS = """function getBusinessDate(date = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Europe/Berlin',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}"""

PG_HELPERS_JS = """function pgStr(v) { return v === null || v === undefined ? 'NULL' : `'` + String(v).replace(/'/g, `''`) + `'`; }
function pgNum(v) { return v === null || v === undefined || v === '' || isNaN(Number(v)) ? 'NULL' : Number(v); }
function pgBool(v) { return v === null || v === undefined ? 'NULL' : (v ? 'TRUE' : 'FALSE'); }
function pgJson(v) { return `'` + JSON.stringify(v === undefined ? null : v).replace(/'/g, `''`) + `'::jsonb`; }
function pgArr(v) { return `'{` + (Array.isArray(v) ? v : []).map(x => String(x).replace(/"/g,'\\\\"')).join(',') + `}'`; }"""


class Builder:
    def __init__(self, workflow_name):
        self.workflow_name = workflow_name
        self.nodes = []
        self.conns = {}
        self._counter = 0

    def _next_id(self, prefix="n"):
        self._counter += 1
        return f"{prefix}-{self._counter:08d}-0000-4000-8000-000000000000"[:36]

    def add(self, node):
        if "id" not in node:
            node["id"] = self._next_id()
        self.nodes.append(node)
        return node["name"]

    def link(self, src, dst, src_index=0, dst_index=0):
        self.conns.setdefault(src, {"main": []})
        while len(self.conns[src]["main"]) <= src_index:
            self.conns[src]["main"].append([])
        self.conns[src]["main"][src_index].append({"node": dst, "type": "main", "index": dst_index})

    def pg_exec_pair(self, label, position, sql_js_body, on_error="continueRegularOutput"):
        code_name = f"{label} (SQL bauen)"
        pg_name = f"{label} (ausfuehren)"
        self.add({
            "parameters": {
                "mode": "runOnceForEachItem",
                "jsCode": PG_HELPERS_JS + "\n\n" + sql_js_body
            },
            "name": code_name,
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [position[0], position[1]]
        })
        pg_params = {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}}
        pg_node = {
            "parameters": pg_params,
            "name": pg_name,
            "type": "n8n-nodes-base.postgres",
            "typeVersion": 2.5,
            "position": [position[0] + 176, position[1]],
            "credentials": {"postgres": PG_CRED}
        }
        if on_error:
            pg_node["onError"] = on_error
        self.add(pg_node)
        self.link(code_name, pg_name)
        return code_name, pg_name

    def build(self, settings=None):
        wf = {
            "name": self.workflow_name,
            "nodes": self.nodes,
            "connections": self.conns,
            "pinData": {},
            "settings": settings or {"executionOrder": "v1"}
        }
        return wf

    def write_and_validate(self, path):
        wf = self.build()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        with open(path, encoding="utf-8") as f:
            check = json.load(f)
        names = {n["name"] for n in check["nodes"]}
        dangling = []
        for src, o in check["connections"].items():
            if src not in names:
                dangling.append(("SRC_MISSING", src))
            for branch in o.get("main", []):
                for c in branch:
                    if c["node"] not in names:
                        dangling.append(("DST_MISSING", c["node"]))
        ids = [n["id"] for n in check["nodes"]]
        print(f"[{self.workflow_name}] nodes: {len(check['nodes'])}  dangling: {dangling}  dup_ids: {len(ids) != len(set(ids))}")
        return check
