# SCHRITT 4Q.1 — Runtime Sizing Trace + Parity Root-Cause-Diagnose

Datum: 2026-09-13
Repo-HEAD zu Sitzungsbeginn: `b7447f7`. Nach Instrumentierung (dieser Bericht): `e31e3a9`
("LIVE_PARITY 4Q.1: Runtime Sizing Trace Instrumentation in WF17"), Branch `agenten-modernisierung`,
gepusht nach `origin/agenten-modernisierung`.
Vorgaenger-Bericht (bleibt unveraendert, historische Evidenz):
`finanz/docs/adhoc/4Q_sizing_clamp_root_cause_2026-09-13.md`

**Status: ABGESCHLOSSEN (Phase 0-24 vollstaendig durchgefuehrt). Nach einem WF97-Zwischenstopp
(exakt eine, vom Nutzer direkt autorisierte und vom Koordinator selbst ausgefuehrte SELECT-Abfrage,
danach WF97 sofort wieder geschlossen und unabhaengig verifiziert) wurden alle 42 READY-Kandidaten
des Mini-Runs 43 gegen die echte Python-Engine (`http://172.16.1.14:8099/engine/portfolio/
check-and-size`) mit den exakten Runtime-Inputs gegengerechnet.**

**Kernergebnis: Die Sizing-FORMEL selbst ist zu 100% parity-korrekt (42/42 exakte
Uebereinstimmung, Phase 21). Gleichzeitig wurde ein ANDERER, echter Bug gefunden: der
Portfolio-Zustand (`proposed_count`/`open_count`/`total_risk_used`), der der Formel als Input
zugefuehrt wird, explodiert ab dem zweiten Handelstag des Mini-Runs auf ein unplausibles
Vielfaches (Faktor ~397) des erwarteten Werts — ein Portfolio-State-Input-Bug, kein Sizing-Bug
(siehe Phase 22-23). Gemaess der harten STOPP-Regel der Spezifikation: Bericht fertig, KEIN Fix,
KEIN Tuning, KEIN neuer Full-Replay.**

---

## PHASE 0 — PREFLIGHT (fresh, nicht auf 4Q verlassen)

Alles in diesem Abschnitt wurde in DIESER Sitzung neu gelesen/geprueft, nicht aus dem 4Q-Bericht
uebernommen:

- `git log -1`: **`b7447f7`** (LIVE_PARITY 4O.4B), unveraendert seit 4Q. `git status` zeigte vor
  Sitzungsbeginn nur die bereits bekannten Backup-/Report-Dateien als untracked, keine
  uncommitted Aenderungen an Kerncode.
- **Live WF17 (`9JWDOTXFQWHYkypO`) frisch per GET geladen** und mit der Repo-Datei
  normalisiert verglichen (nodes/connections/settings): **identisch**. Bestaetigt: Live == Repo,
  vor jeder eigenen Aenderung.
- `trading_engine/position_sizing.py`, `risk_limits.py`, `models.py`: `git diff HEAD` leer, keine
  Aenderung seit 4Q. Fresh gelesen (Umfang: 156/127/237 Zeilen), Inhalt deckt sich mit dem im
  4Q-Bericht zitierten Code.
- `sql/084`, `087`, `088`, `089`: fresh gelesen. Bestaetigt: `trading.simulation_decision_log`
  hat eine additive, nullable `diagnostics_json jsonb`-Spalte (Migration 087) sowie
  `blockers_json jsonb` (ebenfalls 087) — beide geeignet fuer eine additive
  Trace-Persistierung ohne neue Migration (siehe Phase 7).
- **WF97 (`NInmI0f9TfdndwI1`): read-only per GET geprueft — `active: false`, Node "Diag Webhook"
  weiterhin `disabled: true`.** Keine Aktivierung, keine Aenderung. Dies wird am Ende erneut
  geprueft (siehe STOPP-Abschnitt).

---

## TEIL A — 4Q REVIEW (Phase 1 der Spezifikation)

| # | Aussage | Status | Begruendung |
|---|---|---|---|
| A | 427 QTS gesamt | **CONFIRMED** | In 4Q live aus `simulation_decision_log` (Run 42) gezaehlt: `job_a_portfolio_check.blockers=['QUANTITY_TOO_SMALL']` bei exakt 427 von 463 READY-Zeilen. Nicht in dieser Sitzung erneut gegen die DB gezaehlt (dafuer waere wieder WF97 noetig gewesen, siehe unten) — aber der Code, der diese Zahl erzeugt hat, wurde in dieser Sitzung fresh erneut gelesen und ist unveraendert. |
| B | 401/427 nicht durch rekonstruierte Clamp-Logik erklaerbar | **CONFIRMED** (methodisch), mit einer wichtigen Praezisierung | Die 4Q-Nachrechnung selbst wurde in dieser Sitzung als Regressionsbasis wiederverwendet (siehe unten) und liefert dieselben Zahlen. Die AUSSAGE "93,9% nicht erklaerbar" bleibt bestehen — WICHTIG: 4Q.1 zeigt zusaetzlich (Phase 2), dass die Ursache dafuer sehr wahrscheinlich (aber, siehe STOPP, noch nicht runtime-bewiesen) genau die in 4Q vermutete Beobachtungsluecke ist: `binding_limit` und die Clamp-Zwischenwerte wurden nie persistiert, die 4Q-Rekonstruktion mmusste daher raten. |
| C | 26/427 erklaerbar | **CONFIRMED** | Unveraendert aus 4Q, gleiche Datenbasis. |
| D | Config-Drift ausgeschlossen | **CONFIRMED** | Fresh erneut in "Baue Run-Kontext" gelesen: `run.config_snapshot_json` wird EINMALIG bei Run-Erstellung eingefroren, der Live-Reload-Pfad ("DB: Simulations-Konfiguration laden") ist laut eigenem Code-Kommentar "aus dem Ausfuehrungspfad entfernt" — bestaetigt unveraendert. |
| E | Code-Drift ausgeschlossen | **CONFIRMED** | Live-WF17-Code wurde in DIESER Sitzung (vor jeder eigenen Aenderung) fresh gegen die Repo-Kopie verglichen — normalisiert identisch. Der Vergleich in 4Q war bereits derselbe Befund; hier unabhaengig reproduziert. |
| F | Portfolio-State-Rekonstruktion plausibel | **PARTIALLY CONFIRMED** | Die 4Q-Rekonstruktionsmethodik (Zustand aus `simulation_shadow_trades.decision_date/exit_date` abgeleitet) reproduziert exakt den EINEN unabhaengig ueberpruefbaren Fall (Tag 1, leeres Portfolio). Sie ist aber NICHT geeignet, um die 401 unerklaerten Faelle ursaechlich zu erklaeren — genau das ist der Kern von 4Q.1: die Rekonstruktion aus Endzustaenden kann strukturell NICHT beweisen, was zur Laufzeit tatsaechlich vorlag (siehe Phase 22/23 unten). "Plausibel" heisst hier: methodisch sauber fuer das, was sie zeigen kann — nicht: ausreichend, um den 93,9%-Befund ursaechlich zu erklaeren. |
| G | `binding_limit` bisher nicht persistiert | **CONFIRMED** | Fresh im Live-Code verifiziert (vor der eigenen Aenderung): `job_a_portfolio_check` enthielt nur `{approved, blockers, drawdown_pct_at_check, correlation_checked, strategy_status_policy_mode}` — kein `binding_limit`, keine Clamp-Zwischenwerte. Das im Code intern berechnete `sizing.binding_limit` (im Veto-Fall) bzw. der implizite `binding`-Wert (im Erfolgsfall, dort nur `clamp_reason` bei tatsaechlicher Kappung) wurden nie in die DB geschrieben. |
| H | Zwischenwerte nicht persistiert | **CONFIRMED** | Ebenfalls fresh bestaetigt — `remaining_portfolio_quantity`/`remaining_sector_quantity`/`remaining_region_quantity`/`maxSinglePositionQuantity` (die vier `candidates`-Kandidaten neben RAW_RISK_SIZE) existierten nur als lokale Variablen innerhalb von `sizePosition()` und wurden nirgends zurueckgegeben oder gespeichert. |

