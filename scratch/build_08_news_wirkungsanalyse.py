# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED

OUT = r"C:\Users\olietz\Documents\finanz\08 – News-Wirkungsanalyse.json"

b = Builder("08 – News-Wirkungsanalyse")

# Preisquelle: stock_price_history wird laut ARCHITEKTUR_BESTAND.md von
# KEINEM der 8 Original-Workflows befuellt (Herkunft ungeklaert). Stattdessen
# genutzt: stock_technical_signals (taeglich von 02 geschrieben, enthaelt
# aktueller_kurs+datum je Ticker) und stock_market_context (taeglich von 02b
# geschrieben, enthaelt aktueller_kurs+datum je Benchmark-Symbol) -- beide
# akkumulieren dadurch automatisch genau die Tages-Schlusskurshistorie, die
# hier gebraucht wird, ohne neue Datenquelle zu erfinden.

n_trigger = b.add({
    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 0 19 * * 1-5"}]}},
    "name": "Trigger: Wirkungsanalyse (19:00 Werktage)",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.1,
    "position": [-3000, 0]
})

# ---------------------------------------------------------------------------
# 1. Neue (News,Ticker)-Paare ohne Tracking-Zeile finden
# ---------------------------------------------------------------------------
n_new_pairs = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT ni.id AS news_id, ni.news_key, ni.published_at, ni.created_at,\n"
                 "       na.wirkungsrichtung, na.wirkung_staerke, na.konfidenz, na.news_kategorie,\n"
                 "       na.betroffene_ticker_json\n"
                 "FROM trading.news_items ni\n"
                 "JOIN trading.news_assessments na ON na.news_id = ni.id\n"
                 "WHERE na.relevant = TRUE\n"
                 "  AND jsonb_array_length(na.betroffene_ticker_json) > 0\n"
                 "  AND NOT EXISTS (SELECT 1 FROM trading.news_impact_tracking nit WHERE nit.news_id = ni.id)\n"
                 "ORDER BY ni.id;",
        "options": {}
    },
    "name": "DB: Neue News-Ticker-Paare laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2800, -160],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_new_pairs)

n_expand_pairs = b.add({
    "parameters": {
        "jsCode": GET_BUSINESS_DATE_JS + """

// Bestimmt anhand der Veroeffentlichungszeit (Europe/Berlin) den Ausgangskurs-
// Fall gemaess Auftrag: vor Handelsbeginn (<9:00) / waehrend Handelszeit
// (9:00-17:30, vorerst Vortagesschluss, Intraday-Ergaenzung spaeter noetig -
// siehe Kommentar unten) / nach Handelsende (>17:30).
function berlinHour(iso) {
  const d = new Date(iso);
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Berlin', hour: '2-digit', hour12: false }).formatToParts(d);
  return Number(parts.find(p => p.type === 'hour').value);
}

const rows = $input.all().map(i => i.json);
const out = [];

for (const r of rows) {
  const tickers = Array.isArray(r.betroffene_ticker_json) ? r.betroffene_ticker_json : [];
  const pubIso = r.published_at || r.created_at;
  const hour = berlinHour(pubIso);
  const newsDate = getBusinessDate(new Date(pubIso));

  let baselineCase;
  if (hour < 9) baselineCase = 'vor_handelsbeginn';
  else if (hour < 17) baselineCase = 'waehrend_handelszeit'; // 17:30 vereinfacht auf Stunde 17
  else baselineCase = 'nach_handelsende';

  for (const ticker of tickers) {
    out.push({ json: {
      news_id: r.news_id,
      news_key: r.news_key,
      ticker: String(ticker).trim(),
      news_date: newsDate,
      publication_timestamp: pubIso,
      predicted_direction: r.wirkungsrichtung,
      predicted_strength: r.wirkung_staerke,
      prediction_confidence: r.konfidenz,
      news_category: r.news_kategorie,
      source: r.source,
      baseline_case: baselineCase
    } });
  }
}

return out;
"""
    },
    "name": "Baseline-Fall je (News,Ticker) bestimmen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2600, -160]
})
b.link(n_new_pairs, n_expand_pairs)

