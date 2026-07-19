# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED, OPENAI_CRED

OUT = r"C:\Users\olietz\Documents\finanz\03a – News-Recherche-Agent.json"

b = Builder("03a – News-Recherche-Agent")

# ---------------------------------------------------------------------------
# Node-Verfuegbarkeits-Hinweis (siehe Docstring): dieses n8n-Projekt hat in
# keinem der 8 Original-Workflows einen @n8n/n8n-nodes-langchain.agent- oder
# Tool-Node im Einsatz -- nur den einfachen @n8n/n8n-nodes-langchain.openAi
# Chat-Node (bestaetigt in 03/05). Ein echter mehrstufiger Tool-Calling-Agent
# waere daher eine unbestaetigte, moeglicherweise nicht verfuegbare Node-
# Funktion. Stattdessen: "Retrieve-then-Generate" -- alle im Auftrag
# genannten "Werkzeuge" werden als deterministische n8n-Lese-Nodes VOR dem
# KI-Aufruf ausgefuehrt, ihr Ergebnis wird dem bestaetigten openAi-Node als
# strukturierter Kontext mitgegeben. Vorteil gegenueber einem echten Tool-
# Agenten: dem Modell wird technisch gar kein schreibfaehiges Werkzeug
# angeboten -- "Agent darf nicht loeschen/anlegen/traden" ist damit nicht nur
# eine Prompt-Regel, sondern strukturell erzwungen (es existiert kein Tool
# dafuer). Persistenz erfolgt ausschliesslich durch einen separaten,
# deterministischen Code+Postgres-Schritt NACH dem KI-Aufruf.
# ---------------------------------------------------------------------------

n_trigger = b.add({
    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 20 */2 * * 1-5"}]}},
    "name": "Trigger: Recherche-Agent (alle 2h, Werktage)",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.1,
    "position": [-2400, 0]
})

# ---------------------------------------------------------------------------
# 1. Zweitpass-Kandidaten laden: News, deren Ersteinordnung (03) wirkungsebene
#    = 'unklar' ergab und die noch nicht vom Recherche-Agenten bearbeitet
#    wurden (prompt_version-Marker verhindert Doppelverarbeitung -> idempotent).
# ---------------------------------------------------------------------------
n_load_candidates = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT DISTINCT ON (ni.id) ni.id, ni.news_key, ni.title, ni.url, ni.source, ni.published_at, na.betroffene_ticker_json\n"
                 "FROM trading.news_items ni\n"
                 "JOIN trading.news_assessments na ON na.news_id = ni.id\n"
                 "WHERE na.wirkungsebene = 'unklar'\n"
                 "  AND na.prompt_version <> 'news-recherche-agent-v1'\n"
                 "  AND ni.status = 'evaluated'\n"
                 "ORDER BY ni.id, na.created_at DESC\n"
                 "LIMIT 20;",
        "options": {}
    },
    "name": "DB: Zweitpass-Kandidaten laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2200, 0],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_load_candidates)

# ---------------------------------------------------------------------------
# 2. Werkzeug "Instrumententabelle lesen" (deckt zugleich Aliase/Ausschluss-
#    muster/Sektorinfo ab, da alles Spalten derselben Tabelle sind) -- einmal
#    pro Lauf, nicht pro News.
# ---------------------------------------------------------------------------
n_load_instruments = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT ticker, name, sektor, aliases_json, exclude_patterns_json, benchmark_symbol FROM trading.stock_instruments WHERE aktiv = TRUE ORDER BY sortierung;",
        "options": {}
    },
    "name": "Werkzeug: Instrumententabelle lesen",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2200, 200],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_load_instruments)

n_instruments_pack = b.add({
    "parameters": {
        "jsCode": "return [{ json: { instruments: $input.all().map(i => i.json) } }];"
    },
    "name": "Instrumente buendeln",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2000, 200]
})
b.link(n_load_instruments, n_instruments_pack)

n_merge_ctx = b.add({
    "parameters": {},
    "name": "Kandidaten + Instrumente zusammenfuehren",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [-1800, 100]
})
b.link(n_load_candidates, n_merge_ctx, dst_index=0)
b.link(n_instruments_pack, n_merge_ctx, dst_index=1)