**Weitere wichtige 4Q-Probleme (Punkt 6 der Spezifikation), beim Re-Read gefunden:**
- Der 4Q-Bericht selbst benennt bereits offen, dass er den exakten Mechanismus NICHT gefunden hat
  (Abschnitt 5.4 dort) — das ist kein neuer Fund, aber wichtig festzuhalten: 4Q hat sich nicht
  als abgeschlossene Diagnose ausgegeben, sondern explizit als unvollstaendig markiert. Das deckt
  sich mit dem, was diese Sitzung jetzt weiterverfolgt.
- Kein neuer Widerspruch beim Re-Read gefunden. Die 4Q-Rechenschritte (Accounting Phase 1-3,
  MTM Phase 2, Benchmark Phase 31) wurden nicht erneut nachgerechnet, da 4Q.1 laut Spezifikation
  ausdruecklich NICHT die Performance-Rekonstruktion, sondern die Sizing-Runtime-Beobachtbarkeit
  zum Ziel hat.

---

## TEIL B — INSTRUMENTATION

### Phase 2 — Source of Truth (Call Chain, fresh dokumentiert)

**Aktiver Shadow-Replay-Pfad** (bestaetigt: `TRADING_ENGINE_STEP_ENABLED=false` im
`config_snapshot_json` von Run 42 UND Run 43 — der Python-Engine-HTTP-Pfad
"Verarbeite Tage-Paket (Engine)" ist fuer diese Laeufe nicht aktiv):

```
READY Candidate (buildLiveParityShadowCandidate())
  -> sizePosition(signal, entryPrice, cfg, openPositionsState, sektor, region)
     [Datei: "Verarbeite Tage-Paket" Code-Node in WF17, Funktion ab Zeile 74 (vor 4Q.1-Edit)]
     -> gibt {veto|null, ...Felder..., trace:{...}} zurueck  (4Q.1: trace neu, additiv)
  -> Aufrufer A (isoliert, Zeile ~2443): shadowSizing = sizePosition(..., [], ...)
     -> buildShadowDecisionLogRow() schreibt shadowSizing in decisionLogRow.diagnostics_json.sizing
  -> Aufrufer B (stateful, Job A, Zeile ~2678): sizing = sizePosition(..., shadowOpenPositionsForCheck(), ...)
     -> jobAOutcome = { approved, blockers: [sizing.veto] oder checkShadowPortfolioLimits()-Ergebnis, sizing }
     -> decisionLogRow.diagnostics_json.job_a_portfolio_check wird befuellt (4Q.1: jetzt inkl. trace)
  -> decisionLogRows.push(...) -> "Baue SQL fuer Paket-Ergebnisse" -> INSERT INTO trading.simulation_decision_log
```

Die vom Nutzer im 4Q-Bericht zitierten Funnel-Zahlen stammen — bereits in 4Q bewiesen, hier
unveraendert bestaetigt — aus Aufrufer B (dem stateful Job-A-Aufruf).

**Produktive Python-Engine Call Chain** (zum Vergleich, aktuell NICHT der Live-Pfad fuer
AVAILABLE_DATA_LIVE_REPLAY-Laeufe, siehe oben):

```
"Verarbeite Tage-Paket (Engine)" Code-Node
  -> HTTP POST http://172.16.1.14:8099/engine/simulation/step  (payload: bars, pending_orders,
     open_trades, cash, risk_cfg, fee_model, sizing_mode='clamp', ...)
  -> [im externen Python-Service, NICHT Teil dieses Repos - nur die Client-Seite ist hier sichtbar]
     vermutlich: trading_engine.position_sizing.size_position() -> _size_position_clamp()
  -> Response: { new_trades, new_orders, still_open_trades, still_pending_orders, cash, portfolio }
```

**Wichtige Einschraenkung fuer Phase 19 (Python-Engine-Crosscheck):** `trading_engine/
position_sizing.py`/`risk_limits.py` sind die REPO-Kopie der Engine-Logik (fuer Code-Review
gedacht) — der tatsaechliche Laufzeit-Service laeuft unter `172.16.1.14:8099` und wird von hier
aus nur ueber HTTP aufgerufen (kein direkter Python-Import in diesem Environment moeglich, kein
Python-Interpreter verfuegbar, wie bereits in 4Q festgestellt). Ein echter Runtime-Crosscheck
(Phase 19) muss daher entweder (a) exakt denselben HTTP-Request `POST /engine/simulation/step`
mit den im Trace gespeicherten Inputs an den echten Service schicken, oder (b) — falls der Service
z.B. nicht fuer Einzelkandidaten-Aufrufe gebaut ist — die Python-Funktion `_size_position_clamp()`
direkt mit denselben Inputs aufrufen (erfordert einen Python-Interpreter, der in dieser Sitzung
nicht verfuegbar war; noch nicht geprueft, ob einer auf dem Engine-Host/Server erreichbar waere).
**Auch dieser Punkt ist Teil der am Ende dieses Berichts offenen Fragen**, unabhaengig vom
WF97-Block.

### Phase 3 — Exakte Clamp-Reihenfolge (aus Code, nicht aus Dokumentation)

Fresh aus dem Code abgeleitet (siehe Instrumentierung selbst als Beleg — der Trace-Code liest
exakt diese Variablen, keine andere Quelle):

Die 5 Clamp-Kandidaten werden **parallel** berechnet, NICHT sequenziell kaskadiert — das
striktes Minimum entscheidet:

| Stufe | Formel | Input | Capacity/Limit |
|---|---|---|---|
| RAW_RISK_SIZE | `floor(mpv*max_risk_per_trade_pct/100 / unit_risk)` | unit_risk (Geometrie) | theoretischer Risikobetrag (EUR) |
| SINGLE_POSITION_LIMIT | `floor(mpv*max_single_position_pct/100 / entry_price)` | entry_price | mpv*8% (EUR) |
| TOTAL_RISK_LIMIT | `floor(max(0, mpv*max_total_open_risk_pct/100 - sum(open.risk_amount)) / unit_risk)` | offene Positionen (risk_amount) | mpv*6% minus bereits gebunden (EUR) |
| SECTOR_LIMIT | `floor(max(0, mpv*max_sector_exposure_pct/100 - sum(open[sektor].position_value)) / entry_price)` | offene Positionen im Sektor | mpv*15% minus Sektor-Ist (EUR) |
| REGION_LIMIT | `floor(max(0, mpv*max_region_exposure_pct/100 - sum(open[region].position_value)) / entry_price)` | offene Positionen in der Region | mpv*60% minus Region-Ist (EUR) |

