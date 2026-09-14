# 4T – Cost-Aware Trade Quality Gate: Single-Hypothesis Development Experiment

**Datum:** 2026-09-14
**Vorlage:** 4S (`docs/adhoc/4S_trade_quality_cost_efficiency_2026-09-14.md`), Commit `7e044ef`
**Source Run (Baseline):** Run 45 · **Experiment Run:** Run 47

## Exakte Hypothese (vor dem Experiment festgelegt)

> Ein Trade sollte nur zugelassen werden, wenn sein erwarteter Bruttogewinn bis zum Target
> mindestens das **2.0-fache** der vor Trade geschätzten Round-Trip-Handelskosten beträgt.

Formal: `cost_coverage_ratio = expected_target_gross_profit / estimated_round_trip_cost`;
Regel: `cost_coverage_ratio <= 2.0` → Candidate **nicht** handeln (`COST_EDGE_TOO_LOW`).
Schwelle **2.0 war vor dem Experiment festgelegt** und wurde **nicht** nachträglich angepasst.
Keine zweite Schwelle getestet (Phase 25 der Vorgabe).

---

## TEIL A – Implementation

1. **Cost model source:** `sizePosition()` in Node "Verarbeite Tage-Paket" (WF17), bestätigt
   identisch zum bereits im Code aktiven Job-B-LEGACY-Kostenmodell (fee/slippage auf Entry- bzw.
   Exit-Notional, Financing=0) – siehe Phase-1-Rekonstruktion unten.
2. **Fee rate:** `DEFAULT_FEES_BPS = 15` (0.15%) – aus `runCtx._fees_bps`, bestätigt sowohl im Code
   als auch empirisch gegen Run-45-Realdaten (Entry-Fee exakt 15bps auf Positionswert).
3. **Slippage rate:** `DEFAULT_SLIPPAGE_BPS = 10` (0.10%) – analog bestätigt.
4. **Estimated round-trip formula:**
   `estimated_round_trip_cost = entry_notional * cost_rate + target_notional * cost_rate`,
   `cost_rate = (fees_bps + slippage_bps) / 10000`, `entry_notional = finalQuantity * entryPriceEstimate`
   (bereits final sizierter Wert), `target_notional = finalQuantity * target_price`.
5. **Expected gross target formula:** LONG `(target_price - entryPriceEstimate) * finalQuantity`,
   SHORT `(entryPriceEstimate - target_price) * finalQuantity`.
6. **Coverage ratio formula:** `expected_target_gross_profit / estimated_round_trip_cost`.
7. **Threshold:** `2.0`, Vergleich `<= 2.0` → BLOCK (exakt 2.0 blockt, wie gefordert).
8. **Gate location:** innerhalb `sizePosition()`, direkt nach dem bestehenden `RRR_TOO_LOW`-Veto,
   vor dem finalen `return { veto: null, ... }` (Approved-Pfad). Verwendet ausschliesslich bereits
   berechnete finale Werte (`finalQuantity`, `entryPriceEstimate`, `positionValue`,
   `signal.target_price`) – keine zweite Sizing-Berechnung.
9. **Gate changes portfolio state when blocked: NEIN.** Ein `COST_EDGE_TOO_LOW`-Veto durchläuft
   exakt denselben bestehenden Code-Pfad wie jedes andere Sizing-Veto (`if (sizing.veto) { jobAOutcome
   = { approved: false, blockers: [sizing.veto] } }` → `if (!jobAOutcome.approved) continue;`) –
   kein Shadow-Trade, keine Exposure-, Risk-Used- oder MAX_OPEN-Mutation vor diesem Punkt.
   Strukturell verifiziert (Code-Pfad-Analyse) und live bestätigt (Run 47: 171 COST_EDGE_TOO_LOW-Blocks,
   0 daraus resultierende Shadow-Trades).
