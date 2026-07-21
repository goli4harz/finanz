# -*- coding: utf-8 -*-
# Prioritaet 9: baut die 4 Dimension-SQL-Nodes in 09 auf Horizont-Kombination
# um (UNION ALL ueber D+1/D+3/D+5/D+10/D+20) und aktualisiert die 5
# nachgelagerten Code-Nodes (Klassifizierung, Prompt, Validierung, Insert,
# Bericht). Liest/schreibt die lokale Datei direkt als JSON, kein Neuaufbau
# von Grund auf (Builder-Klasse wuerde hier mehr Risiko bergen als Nutzen,
# da nur ein Teil der bestehenden Nodes veraendert wird).
import json

PATH = r"C:\Users\olietz\Documents\finanz\09 – Lernagent Newswirkung.json"

with open(PATH, encoding="utf-8") as f:
    d = json.load(f)

nodes_by_name = {n["name"]: n for n in d["nodes"]}

HORIZONS = [("D+1", "d1"), ("D+3", "d3"), ("D+5", "d5"), ("D+10", "d10"), ("D+20", "d20")]

CASE_WEIGHT_SQL = (
    "CASE WHEN confounded THEN 0.25 "
    "WHEN baseline_quality = 'high' THEN 1.0 "
    "WHEN baseline_quality = 'medium' THEN 0.7 "
    "WHEN baseline_quality = 'limited' THEN 0.4 "
    "ELSE 0.5 END"
)


def horizon_block(dim_label, group_col, horizon_label, suffix, where_extra):
    dcol = f"direction_correct_{suffix}"
    acol = f"abnormal_return_{suffix}"
    # Gating laeuft ueber "{dcol} IS NOT NULL" (= dieser Horizont ist fuer die
    # Zeile bereits berechnet), NICHT ueber status='completed' -- eine Zeile
    # erreicht status='completed' erst, wenn ALLE Horizonte (bis D+20) fertig
    # sind, direction_correct_d1 kann aber laengst befuellt sein, waehrend die
    # Zeile noch bei status='waiting_d3' o.ae. haengt. direction_accuracy
    # (ungewichtet) schliesst konfundierte Faelle weiterhin aus (wie vor
    # Prioritaet 9), weighted_direction_accuracy bezieht sie MIT ein, aber
    # abgewertet ueber case_weight=0.25 -- das ist der eigentliche Sinn der
    # Gewichtung aus Punkt 24 (abwerten statt hart ausschliessen).
    return f"""SELECT '{dim_label}' AS dimension, {group_col} AS value, '{horizon_label}' AS horizon,
  count(*) FILTER (WHERE {dcol} IS NOT NULL) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE {dcol} = TRUE AND confounded = FALSE) / NULLIF(count(*) FILTER (WHERE {dcol} IS NOT NULL AND confounded = FALSE), 0), 1) AS direction_accuracy,
  round(100.0 * sum(case_weight) FILTER (WHERE {dcol} = TRUE) / NULLIF(sum(case_weight) FILTER (WHERE {dcol} IS NOT NULL), 0), 1) AS weighted_direction_accuracy,
  round(avg({acol}) FILTER (WHERE {dcol} IS NOT NULL)::numeric, 3) AS avg_abnormal_return,
  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY {acol}) FILTER (WHERE {dcol} IS NOT NULL)::numeric, 3) AS median_abnormal_return,
  round(100.0 * count(*) FILTER (WHERE {dcol} IS NOT NULL AND confounded = TRUE) / NULLIF(count(*) FILTER (WHERE {dcol} IS NOT NULL), 0), 1) AS confounded_pct,
  round(avg(prediction_confidence) FILTER (WHERE {dcol} IS NOT NULL)::numeric, 1) AS avg_confidence
FROM (
  SELECT *, {CASE_WEIGHT_SQL} AS case_weight
  FROM trading.news_impact_tracking
  WHERE created_at >= now() - interval '90 days' AND status != 'failed' AND {where_extra}
) t
GROUP BY {group_col}"""


def build_dimension_query(dim_label, group_col, where_extra):
    blocks = [horizon_block(dim_label, group_col, hlabel, suffix, where_extra) for hlabel, suffix in HORIZONS]
    return "\nUNION ALL\n".join(blocks) + "\nORDER BY dimension, value, horizon;"


DIMENSION_SPECS = {
    "SQL: Je Newskategorie": ("news_category", "news_category", "news_category IS NOT NULL"),
    "SQL: Je Quelle": ("source", "source", "source IS NOT NULL"),
    "SQL: Je Ticker": ("ticker", "ticker", "ticker IS NOT NULL"),
    "SQL: Je Konfidenz-Bucket": (
        "konfidenz_bucket",
        "(CASE WHEN prediction_confidence >= 70 THEN 'hoch (>=70)' ELSE 'niedrig (<70)' END)",
        "prediction_confidence IS NOT NULL",
    ),
}