`binding = argmin(alle 5)`. `final_quantity = max(0, floor(binding.quantity))`. **Jede der 5
Groessen ist bereits VOR dem Vergleich einzeln `Math.floor()`-gerundet** — es gibt keinen
zusaetzlichen, separaten "Rundungsschritt danach". Der 4Q.1-Trace bildet dies als laufende
Minimumbildung in dieser Reihenfolge ab (mathematisch identisch zum parallelen Vergleich, siehe
Code-Kommentar in der Instrumentierung selbst) — eine Praesentationsentscheidung, keine
Logikaenderung.

Danach, NUR wenn `final_quantity >= 1`: sequenziell `UNECONOMICAL_AFTER_COSTS`-Veto, dann
`RRR_TOO_LOW`-Veto.

### Phase 4-6 — Runtime Trace Contract + Implementation

**Die Instrumentierung ist LIVE (siehe Phase 16) und erweitert AUSSCHLIESSLICH die bestehende
`sizePosition()`-Funktion** — keine zweite/parallele Implementierung (Phase 6 der Spezifikation
strikt eingehalten). Jeder Rueckgabepfad (5 Veto-Faelle + Erfolgsfall) enthaelt jetzt zusaetzlich
ein `trace`-Objekt:

```js
trace: {
  trace_version: '4Q1-v1',
  candidate_input: { entry_price, stop_price, target_price, stop_distance_abs, stop_distance_pct, reward_risk_ratio },
  raw_quantity, raw_position_value, raw_risk_amount,          // nur ab RAW_RISK_SIZE-Stufe verfuegbar
  sizing_trace: [                                              // nur wenn alle 5 Kandidaten berechnet wurden
    { stage: 'RAW_RISK_SIZE',          quantity_before: null, allowed_quantity, quantity_after, limit, remaining_capacity, binding },
    { stage: 'SINGLE_POSITION_LIMIT',  quantity_before, allowed_quantity, quantity_after, limit, remaining_capacity, binding },
    { stage: 'TOTAL_RISK_LIMIT',       ... },
    { stage: 'SECTOR_LIMIT',           ... },
    { stage: 'REGION_LIMIT',           ... }
  ],
  quantity_before_final_floor, quantity_after_final_floor,     // siehe Phase 10 unten
  binding_limit,                                                // IMMER gesetzt, auch bei APPROVED (Phase 8)
  stage_reached: 'GEOMETRY'|'RAW_RISK_SIZE'|'QUANTITY_TOO_SMALL'|'UNECONOMICAL_AFTER_COSTS'|'RRR_TOO_LOW'|'APPROVED',
  final_position_value, final_risk_amount                      // nur wenn final_quantity>=1
}
```

Zusaetzlich (Job-A-Aufrufer, additiv in `diagnostics_json.job_a_portfolio_check`):

```js
{
  ...bestehende Felder unveraendert (approved, blockers, drawdown_pct_at_check, correlation_checked, strategy_status_policy_mode)...
  binding_limit,             // aus sizing.trace.binding_limit bzw. sizing.binding_limit
  runtime_sizing_trace,      // = sizing.trace (der VOLLE Trace-Objekt von oben), oder null bei STRATEGY_DEACTIVATED
  portfolio_state_before: { proposed_count, open_count, total_risk_used, sector_exposure_used, region_exposure_used },
  config_source: 'run.config_snapshot_json (frozen, siehe backtest_runs.id=<runId>)'
}
```

Das `portfolio_state_before`-Objekt wird **VOR** dem sizePosition()-Aufruf fuer GENAU diesen
Kandidaten eingefroren (Phase 11 der Spezifikation: kein nachtraeglicher Rekonstruktionsschritt),
direkt aus `shadowState.proposed.length`/`shadowState.open.length` sowie aus derselben
`shadowPortfolio.open_positions`-Liste, die `sizePosition()` selbst gleich erhaelt — also exakt
der Zustand, den die Engine tatsaechlich gesehen hat, nicht eine spaetere Naeherung.

Currency-/Directional-Exposure (`checkShadowPortfolioLimits()`) wurden **bewusst NICHT**
zusaetzlich instrumentiert — begruendet: (a) `sizePosition()` selbst verwendet diese beiden Werte
gar nicht (sie werden erst im nachgelagerten, separaten Portfolio-Check gebraucht), (b) im
gesamten Run 42 trat unter 427 Faellen kein einziger CURRENCY_LIMIT/DIRECTIONAL_LIMIT-Blocker auf
(siehe 4Q), (c) eine Erweiterung haette die Rueckgabeform von `checkShadowPortfolioLimits()`
aendern muessen (Array -> Objekt) und damit ein zusaetzliches Risiko fuer eine ohnehin schon
grosse Live-Aenderung bedeutet. Diese Entscheidung wird hier offen als Scope-Begrenzung benannt,
nicht verschwiegen.

### Phase 7 — Persistenz: additiv, KEINE Migration

`diagnostics_json jsonb` (Migration 087) existiert bereits, ist nullable, additiv gedacht laut
eigenem Migrations-Kommentar ("Sammel-Feld fuer Strategie-spezifische Zusatzwerte"). Der gesamte
Trace wurde dort hineingehaengt. **Keine Schema-Migration noetig, keine erstellt.**

### Phase 8 — `binding_limit` fuer ALLE READY-Kandidaten, nicht nur QTS

Bestaetigt durch die Instrumentierung selbst: `binding_limit` wird im `trace`-Objekt IMMER
gesetzt, sobald die 5 Kandidaten berechnet wurden (unabhaengig davon, ob am Ende APPROVED,
QUANTITY_TOO_SMALL, UNECONOMICAL_AFTER_COSTS oder RRR_TOO_LOW herauskommt) — vorher war
`binding_limit` nur im Veto-Fall gesetzt (`clamp_reason` im Erfolgsfall, und dort nur `null`,
wenn NICHT tatsaechlich gekappt wurde). Jetzt ist es immer `binding.reason || 'RAW_RISK_SIZE'`.

### Phase 9 — Exakte QUANTITY_TOO_SMALL-Bedingung

Unveraendert (durch die Instrumentierung nicht angetastet, nur zusaetzlich sichtbar gemacht):

```js
const finalQuantity = Math.max(0, Math.floor(binding.quantity));
if (finalQuantity < MIN_TRADABLE_QUANTITY) return { veto: 'QUANTITY_TOO_SMALL', ... };
// MIN_TRADABLE_QUANTITY = 1 (hartkodierte Modulkonstante)
```

Exakte Semantik: **`final_quantity < 1`** — wegen vorherigem `Math.max(0, Math.floor(...))`
aequivalent zu **`final_quantity === 0`** (kann durch die Konstruktion nie negativ oder
gebrochen sein). Keine Umschreibung noetig — das ist die woertliche Bedingung.

### Phase 10 — Pre-Floor / Post-Floor

`quantity_before_final_floor = binding.quantity` (der Wert des argmin-Kandidaten, BEVOR die
letzte `Math.max(0, Math.floor(...))`-Anwendung), `quantity_after_final_floor = final_quantity`
(danach). **Wichtiger struktureller Befund, durch die Golden-Tests (Phase 12, Fall F) bestaetigt:
in dieser Implementierung sind pre- und post-floor IMMER identisch**, weil jeder der 5
Kandidaten bereits EINZELN durch sein eigenes `Math.floor(...)` gerundet wird, bevor der
Minimum-Vergleich ueberhaupt stattfindet — es gibt keinen zusaetzlichen, nachgelagerten
Float-zu-Integer-Uebergang. Das bedeutet: **Rundungs-/Floor-Effekte als EIGENSTAENDIGE
Fehlerursache (getrennt von "welcher Constraint band") sind in dieser Codebasis strukturell
ausgeschlossen** — ein Befund, der bereits in 4Q vermutet, hier durch die Instrumentierung selbst
bewiesen wurde.