# ---------------------------------------------------------------------------
# 3. Pro Kandidat: Werkzeug "vollstaendigen Artikel laden" + "aehnliche News
#    suchen" + "fruehere Meldungen zum Ticker lesen", dann KI-Aufruf.
#    Ueber SplitInBatches (Batchgroesse 1), da pro News ein individueller
#    HTTP-Abruf + individuelle Postgres-Aehnlichkeitsabfrage noetig ist.
# ---------------------------------------------------------------------------
n_split = b.add({
    "parameters": {"batchSize": 1, "options": {}},
    "name": "Loop: 1 News pro Durchlauf",
    "type": "n8n-nodes-base.splitInBatches",
    "typeVersion": 3,
    "position": [-1600, 100]
})
b.link(n_merge_ctx, n_split)

n_route = b.add({
    "parameters": {
        "jsCode": "// Trennt in diesem Merge-Item entweder einen echten Kandidaten (hat news_key)\n"
                  "// oder das einmalige Instrumente-Bündel (hat 'instruments'). Nur Kandidaten\n"
                  "// werden weiterverarbeitet, das Instrumente-Item wird separat per $('...')\n"
                  "// referenziert, nicht durch die Loop-Kette geschleift.\n"
                  "const j = $json;\nif (j.news_key) return [{ json: j }];\nreturn [];"
    },
    "name": "Nur echte Kandidaten weiterreichen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1400, 40]
})
# SplitInBatches: Index 0 = "fertig", Index 1 = "aktueller Batch" (siehe
# Korrektur in build_03_news_ingestion.py, live-bestaetigt).
b.link(n_split, n_route, src_index=1)

n_fetch_article = b.add({
    "parameters": {
        "url": "={{ $json.url }}",
        "options": {
            "response": {"response": {"neverError": True, "responseFormat": "text"}},
            "timeout": 15000
        }
    },
    "name": "Werkzeug: Vollstaendigen Artikel laden",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [-1200, -80],
    "onError": "continueRegularOutput",
    "settings": {"retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000}
})
b.link(n_route, n_fetch_article)

n_similar = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT title FROM trading.news_items\n"
                 "WHERE id <> {{ $('Nur echte Kandidaten weiterreichen').item.json.id }}\n"
                 "  AND created_at >= now() - interval '14 days'\n"
                 "ORDER BY created_at DESC LIMIT 40;",
        "options": {}
    },
    "name": "Werkzeug: Aehnliche News suchen",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-1200, 80],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_route, n_similar)

n_ticker_history = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT ni.title, na.wirkungsrichtung, na.created_at\n"
                 "FROM trading.news_assessments na\n"
                 "JOIN trading.news_items ni ON ni.id = na.news_id\n"
                 "WHERE na.betroffene_ticker_json @> '{{ JSON.stringify($('Nur echte Kandidaten weiterreichen').item.json.betroffene_ticker_json || []).replace(/'/g, \"''\") }}'::jsonb\n"
                 "  AND na.betroffene_ticker_json <> '[]'::jsonb\n"
                 "ORDER BY na.created_at DESC LIMIT 10;",
        "options": {}
    },
    "name": "Werkzeug: Fruehere Meldungen zum Ticker lesen",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-1200, 220],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_route, n_ticker_history)

n_merge_tools = b.add({
    "parameters": {},
    "name": "Werkzeug-Ergebnisse buendeln",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [-1000, 80]
})
b.link(n_fetch_article, n_merge_tools, dst_index=0)
b.link(n_similar, n_merge_tools, dst_index=1)

n_merge_tools2 = b.add({
    "parameters": {},
    "name": "Werkzeug-Ergebnisse + Kandidat",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [-800, 80]
})
b.link(n_merge_tools, n_merge_tools2, dst_index=0)
b.link(n_ticker_history, n_merge_tools2, dst_index=1)

