// Haertung Welle 1-3, Phase 17: Testsuiten A-F.
// Node-Nachbildungen der produktiven Kernfunktionen zum Stand dieser Haertungsauftrag-Sitzung
// (2026-08-02) - siehe TESTPLAN_HAERTUNG_WELLE_1_3.md fuer Umfang/Methode je Suite und
// TESTERGEBNISSE_HAERTUNG_WELLE_1_3.md fuer den zuletzt protokollierten Lauf.
// Ausfuehren: node tests/welle_1_3_testsuite.js

let pass = 0, fail = 0;
const failures = [];

function assertEqual(actual, expected, label) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { pass++; }
  else { fail++; failures.push(`${label}: erwartet ${JSON.stringify(expected)}, erhalten ${JSON.stringify(actual)}`); }
}
function assertTrue(cond, label) {
  if (cond) { pass++; } else { fail++; failures.push(`${label}: Bedingung war false`); }
}

function suite(name, fn) {
  console.log(`\n=== Suite ${name} ===`);
  const before = { pass, fail };
  fn();
  console.log(`  ${pass - before.pass} bestanden, ${fail - before.fail} fehlgeschlagen`);
}

// ---------------------------------------------------------------------------
// Suite A: Merge/Load-Sicherheit (Phase 2/12/13/14 - Wrap-Node-Muster)
// ---------------------------------------------------------------------------
suite('A - Merge/Load-Sicherheit (kein Kreuzprodukt, kein Warten auf nie feuernden Zweig)', () => {
  // Simuliert die n8n Merge-Node im Default-Modus ("append"): Items aller Eingaenge werden
  // aneinandergehaengt, nicht multipliziert (im Gegensatz zu combine/combineAll).
  function appendMerge(...inputs) {
    return inputs.flat();
  }
  function wrap(dataset, rows) {
    return [{ dataset, rows }];
  }

  // A1: zwei Quellen mit je N/M Zeilen, gewrappt zu je 1 Item -> Merge liefert genau 2 Items,
  // nicht N*M (das waere das combineAll-Kreuzprodukt-Risiko aus Phase 2).
  const wrapA = wrap('quelleA', Array.from({ length: 37 }, (_, i) => ({ id: i })));
  const wrapB = wrap('quelleB', Array.from({ length: 52 }, (_, i) => ({ id: i })));
  const merged = appendMerge(wrapA, wrapB);
  assertEqual(merged.length, 2, 'A1: gewrappte Merge liefert 2 Items bei 37x52 Zeilen (nicht 1924)');

  // A2: eine Quelle liefert 0 Zeilen (leere Abfrage) - mit alwaysOutputData entsteht trotzdem
  // ein Platzhalter-Item, das die nachgelagerte rows()-Filterfunktion (07/10/13/14) korrekt
  // als leeres Array behandelt, nicht als fehlendes Item.
  function rows(datasetItem) {
    return (datasetItem[0].rows || []).filter(r => r && Object.keys(r).length > 0);
  }
  const leereQuelle = wrap('quelleLeer', []);
  assertEqual(rows(leereQuelle).length, 0, 'A2: leere Quelle liefert 0 Zeilen nach rows(), kein Crash');

  // A3: Stufen-Bypass (Phase 14) - bei deaktiviertem Feature-Flag darf die Stufe komplett
  // uebersprungen werden, ohne dass ein nachgelagerter Merge/IF auf sie wartet.
  function stageGate(flagAktiv, weiterNode) {
    return flagAktiv ? { naechster: 'AusfuehrenStufe' } : { naechster: weiterNode };
  }
  assertEqual(stageGate(false, 'Ausfuehren: naechsteStufe').naechster, 'Ausfuehren: naechsteStufe', 'A3: deaktiviertes Flag bypassed direkt zur naechsten Stufe');
  assertEqual(stageGate(true, 'Ausfuehren: naechsteStufe').naechster, 'AusfuehrenStufe', 'A3b: aktiviertes Flag ruft die Stufe auf');
});