### Phase 11 — Portfolio State Observability

Siehe Phase 4-6 oben — `portfolio_state_before` wird VOR dem Kandidaten eingefroren, nicht
nachtraeglich aus `simulation_shadow_trades` rekonstruiert. Das ist die zentrale Antwort auf die
"wahrscheinlich kritischste Luecke" der Spezifikation.

### Phase 12 — Trace Sanity Tests (Golden Tests, lokal)

22 lokale Tests (Node.js, gegen die tatsaechlich aus der WF17-Datei extrahierte, editierte
Funktion — nicht gegen eine separate Kopie) fuer alle 8 geforderten Faelle A-H:

```
PASS A.veto_null / A.trace_present / A.5_stages / A.final_qty_gt_0 / A.reason_approved /
     A.raw_qty_matches_theoretical / A.exactly_one_binding / A.binding_matches_top_level
PASS B.veto_qts / B.final_qty_zero / B.total_risk_binding / B.binding_limit_total_risk
PASS C.sector_binding / C.binding_limit_sector
PASS D.region_binding / D.binding_limit_region
PASS E.single_position_binding
PASS F.pre_post_floor_present / F.pre_equals_post_by_construction
PASS G.remaining_capacity_full
PASS H.remaining_total_risk_correct / H.remaining_sector_correct

=== 22 PASS / 0 FAIL ===
```

### Phase 13-14 — Regression (Existing Logic + Research)

**937 Vergleiche** (10 synthetische Golden-/Veto-Faelle + alle 463 READY-Kandidaten aus Run 42,
JEWEILS mit isoliertem UND stateful rekonstruiertem Portfolio-Zustand aus 4Q) zwischen der
ALTEN (unveraenderten, aus dem Live-System vor der Aenderung extrahierten) und der NEUEN
(instrumentierten, tatsaechlich jetzt live deployten) `sizePosition()`-Implementierung, verglichen
in 12 entscheidungsrelevanten Feldern (`veto, theoretical_quantity, actual_quantity,
theoretical_risk_amount, actual_risk_amount, unit_risk, position_value, reward_risk_ratio,
quantity_by_value, clamped, clamp_reason, binding_limit`):

```
TOTAL COMPARISONS: 937
FIELD MISMATCHES: 0
PASS: max numeric diff = 0
```

Da `sizePosition()` von BEIDEN Pfaden (RESEARCH_BASELINE/`isResearchExecution` UND
AVAILABLE_DATA_LIVE_REPLAY/Job A) als **dieselbe** Funktion aufgerufen wird, und alle
Aufrufer-Codestellen ausschliesslich einzelne benannte Felder lesen (`sizing.veto`,
`sizing.theoretical_quantity`, usw. — nie eine strukturelle/vollstaendige Objektpruefung, per
`grep` verifiziert), gilt: **Research Regression max diff = 0** folgt direkt aus demselben Beweis,
nicht aus einem separaten Testlauf (RESEARCH_BASELINE braucht/nutzt den neuen `trace` nirgends).

---

## TEIL C — DEPLOY

### Phase 16 — Deploy

1. **Commit** `e31e3a960d40fc0ee8749a46b2003ae7ee137a08` auf Branch `agenten-modernisierung` —
   Diff beschraenkt sich (nach Entfernen einer kosmetischen Trailing-Newline-Differenz) auf
   **genau 1 Zeile** in der WF17-Repo-Datei (die eine `jsCode`-Zeile des Node "Verarbeite
   Tage-Paket", da n8n-Exporte den gesamten Code als einen JSON-String auf einer Zeile
   speichern) — strukturell bestaetigt: `git diff --stat` zeigt 1 Insertion/1 Deletion,
   und ein direkter Node-fuer-Node-Vergleich (JSON) zwischen alter und neuer Workflow-Definition
   zeigt: **nur genau der eine Node unterscheidet sich, alle anderen 52 Nodes, alle
   Connections, alle Settings sind byte-identisch.**
2. Backup des Vorzustands: `n8n_live_backup/17 – Historische Simulation (Walk-Forward, Pilot
   ohne Nachrichten)_PRE_4Q1_SIZING_TRACE_20260913.json` (vollstaendige Live-Kopie vor der
   Aenderung).
3. **Push** nach `origin/agenten-modernisierung` — erfolgreich (`b7447f7..e31e3a9`).
4. **Deploy** per `PUT /api/v1/workflows/9JWDOTXFQWHYkypO` (name/nodes/connections/settings aus
   der committeten Repo-Datei).
5. **Fresh GET zur Bestaetigung** (nicht nur PUT-Antwort vertraut): normalisierter Vergleich
   Live vs. Repo nach dem Deploy = **identisch**. `jsCode`-Laenge des geaenderten Node:
   187.161 Zeichen (erwartet, exakt), `active: true` (WF17 blieb wie zuvor aktiv — das ist der
   Produktions-Scheduler, unveraendert von diesem Schritt).

---

## TEIL D — MINI RUN

### Phase 15 — Scope-Auswahl (rein nach diagnostischer Dichte, aus Run-42-Daten geschaetzt)

Sliding-Window-Analyse ueber die 463 READY-Kandidaten aus Run 42 (Kalenderfenster mit den
meisten QTS+Approved-Ereignissen bei 5-10 Handelstagen Laenge):

```
Fenster 2026-06-17 bis 2026-06-23 (5 Handelstage mit READY-Kandidaten):
  READY (in Run 42, zum Vergleich): 42, davon QTS: 34, Approved: 8
```

Das uebertrifft die Mindestanforderung (>=20 QTS, >=2 Approved) deutlich, bei minimaler
Fenstergroesse (unteres Ende von "ca. 5-10 Handelstagen"). **Wichtiger Hinweis:** diese Zahlen
(34 QTS/8 Approved) sind eine Schaetzung AUS RUN 42 fuer denselben Kalenderausschnitt — Run 42
hatte an diesen Tagen aber bereits ein durch vorherige Bursts (05-04/05-07/05-29) TEILWEISE
gefuelltes Portfolio. Der neue Mini-Run startet dagegen mit EMPTY_SYNTHETIC (frischer,
leerer Zustand, da ein neuer `simulation_run_id`) — seine tatsaechlichen QTS/Approved-Zahlen
werden daher vermutlich abweichen (eher MEHR fruehe Genehmigungen, da das Portfolio zu Beginn
leer ist). Das ist erwuenscht und kein Problem: das Ziel ist diagnostische Dichte, nicht
Uebereinstimmung mit Run 42.

Ticker: dieselben 15 Core-Ticker wie Run 42 (ADS.DE, ALV.DE, BAS.DE, BAYN.DE, BMW.DE, DBK.DE,
DTE.DE, EOAN.DE, FRE.DE, HEN3.DE, MBG.DE, RWE.DE, SAP.DE, SIE.DE, VOW3.DE) — fuer realistische
Sektor-/Regions-Exposition.

### Phase 17 — Mini Diagnostic Replay gestartet

