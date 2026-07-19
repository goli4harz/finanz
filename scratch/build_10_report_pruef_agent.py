# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED, OPENAI_CRED

OUT = r"C:\Users\olietz\Documents\finanz\10 – Report- und Prüfagent.json"

b = Builder("10 – Report- und Prüfagent")

n_trigger = b.add({
    "parameters": {
        "workflowInputs": {"values": [
            {"name": "run_id"},
            {"name": "business_date"}
        ]}
    },
    "name": "Execute Workflow Trigger",
    "type": "n8n-nodes-base.executeWorkflowTrigger",
    "typeVersion": 1.1,
    "position": [-3200, 0]
})

# ---------------------------------------------------------------------------
# 1. Grunddaten laden (unveraendert aus n8n Data Tables -- diese Tabellen
#    werden in dieser Migration NICHT verschoben, siehe Migrationsplan)
# ---------------------------------------------------------------------------
def dt_read(name, table_id, table_cached, position):
    return b.add({
        "parameters": {
            "operation": "get",
            "dataTableId": {"__rl": True, "value": table_id, "mode": "list", "cachedResultName": table_cached},
            "returnAll": True
        },
        "name": name,
        "type": "n8n-nodes-base.dataTable",
        "typeVersion": 1,
        "position": position,
        "onError": "continueRegularOutput"
    })

n_fund = dt_read("DB: Fundamentaldaten laden", "Le3FJQ6pctb6qtGi", "stock_fundamentals", [-3000, -240])
b.link(n_trigger, n_fund)
n_tech = dt_read("DB: Technische Signale laden", "GDMAKrvQovPcBItA", "stock_technical_signals", [-3000, -80])
b.link(n_trigger, n_tech)
n_markt = dt_read("DB: Marktumfeld laden", "dzUOoGnfASjaaVhn", "stock_market_context", [-3000, 80])
b.link(n_trigger, n_markt)
n_empf = dt_read("DB: Empfehlungen laden", "TJgigfIfzXm7c7Ob", "stock_empfehlungen", [-3000, 240])
b.link(n_trigger, n_empf)

# ---------------------------------------------------------------------------
# 2. Neue Datenquellen aus trading.* (Postgres)
# ---------------------------------------------------------------------------
n_news = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT ni.title AS titel, ni.url AS link, ni.published_at, ni.created_at,\n"
                 "       na.relevant, na.wirkungsebene, na.betroffene_ticker_json, na.wirkungsrichtung,\n"
                 "       na.wirkung_staerke, na.ticker_begruendung, na.wirkungs_begruendung, na.sentiment\n"
                 "FROM trading.news_assessments na\n"
                 "JOIN trading.news_items ni ON ni.id = na.news_id\n"
                 "WHERE na.relevant = TRUE AND na.wirkung_staerke IN ('hoch','mittel')\n"
                 "  AND ni.created_at >= now() - interval '2 days'\n"
                 "ORDER BY ni.created_at DESC;",
        "options": {}
    },
    "name": "DB: Relevante News laden (trading.*)",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3000, 400],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_news)

n_learn = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "SELECT proposal_type, target_value, current_value, proposed_value, sample_size, reason, confidence_level, status\n"
                 "FROM trading.learning_rule_proposals\n"
                 "WHERE status IN ('proposed','approved') AND created_at >= now() - interval '14 days'\n"
                 "ORDER BY created_at DESC LIMIT 10;",
        "options": {}
    },
    "name": "DB: Aktuelle Lernhinweise laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3000, 560],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_learn)

n_pipeline = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": "=SELECT stage_name, status, error_message FROM trading.pipeline_runs "
                 "WHERE run_id = '{{ $json.run_id.replace(/'/g, \"''\") }}' ORDER BY id;",
        "options": {}
    },
    "name": "DB: Orchestrator-Lauf laden",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-3000, 720],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_pipeline)

