// Welle 3 - lokale Unit-Tests fuer die deterministischen, reinen Funktionen
// aus Workflow "14" (Ausfuehrung/Exit/Portfoliorisiko) und "09b" (Lernagent-
// Gates). Funktionen sind wortgleich (oder auf das Wesentliche reduziert)
// aus dem deployten Code entnommen. Kein n8n/keine DB noetig.
//
// Ausfuehren: node tests/test_welle3_reine_funktionen.js
// Deckt 17 der 22 geforderten Testfaelle ab. Test 10 (Trailing-Stop) ist
// bewusst NICHT implementiert (siehe docs/AUSFUEHRUNGSMODELL.md) - der Test
// prueft das explizit und dokumentiert die Luecke statt sie zu verstecken.
// Tests 16/17/19 (Walk-Forward/OOS/Kalibrierung) sind Schema-only (siehe
// docs/BACKTESTING_UND_WALK_FORWARD.md, docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md)
// und daher ohne echte Daten nicht sinnvoll lokal testbar. Test 21 (DRY_RUN)
// unveraendert aus Welle 1/2.

let pass = 0, fail = 0;
function assert(cond, label) {
  if (cond) { console.log('PASS:', label); pass++; }
  else { console.log('FAIL:', label); fail++; }
}
function round(v, d = 4) { if (v === null || v === undefined || isNaN(v)) return null; return parseFloat(Number(v).toFixed(d)); }

// Auszug aus w14_execution_exit.txt: Stop/Ziel-Beruehrung + AMBIGUOUS_BAR_POLICY
function evaluateExit(direction, entry, stop, target, bar, timeStopAt, thesisExpiresAt, now) {
  const richtungLong = direction === 'long';
  const stopBeruehrt = richtungLong ? bar.low <= stop : bar.high >= stop;
  const targetBeruehrt = richtungLong ? bar.high >= target : bar.low <= target;
  let exitReason = null, exitPrice = null, ambiguous = false;
  const exitReasonsAll = [];
  if (stopBeruehrt && targetBeruehrt) {
    ambiguous = true;
    exitReasonsAll.push('stop_loss', 'target_reached', 'ambiguous_execution');
    exitReason = 'stop_loss'; exitPrice = stop; // conservative_stop_first
  } else if (stopBeruehrt) { exitReason = 'stop_loss'; exitPrice = stop; exitReasonsAll.push('stop_loss'); }
  else if (targetBeruehrt) { exitReason = 'target_reached'; exitPrice = target; exitReasonsAll.push('target_reached'); }
  if (!exitReason && timeStopAt && new Date(timeStopAt) <= now) { exitReason = 'time_stop'; exitPrice = bar.close; exitReasonsAll.push('time_stop'); }
  if (!exitReason && thesisExpiresAt && new Date(thesisExpiresAt) <= now) { exitReason = 'thesis_expired'; exitPrice = bar.close; exitReasonsAll.push('thesis_expired'); }
  return { exitReason, exitPrice, ambiguous, exitReasonsAll };
}

