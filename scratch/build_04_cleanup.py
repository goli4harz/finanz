# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED

OUT = r"C:\Users\olietz\Documents\finanz\04 – Cleanup News-Tabellen – Agent V1.json"

b = Builder("04 – Cleanup News-Tabellen – Agent V1")

n_trig1 = b.add({
    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 45 23 * * 1-5"}]}},
    "name": "Trigger: Cleanup (23:45 Mo-Fr)",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.1,
    "position": [-800, -80]
})
n_trig2 = b.add({
    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 15 0 * * 6"}]}},
    "name": "Trigger: Cleanup (Sa 00:15)",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.1,
    "position": [-800, 80]
})

# Kein Merge-Node noetig: beide Trigger fuehren unabhaengig (entweder/oder,
# nicht kombiniert) direkt zum selben ersten Verarbeitungsschritt.

# ---------------------------------------------------------------------------
# Neue Aufbewahrungsregeln (Phase 12): archivieren-statt-loeschen ist fuer
# trading.* nicht als separates Flag noetig, da news_impact_tracking/
# learning_rule_proposals ohnehin nie hier geloescht werden (eigene Tabellen,
# von diesem Workflow gar nicht angefasst) -- "dauerhaft" ist damit bereits
# strukturell erfuellt, nicht nur per Frist. Zusaetzliche Sicherheit: evaluierte
# News werden nur geloescht, wenn KEINE trading.news_impact_tracking-Zeile mehr
# referenziert (NOT EXISTS-Check), damit Wirkungsanalyse-Grundlagen nie
# versehentlich vor Abschluss der Beobachtung verschwinden.
# ---------------------------------------------------------------------------

n_del_discarded_in, n_del_discarded_out = b.pg_exec_pair("Loesche irrelevante Rohnews (21 Tage)", [-400, -160], """
const sql = `DELETE FROM trading.news_items
  WHERE status = 'discarded' AND created_at < now() - interval '21 days';`;
return { json: { ...$json, sql, stufe: 'discarded_21d' } };
""")
b.link(n_trig1, n_del_discarded_in)
b.link(n_trig2, n_del_discarded_in)

n_del_failed_in, n_del_failed_out = b.pg_exec_pair("Loesche fehlgeschlagene News (30 Tage)", [-400, 0], """
const sql = `DELETE FROM trading.news_items
  WHERE status = 'failed' AND created_at < now() - interval '30 days';`;
return { json: { ...$json, sql, stufe: 'failed_30d' } };
""")
b.link(n_del_discarded_out, n_del_failed_in)

n_del_evaluated_in, n_del_evaluated_out = b.pg_exec_pair("Loesche alte evaluierte News (365 Tage, ohne Wirkungsdaten)", [-400, 160], """
const sql = `DELETE FROM trading.news_items ni
  WHERE ni.status = 'evaluated'
    AND ni.created_at < now() - interval '365 days'
    AND NOT EXISTS (
      SELECT 1 FROM trading.news_impact_tracking nit WHERE nit.news_id = ni.id
    );`;
return { json: { ...$json, sql, stufe: 'evaluated_365d' } };
""")
b.link(n_del_failed_out, n_del_evaluated_in)

# Datenqualitaetsmarkierung statt Loeschung fuer Zeilen ohne verwertbares
# Veroeffentlichungsdatum (published_at). created_at ist bei uns immer
# gesetzt (DEFAULT now(), NOT NULL) -- die urspruengliche Original-Luecke
# ("Datensaetze ohne Datum werden sofort geloescht") kann in diesem Schema
# strukturell nicht mehr auftreten, da die Loeschfristen ausschliesslich auf
# created_at rechnen, nie auf published_at.
n_mark_dq_in, n_mark_dq_out = b.pg_exec_pair("Markiere News ohne Veroeffentlichungsdatum", [-400, 320], """
const sql = `UPDATE trading.news_items
  SET metadata_json = metadata_json || '{"datenqualitaet_hinweis":"fehlendes_veroeffentlichungsdatum"}'::jsonb
  WHERE published_at IS NULL
    AND status IN ('evaluated','discarded')
    AND NOT (metadata_json ? 'datenqualitaet_hinweis');`;
return { json: { ...$json, sql, stufe: 'datenqualitaet_markierung' } };
""")
b.link(n_del_evaluated_out, n_mark_dq_in)

n_log_in, n_log_out = b.pg_exec_pair("Log Cleanup-Lauf", [-200, 0], GET_BUSINESS_DATE_JS + """

const sql = `INSERT INTO trading.pipeline_runs
  (run_id, workflow_name, stage_name, status, started_at, finished_at)
  VALUES (${pgStr('cleanup-' + getBusinessDate() + '-' + Date.now())}, '04 – Cleanup News-Tabellen', 'cleanup',
          'success', now(), now());`;
return { json: { ...$json, sql } };
""")
b.link(n_mark_dq_out, n_log_in)

b.write_and_validate(OUT)