Erzeugt ueber den bestehenden, bereits aktiven WF17-eigenen Formular-Endpunkt
(`POST /webhook/historische-simulation`, `action=create_run`) — **kein WF97, keine Config-
Aenderung**, ausschliesslich die whitelisted Formularfelder:

```
name: "4Q.1 Mini Diagnostic Replay (Sizing Trace)"
start_date: 2026-06-17    end_date: 2026-06-23
initial_capital: 100000   news_enabled: false   run_type: walk_forward
live_parity_mode: AVAILABLE_DATA_LIVE_REPLAY
instruments: <15 Core-Ticker>
```

Ergebnis: **Run-ID 43** erstellt, Status zunaechst "laeuft" (queued/running), 5 Tage-Pakete in
die Warteschlange gestellt (bestaetigt ueber die bereits aktive, unveraenderte
Simulation-Steuerzentrale-Uebersicht, GET, kein Schreibzugriff).

**Update, ca. 6 Minuten spaeter:** Run 43 zeigt Status **"abgeschlossen"**, Warteschlange
Sim-Worker wieder bei 0, **"Keine Fehler"** in der Fehlertabelle des Laufs. Wie bei Run 42
(4Q, bereits dokumentiert) zeigt das Lauf-Detail selbst "Trades: 0" / "Rendite: 0.00%" — das ist
die bekannte Dashboard-Bindheit gegenueber AVAILABLE_DATA_LIVE_REPLAY-Laeufen (Dashboard fragt
`simulation_trades`/`simulation_daily_portfolio` ab, nicht `simulation_shadow_trades`/
`simulation_decision_log`) und **kein neuer Befund** — genau der Grund, warum fuer Phase 18 ein
Lesezugriff auf `simulation_decision_log` noetig ist (siehe unten).

### Phase 18 — Runtime Trace Auswertung

**Update:** Der Koordinator hat die im vorherigen STOPP-Abschnitt exakt benannte SELECT-Anfrage
nach frischer, expliziter Nutzerfreigabe **selbst** ausgefuehrt (nicht ich), das Ergebnis als
`docs/adhoc/run43_decision_log_raw_2026-09-13.json` abgelegt, und WF97 danach sofort wieder
geschlossen. **Ich habe das unabhaengig verifiziert, nicht nur die Behauptung uebernommen:**
fresh GET zeigt `active:false`, Node "Diag Webhook" weiterhin `disabled:true`,
`POST /webhook/diag-repair` → 404. Die im STOPP-Abschnitt beschriebene Grenze wurde eingehalten
— exakt eine Query, kein eigenmaechtiger Zugriff meinerseits.

**59 Zeilen ausgelesen** (Run 43, `simulation_run_id=43`): `reason='READY'`: 42, `reason=
'GEOMETRY_INVALID'`: 17. Stichprobe der ersten READY-Zeile (ADS.DE, 2026-06-17) bestaetigt: die
4Q.1-Instrumentierung ist korrekt live und liefert exakt die in Phase 4 spezifizierte Form —
`diagnostics_json.job_a_portfolio_check.runtime_sizing_trace` mit vollstaendigem
`sizing_trace`-Array (5 Stufen, je `stage/quantity_before/allowed_quantity/quantity_after/limit/
remaining_capacity/binding`), `binding_limit`, `portfolio_state_before`
(`proposed_count/open_count/total_risk_used/sector_exposure_used/region_exposure_used`),
`quantity_before_final_floor`/`quantity_after_final_floor`.

### Phase 19 — Python-Engine-Crosscheck (echter Live-Service, exakte Runtime-Inputs)

Der aktive Python-Trading-Engine-Service (`http://172.16.1.14:8099`, derselbe Host, den auch
der — hier inaktive — "Verarbeite Tage-Paket (Engine)"-Pfad in WF17 aufruft) ist von dieser
Umgebung aus direkt erreichbar (`GET /health` → 200; `/openapi.json` verfuegbar). Er stellt einen
dedizierten Endpunkt **`POST /engine/portfolio/check-and-size`** bereit — laut eigener
OpenAPI-Beschreibung *"Reine Weiterleitung an size_position() + check_portfolio_limits() - keine
eigene Fachlogik"* — also exakt die produktive Python-Referenzimplementierung, ohne Umweg ueber
den tagesweisen `/engine/simulation/step`-Endpunkt.

Fuer jeden der 42 READY-Kandidaten wurde ein Request gebaut, der **ausschliesslich Werte aus dem
gerade ausgelesenen Runtime-Trace verwendet** (nicht rekonstruiert, nicht approximiert):

- `signal.stop_price/target_price`, `entry_price_estimate`: 1:1 aus `trace.candidate_input`.
- `sektor/region/currency`: 1:1 aus `diagnostics_json.sector/region/currency` derselben Zeile.
- `risk_cfg`: die 5 sizing-relevanten Prozentwerte (`max_risk_per_trade_pct`,
  `max_single_position_pct`, `max_total_open_risk_pct`, `max_sector_exposure_pct`,
  `max_region_exposure_pct`) sind **direkt aus dem Trace selbst rekonstruierbar** (die
  `limit`/`remaining_capacity`-Felder der isolierten Stufen zeigen sie exakt: 1000 EUR
  Risikobudget @ 100.000 EUR Portfolio = 1%, 8/6/15/60 als Prozentwerte) — keine Annahme noetig.
  Die uebrigen, hier nicht sizing-relevanten `risk_cfg`-Felder (`max_open_positions`,
  `max_directional_exposure_pct`, `max_portfolio_drawdown_pct`, `max_pairwise_correlation`,
  `max_non_eur_exposure_pct`, `stress_risk_reduction_factor`, `min_reward_risk_ratio`) wurden aus
  dem in 4Q fuer Run 42 bestaetigten `config_snapshot_json` uebernommen, **nicht** fuer Run 43
  selbst erneut einzeln nachgewiesen — offen benannt, siehe Einschraenkung unten.
- `fee_model`: `fee_bps=15`, `slippage_bps=10` (4Q-bestaetigte Default-Werte).
- `portfolio.open_positions`: da mein Trace nur AGGREGIERTE Werte
  (`total_risk_used`/`sector_exposure_used`/`region_exposure_used`) speichert, nicht die
  Einzelpositionen, wurden 2-3 synthetische Positionen konstruiert, die exakt dieselben
  Aggregatsummen erzeugen wie im echten Shadow-Zustand (je eine Position, die ausschliesslich zum
  Gesamtrisiko, zur Sektor-Summe bzw. zur Regions-Summe beitraegt, plus Nullwert-Fuellpositionen
  bis zur korrekten Gesamtzahl `proposed_count+open_count`). Das reproduziert `size_position()`s
  eigene Filterlogik (`filter(sektor==X)`/`filter(region==Y)`) exakt, **kann aber
  `DIRECTIONAL_LIMIT`/`MAX_OPEN_POSITIONS`/Korrelation nicht 1:1 nachbilden**, da diese Werte im
  Trace nicht separat erfasst wurden (bewusste Scope-Entscheidung aus Phase 4-6, siehe oben) —
  offen benannt, betrifft aber nur den SEPARATEN Portfolio-Check, nicht `size_position()` selbst.

Alle 42 Requests erhielten HTTP 200.

### Phase 20 — Parity-Matrix