# ---------------------------------------------------------------------------
# 3. Alles zusammenfuehren + Reportdaten aufbereiten (Logik weitgehend aus
#    dem Original 05 uebernommen, News-Feldnamen an trading.news_assessments
#    angepasst, Lernhinweise + Orchestrator-Datenqualitaet neu ergaenzt)
# ---------------------------------------------------------------------------
n_m1 = b.add({"parameters": {}, "name": "Merge Grunddaten 1", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2800, -80]})
b.link(n_fund, n_m1, dst_index=0); b.link(n_tech, n_m1, dst_index=1)
n_m2 = b.add({"parameters": {}, "name": "Merge Grunddaten 2", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2600, 80]})
b.link(n_m1, n_m2, dst_index=0); b.link(n_markt, n_m2, dst_index=1)
n_m3 = b.add({"parameters": {}, "name": "Merge Grunddaten 3", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2400, 240]})
b.link(n_m2, n_m3, dst_index=0); b.link(n_empf, n_m3, dst_index=1)
n_m4 = b.add({"parameters": {}, "name": "Merge Grunddaten 4", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2200, 400]})
b.link(n_m3, n_m4, dst_index=0); b.link(n_news, n_m4, dst_index=1)
n_m5 = b.add({"parameters": {}, "name": "Merge Grunddaten 5", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2000, 560]})
b.link(n_m4, n_m5, dst_index=0); b.link(n_learn, n_m5, dst_index=1)
n_m6 = b.add({"parameters": {}, "name": "Merge Grunddaten 6", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-1800, 720]})
b.link(n_m5, n_m6, dst_index=0); b.link(n_pipeline, n_m6, dst_index=1)

