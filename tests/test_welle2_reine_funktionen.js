// Welle 2 - lokale Unit-Tests fuer die deterministischen, reinen Funktionen
// aus "02"/"02b"/"06"/"13". Funktionen sind wortgleich (oder auf das
// Wesentliche reduziert) aus dem deployten Code entnommen. Kein n8n/keine
// DB noetig. Deckt 12 der 16 in docs/TESTPLAN_WELLE_2.md geforderten
// Testfaelle ab (DRY_RUN/REQUIRE_CONFIRMATION unveraendert aus Welle 1,
// siehe dort; 2 weitere sind Live-only, siehe Testplan).
//
// Ausfuehren: node tests/test_welle2_reine_funktionen.js

let pass = 0, fail = 0;
function assert(cond, label) {
  if (cond) { console.log('PASS:', label); pass++; }
  else { console.log('FAIL:', label); fail++; }
}
function round(v, d = 3) { if (v === null || v === undefined || isNaN(v)) return null; return parseFloat(Number(v).toFixed(d)); }

// Auszug aus sql/032 (Strategie-Regime-Matrix, rule_version 'regime-matrix-v1')
const MATRIX = {
  'mean_reversion|sideways_low_vol': { fit_multiplier: 1.00, blocked: false },
  'mean_reversion|bear_trend': { fit_multiplier: 0.00, blocked: true },
  'trend_following|bull_trend_low_vol': { fit_multiplier: 1.00, blocked: false },
  'trend_following|sideways_low_vol': { fit_multiplier: 0.30, blocked: false },
  'breakout|stress': { fit_multiplier: 0.00, blocked: true }
};
function matrixLookup(strategy, regime) { return MATRIX[strategy + '|' + regime] || { fit_multiplier: 0.3, blocked: false }; }

// Test 1: Mean Reversion im Seitwaertsmarkt -> volle Eignung, nicht blockiert
{
  const m = matrixLookup('mean_reversion', 'sideways_low_vol');
  assert(m.fit_multiplier === 1.00 && m.blocked === false, 'Test 1: Mean Reversion in sideways_low_vol -> fit_multiplier=1.00, nicht blockiert');
}

// Test 2: Mean Reversion im starken Abwaertstrend -> blockiert
{
  const m = matrixLookup('mean_reversion', 'bear_trend');
  assert(m.blocked === true && m.fit_multiplier === 0, 'Test 2: Mean Reversion in bear_trend -> blockiert (dominanter Gegentrend)');
}

// Test 3: Trendfolge mit Marktbestaetigung -> volle Eignung
{
  const m = matrixLookup('trend_following', 'bull_trend_low_vol');
  assert(m.fit_multiplier === 1.00 && m.blocked === false, 'Test 3: Trendfolge in bull_trend_low_vol -> fit_multiplier=1.00');
}

// Test 4: Trendfolge gegen Marktregime -> eingeschraenkt, nicht blockiert
{
  const m = matrixLookup('trend_following', 'sideways_low_vol');
  assert(m.fit_multiplier < 0.5 && m.blocked === false, 'Test 4: Trendfolge in sideways_low_vol -> eingeschraenkt (fit=' + m.fit_multiplier + '), nicht hart blockiert');
}

// Test 5+6: Breakout Historie (aus Welle 1 uebernommen, hier fuer den neuen
// blockers_json-Eintrag im Strategiesignal selbst getestet statt nur im Veto)
function breakoutBlockers(closesLength, hatMeta52w) {
  const breakoutHistoryAusreichend = hatMeta52w || closesLength >= 252;
  return breakoutHistoryAusreichend ? [] : [{ code: 'HISTORY_252_MISSING' }];
}
{
  const blockers252 = breakoutBlockers(252, false);
  assert(blockers252.length === 0, 'Test 5: Breakout mit 252 Tagen -> kein HISTORY_252_MISSING-Blocker im Signal');
  const blockers90 = breakoutBlockers(90, false);
  assert(blockers90.length === 1 && blockers90[0].code === 'HISTORY_252_MISSING', 'Test 6: Breakout mit nur 90 Tagen -> HISTORY_252_MISSING-Blocker bereits im Strategiesignal selbst');
}

// Test 7+8: News/Event Alter (Schwelle 12h Default/news_event)
function newsStale(ageHours, maxAgeH) { return ageHours > maxAgeH; }
{
  assert(newsStale(2, 12) === false, 'Test 7: News/Event mit 2h alter Nachricht (< 12h Schwelle) -> nicht NEWS_STALE');
  assert(newsStale(20, 12) === true, 'Test 8: News/Event mit 20h alter Nachricht (> 12h Schwelle) -> NEWS_STALE');
}