# ---------------------------------------------------------------------------
# 2. Bereits offene Tracking-Zeilen laden (alle Status ausser Endzustaenden)
# ---------------------------------------------------------------------------
n_open_rows = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM trading.news_impact_tracking WHERE status NOT IN ('completed','confounded','failed');",
        "options": {}
    },
    "name": "DB: Offene Tracking-Zeilen laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2800, 160],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_open_rows)

n_merge_pairs = b.add({
    "parameters": {},
    "name": "Neu + Offen zusammenfuehren",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [-2400, 0]
})
b.link(n_expand_pairs, n_merge_pairs, dst_index=0)
b.link(n_open_rows, n_merge_pairs, dst_index=1)

# ---------------------------------------------------------------------------
# 3. Instrumente laden (fuer benchmark_symbol je Ticker) -- einmal pro Lauf
# ---------------------------------------------------------------------------
n_instruments = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT ticker, benchmark_symbol FROM trading.stock_instruments;",
        "options": {}
    },
    "name": "DB: Instrumente (Benchmark-Zuordnung)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2400, -320],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_instruments)

# ---------------------------------------------------------------------------
# 4. Distinct Ticker extrahieren, Kursverlauf je Ticker laden (n8n-Standard-
#    verhalten: ein dataTable-get-Node mit N Input-Items fuehrt automatisch
#    N gefilterte Einzelabfragen aus, siehe bestaetigtes Muster in 02b/01 --
#    KEINE volle Tabellenladung, jede Abfrage ist auf 1 Ticker gefiltert).
# ---------------------------------------------------------------------------
n_distinct_tickers = b.add({
    "parameters": {
        "jsCode": "const all = $input.all().map(i => i.json);\n"
                  "const tickers = [...new Set(all.map(r => r.ticker).filter(Boolean))];\n"
                  "return tickers.map(t => ({ json: { ticker: t } }));"
    },
    "name": "Distinkte Ticker extrahieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2200, 0]
})
b.link(n_merge_pairs, n_distinct_tickers)

n_load_signals = b.add({
    "parameters": {
        "operation": "get",
        "dataTableId": {"__rl": True, "value": "GDMAKrvQovPcBItA", "mode": "list", "cachedResultName": "stock_technical_signals"},
        "filters": {"conditions": [{"keyName": "ticker", "keyValue": "={{ $json.ticker }}"}]},
        "returnAll": True
    },
    "name": "DB: Kursverlauf je Ticker laden",
    "type": "n8n-nodes-base.dataTable",
    "typeVersion": 1,
    "position": [-2000, 0],
    "onError": "continueRegularOutput"
})
b.link(n_distinct_tickers, n_load_signals)

n_group_signals = b.add({
    "parameters": {
        "jsCode": "const rows = $input.all().map(i => i.json);\n"
                  "const byTicker = {};\n"
                  "for (const r of rows) {\n"
                  "  if (!byTicker[r.ticker]) byTicker[r.ticker] = [];\n"
                  "  byTicker[r.ticker].push({ datum: r.datum, kurs: Number(r.aktueller_kurs) });\n"
                  "}\n"
                  "for (const t in byTicker) byTicker[t].sort((a,b) => a.datum < b.datum ? -1 : 1);\n"
                  "return [{ json: { kursverlauf: byTicker } }];"
    },
    "name": "Kursverlauf gruppieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1800, 0]
})
b.link(n_load_signals, n_group_signals)

