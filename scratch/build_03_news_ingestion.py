# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED, MATRIX_CRED, OPENAI_CRED, MATRIX_ROOM

OUT = r"C:\Users\olietz\Documents\finanz\03 – News Ingestion stündlich – Agent V1.json"
ORIG = r"C:\Users\olietz\Downloads\Aktien\03 – News Ingestion stündlich.json"

with open(ORIG, encoding="utf-8") as f:
    orig = json.load(f)
orig_nodes = {n["name"]: n for n in orig["nodes"]}

b = Builder("03 – News Ingestion stündlich – Agent V1")

# ---------------------------------------------------------------------------
# 1. Trigger (unveraendert)
# ---------------------------------------------------------------------------
n_trigger = b.add(dict(orig_nodes["Trigger: Nachrichten (stündlich)"], position=[-5000, 1712]))

# ---------------------------------------------------------------------------
# 2. RSS laden/filtern/Fehlerpfad (unveraendert uebernommen)
# ---------------------------------------------------------------------------
n_rss = b.add(dict(orig_nodes["RSS-Feeds laden & filtern"], position=[-4800, 1712]))
b.link(n_trigger, n_rss)

n_rss_err = b.add(dict(orig_nodes["RSS: Fehler prüfen"], position=[-4600, 1712]))
b.link(n_rss, n_rss_err)

n_if_rss_err = b.add(dict(orig_nodes["IF: RSS fehlgeschlagen?"], position=[-4400, 1712]))
b.link(n_rss_err, n_if_rss_err)

n_matrix_rss_err = b.add(dict(orig_nodes["Matrix: RSS-Fehler-Alert"], position=[-4200, 1800]))
b.link(n_if_rss_err, n_matrix_rss_err, src_index=0)

n_filter_echt = b.add(dict(orig_nodes["Filter: Nur echte Nachrichten"], position=[-4200, 1600]))
b.link(n_if_rss_err, n_filter_echt, src_index=1)

# ---------------------------------------------------------------------------
# 3. news_key erzeugen -- Europe/Berlin statt UTC (Bestand-Pruefpunkt 8 fix)
# ---------------------------------------------------------------------------
n_newskey = b.add({
    "parameters": {
        "mode": "runOnceForEachItem",
        "jsCode": GET_BUSINESS_DATE_JS + """

function normalizeTitle(raw) {
  return String(raw || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .toLowerCase()
    .replace(/[^a-z0-9äöüß\\s]/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim()
    .substring(0, 160);
}

const heute = getBusinessDate();
const link  = ($json.link || '').trim();
const quelle = ($json.quelle || 'unbekannt').trim();
const titel  = $json.titel || '';

const news_key = link
  ? `${heute}|${link}`
  : `${heute}|${quelle}|${normalizeTitle(titel)}`;

return {
  json: {
    ...$json,
    news_key
  }
};
"""
    },
    "name": "News: news_key erzeugen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-4000, 1600]
})
b.link(n_filter_echt, n_newskey)

# ---------------------------------------------------------------------------
# 4. Einmal-Trigger (genau 1 Item, unabhaengig von der Anzahl News),
#    faechert auf: (a) Dedup-Lookup, (b) faellige News fuer diesen Lauf
# ---------------------------------------------------------------------------
n_once = b.add({
    "parameters": {
        "jsCode": "// Reduziert beliebig viele Input-Items auf genau 1 Item, damit die\n"
                  "// nachfolgenden Postgres-Abfragen nicht pro News-Item, sondern einmal\n"
                  "// pro Lauf ausgefuehrt werden (gleiches Prinzip wie im Original 'Dedup:\n"
                  "// DB-Lesen einmal starten').\nreturn [{ json: { _trigger: true } }];"
    },
    "name": "Einmal-Trigger (Dedup+Faellige)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-4000, 1400]
})
b.link(n_newskey, n_once)

# ---------------------------------------------------------------------------
# 5. Dedup-Lookup gegen trading.news_items (35 Tage Lookback statt volle
#    Tabelle -- fixt Bestand-Pruefpunkt 6)
# ---------------------------------------------------------------------------
n_dedup_load = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT news_key, url AS link, title AS titel FROM trading.news_items WHERE created_at >= now() - interval '35 days';",
        "options": {}
    },
    "name": "DB: Bekannte News laden (35 Tage)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3800, 1300],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_once, n_dedup_load)

