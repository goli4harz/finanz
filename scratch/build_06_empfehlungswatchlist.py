# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED, MATRIX_CRED, MATRIX_ROOM

OUT = r"C:\Users\olietz\Documents\finanz\06 – Empfehlungswatchlist – Agent V1.json"
ORIG = r"C:\Users\olietz\Downloads\Aktien\06 – Empfehlungswatchlist.json"

with open(ORIG, encoding="utf-8") as f:
    orig = json.load(f)
orig_nodes = {n["name"]: n for n in orig["nodes"]}

b = Builder("06 – Empfehlungswatchlist – Agent V1")

# ---------------------------------------------------------------------------
# 1. Zwei Trigger: eigener Zeitplan (unveraendert lauffaehig ohne Orchestrator)
#    UND Execute Workflow Trigger (fuer den Aufruf durch 00, uebergibt DRY_RUN
#    und optional REQUIRE_CONFIRMATION).
# ---------------------------------------------------------------------------
n_trig_schedule = b.add(dict(orig_nodes["Trigger: Empfehlungswatchlist (18:10)"], position=[-4000, 300]))

n_trig_exec = b.add({
    "parameters": {"workflowInputs": {"values": [{"name": "run_id"}, {"name": "DRY_RUN"}]}},
    "name": "Execute Workflow Trigger",
    "type": "n8n-nodes-base.executeWorkflowTrigger",
    "typeVersion": 1.1,
    "position": [-4000, 500]
})

n_normalize_input = b.add({
    "parameters": {
        "jsCode": "// Vereinheitlicht beide Trigger-Pfade auf ein gemeinsames Item mit\n"
                  "// DRY_RUN (Default false bei eigenstaendigem Zeitplan-Lauf) und optional\n"
                  "// REQUIRE_CONFIRMATION (aktuell als Konstante hier gesetzt -- kann spaeter\n"
                  "// zu einem echten Konfigurationswert werden, z.B. aus stock_instruments\n"
                  "// oder einer eigenen Einstellungstabelle).\n"
                  "const j = $json || {};\n"
                  "return [{ json: {\n"
                  "  run_id: j.run_id || ('standalone-' + Date.now()),\n"
                  "  DRY_RUN: j.DRY_RUN === true || j.DRY_RUN === 'true',\n"
                  "  REQUIRE_CONFIRMATION: false\n"
                  "} }];"
    },
    "name": "Trigger-Eingabe normalisieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-3820, 400]
})
b.link(n_trig_schedule, n_normalize_input)
b.link(n_trig_exec, n_normalize_input)

n_tech = b.add(dict(orig_nodes["DB: Technische Signale laden (Empf.)"], position=[-3616, 416]))
b.link(n_normalize_input, n_tech)

# ---------------------------------------------------------------------------
# 2. News-Quelle umgestellt: trading.news_assessments/news_items statt
#    stock_news_evaluated (Phase 4 Migration) -- nur heutige, starke News,
#    Feldnamen an das neue Schema angepasst (in "Empfehlungen: Abgleich
#    berechnen" unten nachgezogen).
# ---------------------------------------------------------------------------
n_news = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT ni.title AS titel, ni.published_at, ni.created_at, na.betroffene_ticker_json,\n"
                 "       na.wirkungsebene, na.wirkungsrichtung, na.wirkung_staerke,\n"
                 "       na.ticker_begruendung, na.wirkungs_begruendung\n"
                 "FROM trading.news_assessments na\n"
                 "JOIN trading.news_items ni ON ni.id = na.news_id\n"
                 "WHERE na.relevant = TRUE AND na.wirkung_staerke = 'hoch'\n"
                 "  AND (ni.published_at AT TIME ZONE 'Europe/Berlin')::date = (now() AT TIME ZONE 'Europe/Berlin')::date;",
        "options": {}
    },
    "name": "DB: News laden (Empf., trading.*)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3392, 416],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_tech, n_news)

n_empf_load = b.add(dict(orig_nodes["DB: Bestehende Empfehlungen laden"], position=[-3168, 416]))
b.link(n_news, n_empf_load)