for node_name, (dim_label, group_col, where_extra) in DIMENSION_SPECS.items():
    n = nodes_by_name[node_name]
    n["parameters"]["query"] = build_dimension_query(dim_label, group_col, where_extra)

# ---------------------------------------------------------------------------
# Mindestfallzahlen klassifizieren -- jetzt je (dimension,value,horizon)-Zeile,
# proposal_eligible nutzt weighted_direction_accuracy als primaere Ausloesegroesse.
# ---------------------------------------------------------------------------
nodes_by_name["Mindestfallzahlen klassifizieren"]["parameters"]["jsCode"] = """// Mindestfallzahlen-Einordnung exakt wie im Auftrag, rein deterministisch --
// die KI bekommt diese Einordnung als FESTE Vorgabe, sie darf sie nicht
// selbst neu bewerten oder aendern.
// Seit Prioritaet 9: jede Zeile ist bereits eine (Dimension x Wert x Horizont)-
// Kombination (z.B. "source=Reuters bei D+1") -- die Mindestfallzahl gilt
// PRO Kombination, nicht mehr nur pro Einzeldimension.
function confidenceLevel(n) {
  if (n < 10) return null; // keine belastbare Aussage -> wird komplett ausgeblendet
  if (n < 30) return 'niedrig';   // Hinweis mit geringer Datenbasis
  if (n < 100) return 'mittel';   // vorsichtiger Verbesserungsvorschlag
  return 'hoch';                  // staerker belastbare Kalibrierung
}

const dims = $input.all().map(i => i.json).filter(r => r.dimension);
const findings = [];
for (const d of dims) {
  const level = confidenceLevel(Number(d.sample_size));
  if (level === null) continue;
  findings.push({
    dimension: d.dimension,
    value: d.value,
    horizon: d.horizon,
    sample_size: Number(d.sample_size),
    direction_accuracy: d.direction_accuracy === null ? null : Number(d.direction_accuracy),
    weighted_direction_accuracy: d.weighted_direction_accuracy === null ? null : Number(d.weighted_direction_accuracy),
    avg_abnormal_return: d.avg_abnormal_return === null ? null : Number(d.avg_abnormal_return),
    median_abnormal_return: d.median_abnormal_return === null ? null : Number(d.median_abnormal_return),
    confounded_pct: d.confounded_pct === null ? null : Number(d.confounded_pct),
    avg_confidence: d.avg_confidence === null ? null : Number(d.avg_confidence),
    confidence_level: level,
    // Nur Findings mit sample_size>=30 UND deutlich unterdurchschnittlicher
    // (<50%) oder ueberdurchschnittlicher (>=80%) GEWICHTETER Trefferquote
    // sind Kandidaten fuer einen Verbesserungsvorschlag -- deterministische
    // Vorauswahl, die KI bekommt nur diese Teilmenge ueberhaupt vorgelegt.
    proposal_eligible: Number(d.sample_size) >= 30 && d.weighted_direction_accuracy !== null && (Number(d.weighted_direction_accuracy) < 50 || Number(d.weighted_direction_accuracy) >= 80)
  });
}

const overall = $('SQL: Gesamtkennzahlen').first().json;

return [{ json: {
  analysis_from: new Date(Date.now() - 90 * 86400000).toISOString().substring(0,10),
  analysis_to: new Date().toISOString().substring(0,10),
  total_events: Number(overall.total_events) || 0,
  clean_events: Number(overall.clean_events) || 0,
  confounded_events: Number(overall.confounded_events) || 0,
  overall_direction_accuracy: overall.overall_direction_accuracy === null ? null : Number(overall.overall_direction_accuracy),
  weighting_formula: 'high=1.0, medium=0.7, limited=0.4, confounded=0.25 (nach baseline_quality bzw. confounded-Flag je Einzelfall)',
  findings
} }];
"""