n_build_prompt = b.add({
    "parameters": {
        "jsCode": """const cand = $('Nur echte Kandidaten weiterreichen').item.json;
const article = $('Werkzeug: Vollstaendigen Artikel laden').item.json;
const similar = $('Werkzeug: Aehnliche News suchen').all().map(i => i.json.title);
const tickerHist = $('Werkzeug: Fruehere Meldungen zum Ticker lesen').all().map(i => i.json);
const instruments = $('Instrumente buendeln').first().json.instruments;

const articleText = typeof article === 'string' ? article : (article && article.data) || '';

const systemPrompt = `Du bist ein sorgfaeltiger Recherche-Analyst fuer ein automatisiertes Aktien-Beobachtungssystem.
Eine bereits grob eingeordnete Nachricht konnte in der Ersteinordnung keiner klaren Wirkungsebene zugeordnet werden
(wirkungsebene='unklar'). Deine Aufgabe: mit den bereitgestellten Recherche-Informationen (Artikeltext, Instrumentenliste
mit Aliasen/Ausschlussmustern, aehnliche juengere News, fruehere Meldungen zu moeglicherweise betroffenen Tickern)
eine fundiertere Einordnung treffen.

Regeln:
- Keine Anlageberatung, keine Kauf-/Verkaufsempfehlungen, keine erfundenen Fakten.
- Nutze die Alias-/Ausschlussmuster der Instrumente, um Namensgleichheiten korrekt aufzuloesen
  (z.B. 'RWE' im Fussballkontext ausschliessen, 'Bayer' vs 'Bayern' unterscheiden).
- ist_wiederholung=true, wenn der Artikelinhalt inhaltlich bereits durch eine der 'aehnliche News'-Titel abgedeckt ist.
- Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt exakt in diesem Schema, kein Markdown, kein Text davor/danach:
{
  "news_id": ${cand.id},
  "relevant": true,
  "status": "evaluated",
  "wirkungsebene": "aktie",
  "betroffene_ticker": [],
  "betroffene_sektoren": [],
  "wirkungsrichtung": "positiv",
  "wirkung_staerke": "mittel",
  "sentiment": "positiv",
  "konfidenz": 78,
  "news_kategorie": "",
  "ticker_begruendung": "",
  "wirkungs_begruendung": "",
  "ist_wiederholung": false,
  "referenz_news_ids": [],
  "unsicherheiten": [],
  "modell_version": "",
  "prompt_version": "news-recherche-agent-v1"
}
wirkungsrichtung nur aus: positiv, negativ, neutral, unklar.
wirkung_staerke nur aus: niedrig, mittel, hoch, unklar.`;

const userPrompt = `NACHRICHT:
Titel: ${cand.title}
Quelle: ${cand.source}
URL: ${cand.url}

ARTIKELTEXT (best effort, kann leer/unvollstaendig sein):
${String(articleText).substring(0, 4000)}

INSTRUMENTENLISTE (Ticker, Name, Sektor, Aliase, Ausschlussmuster):
${JSON.stringify(instruments)}

AEHNLICHE JUENGERE NEWS (letzte 14 Tage, Titel):
${JSON.stringify(similar)}

FRUEHERE MELDUNGEN ZU MOEGLICHERWEISE BETROFFENEN TICKERN:
${JSON.stringify(tickerHist)}`;

return { json: { cand, systemPrompt, userPrompt } };
"""
    },
    "name": "Baue Recherche-Prompt",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-600, 80]
})
b.link(n_merge_tools2, n_build_prompt)

n_ki = b.add({
    "parameters": {
        "modelId": {"__rl": True, "value": "gpt-5.4-mini", "mode": "list", "cachedResultName": "GPT-5.4-MINI"},
        "responses": {"values": [
            {"role": "system", "content": "={{ $json.systemPrompt }}"},
            {"content": "={{ $json.userPrompt }}"}
        ]},
        "builtInTools": {},
        "options": {"maxTokens": 1200}
    },
    "name": "KI: Recherche-Bewertung",
    "type": "@n8n/n8n-nodes-langchain.openAi",
    "typeVersion": 2.3,
    "position": [-400, 80],
    "retryOnFail": True,
    "waitBetweenTries": 5000,
    "credentials": {"openAiApi": OPENAI_CRED}
})
b.link(n_build_prompt, n_ki)