10. **Experiment isolated from live policy: JA.** Das Flag `cfg.costGateEnabled` existiert nur auf
    `shadowSizingCfg` (dem stateful Job-A-Sizing-Aufruf für den Shadow-Pfad) – der äussere `cfg` fuer
    RESEARCH_BASELINE (echter Handelspfad) und der isolierte Diagnose-Aufruf bekommen dieses Feld
    nie gesetzt. Aktiviert wird es ausschliesslich über ein neues, opt-in Formularfeld
    `cost_gate_enabled` bei Run-Erstellung (`config_snapshot_json.cost_gate_enabled`), Default
    `false`/fehlend für jeden bestehenden Run inkl. Run 45.

---

## TEIL B – Tests

11. **Golden Tests: 13 / 13 bestanden** (12 gefordert + 1 zusaetzlich – Test 8 in zwei Teilfaelle
    aufgespalten). Isolierte Reimplementierung der neuen Gate-Formel: ratio&lt;2→BLOCK,
    ratio==2.0→BLOCK, ratio&gt;2→PASS, LONG-/SHORT-Vorzeichen, Quantity-Skalierung invariant zur
    Ratio, verschiedene Target-Notionals monoton, Zero-Cost-Fail-Closed (kein Div/0), sowie
    strukturell begründete (nicht separat unit-getestete) Faelle fuer invalide Geometrie und
    Portfolio-State-Unberuehrtheit bei BLOCK.
12. **Gate-off Regression: PASS.** Mini-Replay Run 46 (identischer 5-Tage-Scope wie Run 43/44,
    `cost_gate_enabled` weggelassen) exakt gegen Run 44 verglichen: Shadow-Trades (2 closed/7
    open/3 proposed) auf den Cent identisch (Gross/Net/Risk/Position-Value), 59 Decision-Log-Zeilen
    in beiden Laeufen. Einziger Unterschied: 42 Zeilen in Run 46 haben zusaetzlich ein rein additives
    `diagnostics_json.cost_gate: null`-Feld (erwartungsgemaess, keine Verhaltensaenderung).
13. **Research Regression: PASS** (durch Konstruktion – `cfg.costGateEnabled` existiert auf dem
    RESEARCH_BASELINE-`cfg`-Objekt gar nicht, der neue Code-Block ist fuer diesen Pfad strukturell
    unerreichbar; zusaetzlich bestaetigt live-deploy-seitig durch Byte-Vergleich des deployten
    Codes gegen den beabsichtigten Quelltext nach dem Push).
14. **Max diff:** Shadow-Trades Gate-off: **0** (exakte Uebereinstimmung Run 46 vs. Run 44).

---

## TEIL C – Run

15. **Experiment Run ID:** 47 (Name "4T Cost-Aware Gate Experiment (threshold 2.0)")
16. **Completed:** JA, 100% (2026-08-14)
17. **Errors:** 0 (`trading.simulation_errors` fuer Run 47: 0 Zeilen)
18. **Business Days:** 76 (identisch zu Run 45: 2026-05-01 bis 2026-08-15)
19. **READY (Shadow-Kandidaten, die den Job-A-Sizing-Aufruf erreichten):** 463
20. **Gate evaluated (davon tatsaechlich bis zum Cost Gate durchgedrungen):** 380
    (463 − 40 QUANTITY_TOO_SMALL − 43 RRR_TOO_LOW, beide Vetos liegen im Code VOR dem Cost Gate)
21. **COST_EDGE_TOO_LOW (Cost-Gate-Block):** 171
22. **Gate PASS:** 209
23. **Approved (nach zusaetzlichen Portfolio-Haertegrenzen):** 41
    (209 Gate-PASS − 168 durch DIRECTIONAL_LIMIT/CORRELATION_LIMIT geblockt)
24. **Filled/Closed:** 36 geschlossene Shadow-Trades
25. **Open:** 2
26. **Proposed (noch nicht gefuellt):** 2, **Expired unfilled:** 1

**Vollstaendiger Funnel:** 463 READY → 40 QUANTITY_TOO_SMALL → 43 RRR_TOO_LOW → 380 Cost-Gate-geprueft
→ 171 COST_EDGE_TOO_LOW → 209 PASS → 168 Portfolio-Haertegrenzen (DIRECTIONAL_LIMIT 161,
CORRELATION_LIMIT 11, teils ueberlappend) → **41 Approved** → 36 Closed + 2 Open + 2 Proposed + 1 Expired = 41 ✓