# ---------------------------------------------------------------------------
# 3. Abgleich berechnen -- Kernlogik (News+Signal-Kombination, Hebelhinweis)
#    unveraendert uebernommen, nur die News-Feldzugriffe an trading.news_
#    assessments angepasst + SIMULATION-Marker in Grund-Texten ergaenzt +
#    REQUIRE_CONFIRMATION durchgereicht.
# ---------------------------------------------------------------------------
orig_code = orig_nodes["Empfehlungen: Abgleich berechnen"]["parameters"]["jsCode"]
new_code = orig_code.replace(
    "const heute = new Date().toISOString().substring(0, 10);\nconst zeitstempel = new Date().toISOString();",
    GET_BUSINESS_DATE_JS + "\nconst heute = getBusinessDate();\nconst zeitstempel = new Date().toISOString();\n"
    "const _triggerCtx = $('Trigger-Eingabe normalisieren').all()[0];\n"
    "const DRY_RUN = _triggerCtx && _triggerCtx.json ? _triggerCtx.json.DRY_RUN : false;\n"
    "const REQUIRE_CONFIRMATION = _triggerCtx && _triggerCtx.json ? _triggerCtx.json.REQUIRE_CONFIRMATION : false;"
)
new_code = new_code.replace("$('DB: News laden (Empf.)')", "$('DB: News laden (Empf., trading.*)')")
new_code = new_code.replace(
    "const d = String(n.datum_iso || n.datum || '');\n  if (!d.startsWith(heute)) continue;",
    "// Datumsfilter bereits per SQL (Europe/Berlin) erledigt -- hier nur noch inhaltlich filtern."
)
new_code = new_code.replace(
    "const genannt = Array.isArray(n.betroffene_ticker)\n    ? n.betroffene_ticker\n    : String(n.betroffene_ticker || '').split(',').map(t => t.trim()).filter(Boolean);",
    "const genannt = Array.isArray(n.betroffene_ticker_json) ? n.betroffene_ticker_json : [];"
)
new_code = new_code.replace(
    "const matchText = [n.titel, n.begruendung, n.begruendung_tickerbezug].filter(Boolean).join(' ');",
    "const matchText = [n.titel, n.wirkungs_begruendung, n.ticker_begruendung].filter(Boolean).join(' ');"
)
assert "betroffene_ticker_json" in new_code and "$('DB: News laden (Empf., trading.*)')" in new_code
# SIMULATION-Marker in beiden Grund-Texten (Auftrag Punkt 5: "Empfehlungen klar als
# Simulation kennzeichnen") + _dry_run/_require_confirmation an jedes Output-Item.
new_code = new_code.replace(
    "output.push({ json: {\n    _aktion: 'oeffnen',",
    "output.push({ json: {\n    _aktion: 'oeffnen', _dry_run: DRY_RUN, _require_confirmation: REQUIRE_CONFIRMATION,"
)
new_code = new_code.replace(
    "entry_grund: grund, letzte_aktualisierung: zeitstempel,",
    "entry_grund: '[SIMULATION - keine reale Order] ' + grund, letzte_aktualisierung: zeitstempel,"
)
new_code = new_code.replace(
    "output.push({ json: {\n    _aktion: 'schliessen',",
    "output.push({ json: {\n    _aktion: 'schliessen', _dry_run: DRY_RUN, _require_confirmation: REQUIRE_CONFIRMATION,"
)
new_code = new_code.replace(
    "exit_grund: `Gegensignal: ${grund}`,",
    "exit_grund: `[SIMULATION] Gegensignal: ${grund}`,"
)

n_abgleich = b.add({
    "parameters": {"jsCode": new_code},
    "name": "Empfehlungen: Abgleich berechnen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2944, 416]
})
b.link(n_empf_load, n_abgleich)

# ---------------------------------------------------------------------------
# 4. Aktion verzweigen: schliessen / oeffnen (bei REQUIRE_CONFIRMATION: nur
#    Vorschlag statt sofortigem Schreiben) / uebersprungen wegen Bestaetigung
# ---------------------------------------------------------------------------
n_if_schliessen = b.add(dict(orig_nodes["IF: Aktion = schließen?"], position=[-2720, 288]))
b.link(n_abgleich, n_if_schliessen)

n_db_schliessen = b.add(dict(orig_nodes["DB: Empfehlung schließen"], position=[-2496, 160]))
b.link(n_if_schliessen, n_db_schliessen, src_index=0)

n_if_confirmation = b.add({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{
                "leftValue": "={{ $json._require_confirmation }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True}
            }],
            "combinator": "and"
        },
        "options": {}
    },
    "name": "IF: Bestaetigung erforderlich?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-2496, 448]
})
b.link(n_if_schliessen, n_if_confirmation, src_index=1)

