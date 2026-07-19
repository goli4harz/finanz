# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from n8n_builder_helpers import Builder, PG_HELPERS_JS, GET_BUSINESS_DATE_JS, PG_CRED, OPENAI_CRED, MATRIX_CRED, MATRIX_ROOM

OUT = r"C:\Users\olietz\Documents\finanz\09 – Lernagent Newswirkung.json"

b = Builder("09 – Lernagent Newswirkung")

ANALYSIS_WINDOW_DAYS = 90

n_trigger = b.add({
    "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 0 8 * * 6"}]}},
    "name": "Trigger: Lernagent (Samstag 08:00)",
    "type": "n8n-nodes-base.scheduleTrigger",
    "typeVersion": 1.1,
    "position": [-2600, 0]
})

# ---------------------------------------------------------------------------
# 1. Alle statistischen Kennzahlen werden deterministisch per SQL berechnet
#    (Prinzip: KI interpretiert, berechnet aber keine Kennzahlen selbst neu).
# ---------------------------------------------------------------------------
n_overall = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": f"""SELECT
  count(*) FILTER (WHERE status IN ('completed','confounded')) AS total_events,
  count(*) FILTER (WHERE status = 'completed' AND confounded = FALSE) AS clean_events,
  count(*) FILTER (WHERE confounded = TRUE) AS confounded_events,
  round(100.0 * count(*) FILTER (WHERE status = 'completed' AND confounded = FALSE AND direction_correct = TRUE)
    / NULLIF(count(*) FILTER (WHERE status = 'completed' AND confounded = FALSE AND direction_correct IS NOT NULL), 0), 1) AS overall_direction_accuracy
FROM trading.news_impact_tracking
WHERE created_at >= now() - interval '{ANALYSIS_WINDOW_DAYS} days';""",
        "options": {}
    },
    "name": "SQL: Gesamtkennzahlen",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2400, -240],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_overall)

def dimension_query(name, position, group_col, dim_label):
    return b.add({
        "parameters": {
            "operation": "executeQuery",
            "query": f"""SELECT '{dim_label}' AS dimension, {group_col} AS value,
  count(*) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct IS NOT NULL), 0), 1) AS direction_accuracy,
  round(100.0 * count(*) FILTER (WHERE strength_correct = TRUE) / NULLIF(count(*) FILTER (WHERE strength_correct IS NOT NULL), 0), 1) AS strength_accuracy,
  round(avg(prediction_confidence), 1) AS avg_confidence
FROM trading.news_impact_tracking
WHERE created_at >= now() - interval '{ANALYSIS_WINDOW_DAYS} days'
  AND status = 'completed' AND confounded = FALSE AND {group_col} IS NOT NULL
GROUP BY {group_col}
ORDER BY sample_size DESC;""",
            "options": {}
        },
        "name": name,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": position,
        "onError": "continueRegularOutput",
        "credentials": {"postgres": PG_CRED}
    })

n_by_category = dimension_query("SQL: Je Newskategorie", [-2400, -80], "news_category", "news_category")
b.link(n_trigger, n_by_category)

n_by_source = dimension_query("SQL: Je Quelle", [-2400, 80], "source", "source")
b.link(n_trigger, n_by_source)

n_by_ticker = dimension_query("SQL: Je Ticker", [-2400, 240], "ticker", "ticker")
b.link(n_trigger, n_by_ticker)

# Zusaetzliche, im Auftrag explizit genannte Frage: wirken hohe KI-Konfidenzen
# tatsaechlich haeufiger richtig? Bucket-Vergleich hoch (>=70) vs niedrig (<70).
n_by_confidence = b.add({
    "parameters": {
        "operation": "executeQuery",
        "query": f"""SELECT 'konfidenz_bucket' AS dimension,
  CASE WHEN prediction_confidence >= 70 THEN 'hoch (>=70)' ELSE 'niedrig (<70)' END AS value,
  count(*) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct IS NOT NULL), 0), 1) AS direction_accuracy,
  NULL::numeric AS strength_accuracy,
  round(avg(prediction_confidence), 1) AS avg_confidence
FROM trading.news_impact_tracking
WHERE created_at >= now() - interval '{ANALYSIS_WINDOW_DAYS} days'
  AND status = 'completed' AND confounded = FALSE AND prediction_confidence IS NOT NULL