n_parse = b.add({
    "parameters": {
        "jsCode": """function getAiText(resp) {
  if (typeof resp === 'string') return resp;
  if (resp && Array.isArray(resp.output)) {
    const msg = resp.output.find(o => o.type === 'message');
    const part = msg && Array.isArray(msg.content) ? msg.content.find(c => c.type === 'output_text') : null;
    if (part && part.text) return part.text;
  }
  if (resp && resp.choices && resp.choices[0] && resp.choices[0].message) return resp.choices[0].message.content || '';
  return JSON.stringify(resp || '');
}
function parseObj(text) {
  let t = String(text || '').trim().replace(/^```json\\s*/i,'').replace(/^```\\s*/i,'').replace(/```\\s*$/i,'').trim();
  try { const p = JSON.parse(t); return (p && typeof p === 'object') ? p : null; } catch(e) {}
  const s = t.indexOf('{'); const e = t.lastIndexOf('}');
  if (s >= 0 && e > s) { try { const p = JSON.parse(t.substring(s, e+1)); return (p && typeof p === 'object') ? p : null; } catch(err) {} }
  return null;
}

const cand = $('Baue Recherche-Prompt').item.json.cand;
const parsed = parseObj(getAiText($json));

if (!parsed) {
  return [{ json: { _action: 'retry', news_id: cand.id, _error: 'Recherche-Agent JSON nicht parsebar' } }];
}

const enumOk = (v, allowed) => allowed.includes(v) ? v : 'unklar';

return [{ json: {
  _action: 'persist',
  news_id: cand.id,
  relevant: parsed.relevant !== false,
  wirkungsebene: parsed.wirkungsebene || 'unklar',
  betroffene_ticker: Array.isArray(parsed.betroffene_ticker) ? parsed.betroffene_ticker : [],
  betroffene_sektoren: Array.isArray(parsed.betroffene_sektoren) ? parsed.betroffene_sektoren : [],
  wirkungsrichtung: enumOk(parsed.wirkungsrichtung, ['positiv','negativ','neutral','unklar']),
  wirkung_staerke: enumOk(parsed.wirkung_staerke, ['niedrig','mittel','hoch','unklar']),
  sentiment: parsed.sentiment || 'unklar',
  konfidenz: Number(parsed.konfidenz) || 0,
  news_kategorie: parsed.news_kategorie || '',
  ticker_begruendung: parsed.ticker_begruendung || '',
  wirkungs_begruendung: parsed.wirkungs_begruendung || '',
  ist_wiederholung: !!parsed.ist_wiederholung,
  referenz_news_ids: Array.isArray(parsed.referenz_news_ids) ? parsed.referenz_news_ids : [],
  unsicherheiten: Array.isArray(parsed.unsicherheiten) ? parsed.unsicherheiten : []
} }];
"""
    },
    "name": "Antwort validieren (Schema)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-200, 80]
})
b.link(n_ki, n_parse)

n_persist_in, n_persist_out = b.pg_exec_pair("Recherche-Ergebnis persistieren", [0, 80], """
const j = $json;
let sql;

if (j._action === 'persist') {
  const status = j.ist_wiederholung ? 'discarded' : (j.relevant ? 'evaluated' : 'discarded');
  sql = `INSERT INTO trading.news_assessments
    (news_id, relevant, wirkungsebene, betroffene_ticker_json, betroffene_sektoren_json, wirkungsrichtung,
     wirkung_staerke, sentiment, konfidenz, news_kategorie, ticker_begruendung, wirkungs_begruendung,
     ist_wiederholung, referenz_news_ids_json, unsicherheiten_json, prompt_version)
    VALUES (${pgNum(j.news_id)}, ${pgBool(j.relevant)}, ${pgStr(j.wirkungsebene)}, ${pgJson(j.betroffene_ticker)},
            ${pgJson(j.betroffene_sektoren)}, ${pgStr(j.wirkungsrichtung)}, ${pgStr(j.wirkung_staerke)},
            ${pgStr(j.sentiment)}, ${pgNum(j.konfidenz)}, ${pgStr(j.news_kategorie)}, ${pgStr(j.ticker_begruendung)},
            ${pgStr(j.wirkungs_begruendung)}, ${pgBool(j.ist_wiederholung)}, ${pgJson(j.referenz_news_ids)},
            ${pgJson(j.unsicherheiten)}, 'news-recherche-agent-v1');
   UPDATE trading.news_items SET status = ${pgStr(status)}, updated_at = now() WHERE id = ${pgNum(j.news_id)};`;
} else {
  sql = `UPDATE trading.news_items SET
    last_error = ${pgStr(j._error)}, last_attempt_at = now(), updated_at = now()
   WHERE id = ${pgNum(j.news_id)};`;
}

return { json: { ...j, sql } };
""")
b.link(n_parse, n_persist_in)

# ---------------------------------------------------------------------------
# 4. Agentenlauf protokollieren (trading.agent_runs)
# ---------------------------------------------------------------------------
n_agentlog_in, n_agentlog_out = b.pg_exec_pair("Agentenlauf protokollieren", [200, 80], GET_BUSINESS_DATE_JS + """

const j = $json;
const sql = `INSERT INTO trading.agent_runs
  (run_id, agent_name, agent_role, model_name, prompt_version, input_reference, output_reference, status, started_at, finished_at)
  VALUES (${pgStr('news-recherche-' + getBusinessDate() + '-' + Date.now())}, 'news-recherche-agent', 'recherche',
          'gpt-5.4-mini', 'news-recherche-agent-v1', ${pgStr('news_id=' + j.news_id)}, ${pgStr(j._action)},
          ${pgStr(j._action === 'persist' ? 'success' : 'failed')}, now(), now());`;
return { json: { ...j, sql } };
""")
b.link(n_persist_out, n_agentlog_in)
b.link(n_agentlog_out, n_split)

b.write_and_validate(OUT)