n_known_build = b.add({
    "parameters": {
        "jsCode": "const rows = $input.all().map(i => i.json || {});\n"
                  "return [{ json: {\n"
                  "  known_keys: rows.flatMap(r => [r.news_key, r.link].filter(Boolean)),\n"
                  "  known_titles: rows.map(r => r.titel).filter(Boolean)\n"
                  "} }];"
    },
    "name": "Baue Known-Keys/Titles",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-3600, 1300]
})
b.link(n_dedup_load, n_known_build)

n_dedup_merge = b.add({
    "parameters": {},
    "name": "Dedup: News + Keys sync",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [-3400, 1450]
})
b.link(n_newskey, n_dedup_merge, dst_index=0)
b.link(n_known_build, n_dedup_merge, dst_index=1)

# ---------------------------------------------------------------------------
# 6. Duplikat-Check (Jaccard-Logik unveraendert uebernommen)
# ---------------------------------------------------------------------------
n_dup_check = b.add(dict(orig_nodes["News: Duplikat-Check"], position=[-3200, 1450]))
b.link(n_dedup_merge, n_dup_check)

n_if_neu = b.add(dict(orig_nodes["IF: News neu?"], position=[-3000, 1450]))
b.link(n_dup_check, n_if_neu)

# ---------------------------------------------------------------------------
# 7. Neue News als 'pending' speichern (Postgres, ON CONFLICT DO NOTHING ->
#    idempotent bei erneutem Lauf)
# ---------------------------------------------------------------------------
n_save_new_in, n_save_new_out = b.pg_exec_pair("Neue News speichern", [-2800, 1450], """
const j = $json;
const sql = `INSERT INTO trading.news_items
  (news_key, title, url, source, published_at, status)
  VALUES (${pgStr(j.news_key)}, ${pgStr(j.titel)}, ${pgStr(j.link || null)}, ${pgStr(j.quelle)},
          ${j.datum_iso ? pgStr(j.datum_iso) : 'NULL'}, 'pending')
  ON CONFLICT (news_key) DO NOTHING;`;
return { json: { ...j, sql } };
""")
b.link(n_if_neu, n_save_new_in, src_index=0)

# ---------------------------------------------------------------------------
# 8. Faellige News fuer DIESEN Lauf laden (pending ODER retry mit
#    faelligem next_retry_at) -- laeuft erst NACH den Neu-Inserts (n8n
#    wartet je Node auf alle Input-Items, bevor der naechste Node startet),
#    damit auch in diesem Lauf frisch eingefuegte News direkt mit bewertet
#    werden. Zusaetzlich per Einmal-Trigger auf genau 1 Ausfuehrung reduziert,
#    da 'Neue News speichern' pro Item durchlaeuft.
# ---------------------------------------------------------------------------
n_once2 = b.add({
    "parameters": {"jsCode": "return [{ json: { _trigger: true } }];"},
    "name": "Einmal-Trigger (Faellige laden)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2600, 1450]
})
b.link(n_save_new_out, n_once2)

n_due_load = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT id, news_key, title AS titel, url AS link, source AS quelle, published_at AS datum_iso, retry_count\n"
                 "FROM trading.news_items\n"
                 "WHERE status = 'pending' OR (status = 'retry' AND (next_retry_at IS NULL OR next_retry_at <= now()))\n"
                 "ORDER BY created_at ASC\n"
                 "LIMIT 300;",
        "options": {}
    },
    "name": "DB: Faellige News laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2400, 1450],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_once2, n_due_load)

# ---------------------------------------------------------------------------
# 9. Batch-Verarbeitung: 15 News pro KI-Aufruf statt unbegrenzt (fixt den
#    im Auftrag genannten Batchgroessen-Punkt); Loop ueber SplitInBatches.
# ---------------------------------------------------------------------------
n_split = b.add({
    "parameters": {"batchSize": 15, "options": {}},
    "name": "Batch: 15 News pro KI-Aufruf",
    "type": "n8n-nodes-base.splitInBatches",
    "typeVersion": 3,
    "position": [-2200, 1450]
})
b.link(n_due_load, n_split)