GROUP BY 1, 2;""",
        "options": {}
    },
    "name": "SQL: Je Konfidenz-Bucket",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.5,
    "position": [-2400, 400],
    "onError": "continueRegularOutput",
    "credentials": {"postgres": PG_CRED}
})
b.link(n_trigger, n_by_confidence)

# ---------------------------------------------------------------------------
# 2. Zusammenfuehren + Mindestfallzahlen-Klassifikation (rein deterministisch)
# ---------------------------------------------------------------------------
n_merge1 = b.add({"parameters": {}, "name": "Merge 1", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2200, 0]})
b.link(n_by_category, n_merge1, dst_index=0)
b.link(n_by_source, n_merge1, dst_index=1)

n_merge2 = b.add({"parameters": {}, "name": "Merge 2", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-2000, 100]})
b.link(n_merge1, n_merge2, dst_index=0)
b.link(n_by_ticker, n_merge2, dst_index=1)

n_merge3 = b.add({"parameters": {}, "name": "Merge 3", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [-1800, 200]})
b.link(n_merge2, n_merge3, dst_index=0)
b.link(n_by_confidence, n_merge3, dst_index=1)

n_classify = b.add({
    "parameters": {
        "jsCode": """// Mindestfallzahlen-Einordnung exakt wie im Auftrag, rein deterministisch --
// die KI bekommt diese Einordnung als FESTE Vorgabe, sie darf sie nicht
// selbst neu bewerten oder aendern.
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
    sample_size: Number(d.sample_size),
    direction_accuracy: d.direction_accuracy === null ? null : Number(d.direction_accuracy),
    strength_accuracy: d.strength_accuracy === null ? null : Number(d.strength_accuracy),
    avg_confidence: d.avg_confidence === null ? null : Number(d.avg_confidence),
    confidence_level: level,
    // Nur Findings mit sample_size>=30 UND deutlich unterdurchschnittlicher
    // (<50%) oder ueberdurchschnittlicher (>=80%) Trefferquote sind
    // ueberhaupt Kandidaten fuer einen Verbesserungsvorschlag -- diese
    // Vorauswahl ist deterministisch, die KI bekommt nur diese Teilmenge
    // ueberhaupt zur Formulierung eines proposals vorgelegt.
    proposal_eligible: Number(d.sample_size) >= 30 && d.direction_accuracy !== null && (Number(d.direction_accuracy) < 50 || Number(d.direction_accuracy) >= 80)
  });
}

const overall = $('SQL: Gesamtkennzahlen').first().json;

return [{ json: {
  analysis_from: new Date(Date.now() - """ + str(ANALYSIS_WINDOW_DAYS) + """ * 86400000).toISOString().substring(0,10),
  analysis_to: new Date().toISOString().substring(0,10),
  total_events: Number(overall.total_events) || 0,
  clean_events: Number(overall.clean_events) || 0,
  confounded_events: Number(overall.confounded_events) || 0,
  overall_direction_accuracy: overall.overall_direction_accuracy === null ? null : Number(overall.overall_direction_accuracy),
  findings
} }];
"""
    },
    "name": "Mindestfallzahlen klassifizieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1600, 200]
})
b.link(n_merge3, n_classify)

# ---------------------------------------------------------------------------
# 3. KI: nur Interpretation/Formulierung, keine eigene Zahlenbasis
# ---------------------------------------------------------------------------
n_build_prompt = b.add({
    "parameters": {
        "jsCode": """const d = $json;
const eligible = d.findings.filter(f => f.proposal_eligible);
const all = d.findings;

const systemPrompt = `Du bist ein vorsichtiger, ruecksichtsvoller Lernagent fuer ein automatisiertes Aktien-Beobachtungssystem.
Du bekommst BEREITS FERTIG BERECHNETE Statistiken (Fallzahlen, Trefferquoten) -- du darfst diese Zahlen NICHT veraendern
oder neu berechnen, nur interpretieren und in Worte fassen.

Regeln:
- Du erstellst AUSSCHLIESSLICH Vorschlaege (status wird spaeter separat auf 'proposed' gesetzt), niemals Aktivierungen.
- Ein proposal darf sich NUR auf ein Finding aus der Liste 'proposal_candidates' stuetzen (sample_size bereits >=30 geprueft).
- current_value fuer proposal_type='source_weight' ist immer 1.0 (Standardgewichtung, sofern keine andere bekannt ist).
- proposed_value soll die Richtung der beobachteten Abweichung widerspiegeln (z.B. Gewicht senken bei <50% Trefferquote,
  Gewicht anheben bei >=80% Trefferquote), aber moderat bleiben (Aenderungen typischerweise 0.1-0.3, nie mehr als 0.5).
- reason muss die tatsaechliche Fallzahl und Trefferquote nennen.
- Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt in diesem Schema, kein Markdown, kein Text davor/danach:
{
  "findings": [ { "dimension": "", "value": "", "sample_size": 0, "direction_accuracy": 0, "observation": "", "confidence_level": "" } ],
  "proposals": [ { "proposal_type": "source_weight", "target": "", "current_value": 1.0, "proposed_value": 0.8, "sample_size": 0, "reason": "", "requires_approval": true } ]
}`;