**Cost Gate Distribution (Coverage Ratio):** PASS-Faelle liegen per Definition &gt;2.0, BLOCK-Faelle
&le;2.0 (Schwelle exakt eingehalten, keine Ausreisser in die falsche Richtung gefunden).

---

## TEIL D – Performance (Experiment, Run 47)

27. **Gross P&L:** +2332.70 EUR
28. **Costs:** 1385.04 EUR
29. **Net P&L:** +947.66 EUR (Accounting-Identitaet 2332.70 − 1385.04 = 947.66 ✓, exakt, tautologisch
    wie in 4S dokumentiert – total_costs ist als Residuum definiert)
30. **Unrealized P&L (2 offene Positionen, MTM zum letzten verfuegbaren Kurs im Fenster):** −64.79 EUR
    (DTE.DE: Entry 29.04, letzter Kurs 28.67, 275 Stk → −101.75 EUR; SAP.DE: Entry 179.30, letzter
    Kurs 180.14, 44 Stk → +36.96 EUR)
31. **MTM Final Equity:** 100000 + 947.66 − 64.79 = **100882.87 EUR**
32. **MTM Return:** **+0.88%**
33. **Gross PF:** 1.42
34. **Net PF:** 1.15
35. **Gross EV/Trade:** +64.80 EUR
36. **Net EV/Trade:** +26.32 EUR
37. **Win Rate:** 50.0% (18/36)
38. **Max Drawdown (auf Net-P&L-Equity-Kurve der 36 Closed Trades):** 2.83%

---

## TEIL E – Baseline Delta (Run 45 vs. Run 47)

| # | Metrik | Run 45 | Run 47 | Delta |
|---|---|---|---|---|
| 39/40 | Closed Trades | 60 | 36 | |
| 41 | Trade Reduction | | | **−40.0%** |
| 42/43 | Gross | +652.00 | +2332.70 | +1680.70 |
| 44/45 | Costs | 1858.20 | 1385.04 | −473.16 |
| 46/47 | Net | −1206.20 | +947.66 | |
| 48 | Net Improvement | | | **+2153.86 EUR** |
| 49/50 | Net EV/Trade | −20.10 | +26.32 | +46.42 |
| 51/52 | Net PF | 0.85 | 1.15 | +0.30 |
| 53/54 | Max DD | 3.40% | 2.83% | −0.57pp |

Ergaenzend – vollstaendige Tabelle (Phase 24 der Vorgabe):

| | Run45 | 4T (Run47) |
|---|---|---|
| Closed Trades | 60 | 36 |
| Gross P&L | 652.00 | 2332.70 |
| Costs | 1858.20 | 1385.04 |
| Net P&L | −1206.20 | 947.66 |
| MTM Return | n/a (Run 45 wurde nicht MTM-bewertet in 4S) | +0.88% |
| Win Rate | 43.3% | 50.0% |
| Gross PF | 1.09 | 1.42 |
| Net PF | 0.85 | 1.15 |
| Net EV | −20.10 | +26.32 |
| Max DD | 3.40% | 2.83% |

---

## TEIL F – Filter Quality (methodisch der wichtigste Teil dieses Berichts)

55. **Filtered Run45-equivalent Trades** (Kandidaten, die Run 45 gehandelt haette, Run 47 aber
    durch das Cost Gate oder Folgeeffekte blockierte): **39** (identifiziert ueber `shadow_trade_id`,
    deterministisch aus Ticker+Datum+Strategie)
56. **Ihr historisches Gross (Run-45-Realwerte):** +2036.90 EUR
57. **Ihre historischen Costs:** 1128.91 EUR
58. **Ihr historisches Net:** **+907.99 EUR** (Net PF 1.24)
59. **Ihre historische Win Rate:** 46.15%