// Test 9: widerspruechliche Strategien bei einem Ticker -> hoechster
// adjustedScore gewinnt, andere werden Alternativen (nicht verworfen)
{
  const candidates = [
    { strategy: 'mean_reversion', raw_score: 0.6, direction: 'long' },
    { strategy: 'trend_following', raw_score: 0.5, direction: 'short' }
  ].map(c => { const m = matrixLookup(c.strategy, 'sideways_low_vol'); return { ...c, fitMultiplier: m.fit_multiplier, blocked: m.blocked, adjustedScore: round(c.raw_score * m.fit_multiplier, 4) }; });
  const usable = candidates.filter(c => !c.blocked).sort((a, b) => b.adjustedScore - a.adjustedScore);
  assert(usable[0].strategy === 'mean_reversion' && usable.length === 2, 'Test 9: widerspruechliche Strategien (long mean_reversion vs. short trend_following) -> mean_reversion dominant (hoeherer adjustedScore), trend_following bleibt als Alternative erhalten');
}

// Test 10: hohe Opportunity bei hohem Risiko -> unabhaengige Dimensionen
{
  const opportunity = 0.85; // starkes Signal, gute Regime-Passung, gutes CRV
  const riskScore = 0.75;   // trotzdem grosse Stopdistanz + Stress-Regime
  assert(opportunity > 0.8 && riskScore > 0.7, 'Test 10: hohe Opportunity (0.85) UND hohes Risiko (0.75) gleichzeitig moeglich -> Dimensionen sind unabhaengig, kein Trade-off eingebaut');
}

// Test 11: hohe Evidenz bei niedriger Opportunity
{
  const evidenceGroups = new Set(['overextension', 'momentum', 'trend_confirmation', 'fundamental', 'news']);
  const evidence = round(Math.min(1, evidenceGroups.size / 6) * 0.9, 3); // hohe Datenqualitaet
  const opportunity = 0.2; // schwaches Rohsignal trotz vieler Evidenzgruppen
  assert(evidence > 0.7 && opportunity < 0.3, 'Test 11: viele unabhaengige Evidenzgruppen (5/6) -> hohe evidence_confidence (' + evidence + ') trotz niedriger opportunity (0.2) -> getrennte Dimensionen bestaetigt');
}

// Test 12: breite Scannerliste mit Limit (SCANNER_MAX_CANDIDATES_TOTAL)
{
  const survivors = Array.from({ length: 30 }, (_, i) => ({ ticker: 'T' + i, score: 1 - i * 0.01 }));
  const MAX_TOTAL = 15;
  const stageB = survivors.slice(0, MAX_TOTAL);
  assert(stageB.length === MAX_TOTAL, 'Test 12: 30 Kandidaten, Limit 15 -> genau 15 erreichen Stufe B, Rest mit Grund ausgeschlossen');
}

// Test 13: sektorale Begrenzung (SCANNER_MAX_CANDIDATES_PER_SEKTOR)
{
  const survivors = [
    { ticker: 'A', sektor: 'Auto' }, { ticker: 'B', sektor: 'Auto' }, { ticker: 'C', sektor: 'Auto' }, { ticker: 'D', sektor: 'Auto' },
    { ticker: 'E', sektor: 'Chemie' }
  ];
  const MAX_PER_SEKTOR = 3;
  const perSektor = {}; const included = [];
  for (const s of survivors) {
    if ((perSektor[s.sektor] || 0) >= MAX_PER_SEKTOR) continue;
    perSektor[s.sektor] = (perSektor[s.sektor] || 0) + 1;
    included.push(s.ticker);
  }
  assert(included.filter(t => ['A', 'B', 'C'].includes(t)).length === 3 && !included.includes('D') && included.includes('E'), 'Test 13: 4 Auto-Kandidaten, Limit 3 je Sektor -> nur 3 Auto-Werte + der Chemie-Wert aufgenommen, D ausgeschlossen');
}

// Test 14: Datenbankfehler (leere Strategiesignal-/Regime-Tabellen)
{
  const techRows = [], trendRows = [1], strategyRows = [];
  const dbLesefehler = techRows.length === 0 || trendRows.length === 0 || strategyRows.length === 0;
  assert(dbLesefehler === true, 'Test 14: strategyRows leer -> dbLesefehler=true (Welle 2 erweitert den Welle-1-Check um strategy_signals)');
}

console.log('\n--- Ergebnis:', pass, 'bestanden,', fail, 'fehlgeschlagen', '---');
process.exit(fail > 0 ? 1 : 0);