const userPrompt = `Zeitraum: ${d.analysis_from} bis ${d.analysis_to}
Gesamt-Ereignisse: ${d.total_events} (sauber: ${d.clean_events}, konfundiert: ${d.confounded_events})
Gesamt-Richtungsgenauigkeit: ${d.overall_direction_accuracy}%

ALLE FINDINGS (bereits nach Mindestfallzahl gefiltert, sample_size>=10):
${JSON.stringify(all, null, 2)}

VORSCHLAGS-KANDIDATEN (sample_size>=30 UND auffaellige Trefferquote <50% oder >=80%):
${JSON.stringify(eligible, null, 2)}

Formuliere zu JEDEM Finding aus ALLEN FINDINGS eine kurze Beobachtung (observation).
Erstelle NUR fuer die VORSCHLAGS-KANDIDATEN ggf. einen proposal (kann auch 0 proposals sein, wenn keiner gerechtfertigt ist).`;

return { json: { ...d, systemPrompt, userPrompt } };
"""
    },
    "name": "Baue Lernagent-Prompt",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1400, 200]
})
b.link(n_classify, n_build_prompt)

n_ki = b.add({
    "parameters": {
        "modelId": {"__rl": True, "value": "gpt-5.4-mini", "mode": "list", "cachedResultName": "GPT-5.4-MINI"},
        "responses": {"values": [
            {"role": "system", "content": "={{ $json.systemPrompt }}"},
            {"content": "={{ $json.userPrompt }}"}
        ]},
        "builtInTools": {},
        "options": {"maxTokens": 3000}
    },
    "name": "KI: Lernbericht interpretieren",
    "type": "@n8n/n8n-nodes-langchain.openAi",
    "typeVersion": 2.3,
    "position": [-1200, 200],
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
  return JSON.stringify(resp || '');
}
function parseObj(text) {
  let t = String(text || '').trim().replace(/^```json\\s*/i,'').replace(/^```\\s*/i,'').replace(/```\\s*$/i,'').trim();
  try { const p = JSON.parse(t); return (p && typeof p === 'object') ? p : null; } catch(e) {}
  const s = t.indexOf('{'); const e = t.lastIndexOf('}');
  if (s >= 0 && e > s) { try { return JSON.parse(t.substring(s, e+1)); } catch(err) {} }
  return null;
}

const base = $('Baue Lernagent-Prompt').item.json;
const parsed = parseObj(getAiText($json)) || { findings: [], proposals: [] };

// Sicherheitsnetz: jeder Vorschlag wird GEGEN die deterministisch berechneten
// proposal_eligible-Findings validiert -- ein Vorschlag, der auf keinen
// bekannten Kandidaten (dimension+value) mit ausreichender Fallzahl passt,
// wird verworfen, egal was die KI behauptet.
const eligibleMap = new Map(
  base.findings.filter(f => f.proposal_eligible).map(f => [f.dimension + '|' + f.value, f])
);

const safeProposals = [];
for (const p of (Array.isArray(parsed.proposals) ? parsed.proposals : [])) {
  const key = (p.proposal_type === 'source_weight' ? 'source' : p.proposal_type) + '|' + p.target;
  const match = eligibleMap.get(key) || [...eligibleMap.values()].find(f => f.value === p.target);
  if (!match) continue; // kein belastbarer Kandidat -> Vorschlag verworfen
  safeProposals.push({
    proposal_type: p.proposal_type || 'source_weight',
    target_type: p.proposal_type === 'source_weight' ? 'source' : 'unbekannt',
    target: String(p.target),
    current_value: p.current_value ?? 1.0,
    proposed_value: p.proposed_value,
    sample_size: match.sample_size,
    metric_name: 'direction_accuracy',
    metric_value: match.direction_accuracy,
    reason: p.reason || '',
    confidence_level: match.confidence_level
  });
}

return [{ json: {
  ...base,
  findings_final: Array.isArray(parsed.findings) ? parsed.findings : [],
  proposals_final: safeProposals
} }];
"""
    },
    "name": "Vorschlaege gegen Fallzahlen validieren",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-1000, 200]
})
b.link(n_ki, n_parse)