**Wichtiger methodischer Zwischenschritt, hier offen dokumentiert statt verschwiegen:** der
erste Vergleichsdurchlauf zeigte 36 scheinbare Abweichungen — bei genauer Pruefung war das ein
Fehler in meinem eigenen Vergleichsskript, nicht im System: ich hatte `shadow.binding_limit`
(ein reines JS-Diagnosefeld ohne Python-Gegenstueck, das AUCH bei erfolgreichem Sizing zeigt,
welche Klammer am naechsten war) gegen Python's `sizing.reason` (das nur bei einem Veto ueberhaupt
gesetzt ist und dort schlicht den Veto-Namen traegt, z.B. `"QUANTITY_TOO_SMALL"`, nicht die
Klammer-Stufe) verglichen — zwei nicht-aequivalente Felder. Nach Korrektur (Vergleich auf
kanonischer Ebene: `sizing.quantity/position_value/risk_amount/reason` bzw. Portfolio-Blocker,
exakt wie es JS's eigenes Top-Level-Rueckgabeobjekt — nicht das zusaetzliche Diagnose-Trace —
auch tut):

```
Total candidates: 42
EXACT_MATCH:  42 / 42
NUMERIC_MISMATCH: 0
Max |final_quantity diff|:      0
Max |final_position_value diff|: 0
Max |final_risk_amount diff|:     0
final_reason identisch in allen 42 Faellen (inkl. der 35 QUANTITY_TOO_SMALL-, 1 RRR_TOO_LOW-,
  1 DIRECTIONAL_LIMIT- und 5 APPROVED-Faelle)
```

### Phase 21 — Harte Parity-Abnahme

**PASS**, ohne Einschraenkung bei den geforderten Kernkriterien: `final_quantity`-Diff = 0,
`final_position_value`-Diff = 0, `final_risk_amount`-Diff = 0, `final_reason` identisch in allen
42 Faellen. Die Sizing-FORMEL selbst — dieselbe Formel, egal ob in JS (Shadow) oder Python
(Engine) ausgefuehrt — reproduziert bei identischen Runtime-Inputs (Kandidat + Portfolio-Zustand
+ Config) exakt dasselbe Ergebnis. **Kein Formel-Parity-Bug.**

### Phase 22-24 — Root-Cause-Klassifikation: EIN ANDERER, ECHTER BUG GEFUNDEN (nicht die Sizing-Formel)

Waehrend der Auswertung des Runtime-Traces (nicht erst beim Python-Vergleich) fiel ein
**unabhaengiger, gravierender Befund** auf, den erst diese Instrumentierung ueberhaupt sichtbar
machen konnte (er betrifft ein Feld, das vorher nirgends gespeichert wurde):

```
2026-06-17  (5 Kandidaten genehmigt: ADS.DE, ALV.DE, DBK.DE, DTE.DE, FRE.DE)
  proposed_count zwischen 0 und 5, total_risk_used zwischen 0 und 1.282,70 EUR -- PLAUSIBEL.

2026-06-18  (naechster Handelstag, alle 7 Kandidaten QUANTITY_TOO_SMALL)
  proposed_count = 1985,  open_count = 0,  total_risk_used = 509.232,20 EUR

2026-06-19  proposed_count = 0,  open_count = 1985,  total_risk_used = 509.232,20 EUR
2026-06-22  proposed_count = 0,  open_count = 1985,  total_risk_used = 509.232,20 EUR
2026-06-23  proposed_count = 0,  open_count = 1588,  total_risk_used = 424.623,60 EUR
```

**Das ist unmoeglich fuer einen Lauf mit 15 Tickern ueber 5 Handelstage.** Zum Vergleich: 1.985
"offene/vorgeschlagene Positionen" bei nur 15 handelbaren Instrumenten insgesamt, und ein
Gesamtrisiko von 509.232 EUR gegen ein Modellportfolio von 100.000 EUR (509% statt der
konfigurierten 6%-Obergrenze). **Auffaelliges Zahlenmuster:** `1985 = 5 × 397` und
`1985 − 1588 = 397` — beide Male ein glatter Vielfaches von 397. Das spricht stark fuer eine
**Multiplikations-/Duplizierungs-Bug** (jede der am 06-17 tatsaechlich genehmigten 5 Positionen
scheint um denselben Faktor 397 dupliziert worden zu sein), nicht fuer eine zufaellige
Zahlenreihe.

**Ausgeschlossen, dass DIESE Instrumentierung selbst die Ursache ist:**
- Der Code, der `shadowState.proposed`/`shadowState.open` befuellt (Hydration aus dem
  DB-Reload, Zeile mit `if (t.status === 'proposed') shadowState.proposed.push(t);`) sowie der
  Code, der neue Kandidaten hineinschiebt (`shadowState.proposed.push(newShadowTrade)`), wurden
  von mir **nicht angefasst** — mein Diff (Abschnitt Phase 16) zeigt exakt, welche Zeilen ich
  geaendert habe, und keine davon beruehrt diese Mutationslogik. Ich lese `shadowState.proposed.
  length`/`shadowState.open.length` nur READ-ONLY, nachdem sie bereits befuellt sind.
- Die SQL-Abfrage "DB: Shadow-State laden" (siehe 4Q.1 Phase 2/Preflight, fresh gelesen) ist ein
  einfaches `SELECT * FROM trading.simulation_shadow_trades WHERE simulation_run_id = X AND
  status IN (...)` — **kein JOIN**, kann also selbst keine Zeilen vervielfachen. Wenn
  `shadowState.proposed.length` wirklich 1985 ist, muessen entweder (a) tatsaechlich ~397
  Duplikat-Zeilen pro Kandidat in `trading.simulation_shadow_trades` fuer `simulation_run_id=43`
  persistiert worden sein (ein Bug in der INSERT/UPSERT-Seite, "Baue SQL fuer Paket-Ergebnisse"),
  oder (b) ein n8n-internes Artefakt bei der Item-Weitergabe zwischen Nodes liefert
  `$('DB: Shadow-State laden').all()` mehrfach dieselben Zeilen. **Ich kann diese beiden
  Hypothesen nicht unterscheiden, ohne eine weitere Abfrage gegen
  `trading.simulation_shadow_trades WHERE simulation_run_id = 43` (z.B. `count(*)` vs.
  `count(DISTINCT id)`) — das wuerde erneut WF97 benoetigen und ist NICHT Teil der einen bereits
  erteilten Autorisierung. Ich stelle diese Anfrage hier nur als Beobachtung fuer eine
  moegliche Folgesitzung dar, aktiviere aber nichts selbst.**

**Wichtig — das ist NICHT dasselbe wie ein Shadow/Engine-Parity-Bug:** Phase 19-21 haben gezeigt,
dass Shadow und Python-Engine bei IDENTISCHEM Input exakt dasselbe berechnen. Der jetzt gefundene
Bug liegt VOR der Sizing-Berechnung — im INPUT selbst (dem Portfolio-Zustand), nicht in der
Formel. Beide Systeme haben also KORREKT auf einen (vermutlich) fehlerhaften Zustand reagiert.

**Root Cause Classification (Phase 22 der Spezifikation): B. PORTFOLIO_STATE_INPUT_BUG.**
Nicht A (Shadow-Formel ist nachweislich korrekt, Phase 21), nicht C (Config bereits als
Prozentwerte direkt aus dem Trace verifiziert, keine Einheiten-/Wert-Diskrepanz gefunden), nicht
D (kein Rundungseffekt — die Zahlen sind um Groessenordnungen zu gross, nicht knapp daneben),
nicht E (das *Fehlen* von binding_limit war das 4Q-Problem, nicht Ursache dieses neuen Fundes),
nicht F (Shadow/Engine stimmen exakt ueberein), nicht G (siehe unten — die 4Q-Rekonstruktion
UND dieser neue State-Bug erklaeren gemeinsam das Bild, siehe Phase 23).