n_db_oeffnen = b.add(dict(orig_nodes["DB: Empfehlung öffnen"], position=[-2272, 520]))
b.link(n_if_confirmation, n_db_oeffnen, src_index=0)  # false = normal oeffnen

n_mark_vorschlag = b.add({
    "parameters": {
        "jsCode": "// REQUIRE_CONFIRMATION=true: kein DB-Write, nur Vorschlag fuer Matrix.\n"
                  "return [{ json: { ...$json, _aktion: 'vorschlag_ungespeichert', id: null } }];"
    },
    "name": "Als Vorschlag markieren (kein Write)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2272, 680]
})
b.link(n_if_confirmation, n_mark_vorschlag, src_index=1)  # true = nur Vorschlag

# ---------------------------------------------------------------------------
# 5. Schreibergebnisse zusammenfuehren + auf Erfolg pruefen, ERST DANACH
#    Matrix bauen und senden (behebt Bestand-Pruefpunkt 4: Matrix wurde
#    bisher unabhaengig vom Schreiberfolg verschickt).
# ---------------------------------------------------------------------------
n_merge_results = b.add({"parameters": {}, "name": "Schreibergebnisse zusammenfuehren", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2048, 400]})
b.link(n_db_schliessen, n_merge_results, dst_index=0)
b.link(n_db_oeffnen, n_merge_results, dst_index=1)

n_merge_vorschlag = b.add({"parameters": {}, "name": "Vorschlaege dazu mergen", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-1900, 500]})
b.link(n_merge_results, n_merge_vorschlag, dst_index=0)
b.link(n_mark_vorschlag, n_merge_vorschlag, dst_index=1)

n_verify = b.add({
    "parameters": {
        "jsCode": "// Nur Zeilen mit einer echten DB-id (erfolgreich geschrieben) ODER expliziten\n"
                  "// Vorschlaegen (id=null, bewusst nicht geschrieben) gehen in die Matrix-\n"
                  "// Nachricht ein. Ein fehlgeschlagener Write (kein id im Ergebnis, kein\n"
                  "// Vorschlag) wird stillschweigend AUS der Nachricht entfernt statt\n"
                  "// faelschlich als erfolgreich gemeldet zu werden.\n"
                  "const items = $input.all().map(i => i.json);\n"
                  "const verified = items.filter(j => j._aktion === 'vorschlag_ungespeichert' || (j.id !== undefined && j.id !== null && String(j.id).trim() !== ''));\n"
                  "return verified.map(j => ({ json: j }));"
    },
    "name": "Schreiberfolg verifizieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1700, 500]
})
b.link(n_merge_vorschlag, n_verify)

n_matrix_build_code = orig_nodes["Matrix: Zusammenfassung bauen"]["parameters"]["jsCode"]
n_matrix_build_code = n_matrix_build_code.replace(
    "const geschlossen = items.filter(i => i._aktion === 'schliessen');\nconst geoeffnet = items.filter(i => i._aktion === 'oeffnen');",
    "const geschlossen = items.filter(i => i._aktion === 'schliessen');\n"
    "const geoeffnet = items.filter(i => i._aktion === 'oeffnen');\n"
    "const vorschlaege = items.filter(i => i._aktion === 'vorschlag_ungespeichert');"
)
n_matrix_build_code = n_matrix_build_code.replace(
    "text += 'Hinweis: hypothetische Watchlist, keine echte Order, keine Anlageberatung.';",
    "if (vorschlaege.length) {\n"
    "  text += 'Vorschlaege (Bestaetigung erforderlich, noch NICHT gespeichert):\\n' + "
    "vorschlaege.map(v => `• ${v.ticker} (${v.richtung}) @ ${v.entry_kurs}`).join('\\n') + '\\n\\n';\n"
    "}\n"
    "text += '⚠️ SIMULATION: hypothetische Watchlist, keine echte Order, keine Anlageberatung.';"
)
n_matrix_build = b.add({
    "parameters": {"jsCode": n_matrix_build_code},
    "name": "Matrix: Zusammenfassung bauen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1500, 500]
})
b.link(n_verify, n_matrix_build)

n_matrix_send = b.add(dict(orig_nodes["Matrix: Empfehlungs-Update senden"], position=[-1300, 500]))
b.link(n_matrix_build, n_matrix_send)

b.write_and_validate(OUT)