# ---------------------------------------------------------------------------
# 5. Benchmark-Kursverlauf laden (i.d.R. nur ^GDAXI, aber generisch ueber
#    distinkte benchmark_symbol-Werte aus der Instrumententabelle)
# ---------------------------------------------------------------------------
n_distinct_benchmarks = b.add({
    "parameters": {
        "jsCode": "const all = $input.all().map(i => i.json);\n"
                  "const syms = [...new Set(all.map(r => r.benchmark_symbol).filter(Boolean))];\n"
                  "if (syms.length === 0) syms.push('^GDAXI');\n"
                  "return syms.map(s => ({ json: { symbol: s } }));"
    },
    "name": "Distinkte Benchmark-Symbole extrahieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-2200, -320]
})
b.link(n_instruments, n_distinct_benchmarks)

n_load_benchmark = b.add({
    "parameters": {
        "operation": "get",
        "dataTableId": {"__rl": True, "value": "dzUOoGnfASjaaVhn", "mode": "list", "cachedResultName": "stock_market_context"},
        "filters": {"conditions": [{"keyName": "symbol", "keyValue": "={{ $json.symbol }}"}]},
        "returnAll": True
    },
    "name": "DB: Benchmark-Kursverlauf laden",
    "type": "n8n-nodes-base.dataTable",
    "typeVersion": 1,
    "position": [-2000, -320],
    "onError": "continueRegularOutput"
})
b.link(n_distinct_benchmarks, n_load_benchmark)

n_group_benchmark = b.add({
    "parameters": {
        "jsCode": "const rows = $input.all().map(i => i.json);\n"
                  "const bySymbol = {};\n"
                  "for (const r of rows) {\n"
                  "  if (!bySymbol[r.symbol]) bySymbol[r.symbol] = [];\n"
                  "  bySymbol[r.symbol].push({ datum: r.datum, kurs: Number(r.aktueller_kurs) });\n"
                  "}\n"
                  "for (const s in bySymbol) bySymbol[s].sort((a,b) => a.datum < b.datum ? -1 : 1);\n"
                  "return [{ json: { benchmarkverlauf: bySymbol } }];"
    },
    "name": "Benchmarkverlauf gruppieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1800, -320]
})
b.link(n_load_benchmark, n_group_benchmark)

# ---------------------------------------------------------------------------
# 6. Alles zusammenfuehren und D+1/D+3/D+5/D+10/D+20 berechnen
#    (Handelstage = tatsaechlich vorhandene Kurszeilen, nicht Kalendertage)
#    inkl. Stoerfaktor-Erkennung (Phase 7).
# ---------------------------------------------------------------------------
n_merge_all = b.add({
    "parameters": {},
    "name": "Kontext zusammenfuehren",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [-1600, -160]
})
b.link(n_group_signals, n_merge_all, dst_index=0)
b.link(n_group_benchmark, n_merge_all, dst_index=1)