**Wichtiger, nicht beschoenigter Befund:** die 39 vom Cost Gate ausgefilterten Kandidaten waren in
ihrer tatsaechlichen Run-45-Realisierung **netto profitabel** (PF 1.24) – das Gate hat also nicht
"die schlechten Trades" herausgefiltert, sondern eine Mischung, die in der Gegenrechnung sogar
netto positiv war. Das Cost Gate ist damit **kein einfacher Trade-Qualitaets-Filter im Sinne von
"blockt schlechte, laesst gute durch"**.

60/61. **Remaining/common Trades (in Run 45 UND Run 47 identisch als Kandidat vorhanden, n=21):**
Mit den tatsaechlichen **Run-47**-Realwerten (nicht Run-45-Werten, siehe Methodik-Hinweis unten):
Net **−1120.58 EUR**, PF **0.75**. Zum Vergleich dieselben 21 Kandidaten mit ihren Run-45-Realwerten:
Net −2114.19 EUR, PF 0.52 – **9 von 21 (43%) dieser identischen Kandidaten wurden in Run 47 mit
einer anderen Stueckzahl gehandelt als in Run 45**, weil sich der verfuegbare Portfolio-Spielraum
(Risk-/Directional-/Correlation-Budget) durch die vom Gate blockierten Kandidaten veraendert hat.

**Zusaetzlicher, nicht in der Vorgabe explizit angeforderter, aber entscheidender Befund:** Run 47
enthaelt **15 geschlossene Trades, die in Run 45 gar nicht existierten** (weder als Kandidat
gehandelt noch geblockt) – sie kamen erst zustande, weil das Cost Gate frueher am Tag anderen
Kandidaten den Zugang verweigerte und dadurch Portfolio-Kapazitaet (Risk-Budget,
Sektor-/Regions-/Richtungs-Exposure) fuer spaetere Kandidaten freigab, die in Run 45 aus reinem
Kapazitaetsmangel nie zum Zug gekommen waeren. Diese 15 "neuen" Trades performten aussergewoehnlich
gut: **Gross +2632.88 EUR, Net +2068.24 EUR, PF 2.62 (netto 2.14), Win Rate 66.7%, Net EV/Trade
+137.88 EUR** – sie tragen fast den gesamten positiven Gesamteffekt von Run 47.

**Rechnerische Zerlegung von Run 47s Net-Ergebnis (+947.66 EUR):**
Gemeinsame Kandidaten (n=21, Run-47-Werte): **−1120.58 EUR** + neue, durch freigewordene Kapazitaet
ermoeglichte Kandidaten (n=15): **+2068.24 EUR** = **+947.66 EUR** ✓ (exakt reproduziert).

---

## Methodische Einordnung (Pflichtlektuere vor TEIL G)

Der Verbesserungseffekt in Run 47 laesst sich **nicht** als "das Cost Gate hat gezielt schlechte
Trades entfernt" beschreiben. Tatsaechlich zeigt die Zerlegung:

- Trades, die das Gate **direkt** blockierte, waeren (kontrafaktisch, Run-45-Realwerte) netto
  **profitabel** gewesen (+907.99 EUR) – ein Filter, der isoliert betrachtet eher schadet als nuetzt.
- Trades, die in **beiden** Laeufen als Kandidat auftauchten, blieben **netto negativ**
  (−1120.58 EUR in Run 47, sogar noch negativer −2114.19 EUR in Run 45) – das Gate hat diese
  Kern-Verlustgruppe nicht behoben.
- Der gesamte positive Netto-Effekt (+947.66 EUR) stammt praktisch vollstaendig aus **15 Trades, die
  es ohne das Gate gar nicht gegeben haette** – ein **Portfolio-Kapazitaets-Verdraengungseffekt**
  (weniger frueh gebundenes Risk-/Directional-/Sektor-Budget liess spaetere, in diesem Sample zufaellig
  sehr gute Kandidaten durch), nicht ein direkter Kausaleffekt des Kosten-Kriteriums selbst.