# ---------------------------------------------------------------------------
# Baue Lernagent-Prompt -- Schema um time_horizon erweitert, Gewichtung erklaert.
# ---------------------------------------------------------------------------
nodes_by_name["Baue Lernagent-Prompt"]["parameters"]["jsCode"] = """const d = $json;
const eligible = d.findings.filter(f => f.proposal_eligible);
const all = d.findings;

const systemPrompt = `Du bist ein vorsichtiger, ruecksichtsvoller Lernagent fuer ein automatisiertes Aktien-Beobachtungssystem.
Du bekommst BEREITS FERTIG BERECHNETE Statistiken (Fallzahlen, Trefferquoten je Dimension UND Zeithorizont) -- du darfst
diese Zahlen NICHT veraendern oder neu berechnen, nur interpretieren und in Worte fassen.

Jedes Finding ist eine Kombination aus Dimension (news_category/source/ticker/konfidenz_bucket), Wert UND Zeithorizont
(D+1/D+3/D+5/D+10/D+20) -- z.B. "source=Reuters bei D+1". Die Faelle sind bereits gewichtet nach Datenqualitaet
(${d.weighting_formula}) -- 'weighted_direction_accuracy' ist die massgebliche Kennzahl, 'direction_accuracy' die
ungewichtete Vergleichszahl.

Regeln:
- Du erstellst AUSSCHLIESSLICH Vorschlaege (status wird spaeter separat auf 'proposed' gesetzt), niemals Aktivierungen.
- Ein proposal darf sich NUR auf ein Finding aus der Liste 'proposal_candidates' stuetzen (sample_size bereits >=30 geprueft).
- Jeder proposal MUSS "dimension" exakt aus dem Finding uebernehmen (news_category, source, ticker oder konfidenz_bucket),
  "target" exakt aus dessen "value" UND "time_horizon" exakt aus dessen "horizon" -- dimension+target+time_horizon
  zusammen muessen eindeutig ein Finding aus 'proposal_candidates' identifizieren. Erfinde niemals eine dimension oder
  einen horizon, der im Finding nicht so steht.
- current_value ist immer 1.0 (Standardgewichtung, sofern keine andere bekannt ist).
- proposed_value soll die Richtung der beobachteten Abweichung widerspiegeln (z.B. Gewicht senken bei <50% gewichteter
  Trefferquote, Gewicht anheben bei >=80%), aber moderat bleiben (Aenderungen typischerweise 0.1-0.3, nie mehr als 0.5).
- reason muss die tatsaechliche Fallzahl, den Zeithorizont und die gewichtete Trefferquote nennen.
- Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt in diesem Schema, kein Markdown, kein Text davor/danach:
{
  "findings": [ { "dimension": "", "value": "", "horizon": "", "sample_size": 0, "weighted_direction_accuracy": 0, "observation": "", "confidence_level": "" } ],
  "proposals": [ { "proposal_type": "weight_adjustment", "dimension": "", "target": "", "time_horizon": "", "current_value": 1.0, "proposed_value": 0.8, "sample_size": 0, "reason": "", "requires_approval": true } ]
}`;

const userPrompt = `Zeitraum: ${d.analysis_from} bis ${d.analysis_to}
Gesamt-Ereignisse: ${d.total_events} (sauber: ${d.clean_events}, konfundiert: ${d.confounded_events})
Gesamt-Richtungsgenauigkeit (ungewichtet, alle Horizonte zusammen): ${d.overall_direction_accuracy}%
Gewichtungsformel: ${d.weighting_formula}

ALLE FINDINGS (bereits nach Mindestfallzahl je Kombination gefiltert, sample_size>=10):
${JSON.stringify(all, null, 2)}

VORSCHLAGS-KANDIDATEN (sample_size>=30 UND auffaellige GEWICHTETE Trefferquote <50% oder >=80%):
${JSON.stringify(eligible, null, 2)}

Formuliere zu JEDEM Finding aus ALLEN FINDINGS eine kurze Beobachtung (observation), unter Nennung des Zeithorizonts.
Erstelle NUR fuer die VORSCHLAGS-KANDIDATEN ggf. einen proposal (kann auch 0 proposals sein, wenn keiner gerechtfertigt ist).`;

return { json: { ...d, systemPrompt, userPrompt } };
"""

# ---------------------------------------------------------------------------
# Vorschlaege gegen Fallzahlen validieren -- 3-Komponenten-Key, evidence-Objekt.
# ---------------------------------------------------------------------------
nodes_by_name["Vorschlaege gegen Fallzahlen validieren"]["parameters"]["jsCode"] = """function getAiText(resp) {
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

const base = $('Baue Lernagent-Prompt').all()[0].json;
const parsed = parseObj(getAiText($json)) || { findings: [], proposals: [] };

// Sicherheitsnetz: jeder Vorschlag wird GEGEN die deterministisch berechneten
// proposal_eligible-Findings validiert -- ein Vorschlag, der auf keinen
// bekannten (dimension+value+horizon)-Kandidaten mit ausreichender Fallzahl
// passt, wird verworfen, egal was die KI behauptet. Seit Prioritaet 9 ist
// der Match-Key 3-teilig (dimension|value|horizon) statt 2-teilig, damit z.B.
// derselbe Ticker bei D+1 und D+20 nicht verwechselt wird.
const eligibleMap = new Map(
  base.findings.filter(f => f.proposal_eligible).map(f => [f.dimension + '|' + f.value + '|' + f.horizon, f])
);

const safeProposals = [];
for (const p of (Array.isArray(parsed.proposals) ? parsed.proposals : [])) {
  const key = String(p.dimension) + '|' + String(p.target) + '|' + String(p.time_horizon);
  const match = eligibleMap.get(key);
  if (!match) continue; // kein belastbarer Kandidat -> Vorschlag verworfen
  safeProposals.push({
    proposal_type: p.proposal_type || 'weight_adjustment',
    target_type: match.dimension,
    target: String(p.target),
    time_horizon: match.horizon,
    current_value: p.current_value ?? 1.0,
    proposed_value: p.proposed_value,
    sample_size: match.sample_size,
    metric_name: 'weighted_direction_accuracy',
    metric_value: match.weighted_direction_accuracy,
    reason: p.reason || '',
    confidence_level: match.confidence_level,
    evidence: {
      direction_accuracy: match.direction_accuracy,
      weighted_direction_accuracy: match.weighted_direction_accuracy,
      avg_abnormal_return: match.avg_abnormal_return,
      median_abnormal_return: match.median_abnormal_return,
      confounded_pct: match.confounded_pct,
      avg_confidence: match.avg_confidence,
      weighting_formula: base.weighting_formula
    }
  });
}

return [{ json: {
  ...base,
  findings_final: Array.isArray(parsed.findings) ? parsed.findings : [],
  proposals_final: safeProposals
} }];
"""