n_compute = b.add({
    "parameters": {
        "jsCode": """function tickerBenchmark(instruments, ticker) {
  const m = instruments.find(i => i.ticker === ticker);
  return (m && m.benchmark_symbol) || '^GDAXI';
}

function findBaselineAndHorizons(verlauf, newsDate, baselineCase) {
  // verlauf: sortierte Liste {datum, kurs}. newsDate: 'YYYY-MM-DD'.
  const idxOnOrBefore = (d) => {
    let idx = -1;
    for (let i = 0; i < verlauf.length; i++) { if (verlauf[i].datum <= d) idx = i; else break; }
    return idx;
  };
  let baselineIdx;
  if (baselineCase === 'nach_handelsende') {
    baselineIdx = verlauf.findIndex(v => v.datum === newsDate);
    if (baselineIdx === -1) baselineIdx = idxOnOrBefore(newsDate);
  } else {
    // vor_handelsbeginn / waehrend_handelszeit -> Vortagesschluss
    const onOrBefore = idxOnOrBefore(newsDate);
    baselineIdx = (verlauf[onOrBefore] && verlauf[onOrBefore].datum === newsDate) ? onOrBefore - 1 : onOrBefore;
  }
  return baselineIdx;
}

const rows = $('Neu + Offen zusammenfuehren').all().map(i => i.json);
const kursverlauf = $('Kursverlauf gruppieren').first().json.kursverlauf;
const benchmarkverlauf = $('Benchmarkverlauf gruppieren').first().json.benchmarkverlauf;
const instruments = $('DB: Instrumente (Benchmark-Zuordnung)').all().map(i => i.json);

const HORIZONS = [1, 3, 5, 10, 20];
const CONFOUND_BENCHMARK_MOVE = 0.02; // 2% Tagesbewegung der Benchmark als grober Schwellenwert
const CATEGORY_KEYWORDS = ['quartalszahl', 'gewinnwarnung', 'dividende', 'kapitalerhoehung', 'uebernahme', 'übernahme', 'analysten', 'herabstufung', 'hochstufung'];

const results = [];

for (const row of rows) {
  const ticker = row.ticker;
  const verlauf = kursverlauf[ticker] || [];
  const benchmarkSymbol = row.benchmark_symbol || tickerBenchmark(instruments, ticker);
  const bverlauf = benchmarkverlauf[benchmarkSymbol] || [];

  const isNew = row.baseline_case !== undefined;

  let baselineIdx, newsDate, baselinePrice, baselineTs, firstTradingDate;

  if (isNew) {
    newsDate = row.news_date;
    baselineIdx = findBaselineAndHorizons(verlauf, newsDate, row.baseline_case);
    if (baselineIdx < 0 || !verlauf[baselineIdx]) {
      // Noch keine Kursdaten fuer diesen Ticker vorhanden -> naechsten Lauf abwarten.
      continue;
    }
    baselinePrice = verlauf[baselineIdx].kurs;
    baselineTs = verlauf[baselineIdx].datum;
    firstTradingDate = verlauf[baselineIdx + 1] ? verlauf[baselineIdx + 1].datum : null;
  } else {
    newsDate = row.news_date;
    baselinePrice = Number(row.baseline_price);
    baselineTs = row.baseline_timestamp;
    baselineIdx = verlauf.findIndex(v => v.datum === baselineTs);
  }

  const bBaselineIdx = bverlauf.findIndex(v => v.datum === baselineTs);
  const benchmarkBaseline = bBaselineIdx >= 0 ? bverlauf[bBaselineIdx].kurs : (isNew ? null : Number(row.benchmark_baseline_price));

  const out = {
    is_new: isNew,
    id: isNew ? null : row.id,
    news_id: row.news_id,
    news_key: row.news_key,
    ticker,
    news_date: newsDate,
    publication_timestamp: isNew ? row.publication_timestamp : row.publication_timestamp,
    first_trading_date: isNew ? firstTradingDate : row.first_trading_date,
    predicted_direction: isNew ? row.predicted_direction : row.predicted_direction,
    predicted_strength: isNew ? row.predicted_strength : row.predicted_strength,
    prediction_confidence: isNew ? row.prediction_confidence : row.prediction_confidence,
    news_category: isNew ? row.news_category : row.news_category,
    source: isNew ? row.source : row.source,
    baseline_price: baselinePrice,
    baseline_timestamp: baselineTs,
    benchmark_symbol: benchmarkSymbol,
    benchmark_baseline_price: benchmarkBaseline
  };

  let maxPos = isNew ? null : row.max_positive_move;
  let maxNeg = isNew ? null : row.max_negative_move;
  let lastFilledIdx = -1;

  for (const h of HORIZONS) {
    const existingPrice = isNew ? null : row['price_d' + h];
    if (existingPrice !== null && existingPrice !== undefined) {
      out['price_d' + h] = existingPrice;
      out['return_d' + h] = row['return_d' + h];
      out['benchmark_return_d' + h] = row['benchmark_return_d' + h];
      out['abnormal_return_d' + h] = row['abnormal_return_d' + h];
      lastFilledIdx = h;
      continue;
    }
    const targetIdx = baselineIdx + h;
    const point = verlauf[targetIdx];
    if (!point || baselineIdx < 0 || !baselinePrice) {
      out['price_d' + h] = null; out['return_d' + h] = null;
      out['benchmark_return_d' + h] = null; out['abnormal_return_d' + h] = null;
      continue;
    }
    const ret = (point.kurs / baselinePrice) - 1;
    const bPoint = bverlauf[bBaselineIdx + h];
    const bRet = (bPoint && benchmarkBaseline) ? (bPoint.kurs / benchmarkBaseline) - 1 : null;
    const abnormal = bRet !== null ? ret - bRet : null;

    out['price_d' + h] = point.kurs;
    out['return_d' + h] = Number(ret.toFixed(6));
    out['benchmark_return_d' + h] = bRet !== null ? Number(bRet.toFixed(6)) : null;
    out['abnormal_return_d' + h] = abnormal !== null ? Number(abnormal.toFixed(6)) : null;

    if (maxPos === null || maxPos === undefined || ret > maxPos) maxPos = ret;
    if (maxNeg === null || maxNeg === undefined || ret < maxNeg) maxNeg = ret;
  }

  out.max_positive_move = maxPos;
  out.max_negative_move = maxNeg;

  const d20Filled = out.price_d20 !== null && out.price_d20 !== undefined;
  const anyNewFilled = HORIZONS.some(h => out['price_d' + h] !== null && out['price_d' + h] !== undefined);

  // Stoerfaktor-Erkennung (Phase 7): grobe, deterministische Heuristik ohne
  // Fundamentaldaten-Kalender (nicht vorhanden) -- Kategorie-Schluesselwoerter
  // in anderen News zum selben Ticker im Beobachtungsfenster + starke
  // Benchmark-Bewegung am jeweiligen Tag.
  let confounded = isNew ? false : !!row.confounded;
  let confoundingReason = isNew ? '' : (row.confounding_reason || '');
  const strongBenchmarkMove = HORIZONS.some(h => out['benchmark_return_d' + h] !== null && Math.abs(out['benchmark_return_d' + h]) > CONFOUND_BENCHMARK_MOVE);
  if (strongBenchmarkMove && !confounded) {
    confounded = true;
    confoundingReason = 'Starke Benchmark-Bewegung (>2%) im Beobachtungsfenster';
  }

  out.confounded = confounded;
  out.confounding_reason = confoundingReason;
  out.additional_news_count = isNew ? 0 : (row.additional_news_count || 0);

  // Abschluss-Status
  if (d20Filled) {
    const observedDirection = out.abnormal_return_d20 === null ? 'unklar' : (out.abnormal_return_d20 > 0.005 ? 'positiv' : out.abnormal_return_d20 < -0.005 ? 'negativ' : 'neutral');
    const observedStrength = out.abnormal_return_d20 === null ? 'unklar' : (Math.abs(out.abnormal_return_d20) > 0.05 ? 'hoch' : Math.abs(out.abnormal_return_d20) > 0.015 ? 'mittel' : 'niedrig');
    out.observed_direction = observedDirection;
    out.observed_strength = observedStrength;
    out.direction_correct = out.predicted_direction && observedDirection !== 'unklar' ? (out.predicted_direction === observedDirection) : null;
    out.strength_correct = out.predicted_strength && observedStrength !== 'unklar' ? (out.predicted_strength === observedStrength) : null;
    out.quality_score = out.direction_correct === null ? null : (out.direction_correct ? (out.strength_correct ? 100 : 60) : 0);
    out.status = confounded ? 'confounded' : 'completed';
    out.completed_at = new Date().toISOString();
  } else if (anyNewFilled || !isNew) {
    const nextHorizon = HORIZONS.find(h => out['price_d' + h] === null || out['price_d' + h] === undefined);
    out.status = nextHorizon ? ('waiting_d' + nextHorizon) : 'waiting_d1';
    out.observed_direction = null; out.observed_strength = null;
    out.direction_correct = null; out.strength_correct = null; out.quality_score = null;
    out.completed_at = null;
  } else {
    out.status = 'waiting_d1';
    out.observed_direction = null; out.observed_strength = null;
    out.direction_correct = null; out.strength_correct = null; out.quality_score = null;
    out.completed_at = null;
  }

  results.push({ json: out });
}

return results;
"""
    },
    "name": "D+1..D+20 berechnen + Stoerfaktoren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1400, -160]
})
b.link(n_merge_all, n_compute)