n_build_data = b.add({
    "parameters": {
        "jsCode": GET_BUSINESS_DATE_JS + """

function safeAll(nodeName) {
  try { const items = $(nodeName).all(); return items ? items.map(i => i.json) : []; }
  catch (e) { return []; }
}

const heute = getBusinessDate();
const fundamentaldaten = safeAll('DB: Fundamentaldaten laden');
const techAusDB = safeAll('DB: Technische Signale laden');
const marktKontext = safeAll('DB: Marktumfeld laden');
const empfehlungenRows = safeAll('DB: Empfehlungen laden');
const alleNews = safeAll('DB: Relevante News laden (trading.*)');
const lernhinweise = safeAll('DB: Aktuelle Lernhinweise laden');
const orchestratorStages = safeAll('DB: Orchestrator-Lauf laden');

const diagnose = {
  fundamental_count: fundamentaldaten.length,
  tech_signale_count: techAusDB.length,
  markt_kontext_count: marktKontext.length,
  news_total: alleNews.length,
  quellen_leer: []
};
if (fundamentaldaten.length === 0) diagnose.quellen_leer.push('stock_fundamentals');
if (techAusDB.length === 0) diagnose.quellen_leer.push('stock_technical_signals');
if (marktKontext.length === 0) diagnose.quellen_leer.push('stock_market_context');
if (alleNews.length === 0) diagnose.quellen_leer.push('trading.news_assessments');
const orchestratorWarnungen = orchestratorStages.filter(s => s.status === 'failed' || s.status === 'warning').map(s => s.stage_name + ': ' + s.status + (s.error_message ? ' (' + s.error_message + ')' : ''));
diagnose.warnungen = [...diagnose.quellen_leer.map(q => 'Datenquelle leer: ' + q), ...orchestratorWarnungen];

const tickerSektorMap = {};
for (const s of techAusDB) if (s.ticker && s.sektor) tickerSektorMap[String(s.ticker).trim()] = String(s.sektor).trim();

const SEKTOR_KEYWORDS = {
  'Auto': ['auto','automobil','fahrzeug','e-auto','elektroauto','zulieferer','pkw'],
  'Energie': ['energie','strom','gas','öl','ölpreis','kraftwerk','erneuerbare'],
  'Chemie': ['chemie','chemiekonzern','chemieindustrie'],
  'Banken': ['bank','banken','zins','zinsen','ezb','kredit','finanzsektor'],
  'Pharma': ['pharma','medikament','arznei','biotech','arzneimittel'],
  'Telekom': ['telekom','mobilfunk','5g','netzausbau','glasfaser'],
  'Versicherung': ['versicherung','versicherer'],
  'Technologie': ['software','chip','halbleiter',' ki ','cloud','tech-branche'],
  'Industrie': ['industrie','maschinenbau','anlagenbau','industriekonzern'],
  'Sport': ['sportartikel','sportbekleidung'],
  'Konsumgüter': ['konsumgüter','konsumgüterkonzern'],
  'Gesundheit': ['gesundheitswesen','klinik','medizintechnik']
};
function ermittleSektorenAusText(text) {
  const t = String(text || '').toLowerCase();
  return Object.entries(SEKTOR_KEYWORDS).filter(([,kw]) => kw.some(k => t.includes(k))).map(([s]) => s);
}
function erweitereTickerFuerSektorNews(n) {
  const bereits = Array.isArray(n.betroffene_ticker_json) ? n.betroffene_ticker_json : [];
  if (n.wirkungsebene !== 'sektor') return { ...n, betroffene_ticker_erweitert: bereits, sektor_treffer: [] };
  const matchText = [n.titel, n.wirkungs_begruendung, n.ticker_begruendung].filter(Boolean).join(' ');
  const sektorTreffer = ermittleSektorenAusText(matchText);
  const zusaetzliche = Object.entries(tickerSektorMap).filter(([,sek]) => sektorTreffer.includes(sek)).map(([t]) => t);
  return { ...n, betroffene_ticker_erweitert: Array.from(new Set([...bereits, ...zusaetzliche])), sektor_treffer: sektorTreffer };
}

const heutigeNews = alleNews.map(erweitereTickerFuerSektorNews);
diagnose.news_heute_relevant = heutigeNews.length;

let techSignale = techAusDB.filter(s => String(s.datum || '').startsWith(heute));
if (techSignale.length === 0) techSignale = techAusDB;
const statusPrio = { handelskandidat: 1, beobachten: 2, nur_info: 3, ignorieren: 4 };
techSignale.sort((a, b) => (statusPrio[a.handels_status] || 9) - (statusPrio[b.handels_status] || 9));

const HAUPT_SYMBOLE = ['^GDAXI','^STOXX50E','^GSPC','^IXIC'];
const KONTEXT_SYMBOLE = ['EURUSD=X','CL=F','GC=F'];
const hauptmaerkte = marktKontext.filter(m => HAUPT_SYMBOLE.includes(m.symbol));
const kontextmaerkte = marktKontext.filter(m => KONTEXT_SYMBOLE.includes(m.symbol));
const risk_off = hauptmaerkte.filter(m => m.markt_status === 'risk_off').length;
const risk_on = hauptmaerkte.filter(m => m.markt_status === 'risk_on').length;
const gesamtMarktLage = marktKontext.length === 0 ? 'unbekannt' : risk_off > risk_on ? 'risk_off' : risk_on > risk_off ? 'risk_on' : 'neutral';

const dax = marktKontext.find(m => m.symbol === '^GDAXI') || null;
const nasdaq = marktKontext.find(m => m.symbol === '^IXIC') || null;
const sp500 = marktKontext.find(m => m.symbol === '^GSPC') || null;
const eurusd = marktKontext.find(m => m.symbol === 'EURUSD=X') || null;
const oel = marktKontext.find(m => m.symbol === 'CL=F') || null;

const handelskandidaten = techSignale.filter(s => s.handels_status === 'handelskandidat');
const beobachtenListe = techSignale.filter(s => s.handels_status === 'beobachten');
const marktBestaetigt = techSignale.filter(s => s.markt_bestaetigt_signal === 'true' && (s.handels_status === 'handelskandidat' || s.handels_status === 'beobachten'));
const marktGegenSignal = techSignale.filter(s => s.markt_bestaetigt_signal === 'false' && (s.handels_status === 'handelskandidat' || s.handels_status === 'beobachten'));

const aktuellerKursByTicker = {};
for (const s of techAusDB) if (s.ticker) aktuellerKursByTicker[String(s.ticker).trim()] = s.aktueller_kurs;
function berechneLivePerformance(row) {
  const entry = Number(row.entry_kurs);
  const aktuell = Number(aktuellerKursByTicker[String(row.ticker || '').trim()]);
  if (isNaN(entry) || isNaN(aktuell) || entry <= 0) return null;
  const pct = row.richtung === 'kauf' ? ((aktuell - entry) / entry) * 100 : ((entry - aktuell) / entry) * 100;
  return parseFloat(pct.toFixed(2));
}
const offenePositionen = empfehlungenRows.filter(r => r.status === 'offen').map(r => ({ ...r, live_performance_pct: berechneLivePerformance(r) }));
const geschlossenePositionen = empfehlungenRows.filter(r => r.status === 'geschlossen');
const geschlossenPerformances = geschlossenePositionen.map(r => Number(r.performance_pct)).filter(v => !isNaN(v));

const empfehlungswatchlist = {
  offen: offenePositionen, geschlossen: geschlossenePositionen,
  anzahl_offen: offenePositionen.length, anzahl_geschlossen: geschlossenePositionen.length,
  durchschnitt_performance_geschlossen: geschlossenPerformances.length > 0 ? parseFloat((geschlossenPerformances.reduce((a,b)=>a+b,0)/geschlossenPerformances.length).toFixed(2)) : null,
  trefferquote_geschlossen: geschlossenPerformances.length > 0 ? parseFloat(((geschlossenPerformances.filter(v=>v>0).length/geschlossenPerformances.length)*100).toFixed(1)) : null
};

return [{ json: {
  run_id: $('Execute Workflow Trigger').first().json.run_id,
  business_date: heute,
  datum: new Date().toLocaleDateString('de-DE'),
  uhrzeit: new Intl.DateTimeFormat('de-DE', { timeZone: 'Europe/Berlin', hour: '2-digit', minute: '2-digit' }).format(new Date()),
  technische_signale: techSignale, handelskandidaten, beobachten_liste: beobachtenListe,
  markt_bestaetigt: marktBestaetigt, markt_gegen_signal: marktGegenSignal,
  fundamentaldaten, nachrichten: heutigeNews, empfehlungswatchlist,
  lernhinweise,
  marktumfeld: {
    kontext: marktKontext, gesamt_lage: gesamtMarktLage, risk_on_count: risk_on, risk_off_count: risk_off,
    haupt_maerkte_count: hauptmaerkte.length,
    kontext_maerkte: kontextmaerkte.map(m => ({ symbol: m.symbol, name: m.name, status: m.markt_status, veraenderung_pct: m.veraenderung_pct })),
    dax: dax ? { status: dax.markt_status, trend: dax.trend, veraenderung_pct: dax.veraenderung_pct, risk_level: dax.risk_level, hinweis: dax.markt_hinweis } : null,
    nasdaq: nasdaq ? { status: nasdaq.markt_status, trend: nasdaq.trend, veraenderung_pct: nasdaq.veraenderung_pct } : null,
    sp500: sp500 ? { status: sp500.markt_status, trend: sp500.trend, veraenderung_pct: sp500.veraenderung_pct } : null,
    eurusd: eurusd ? { kurs: eurusd.aktueller_kurs, veraenderung_pct: eurusd.veraenderung_pct } : null,
    oel: oel ? { kurs: oel.aktueller_kurs, veraenderung_pct: oel.veraenderung_pct } : null
  },
  datenqualitaet: diagnose
} }];
"""
    },
    "name": "Reportdaten aufbereiten",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1600, 240]
})
b.link(n_m6, n_build_data)