### Phase 23 — Einordnung: 4Q-Rekonstruktion UND ein echter State-Bug, nicht "entweder/oder"

Die Spezifikation sah zwei sich gegenseitig ausschliessende Ausgaenge vor ("Formel-Bug bestaetigt"
ODER "4Q-Rekonstruktion war nicht ausreichend"). Der tatsaechliche Befund liegt dazwischen und
sollte nicht in eines der beiden Schemata gepresst werden:

1. **Die Sizing-FORMEL selbst hat keinen Parity-Bug** (Phase 21, hart bewiesen, 42/42 exact
   match gegen die echte Python-Engine mit exakten Runtime-Inputs).
2. **Die 4Q-Rekonstruktion aus `simulation_shadow_trades`-Endzustaenden konnte den in Punkt 3
   beschriebenen Bug prinzipiell nicht sehen** — 4Q rekonstruierte Portfolio-Groessen aus den
   FINAL persistierten, sauberen 32 Trades (0 Duplikate, in 4Q selbst geprueft) und kam dadurch
   auf plausible, kleine Kapazitaetswerte. Der jetzt gefundene Bug zeigt sich aber genau in der
   Differenz zwischen "was `shadowState.proposed/open` zur LAUFZEIT tatsaechlich enthielt" (1985)
   und "was am Ende in der Tabelle landete" (fuer Run 42 nachweislich 32 saubere Zeilen) — eine
   Diskrepanz, die eine Rekonstruktion aus Endzustaenden per Definition nicht aufdecken kann.
3. **Es gibt vermutlich einen echten, bisher unsichtbaren State-Bug** (proposed/open-Zaehler
   explodieren um den Faktor ~397), der in Run 42 (76 Tage, viel mehr Gelegenheiten) sehr
   wahrscheinlich ebenfalls aufgetreten sein koennte — das ist an dieser Stelle eine **Vermutung,
   keine bewiesene Tatsache**: ich habe NICHT geprueft, ob Run 42 dasselbe Muster zeigt (das
   haette eine weitere WF97-Abfrage gegen die Run-42-Daten gebraucht, die es so granular vorher
   nicht gab, da `portfolio_state_before` erst mit dieser Instrumentierung existiert).

**Damit ist die praeziseste, ehrliche Formulierung:** Der urspruengliche 93,9%-Befund aus 4Q ist
NICHT auf eine falsche Sizing-Formel zurueckzufuehren (das ist jetzt ausgeschlossen). Er ist aber
auch nicht einfach ein reines "Rekonstruktionsartefakt" im Sinne von "die Formel war immer schon
grosszuegig genug, 4Q hat sich nur geirrt" — sondern es gibt sehr starke, neue Evidenz fuer einen
ECHTEN, separaten Bug in der Portfolio-Zustandsfuehrung, der 4Q's Rekonstruktion unterlaufen haben
koennte, ohne dass 4Q das haette sehen koennen.

---

## STOPP — gemaess Spezifikation, nach Bericht, kein Fix, kein Tuning, kein Full Replay

Wie in der harten STOPP-Regel der Spezifikation vorgesehen: Parity ist bewiesen (PASS), UND
gleichzeitig wurde ein anderer, echter Bug identifiziert. Beides zusammen bedeutet: **STOPP nach
diesem Bericht.** Keine Reparatur des vermuteten State-Bugs, kein Parameter-Tuning, kein erneuter
Run-42-Vollreplay, keine neue Untersuchung des `1985`-Musters ueber eine weitere Abfrage — auch
wenn das naheliegend waere. Falls eine Folgesitzung die Ursache des Faktor-397-Musters klaeren
soll, waere die noetige Abfrage (rein informativ, NICHT hier ausgefuehrt):

```sql
SELECT count(*) AS n_rows, count(DISTINCT id) AS n_distinct_pk,
       count(DISTINCT shadow_trade_id) AS n_distinct_trade_id
FROM trading.simulation_shadow_trades WHERE simulation_run_id = 43;
```

— read-only, wuerde zeigen, ob die 1985 aus echten Duplikat-Zeilen in der Tabelle stammen oder
aus einem n8n-internen Weitergabe-Artefakt. Das ist eine Beobachtung fuer die Zukunft, keine
Aufforderung — ich aktiviere WF97 dafuer nicht selbst, weder jetzt noch impliziet spaeter.

---

## ABSCHLUSSBERICHT (47 PUNKTE)

### TEIL A — 4Q REVIEW

1. **4Q Bericht gelesen:** JA.
2. **427 QTS bestaetigt:** JA (methodisch — der Code, der diese Zahl in Run 42 erzeugt hat,
   wurde fresh erneut gelesen und ist unveraendert).
3. **401/427 Rekonstruktionsabweichung bestaetigt:** JA, mit wichtiger Praezisierung (siehe
   Phase 23): die Formel selbst ist NICHT die Ursache (Phase 21 bewiesen) — die Abweichung ist
   sehr wahrscheinlich (nicht bewiesen fuer Run 42 selbst) auf denselben Typ State-Bug
   zurueckzufuehren, der in Run 43 direkt beobachtet wurde.
4. **26/427 erklaerbar bestaetigt:** JA.
5. **binding_limit bisher nicht persistiert:** JA, fresh bestaetigt.
6. **Weitere wichtige 4Q-Probleme:** Ein NEUER, in 4Q noch nicht sichtbarer Befund kam in 4Q.1
   hinzu (Portfolio-State-Explosion, siehe Phase 22) — kein 4Q-Fehler, sondern eine
   Beobachtbarkeitsluecke, die erst mit dieser Instrumentierung schliessbar wurde.

### TEIL B — INSTRUMENTATION

7. **Runtime Trace implementiert:** JA.
8. **Gleiche Sizing Source of Truth:** JA — der Trace wird ausschliesslich aus den in
   `sizePosition()` selbst bereits berechneten Variablen gebaut, keine zweite Berechnung.
9. **Separate Diagnostic-Sizing-Implementierung erstellt:** **NEIN** (wie gefordert).
10. **binding_limit persistiert:** JA — sowohl im isolierten Aufruf (`diagnostics_json.sizing.
    runtime_trace.binding_limit`) als auch im stateful Job-A-Aufruf
    (`diagnostics_json.job_a_portfolio_check.binding_limit`), fuer JEDEN READY-Kandidaten mit
    ausgefuehrtem Sizing (nicht nur QTS).
11. **pre-floor quantity persistiert:** JA (`quantity_before_final_floor`).
12. **final quantity persistiert:** JA (`quantity_after_final_floor`, sowie weiterhin
    `actual_quantity`/`theoretical_quantity` unveraendert).
13. **Portfolio State Before persistiert:** JA (`portfolio_state_before`: proposed_count,
    open_count, total_risk_used, sector_exposure_used, region_exposure_used) — eingefroren VOR
    dem jeweiligen Kandidaten, nicht rekonstruiert.
14. **Sizing Config nachvollziehbar:** JA — ueber `config_source`-Verweis auf das bereits
    bestehende, eingefrorene `backtest_runs.config_snapshot_json` (keine Duplizierung der
    Config je Kandidat, da sie laufweit ohnehin konstant ist, siehe 4Q).