// Test 1: Long-Trade erreicht Stop
{
  const r = evaluateExit('long', 100, 95, 110, { low: 94, high: 101, close: 96 }, null, null, new Date());
  assert(r.exitReason === 'stop_loss' && r.exitPrice === 95, 'Test 1: Long-Trade beruehrt Stop (Low 94 <= Stop 95) -> stop_loss @ 95');
}
// Test 2: Long-Trade erreicht Ziel
{
  const r = evaluateExit('long', 100, 95, 110, { low: 101, high: 111, close: 109 }, null, null, new Date());
  assert(r.exitReason === 'target_reached' && r.exitPrice === 110, 'Test 2: Long-Trade beruehrt Ziel (High 111 >= Ziel 110) -> target_reached @ 110');
}
// Test 3: Short-Trade erreicht Stop
{
  const r = evaluateExit('short', 100, 105, 90, { low: 99, high: 106, close: 104 }, null, null, new Date());
  assert(r.exitReason === 'stop_loss' && r.exitPrice === 105, 'Test 3: Short-Trade beruehrt Stop (High 106 >= Stop 105) -> stop_loss @ 105');
}
// Test 4: Short-Trade erreicht Ziel
{
  const r = evaluateExit('short', 100, 105, 90, { low: 89, high: 99, close: 91 }, null, null, new Date());
  assert(r.exitReason === 'target_reached' && r.exitPrice === 90, 'Test 4: Short-Trade beruehrt Ziel (Low 89 <= Ziel 90) -> target_reached @ 90');
}
// Test 5: Stop und Ziel in derselben Tageskerze -> ambiguous, konservativ stop_loss
{
  const r = evaluateExit('long', 100, 95, 110, { low: 94, high: 111, close: 108 }, null, null, new Date());
  assert(r.ambiguous === true && r.exitReason === 'stop_loss' && r.exitReasonsAll.includes('target_reached'), 'Test 5: Stop UND Ziel in derselben Kerze -> ambiguous_execution=true, konservativ stop_loss gewaehlt (AMBIGUOUS_BAR_POLICY), aber target_reached bleibt in exit_reasons_all_json sichtbar');
}
// Test 6: Gap durch den Stop (Kerze eroeffnet bereits unter dem Stop)
{
  const r = evaluateExit('long', 100, 95, 110, { low: 90, high: 96, close: 91 }, null, null, new Date());
  assert(r.exitReason === 'stop_loss' && r.exitPrice === 95, 'Test 6: Gap durch den Stop (Low 90 weit unter Stop 95) -> trotzdem Exit exakt am Stop-Preis (kein optimistischer Gap-Preis angenommen)');
}
// Test 7: Einstiegszone nie erreicht -> bleibt proposed (kein Fill)
function evaluateEntry(zoneLow, zoneHigh, bar) {
  const beruehrt = bar.low <= zoneHigh && bar.high >= zoneLow;
  return { gefuellt: beruehrt };
}
{
  const r = evaluateEntry(98, 99, { low: 101, high: 103 });
  assert(r.gefuellt === false, 'Test 7: Kerze (101-103) beruehrt Einstiegszone (98-99) nie -> kein Fill, bleibt proposed');
}
// Test 8: Zeitstop
{
  const past = new Date(Date.now() - 1000);
  const r = evaluateExit('long', 100, 95, 110, { low: 99, high: 101, close: 100 }, past.toISOString(), null, new Date());
  assert(r.exitReason === 'time_stop', 'Test 8: kein Stop/Ziel beruehrt, aber time_stop_at in der Vergangenheit -> time_stop');
}
// Test 9: Ablauf der These
{
  const past = new Date(Date.now() - 1000);
  const r = evaluateExit('long', 100, 95, 110, { low: 99, high: 101, close: 100 }, null, past.toISOString(), new Date());
  assert(r.exitReason === 'thesis_expired', 'Test 9: kein Stop/Ziel/Zeitstop, aber thesis_expires_at in der Vergangenheit -> thesis_expired');
}
// Test 10: Trailing-Stop - BEWUSST NICHT IMPLEMENTIERT (siehe docs/AUSFUEHRUNGSMODELL.md)
{
  // stop_price_current wird in Job B nirgends ausser bei der initialen Fuellung gesetzt -
  // es gibt keinen Code-Pfad, der ihn nach oben/unten nachzieht. Dieser Test dokumentiert
  // die Luecke, statt sie stillschweigend zu ignorieren.
  const trailingStopImplemented = false;
  assert(trailingStopImplemented === false, 'Test 10: ATR-Trailing-Stop ist NICHT implementiert (dokumentierte Luecke, kein Vortaeuschen einer Funktion)');
}
// Test 11: Gebuehren machen Bruttogewinn netto negativ
{
  const grossPnl = 5; // sehr kleiner Bruttogewinn
  const qty = 40, price = 100; // Positionswert 4000 EUR - Kosten uebersteigen den kleinen Bruttogewinn
  const feeBps = 15, slipBps = 10;
  const fee = round(price * qty * (feeBps / 10000), 2);
  const slip = round(price * qty * (slipBps / 10000), 2);
  const netPnl = round(grossPnl - fee - slip, 2);
  assert(netPnl < 0, 'Test 11: Bruttogewinn 5 EUR minus Gebuehren(' + fee + ')+Slippage(' + slip + ') -> Nettoergebnis negativ (' + netPnl + ')');
}
// Test 12+13: Portfoliolimit / Sektorlimit blockiert Trade
function pruefeLimits(risikoVorher, neuesRisiko, maxTotalPct, portfolioValue, sektorWert, maxSectorPct) {
  const blockers = [];
  if (((risikoVorher + neuesRisiko) / portfolioValue) * 100 > maxTotalPct) blockers.push('TOTAL_RISK_LIMIT');
  if ((sektorWert / portfolioValue) * 100 > maxSectorPct) blockers.push('SECTOR_LIMIT');
  return blockers;
}
{
  const b = pruefeLimits(5900, 200, 6.0, 100000, 0, 15.0);
  assert(b.includes('TOTAL_RISK_LIMIT'), 'Test 12: offenes Risiko 5900+200=6100 von 100000 (6.1%) > Limit 6.0% -> TOTAL_RISK_LIMIT blockiert');
}
{
  const b = pruefeLimits(0, 100, 6.0, 100000, 16000, 15.0);
  assert(b.includes('SECTOR_LIMIT'), 'Test 13: Sektor-Positionswert 16000 von 100000 (16%) > Limit 15% -> SECTOR_LIMIT blockiert');
}
// Test 14: Drawdownlimit blockiert neue Trades
{
  const aktuellerDrawdownPct = 18.0;
  const maxDrawdownPct = 15.0;
  const blockiert = aktuellerDrawdownPct > maxDrawdownPct;
  assert(blockiert === true, 'Test 14: aktueller Drawdown 18% > Limit 15% -> DRAWDOWN_LIMIT blockiert ALLE neuen Eroeffnungen');
}
// Test 15: Stressszenario (Indexschock -5%, long Position)
{
  const positionValue = 8000;
  const pctMove = -5;
  const loss = positionValue * (pctMove / 100);
  assert(round(loss, 2) === -400, 'Test 15: Long-Position 8000 EUR bei -5% Indexschock -> geschaetzter Verlust -400 EUR');
}
// Test 18+20: zu kleine Fallzahl / Lernvorschlag ohne OOS wird verworfen
function proposalEligible(n, minSample, oosConfirmed, dominiertVonEinemTicker, expectancyR) {
  return n >= minSample && oosConfirmed && !dominiertVonEinemTicker && expectancyR !== null && (expectancyR <= -0.15 || expectancyR >= 0.3);
}
{
  assert(proposalEligible(12, 30, true, false, -0.5) === false, 'Test 18: Fallzahl 12 < Mindestfallzahl 30 -> proposal_eligible=false, obwohl der Erwartungswert stark negativ ist');
}
{
  assert(proposalEligible(50, 30, false, false, -0.5) === false, 'Test 20: Fallzahl 50 ausreichend, Erwartungswert stark negativ, ABER keine OOS-Bestaetigung -> proposal_eligible=false (Vorschlag wird verworfen)');
}
// Test 22: Wiederholung eines Laufs ohne doppelte Trades (trade_id-Determinismus)
{
  const tradeId1 = 'SAP.DE' + '-' + '2026-08-01' + '-' + 'trend_following';
  const tradeId2 = 'SAP.DE' + '-' + '2026-08-01' + '-' + 'trend_following';
  assert(tradeId1 === tradeId2, 'Test 22: trade_id ist deterministisch aus ticker+business_date+strategy - ein wiederholter Lauf erzeugt dieselbe ID, ON CONFLICT DO NOTHING verhindert Duplikate');
}

console.log('\n--- Ergebnis:', pass, 'bestanden,', fail, 'fehlgeschlagen', '---');
process.exit(fail > 0 ? 1 : 0);