# ---------------------------------------------------------------------------
# 4. Report-Agent: interpretiert, berechnet keine Indikatoren neu (Prompt-
#    Struktur unveraendert aus dem Original 05 uebernommen, um bewaehrte
#    Formatvorgaben/Erklaerstil nicht zu verlieren, Lernhinweise-Abschnitt
#    neu ergaenzt).
# ---------------------------------------------------------------------------
n_build_prompt = b.add({
    "parameters": {
        "jsCode": """const d = $input.item.json;
const mu = d.marktumfeld || {};
const dq = d.datenqualitaet || {};

const systemPrompt = `Du bist ein vorsichtiger, sachlicher Aktienbeobachter fuer deutsche Aktien.
Du richtest dich an Einsteiger und erklaerst Fachbegriffe kurz in einfachen Worten.
Du analysierst technische Signale, Fundamentaldaten, Marktumfeld, Nachrichten und Lernhinweise aus
der Vergangenheit. Du gibst KEINE Finanzberatung. Du machst KEINE Kauf- oder Verkaufsempfehlungen.
Du erfindest keine Fakten. Du kennzeichnest Datenluecken klar. Du berechnest KEINE eigenen
technischen Indikatoren neu, sondern interpretierst die bereits berechneten Werte.

FORMATVORGABEN (zwingend einhalten):
- Antworte ausschliesslich in sauberem Markdown.
- Ueberschriften ausschliesslich mit ##.
- Aufzaehlungen ausschliesslich mit "- ".
- Kein HTML, keine Code-Bloecke, keine Tabellen (ausser inhaltlich zwingend noetig).`;

const dqText = dq.warnungen && dq.warnungen.length > 0 ? `\\n\\nDATENQUALITAET-WARNUNGEN:\\n${dq.warnungen.join('\\n')}` : '';
const lernText = (d.lernhinweise && d.lernhinweise.length > 0)
  ? `\\n\\nAKTUELLE LERNHINWEISE (aus dem Lernagenten, noch nicht produktiv aktiv, nur zur Einordnung):\\n${JSON.stringify(d.lernhinweise)}`
  : '';

const userPrompt = `Erstelle einen konkreten Aktien-Tagesreport fuer Einsteiger auf Basis dieser Daten:

${JSON.stringify(d, null, 2)}${dqText}${lernText}

STRUKTUR:
## 1. Marktlage heute (einfache Worte)
## 2. Top-Auffaelligkeiten des Tages (max 5)
## 3. Technische Beobachtungen je Aktie (Kurs, Referenzindex, relative Staerke, Marktbestaetigung, RSI/MACD/Trend erklaert, passende News, vorsichtige Beobachtung)
## 4. Signale mit Marktbestaetigung
## 5. Signale gegen das Marktumfeld
## 6. Nachrichtenlage (positiv/negativ/makro, je relevanter News: betroffene Ticker, Wirkungsebene, Richtung, Staerke, Begruendung)
## 7. Fundamentale Auffaelligkeiten
## 8. Watchlist fuer morgen (Long-/Short-/Neutral-Beobachtung mit Begruendung)
## 9. Lernhinweise aus der Vergangenheit (falls vorhanden: kurz einordnen, klar als noch nicht produktiv aktiv kennzeichnen)
## 10. Risiken und Datenluecken
## 11. Fazit (3 konkrete Beobachtungspunkte)

Haftungshinweis am Ende: Kein Handelssignal. Keine Anlageberatung. Nur automatisierte Markt- und Aktienbeobachtung.
Alle Empfehlungswatchlist-Positionen sind SIMULATION, keine realen Trades - das muss im Text erkennbar bleiben.`;

return [{ json: { ...d, systemPrompt, userPrompt } }];
"""
    },
    "name": "Report-Prompt aufbauen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1400, 240]
})
b.link(n_build_data, n_build_prompt)