15. **Schema Migration:** **NEIN** (wie erwartet/bevorzugt) — additiv in die bereits bestehende
    `diagnostics_json jsonb`-Spalte (Migration 087).

### TEIL C — REGRESSION

16. **Golden Trace Tests:** 22 / 22 PASS.
17. **Existing Replay Regression:** **PASS**.
18. **Replay max numeric diff:** **0** (937 Vergleiche, 12 Felder).
19. **Research Regression:** **PASS** (durch identische Beweisfuehrung wie Punkt 17/18 —
    RESEARCH_BASELINE nutzt dieselbe unveraenderte Funktion und liest nur unveraenderte Felder).
20. **Research max diff:** **0**.
21. **Commit-ID:** `e31e3a960d40fc0ee8749a46b2003ae7ee137a08` (Branch `agenten-modernisierung`,
    gepusht nach `origin/agenten-modernisierung`).
22. **Live/Repo identisch:** JA, fresh per GET nach dem Deploy bestaetigt.

### TEIL D — MINI RUN

23. **Mini Run ID:** 43.
24. **Zeitraum:** 2026-06-17 bis 2026-06-23.
25. **Business Days:** 5 (2026-06-17, -18, -19, -22, -23 — bestaetigt aus den 42 READY-Zeilen).
26. **Ticker:** 15 Core-Ticker (identisch zu Run 42).
27. **READY Candidates:** **42**.
28. **QTS (QUANTITY_TOO_SMALL):** **35**.
29. **Approved:** **5** (uebrige 2: 1× RRR_TOO_LOW, 1× DIRECTIONAL_LIMIT).
30. **Errors:** 0 (bestaetigt ueber die bereits aktive Simulation-Steuerzentrale, GET, sicher).
31. **completed:** JA (Status "abgeschlossen", bestaetigt ueber GET).

### TEIL E — RUNTIME PARITY

32. **Candidates crosschecked:** **42** (alle READY-Kandidaten des Mini-Runs).
33. **Exact matches:** **42 / 42 (100%)** — nach Korrektur eines anfaenglichen Fehlers im
    eigenen Vergleichsskript (siehe Phase 20: `binding_limit`-Diagnosefeld faelschlich gegen
    Python's Veto-`reason` verglichen; nach Korrektur auf kanonische Felder: 100% exakt).
34. **Numeric mismatches:** **0**.
35. **Binding-limit mismatches:** 0 im kanonischen Sinn (Shadow und Engine geben identische
    `reason`-Werte zurueck in allen 42 Faellen). Das JS-interne `binding_limit`-Diagnosefeld hat
    kein direktes Python-Gegenstueck (Python liefert bei einem Veto nur den Veto-Namen, nicht
    welche der 5 Klammern konkret band) — ein Schema-/Granularitaets-Unterschied, kein Bug.
36. **Final-reason mismatches:** **0**.
37. **max final_quantity diff:** **0**.
38. **max final_position_value diff:** **0**.
39. **max final_risk_amount diff:** **0**.
40. **Runtime Shadow / Python Engine parity:** **PASS** — mit der offen benannten
    Einschraenkung, dass `portfolio.open_positions` fuer den Engine-Call aus AGGREGIERTEN
    Trace-Werten synthetisch rekonstruiert wurde (siehe Phase 19), da Einzelpositionen nicht
    Teil des Traces sind, sowie dass ein Teil der `risk_cfg`-Werte (die fuer `size_position()`
    selbst nicht relevanten, siehe Phase 19) aus dem 4Q-Run-42-Snapshot uebernommen, nicht fuer
    Run 43 separat verifiziert wurden.

### TEIL F — ROOT CAUSE

41. **Root Cause Classification:** **B. PORTFOLIO_STATE_INPUT_BUG** — nicht die Sizing-Formel
    (Phase 21 widerlegt das), sondern der ihr zugefuehrte Portfolio-Zustand selbst (`proposed_
    count`/`open_count`/`total_risk_used` explodieren auf das ~397-Fache des plausiblen Werts ab
    dem zweiten Handelstag des Mini-Runs, siehe Phase 22).
42. **First divergence stage:** **N/A im Sinne von Shadow-vs-Engine** (die beiden divergieren
    nicht voneinander — beide erhalten denselben, vermutlich fehlerhaften Input und liefern
    dieselbe, dazu konsistente Antwort). Die eigentliche "erste Divergenz" ist zeitlich: zwischen
    dem plausiblen Zustand am 2026-06-17 (proposed_count 0-5) und dem impausiblen Zustand ab
    2026-06-18 (proposed_count 1985).
43. **Ist der 93,9%-Befund ein echter Runtime-Bug:** **JA, mit Einschraenkung** — ein echter,
    hier direkt beobachteter Bug (Portfolio-State-Explosion) existiert und wuerde plausibel zu
    massenhaften, unberechtigten QUANTITY_TOO_SMALL-Ergebnissen fuehren. Aber: dass GENAU dieser
    Mechanismus auch die 401/427 aus Run 42 (4Q) erklaert, wurde NICHT verifiziert (dafuer haette
    Run 42 selbst mit dieser Instrumentierung neu laufen muessen — explizit nicht erlaubt in
    diesem Schritt, siehe "Kein Full Replay").
44. **Ist die 4Q-Rekonstruktion als Ursache ausreichend:** **NEIN** — sie konnte den jetzt
    gefundenen State-Bug prinzipiell nicht sehen (siehe Phase 23), war methodisch aber nicht
    "falsch", nur strukturell blind fuer diese Fehlerklasse.
45. **Ist QUANTITY_TOO_SMALL aktuell fachlich vertrauenswuerdig:** **NEIN** — nicht wegen der
    Sizing-Formel (die ist jetzt bewiesen korrekt), sondern weil der ihr zugefuehrte
    Portfolio-Zustand vermutlich fehlerhaft aufgeblaeht sein kann. Ein QUANTITY_TOO_SMALL-Eintrag
    im Decision-Log ist derzeit nicht ohne Weiteres von einem durch den State-Bug erzwungenen
    Fehlurteil zu unterscheiden.
46. **Run 42 als Live-Policy-Performance belastbar:** **NEIN** — unveraendert, jetzt mit einer
    zusaetzlichen, konkreteren Begruendung: sehr wahrscheinlich betroffen vom selben
    Fehlerbild wie in Run 43 direkt beobachtet (nicht bewiesen, aber naheliegend).
47. **Genau EIN naechster Schritt:** Vor jeder weiteren Policy-Diskussion und vor jedem neuen
    Full-Window-Replay: den Portfolio-State-Bug isoliert untersuchen — beginnend mit der oben
    (Abschnitt "STOPP") genannten, noch nicht ausgefuehrten `count(*)` vs. `count(DISTINCT id)`-
    Abfrage gegen `trading.simulation_shadow_trades WHERE simulation_run_id IN (42, 43)`, um zu
    klaeren, ob die Vervielfachung in der Datenbank selbst liegt (INSERT/UPSERT-Bug in "Baue SQL
    fuer Paket-Ergebnisse") oder in der n8n-Item-Weitergabe beim Auslesen. Explizit KEINE
    Parameteraenderung, KEIN Fix, KEIN neuer Full-Replay, bis dieser Mechanismus gefunden und
    separat bestaetigt ist.