# ---------------------------------------------------------------------------
# 7. Persistieren (Upsert ueber news_id+ticker)
# ---------------------------------------------------------------------------
n_persist_in, n_persist_out = b.pg_exec_pair("Tracking-Zeile upserten", [-1200, -160], """
const j = $json;
const num = (v) => v === null || v === undefined ? 'NULL' : pgNum(v);

const cols = {
  news_id: pgNum(j.news_id), news_key: pgStr(j.news_key), ticker: pgStr(j.ticker),
  news_date: pgStr(j.news_date), publication_timestamp: j.publication_timestamp ? pgStr(j.publication_timestamp) : 'NULL',
  first_trading_date: j.first_trading_date ? pgStr(j.first_trading_date) : 'NULL',
  predicted_direction: pgStr(j.predicted_direction), predicted_strength: pgStr(j.predicted_strength),
  prediction_confidence: num(j.prediction_confidence), news_category: pgStr(j.news_category), source: pgStr(j.source),
  baseline_price: num(j.baseline_price), baseline_timestamp: j.baseline_timestamp ? pgStr(j.baseline_timestamp) : 'NULL',
  benchmark_symbol: pgStr(j.benchmark_symbol), benchmark_baseline_price: num(j.benchmark_baseline_price),
  price_d1: num(j.price_d1), price_d3: num(j.price_d3), price_d5: num(j.price_d5), price_d10: num(j.price_d10), price_d20: num(j.price_d20),
  return_d1: num(j.return_d1), return_d3: num(j.return_d3), return_d5: num(j.return_d5), return_d10: num(j.return_d10), return_d20: num(j.return_d20),
  benchmark_return_d1: num(j.benchmark_return_d1), benchmark_return_d3: num(j.benchmark_return_d3), benchmark_return_d5: num(j.benchmark_return_d5),
  benchmark_return_d10: num(j.benchmark_return_d10), benchmark_return_d20: num(j.benchmark_return_d20),
  abnormal_return_d1: num(j.abnormal_return_d1), abnormal_return_d3: num(j.abnormal_return_d3), abnormal_return_d5: num(j.abnormal_return_d5),
  abnormal_return_d10: num(j.abnormal_return_d10), abnormal_return_d20: num(j.abnormal_return_d20),
  max_positive_move: num(j.max_positive_move), max_negative_move: num(j.max_negative_move),
  observed_direction: pgStr(j.observed_direction), observed_strength: pgStr(j.observed_strength),
  direction_correct: j.direction_correct === null ? 'NULL' : pgBool(j.direction_correct),
  strength_correct: j.strength_correct === null ? 'NULL' : pgBool(j.strength_correct),
  quality_score: num(j.quality_score),
  confounded: pgBool(j.confounded), confounding_reason: pgStr(j.confounding_reason), additional_news_count: pgNum(j.additional_news_count),
  status: pgStr(j.status), completed_at: j.completed_at ? pgStr(j.completed_at) : 'NULL'
};

const colNames = Object.keys(cols).join(', ');
const colVals = Object.values(cols).join(', ');
const updateSet = Object.keys(cols).filter(k => k !== 'news_id' && k !== 'ticker').map(k => `${k} = EXCLUDED.${k}`).join(', ');

const sql = `INSERT INTO trading.news_impact_tracking (${colNames}, updated_at)
  VALUES (${colVals}, now())
  ON CONFLICT (news_id, ticker) DO UPDATE SET ${updateSet}, updated_at = now();`;

return { json: { ...j, sql } };
""")
b.link(n_compute, n_persist_in)

b.write_and_validate(OUT)