n_report_ki = b.add({
    "parameters": {
        "modelId": {"__rl": True, "value": "gpt-5.4-mini", "mode": "list", "cachedResultName": "GPT-5.4-MINI"},
        "responses": {"values": [
            {"role": "system", "content": "={{ $json.systemPrompt }}"},
            {"content": "={{ $json.userPrompt }}"}
        ]},
        "builtInTools": {},
        "options": {"maxTokens": 8000}
    },
    "name": "KI: Report-Agent",
    "type": "@n8n/n8n-nodes-langchain.openAi",
    "typeVersion": 2.3,
    "position": [-1200, 240],
    "retryOnFail": True,
    "waitBetweenTries": 5000,
    "credentials": {"openAiApi": OPENAI_CRED}
})
b.link(n_build_prompt, n_report_ki)

n_extract_report = b.add({
    "parameters": {
        "jsCode": """function getAiText(resp) {
  if (typeof resp === 'string') return resp;
  if (resp && Array.isArray(resp.output)) {
    const msg = resp.output.find(o => o.type === 'message');
    const part = msg && Array.isArray(msg.content) ? msg.content.find(c => c.type === 'output_text') : null;
    if (part && part.text) return part.text;
  }
  return JSON.stringify(resp || '');
}
const reportMarkdown = getAiText($json);
const base = $('Report-Prompt aufbauen').item.json;
return [{ json: { ...base, report_markdown: reportMarkdown } }];
"""
    },
    "name": "Report-Text extrahieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1000, 240]
})
b.link(n_report_ki, n_extract_report)