n_build_batch = b.add({
    "parameters": {
        "jsCode": "// Baut das news_batch-Array fuer die KI (id = echte trading.news_items.id,\n"
                  "// nicht mehr Array-Index -> robustere Rueckzuordnung, ersetzt die vorherige\n"
                  "// $getWorkflowStaticData-Zwischenspeicherung vollstaendig.\n"
                  "const items = $input.all().map(i => i.json);\n"
                  "const news_batch = items.map(j => ({\n"
                  "  id: j.id,\n"
                  "  type: 'stock_news',\n"
                  "  titel: j.titel,\n"
                  "  beschreibung: '',\n"
                  "  quelle: j.quelle\n"
                  "}));\n"
                  "return [{ json: { news_batch, _originals: items } }];"
    },
    "name": "Baue Batch-Payload",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2000, 1450]
})
# SplitInBatches-Ausgaenge: Index 0 = "fertig" (alle Batches durch), Index 1 =
# "aktueller Batch" -- per Live-Test bestaetigt (00-Item-Ausgabe bei Index 0,
# 15-Item-Batch bei Index 1 beim ersten Durchlauf), nicht wie urspruenglich
# angenommen. Kein lokales Beispiel dieses Node-Typs in den 8 Original-
# Workflows vorhanden, daher beim ersten Bau falsch geraten.
b.link(n_split, n_build_batch, src_index=1)

n_ki = b.add(dict(orig_nodes["KI: Nachricht bewerten"], position=[-1800, 1450]))
b.link(n_build_batch, n_ki)

n_ki_parse = b.add({
    "parameters": {
        "jsCode": """// Robustes Parsing wie im Original, aber mit klarer retry/evaluated-
// Zuordnung statt eines ungefilterten Debug-Fallback-Datensatzes.
function getAiText(resp) {
  if (typeof resp === 'string') return resp;
  if (resp && Array.isArray(resp.output)) {
    const msg = resp.output.find(o => o.type === 'message');
    const part = msg && Array.isArray(msg.content) ? msg.content.find(c => c.type === 'output_text') : null;
    if (part && part.text) return part.text;
  }
  if (resp && resp.choices && resp.choices[0] && resp.choices[0].message) return resp.choices[0].message.content || '';
  if (resp && typeof resp.content === 'string') return resp.content;
  return JSON.stringify(resp || '');
}

function parseKiArray(text) {
  let t = String(text || '').trim();
  t = t.replace(/^```json\\s*/i, '').replace(/^```\\s*/i, '').replace(/```\\s*$/i, '').trim();
  try {
    const p = JSON.parse(t);
    if (Array.isArray(p)) return p;
  } catch (e) {}
  const start = t.indexOf('[');
  const end = t.lastIndexOf(']');
  if (start >= 0 && end > start) {
    try {
      const p = JSON.parse(t.substring(start, end + 1));
      if (Array.isArray(p)) return p;
    } catch (e) {}
  }
  return null;
}

const originals = $('Baue Batch-Payload').item.json._originals;
const rawText = getAiText($json);
const bewertungen = parseKiArray(rawText);

const results = [];

if (!bewertungen) {
  // Kompletter Parse-Fehlschlag: ALLE News dieses Batches auf retry setzen,
  // statt einen leeren Debug-Datensatz in die DB zu schreiben.
  for (const orig of originals) {
    results.push({ json: { _action: 'retry', _origin: orig, _error: 'KI-Antwort nicht als JSON-Array parsebar' } });
  }
  return results;
}

const byId = new Map(bewertungen.filter(x => x && x.id !== undefined).map(x => [String(x.id), x]));

for (const orig of originals) {
  const b = byId.get(String(orig.id));
  if (!b) {
    results.push({ json: { _action: 'retry', _origin: orig, _error: 'Keine Bewertung fuer diese News in der KI-Antwort enthalten' } });
    continue;
  }
  const relevant = b.relevanz && b.relevanz !== 'irrelevant';
  results.push({ json: {
    _action: 'persist',
    _origin: orig,
    news_id: orig.id,
    relevant,
    relevanz: b.relevanz || 'unbekannt',
    sentiment: b.sentiment || 'unklar',
    kurswirkung: b.kurswirkung || 'unklar',
    bezug: b.bezug || '',
    verwendung: b.verwendung || 'speichern',
    score: b.score,
    dringlichkeit: b.dringlichkeit || 'beobachten',
    begruendung: b.begruendung || '',
    betroffene_ticker: Array.isArray(b.betroffene_ticker) ? b.betroffene_ticker : [],
    wirkungsebene: b.wirkungsebene || 'unklar',
    wirkungsrichtung: ['positiv','negativ','neutral','unklar'].includes(b.wirkungsrichtung) ? b.wirkungsrichtung : 'unklar',
    wirkung_staerke: ['niedrig','mittel','hoch','unklar'].includes(b.wirkung_staerke) ? b.wirkung_staerke : 'unklar',
    begruendung_tickerbezug: b.begruendung_tickerbezug || '',
    titel: orig.titel,
    link: orig.link
  } });
}

return results;
"""
    },
    "name": "KI-Bewertung aufbereiten",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1600, 1450]
})
b.link(n_ki, n_ki_parse)