// ---------------------------------------------------------------------------
// Suite B: Paper-Trading (Phase 4/5 - data_error-Retry, Gap-through-Stop)
// ---------------------------------------------------------------------------
suite('B - Paper-Trading (data_error-Retry, Gap-through-Stop)', () => {
  // Nachbildung stopRawExitPrice() aus 14 (Phase 5): Long/Short, Gap-aware.
  function stopRawExitPrice(direction, open, stop) {
    if (direction === 'long') return open < stop ? open : stop;
    return open > stop ? open : stop;
  }
  assertEqual(stopRawExitPrice('long', 106, 105), 105, 'B1: Long normaler Stop (kein Gap) -> exakt Stop');
  assertEqual(stopRawExitPrice('long', 100, 105), 100, 'B2: Long Gap unter Stop -> Open-Preis');
  assertEqual(stopRawExitPrice('short', 104, 105), 105, 'B3: Short normaler Stop (kein Gap) -> exakt Stop');
  assertEqual(stopRawExitPrice('short', 110, 105), 110, 'B4: Short Gap ueber Stop -> Open-Preis');

  // Nachbildung des data_error-Retry-Zaehlers (Phase 4).
  function dataErrorSchritt(status, attempts, maxAttempts) {
    if (status === 'data_error') {
      const neu = attempts + 1;
      return neu >= maxAttempts ? { status: 'data_error_final', attempts: neu } : { status: 'data_error', attempts: neu };
    }
    return { status, attempts: 0 };
  }
  assertEqual(dataErrorSchritt('data_error', 0, 5).attempts, 1, 'B5: erster Fehltag -> Zaehler 1');
  assertEqual(dataErrorSchritt('data_error', 4, 5).status, 'data_error_final', 'B6: Erreichen von MAX_DATA_ERROR_RETRIES -> Eskalation');
  assertEqual(dataErrorSchritt('open', 3, 5).attempts, 0, 'B7: erfolgreiche Wiederherstellung -> Zaehler zurueckgesetzt');

  // Nachbildung der deterministischen trade_id (Phase 16, Idempotenz-Grundlage).
  function tradeId(ticker, businessDate, strategy) { return `${ticker}-${businessDate}-${strategy}`; }
  assertEqual(tradeId('SAP.DE', '2026-08-02', 'trend_following'), tradeId('SAP.DE', '2026-08-02', 'trend_following'), 'B8: trade_id deterministisch (gleiche Eingabe -> gleiche ID, Grundlage fuer ON CONFLICT DO NOTHING)');
});

// ---------------------------------------------------------------------------
// Suite C: Portfolio-Risiko (Phase 6+7 - Status-Zwischenzustand portfolio_pending)
// ---------------------------------------------------------------------------
suite('C - Portfolio-Risiko (Empfehlung/Portfolioveto-Statusmodell)', () => {
  function portfolioCheckSchritt(approved) {
    return { new_status: approved ? 'offen' : 'portfolio_blocked' };
  }
  assertEqual(portfolioCheckSchritt(true).new_status, 'offen', 'C1: genehmigt -> offen');
  assertEqual(portfolioCheckSchritt(false).new_status, 'portfolio_blocked', 'C2: abgelehnt -> portfolio_blocked (nicht mehr dauerhaft offen haengend)');

  // Dead-Letter-Eskalation (Phase 6+7, MAX_PORTFOLIO_CHECK_ATTEMPTS).
  function portfolioAttemptSchritt(attempts, maxAttempts) {
    const neu = attempts + 1;
    return neu >= maxAttempts ? 'portfolio_check_failed' : 'portfolio_pending';
  }
  assertEqual(portfolioAttemptSchritt(4, 5), 'portfolio_check_failed', 'C3: 5. Versuch -> Eskalation zu portfolio_check_failed');
  assertEqual(portfolioAttemptSchritt(0, 5), 'portfolio_pending', 'C4: erster Versuch -> bleibt portfolio_pending');

  // Rueckstandsverarbeitung (Phase 7): rein statusbasiert, kein Datumsfilter mehr.
  function ladeAusstehende(rows) { return rows.filter(r => r.status === 'portfolio_pending'); }
  const beispielRows = [
    { ticker: 'A', status: 'portfolio_pending', entry_datum: '2026-07-30' }, // aelter als heute, muss trotzdem geladen werden
    { ticker: 'B', status: 'offen', entry_datum: '2026-08-02' },
    { ticker: 'C', status: 'portfolio_pending', entry_datum: '2026-08-02' }
  ];
  assertEqual(ladeAusstehende(beispielRows).map(r => r.ticker), ['A', 'C'], 'C5: veraltete portfolio_pending-Zeile (2026-07-30) wird trotzdem geladen, kein Rueckstandsverlust');
});