# ---------------------------------------------------------------------------
# 5. Pruef-Agent: unabhaengige zweite Instanz, prueft NUR den fertigen
#    Berichtstext gegen dieselben Rohdaten -- bekommt den System-Prompt des
#    Report-Agenten NICHT zu sehen.
# ---------------------------------------------------------------------------
n_build_check_prompt = b.add({
    "parameters": {
        "jsCode": """const d = $json;

const systemPrompt = `Du bist ein kritischer, unabhaengiger Pruefer fuer automatisiert erstellte Aktien-Tagesreports.
Du bekommst den fertigen Berichtstext UND dieselben Rohdaten, aus denen er entstanden sein soll.
Deine Aufgabe: pruefe den Bericht kritisch, nicht wohlwollend.

Pruefe insbesondere:
- unsupported_claims: Behauptungen im Bericht, die sich NICHT aus den Rohdaten ableiten lassen.
- contradictions: Widersprueche innerhalb des Berichts oder zu den Rohdaten.
- stale_data: Datenpunkte, die veraltet wirken oder aus der Datenqualitaet-Warnliste haetten erwaehnt werden muessen, es aber nicht wurden.
- missing_warnings: bekannte Datenqualitaets- oder Orchestrator-Warnungen aus den Rohdaten, die im Bericht fehlen.
- required_corrections: konkrete, umsetzbare Korrekturvorschlaege.

approved=false, wenn unsupported_claims oder contradictions nicht leer sind, ODER missing_warnings kritische
Luecken zeigt, ODER quality_score < 60.

Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt in diesem Schema, kein Markdown, kein Text davor/danach:
{
  "approved": true,
  "quality_score": 92,
  "unsupported_claims": [],
  "contradictions": [],
  "stale_data": [],
  "missing_warnings": [],
  "required_corrections": []
}`;

// WICHTIG: der Pruef-Agent kann Behauptungen im Bericht nur gegen Daten
// pruefen, die er tatsaechlich sieht -- ein frueherer Versuch gab ihm nur
// die ANZAHL der Datensaetze mit statt der Werte selbst, wodurch er JEDE
// Detailaussage als "nicht verifizierbar" ablehnte (technisch korrekt,
// aber am eigentlichen Zweck vorbei). Jetzt die vollstaendigen Arrays.
const userPrompt = `BERICHTSTEXT:
${d.report_markdown}

ROHDATEN (Datenqualitaet-Diagnose):
${JSON.stringify(d.datenqualitaet)}

ROHDATEN (Marktumfeld):
${JSON.stringify(d.marktumfeld)}

ROHDATEN (technische Signale, vollstaendig):
${JSON.stringify(d.technische_signale || [])}

ROHDATEN (Fundamentaldaten, vollstaendig):
${JSON.stringify(d.fundamentaldaten || [])}

ROHDATEN (relevante News, vollstaendig):
${JSON.stringify(d.nachrichten || [])}

ROHDATEN (Empfehlungswatchlist):
${JSON.stringify(d.empfehlungswatchlist || {})}`;

return [{ json: { ...d, checkSystemPrompt: systemPrompt, checkUserPrompt: userPrompt } }];
"""
    },
    "name": "Pruef-Prompt aufbauen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-800, 240]
})
b.link(n_extract_report, n_build_check_prompt)