# ---------------------------------------------------------------------------
# 10. Ergebnis persistieren: entweder Assessment+Status (evaluated/discarded)
#     oder retry-Markierung mit Backoff/Failed-Uebergang nach 5 Versuchen.
# ---------------------------------------------------------------------------
n_persist_in, n_persist_out = b.pg_exec_pair("Ergebnis persistieren", [-1400, 1450], """
const j = $json;
let sql;

if (j._action === 'persist') {
  const status = j.relevant ? 'evaluated' : 'discarded';
  sql = `INSERT INTO trading.news_assessments
    (news_id, relevant, wirkungsebene, betroffene_ticker_json, wirkungsrichtung, wirkung_staerke,
     sentiment, news_kategorie, ticker_begruendung, wirkungs_begruendung, prompt_version)
    VALUES (${pgNum(j.news_id)}, ${pgBool(j.relevant)}, ${pgStr(j.wirkungsebene)}, ${pgJson(j.betroffene_ticker)},
            ${pgStr(j.wirkungsrichtung)}, ${pgStr(j.wirkung_staerke)}, ${pgStr(j.sentiment)}, ${pgStr(j.verwendung)},
            ${pgStr(j.begruendung_tickerbezug)}, ${pgStr(j.begruendung)}, ${pgStr('news-ingestion-v1')});
   UPDATE trading.news_items SET status = ${pgStr(status)}, updated_at = now() WHERE id = ${pgNum(j.news_id)};`;
} else {
  const orig = j._origin || {};
  const retryCount = pgNum(orig.retry_count) === 'NULL' ? 0 : Number(orig.retry_count) + 1;
  const nextStatus = retryCount >= 5 ? 'failed' : 'retry';
  const backoffMinutes = retryCount * 15;
  sql = `UPDATE trading.news_items SET
    status = ${pgStr(nextStatus)},
    retry_count = ${pgNum(retryCount)},
    last_error = ${pgStr(j._error)},
    last_attempt_at = now(),
    next_retry_at = now() + interval '${backoffMinutes} minutes',
    updated_at = now()
   WHERE id = ${pgNum(orig.id)};`;
}

return { json: { ...j, sql } };
""")
b.link(n_ki_parse, n_persist_in)

# ---------------------------------------------------------------------------
# 11. Matrix-Alert bei hoher Relevanz (unveraendert uebernommen, filtert
#     retry-Items automatisch weg da diese kein relevanz='hoch' Feld haben)
# ---------------------------------------------------------------------------
n_filter_hoch = b.add(dict(orig_nodes["Filter: Hohe Relevanz → Matrix"], position=[-1200, 1300]))
b.link(n_persist_out, n_filter_hoch)

n_matrix_code = b.add(dict(orig_nodes["Code in JavaScript"], position=[-1000, 1300]))
b.link(n_filter_hoch, n_matrix_code)

n_matrix_send = b.add(dict(orig_nodes["Matrix Alert: Wichtige Nachricht"], position=[-800, 1300]))
b.link(n_matrix_code, n_matrix_send)

# Loop-Rueckfuehrung: sowohl der Matrix-Zweig-Ausgang als auch (fuer Items
# ohne hohe Relevanz) der direkte Filter-Ausgang muessen zur naechsten
# SplitInBatches-Runde zurueckfuehren.
b.link(n_matrix_send, n_split)
b.link(n_filter_hoch, n_split, src_index=1)  # Filter-Node: Index 1 = nicht bestanden

b.write_and_validate(OUT)