Dies ist ein bei sequenziellen, zustandsbehafteten Portfolio-Simulationen **strukturell zu
erwartender** Nebeneffekt jeder Aenderung an der Kandidaten-Zulassung (nicht spezifisch fuer dieses
Cost Gate) – er widerspricht nicht Phase 14 der Vorgabe ("nur das Cost Gate unterscheidet sich
fachlich"; das Cost Gate ist weiterhin die einzige geaenderte Regel, ihre *Downstream-Wirkung* auf
den Portfolio-Pfad ist aber nicht isolierbar ohne die Simulation selbst nicht-sequenziell zu machen).
**Entscheidend fuer die Bewertung in TEIL G: das positive Gesamtergebnis ist real und reproduzierbar,
aber die Kausalgeschichte dahinter ist komplexer als "Kostenfilter verbessert Trade-Auswahl".**

---

## TEIL G – Verdict

62. **Did Net EV improve: JA** (−20.10 → +26.32 EUR/Trade)
63. **Did Net PF improve: JA** (0.85 → 1.15)
64. **Did Net P&L improve: JA** (−1206.20 → +947.66 EUR, +2153.86 EUR)
65. **Did cost efficiency improve: JA** (Costs/Gross-Winning-P&L 23.95% → 17.60%; Avg
    Cost/Trade 30.97 → 38.47 EUR ist zwar hoeher, aber bei mehr als doppelt so hohem Avg-Gross/Trade
    – die Kosten sind relativ zum erzeugten Brutto-Ergebnis deutlich effizienter geworden)
66. **Drawdown acceptable: JA** (2.83% vs. 3.40% zuvor, sogar leicht niedriger)
67. **Development-window evidence fuer Cost Gate: MIXED**, tendenziell **POSITIVE im Ergebnis, aber
    nicht eindeutig im Wirkmechanismus.** Alle harten Zielkennzahlen (Net EV, Net PF, Net P&L, Cost
    Efficiency, Drawdown) verbesserten sich gleichzeitig (Phase 26 der Vorgabe erfuellt: "nur weniger
    Trades" oder "nur hoehere Win Rate" allein haetten nicht gereicht – hier sind es tatsaechlich
    mehrere Dimensionen gleichzeitig). Aber TEIL F zeigt: der Mechanismus ist ueberwiegend ein
    Portfolio-Kapazitaets-Verdraengungseffekt, nicht eine direkte "Kosten-Kante erkennt schlechte
    Trades"-Wirkung – die direkt geblockten Kandidaten waeren isoliert betrachtet sogar profitabel
    gewesen.
68. **Edge proven: MUSS NEIN.** Dies ist Development-Window-Evidenz auf genau einem Lauf (n=41
    approved, 36 closed) – kein Out-of-Sample-, Holdout- oder Forward-Test. "Development-window
    evidence unterstuetzt die Cost-Gate-Hypothese in ihrem Gesamtergebnis" – nicht "Filter
    funktioniert" oder "Edge bewiesen".
69. **Threshold optimized: MUSS NEIN.** Ausschliesslich die vor dem Experiment festgelegte Schwelle
    2.0 getestet. Keine 1.5/1.8/2.2/2.5/3.0-Variante ausprobiert, keine Grid-Search.
70. **Genau EIN empfohlener naechster Schritt:** Bevor die Schwelle 2.0 als naechste Hypothese
    weiterverfolgt wird, sollte zunaechst der in TEIL F aufgedeckte Verdraengungsmechanismus selbst
    verstanden werden – konkret: eine zusaetzliche, ebenfalls ungefittete Diagnose (kein neuer
    Parameter-Test), die misst, wie stark der Anteil "durch freigewordene Kapazitaet neu ermoeglichter
    Trades" das Gesamtergebnis *jeder* zukuenftigen Kandidaten-Zulassungsregel dominieren wird – sonst
    laesst sich der Erfolg oder Misserfolg einer kuenftigen Regeltest (inkl. eines spaeteren Holdouts)
    nicht sauber der Regel selbst zuschreiben.

---

**Harte Grenze eingehalten:** Threshold 2.0 nicht angepasst, keine zweite Schwelle getestet, kein
Holdout gestartet, keine weiteren Strategieparameter veraendert. STOPP nach diesem Bericht.