n_check_ki = b.add({
    "parameters": {
        "modelId": {"__rl": True, "value": "gpt-5.4-mini", "mode": "list", "cachedResultName": "GPT-5.4-MINI"},
        "responses": {"values": [
            {"role": "system", "content": "={{ $json.checkSystemPrompt }}"},
            {"content": "={{ $json.checkUserPrompt }}"}
        ]},
        "builtInTools": {},
        "options": {"maxTokens": 1500}
    },
    "name": "KI: Pruef-Agent",
    "type": "@n8n/n8n-nodes-langchain.openAi",
    "typeVersion": 2.3,
    "position": [-600, 240],
    "retryOnFail": True,
    "waitBetweenTries": 5000,
    "credentials": {"openAiApi": OPENAI_CRED}
})
b.link(n_build_check_prompt, n_check_ki)

n_final = b.add({
    "parameters": {
        "jsCode": """function getAiText(resp) {
  if (typeof resp === 'string') return resp;
  if (resp && Array.isArray(resp.output)) {
    const msg = resp.output.find(o => o.type === 'message');
    const part = msg && Array.isArray(msg.content) ? msg.content.find(c => c.type === 'output_text') : null;
    if (part && part.text) return part.text;
  }
  return JSON.stringify(resp || '');
}
function parseObj(text) {
  let t = String(text || '').trim().replace(/^```json\\s*/i,'').replace(/^```\\s*/i,'').replace(/```\\s*$/i,'').trim();
  try { const p = JSON.parse(t); return (p && typeof p === 'object') ? p : null; } catch(e) {}
  const s = t.indexOf('{'); const e = t.lastIndexOf('}');
  if (s >= 0 && e > s) { try { return JSON.parse(t.substring(s, e+1)); } catch(err) {} }
  return null;
}

const base = $('Pruef-Prompt aufbauen').item.json;
const verdict = parseObj(getAiText($json)) || { approved: false, quality_score: 0, unsupported_claims: [], contradictions: [], stale_data: [], missing_warnings: ['Pruef-Agent-Antwort nicht parsebar'], required_corrections: ['Pruef-Agent erneut ausfuehren'] };

return [{ json: {
  run_id: base.run_id,
  business_date: base.business_date,
  report_markdown: base.report_markdown,
  approved: verdict.approved === true,
  quality_score: verdict.quality_score,
  unsupported_claims: verdict.unsupported_claims || [],
  contradictions: verdict.contradictions || [],
  stale_data: verdict.stale_data || [],
  missing_warnings: verdict.missing_warnings || [],
  required_corrections: verdict.required_corrections || [],
  // Fuer 05s deterministische Zusatzabschnitte (Signal-Uebersicht,
  // Empfehlungs-Watchlist), die NICHT vom Report-Agenten frei formuliert
  // werden, sondern unveraendert aus dem Original-05-Muster uebernommen sind.
  technische_signale: base.technische_signale || [],
  empfehlungswatchlist: base.empfehlungswatchlist || {},
  datenqualitaet: base.datenqualitaet || {}
} }];
"""
    },
    "name": "Endergebnis zusammenstellen",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-400, 240]
})
b.link(n_check_ki, n_final)

# ---------------------------------------------------------------------------
# 6. Beide Agentenlaeufe protokollieren
# ---------------------------------------------------------------------------
n_log1_in, n_log1_out = b.pg_exec_pair("Report-Agent protokollieren", [-200, 120], """
const j = $json;
const sql = `INSERT INTO trading.agent_runs
  (run_id, agent_name, agent_role, model_name, prompt_version, status, started_at, finished_at)
  VALUES (${pgStr(j.run_id)}, 'report-agent', 'report', 'gpt-5.4-mini', 'report-agent-v1', 'success', now(), now());`;
return { json: { ...j, sql } };
""")
b.link(n_final, n_log1_in)

n_log2_in, n_log2_out = b.pg_exec_pair("Pruef-Agent protokollieren", [0, 240], """
const j = $json;
const sql = `INSERT INTO trading.agent_runs
  (run_id, agent_name, agent_role, model_name, prompt_version, status, confidence, started_at, finished_at)
  VALUES (${pgStr(j.run_id)}, 'pruef-agent', 'pruefung', 'gpt-5.4-mini', 'pruef-agent-v1',
          ${pgStr(j.approved ? 'success' : 'warning')}, ${pgNum(j.quality_score)}, now(), now());`;
return { json: { ...j, sql } };
""")
b.link(n_log1_out, n_log2_in)

b.write_and_validate(OUT)