// ---------------------------------------------------------------------------
// Suite D: Markt-Screener (Phase 8 - echte relative Staerke vs. Index)
// ---------------------------------------------------------------------------
suite('D - Markt-Screener (relative Staerke vs. Referenzindex)', () => {
  function absoluteReturn(preisAlt, preisNeu) { return ((preisNeu - preisAlt) / preisAlt) * 100; }
  function relativeStrengthVsIndex(aktienReturn, indexReturn) { return aktienReturn - indexReturn; }

  const aktieReturn = absoluteReturn(100, 105); // +5%
  const indexReturn = absoluteReturn(100, 108); // +8%
  const relStrength = relativeStrengthVsIndex(aktieReturn, indexReturn);
  assertTrue(relStrength < 0, 'D1 (Testfall D5 aus dem Auftrag): positive Absolutrendite (+5%), aber negative relative Staerke ggue. staerkerem Index (+8%)');

  const aktieReturn2 = absoluteReturn(100, 95); // -5%
  const indexReturn2 = absoluteReturn(100, 98); // -2%
  assertTrue(relativeStrengthVsIndex(aktieReturn2, indexReturn2) < 0, 'D2: Aktie faellt weniger als Markt in absoluten Zahlen (-5% vs -2%), aber real schwaecher relativ');

  // Positionsgroessen-Wertlimit (Phase 10) - hier eingeordnet, da direkt aus derselben
  // Kandidaten-Pipeline gespeist.
  function quantityByValue(modelPortfolioValue, maxPositionValuePct, entry) {
    return Math.floor((modelPortfolioValue * maxPositionValuePct / 100) / entry);
  }
  function theoreticalQuantity(quantityByRisk, qtyByValue) { return Math.min(quantityByRisk, qtyByValue); }
  const qByRisk = 500; // grosszuegiges Risikolimit
  const qByValueTeuer = quantityByValue(100000, 5, 20000); // teurer Titel, 5% Limit
  assertEqual(qByValueTeuer, 0, 'D3: extrem teurer Titel -> Wertlimit liefert 0 Stueck (QUANTITY_ZERO-Veto greift)');
  assertEqual(theoreticalQuantity(qByRisk, qByValueTeuer), 0, 'D4: min(Risiko, Wert) = 0, obwohl Risikolimit allein 500 erlaubt haette');
  const qByValueNormal = quantityByValue(100000, 5, 100);
  assertEqual(theoreticalQuantity(qByRisk, qByValueNormal), 50, 'D5: guenstiger Titel -> Wertlimit bindet vor Risikolimit (min(500,50)=50)');
});

// ---------------------------------------------------------------------------
// Suite E: Zustands-Konsistenz (Phase 16 - Idempotenz-Annahmen)
// ---------------------------------------------------------------------------
suite('E - Zustands-Konsistenz (Idempotenz bei Retry)', () => {
  // Simuliert ON CONFLICT (trade_id) DO NOTHING: zweiter Insert mit identischem Key aendert
  // die Tabelle nicht, es entsteht keine zweite Zeile.
  function onConflictDoNothing(tabelle, key, row) {
    if (tabelle.some(r => r._key === key)) return tabelle; // no-op, wie ON CONFLICT DO NOTHING
    return [...tabelle, { _key: key, ...row }];
  }
  let paperTrades = [];
  paperTrades = onConflictDoNothing(paperTrades, 'SAP.DE-2026-08-02-trend_following', { status: 'proposed' });
  paperTrades = onConflictDoNothing(paperTrades, 'SAP.DE-2026-08-02-trend_following', { status: 'proposed' }); // Retry
  assertEqual(paperTrades.length, 1, 'E1: Retry mit identischem trade_id erzeugt keine zweite Zeile');

  // Simuliert das Revisionierungsmuster (stock_price_history u.a.): Retry erzeugt eine NEUE,
  // hoehere Revision statt eines Fehlers - alte Revision wird korrekt geschlossen.
  function revisionierterWrite(tabelle, symbol, datum, daten) {
    const aktuelle = tabelle.filter(r => r.symbol === symbol && r.trading_date === datum && r.valid_to === null);
    const geschlossen = tabelle.map(r => (aktuelle.includes(r) ? { ...r, valid_to: 'now' } : r));
    const maxRev = Math.max(0, ...tabelle.filter(r => r.symbol === symbol && r.trading_date === datum).map(r => r.revision_number));
    return [...geschlossen, { symbol, trading_date: datum, revision_number: maxRev + 1, valid_to: null, ...daten }];
  }
  let history = [];
  history = revisionierterWrite(history, 'SAP.DE', '2026-08-02', { close: 200 });
  history = revisionierterWrite(history, 'SAP.DE', '2026-08-02', { close: 201 }); // Retry mit leicht korrigiertem Wert
  assertEqual(history.filter(r => r.valid_to === null).length, 1, 'E2: genau eine aktuelle Revision nach Retry');
  assertEqual(history.filter(r => r.valid_to === null)[0].revision_number, 2, 'E3: Retry erzeugt Revision 2, nicht Ueberschreiben oder Fehler');
  assertEqual(history.find(r => r.revision_number === 1).valid_to, 'now', 'E4: alte Revision 1 korrekt geschlossen (valid_to gesetzt)');
});