# ---------------------------------------------------------------------------
# 4. Vorschlaege in learning_rule_proposals speichern (status='proposed')
#    -- ueber SplitInBatches, da pro Vorschlag ein eigener INSERT noetig ist.
# ---------------------------------------------------------------------------
n_split_proposals = b.add({
    "parameters": {
        "jsCode": "return ($json.proposals_final || []).map(p => ({ json: p }));"
    },
    "name": "Vorschlaege auffaechern",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-800, 100]
})
b.link(n_parse, n_split_proposals)

n_save_proposal_in, n_save_proposal_out = b.pg_exec_pair("Vorschlag speichern", [-600, 100], """
const j = $json;
const sql = `INSERT INTO trading.learning_rule_proposals
  (proposal_type, target_type, target_value, current_value, proposed_value, sample_size, metric_name, metric_value, reason, confidence_level, status)
  VALUES (${pgStr(j.proposal_type)}, ${pgStr(j.target_type)}, ${pgStr(j.target)}, ${pgStr(j.current_value)}, ${pgStr(j.proposed_value)},
          ${pgNum(j.sample_size)}, ${pgStr(j.metric_name)}, ${pgNum(j.metric_value)}, ${pgStr(j.reason)}, ${pgStr(j.confidence_level)}, 'proposed');`;
return { json: { ...j, sql } };
""")
b.link(n_split_proposals, n_save_proposal_in)

# ---------------------------------------------------------------------------
# 5. Agentenlauf protokollieren + Lernbericht per Matrix versenden
# ---------------------------------------------------------------------------
n_agentlog_in, n_agentlog_out = b.pg_exec_pair("Agentenlauf protokollieren", [-800, 300], GET_BUSINESS_DATE_JS + """

const j = $json;
const sql = `INSERT INTO trading.agent_runs
  (run_id, agent_name, agent_role, model_name, prompt_version, input_reference, output_reference, status, started_at, finished_at)
  VALUES (${pgStr('lernagent-' + getBusinessDate())}, 'lernagent-newswirkung', 'lernen',
          'gpt-5.4-mini', 'lernagent-v1', ${pgStr(j.analysis_from + '..' + j.analysis_to)},
          ${pgStr((j.proposals_final || []).length + ' Vorschlaege')}, 'success', now(), now());`;
return { json: { ...j, sql } };
""")
b.link(n_parse, n_agentlog_in)

n_build_report = b.add({
    "parameters": {
        "jsCode": """const j = $json;
const lines = [
  '📊 Lernagent Newswirkung – Zeitraum ' + j.analysis_from + ' bis ' + j.analysis_to,
  '',
  'Ereignisse gesamt: ' + j.total_events + ' (sauber: ' + j.clean_events + ', konfundiert: ' + j.confounded_events + ')',
  'Gesamt-Richtungsgenauigkeit: ' + (j.overall_direction_accuracy ?? 'n/a') + '%',
  '',
  'Vorschlaege diese Woche: ' + (j.proposals_final || []).length
];
for (const p of (j.proposals_final || [])) {
  lines.push('  - [' + p.proposal_type + '] ' + p.target + ': ' + p.current_value + ' -> ' + p.proposed_value + ' (n=' + p.sample_size + ') ' + p.reason);
}
if ((j.proposals_final || []).length === 0) lines.push('  (keine belastbaren Vorschlaege diese Woche)');

return { json: { ...j, report_text: lines.join('\\n') } };
"""
    },
    "name": "Lernbericht aufbereiten",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-600, 300]
})
b.link(n_agentlog_out, n_build_report)

n_send_report = b.add({
    "parameters": {
        "method": "PUT",
        "url": f"=https://matrix.org/_matrix/client/v3/rooms/{MATRIX_ROOM}/send/m.room.message/{{{{ 'lernbericht_' + $json.analysis_to }}}}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "contentType": "raw",
        "rawContentType": "application/json",
        "body": "={{ JSON.stringify({ msgtype: 'm.text', body: $json.report_text }) }}",
        "options": {"timeout": 30000}
    },
    "name": "Matrix: Lernbericht senden",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [-400, 300],
    "onError": "continueRegularOutput",
    "credentials": {"httpHeaderAuth": MATRIX_CRED}
})
b.link(n_build_report, n_send_report)

b.write_and_validate(OUT)