# ---------------------------------------------------------------------------
# Vorschlag speichern (SQL bauen) -- time_horizon-Spalte + evidence in metadata_json.
# ---------------------------------------------------------------------------
nodes_by_name["Vorschlag speichern (SQL bauen)"]["parameters"]["jsCode"] = """function pgStr(v) { return v === null || v === undefined ? 'NULL' : `'` + String(v).replace(/'/g, `''`) + `'`; }
function pgNum(v) { return v === null || v === undefined || v === '' || isNaN(Number(v)) ? 'NULL' : Number(v); }
function pgBool(v) { return v === null || v === undefined ? 'NULL' : (v ? 'TRUE' : 'FALSE'); }
function pgJson(v) { return `'` + JSON.stringify(v === undefined ? null : v).replace(/'/g, `''`) + `'::jsonb`; }
function pgArr(v) { return `'{` + (Array.isArray(v) ? v : []).map(x => String(x).replace(/\\"/g,'\\\\\\"')).join(',') + `}'`; }


const j = $json;
const sql = `INSERT INTO trading.learning_rule_proposals
  (proposal_type, target_type, target_value, current_value, proposed_value, sample_size, metric_name, metric_value, reason, confidence_level, time_horizon, status, metadata_json)
  VALUES (${pgStr(j.proposal_type)}, ${pgStr(j.target_type)}, ${pgStr(j.target)}, ${pgStr(j.current_value)}, ${pgStr(j.proposed_value)},
          ${pgNum(j.sample_size)}, ${pgStr(j.metric_name)}, ${pgNum(j.metric_value)}, ${pgStr(j.reason)}, ${pgStr(j.confidence_level)},
          ${pgStr(j.time_horizon)}, 'proposed', ${pgJson(j.evidence || {})});`;
return { json: { ...j, sql } };
"""

# ---------------------------------------------------------------------------
# Lernbericht aufbereiten -- Gewichtungshinweis + time_horizon je Vorschlag.
# ---------------------------------------------------------------------------
nodes_by_name["Lernbericht aufbereiten"]["parameters"]["jsCode"] = """const j = $json;
const lines = [
  '📊 Lernagent Newswirkung – Zeitraum ' + j.analysis_from + ' bis ' + j.analysis_to,
  '',
  'Ereignisse gesamt: ' + j.total_events + ' (sauber: ' + j.clean_events + ', konfundiert: ' + j.confounded_events + ')',
  'Gesamt-Richtungsgenauigkeit (ungewichtet, alle Horizonte): ' + (j.overall_direction_accuracy ?? 'n/a') + '%',
  'Gewichtung je Fall: ' + (j.weighting_formula || 'high=1.0, medium=0.7, limited=0.4, confounded=0.25'),
  '',
  'Vorschlaege diese Woche: ' + (j.proposals_final || []).length
];
for (const p of (j.proposals_final || [])) {
  lines.push('  - [' + p.proposal_type + '] ' + p.target + ' bei ' + p.time_horizon + ': ' + p.current_value + ' -> ' + p.proposed_value + ' (n=' + p.sample_size + ', gewichtete Trefferquote ' + (p.metric_value ?? 'n/a') + '%) ' + p.reason);
}
if ((j.proposals_final || []).length === 0) lines.push('  (keine belastbaren Vorschlaege diese Woche)');

return { json: { ...j, report_text: lines.join('\\n') } };
"""

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print("09 aktualisiert.")
for name in DIMENSION_SPECS:
    print("---", name, "query length:", len(nodes_by_name[name]["parameters"]["query"]))