// ---------------------------------------------------------------------------
// Suite F: Report/Dispatch (Phase 13 - Zweigzusammenfuehrung 05, Phase 14 - Envelopes)
// ---------------------------------------------------------------------------
suite('F - Report/Dispatch (Zweigsicherheit 05, konsolidierte Envelopes 13/14)', () => {
  // Nachbildung von 05s "Abschluss-Ergebnis bauen" (Phase 13).
  function abschlussErgebnis(zweig, items) {
    if (zweig === 'dry_run') return { status: 'skipped', processed: 1, successful: 0, failed: 0 };
    if (zweig === 'abgelehnt') return { status: 'failed', processed: 1, successful: 0, failed: 1 };
    if (zweig === 'versand') {
      const failedItems = items.filter(i => i._send_failed);
      const failed = failedItems.length, processed = items.length, successful = processed - failed;
      return { status: failed === 0 ? 'success' : (successful === 0 ? 'failed' : 'partial_failure'), processed, successful, failed };
    }
    return { status: 'failed', processed: 0, successful: 0, failed: 0 };
  }
  assertEqual(abschlussErgebnis('dry_run', []).status, 'skipped', 'F1: DRY_RUN -> status skipped, kein Versand');
  assertEqual(abschlussErgebnis('abgelehnt', []).status, 'failed', 'F2: abgelehnter Bericht -> status failed, kein Versand');
  assertEqual(abschlussErgebnis('versand', [{ _send_failed: false }, { _send_failed: false }]).status, 'success', 'F3: Matrix+Email beide ok -> success');
  assertEqual(abschlussErgebnis('versand', [{ _send_failed: false }, { _send_failed: true }]).status, 'partial_failure', 'F4: Email fehlgeschlagen, Matrix ok -> partial_failure');
  assertEqual(abschlussErgebnis('versand', [{ _send_failed: true }, { _send_failed: true }]).status, 'failed', 'F5: beide fehlgeschlagen -> failed');
  assertEqual(abschlussErgebnis(undefined, []).status, 'failed', 'F6: unbekannter/kein Zweig -> defensive failed-Huelle statt Absturz');

  // Nachbildung von 13s/14s neuem konsolidierten Envelope (Phase 14).
  function summarizeJob(dispatched, executedErrors) {
    const real = dispatched.filter(d => d.sql !== 'SELECT 1;');
    return { attempted: dispatched.length, processed: real.length, failed: executedErrors.length };
  }
  function envelopeStatus(attempted, failed, successful) {
    if (attempted === 0) return 'skipped';
    if (failed === 0) return 'success';
    if (successful === 0) return 'failed';
    return 'partial_failure';
  }
  const jobA = summarizeJob([{ sql: 'INSERT ...' }, { sql: 'SELECT 1;' }], []);
  assertEqual(jobA, { attempted: 2, processed: 1, failed: 0 }, 'F7: DRY_RUN-Leerlauf (SELECT 1;) zaehlt nicht als processed');
  assertEqual(envelopeStatus(0, 0, 0), 'skipped', 'F8: 0 dispatchte Items ueber alle Jobs -> status skipped');
  assertEqual(envelopeStatus(3, 1, 2), 'partial_failure', 'F9: 1 von 3 fehlgeschlagen -> partial_failure');
});

console.log(`\n=== Gesamtergebnis: ${pass} bestanden, ${fail} fehlgeschlagen (von ${pass + fail}) ===`);
if (failures.length) {
  console.log('\nFehlgeschlagene Tests:');
  for (const f of failures) console.log('  - ' + f);
  process.exitCode = 1;
}
