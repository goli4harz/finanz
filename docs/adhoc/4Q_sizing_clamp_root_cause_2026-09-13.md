# SCHRITT 4Q — Sizing-Clamp Root-Cause-Analyse + Performance Accounting Reconciliation

> **NACHTRAG (2026-09-13, nach 4Q.1/4Q.2/4Q.3) — ergaenzt, nichts unten geloescht/umgeschrieben:**
> Die zentrale Hypothese dieses Berichts ("die Sizing-FORMEL erklaert QUANTITY_TOO_SMALL in ~94%
> der Faelle nicht") wurde durch 4Q.1 **teilweise widerlegt**: ein Runtime-Crosscheck gegen die
> echte Python-Engine (42/42 exakte Uebereinstimmung) zeigte, dass die Sizing-FORMEL selbst
> korrekt ist. 4Q.2 hat anschliessend den echten Mechanismus bewiesen: zwei WF17-Postgres-Nodes
> ohne `executeOnce:true` multiplizierten den Portfolio-Zustand im n8n-Datenstrom um Faktor 397
> (nie in der Datenbank selbst). 4Q.3 hat diesen Fehler minimal behoben (siehe
> `4Q1_runtime_sizing_parity_2026-09-13.md`, `4Q2_shadow_state_multiplication_2026-09-13.md`,
> `4Q3_...md`). Die HIER unten dokumentierte Beobachtung selbst (401/427 QTS-Faelle nicht durch
> Rekonstruktion erklaerbar) bleibt als Ausgangsbefund korrekt — nur ihre Interpretation ("Formel
> falsch" vs. "Input-Daten durch einen Item-Multiplikations-Bug korrumpiert") hat sich geaendert.
> Diese Datei bleibt ansonsten unveraendert als historische Evidenz stehen.

Datum: 2026-09-13 (zwei Sitzungsteile: read-only Code-Analyse, dann live-DB-Analyse nach
Freigabe eines SELECT-only-Zugriffswegs)
Repo-HEAD zum Zeitpunkt der Analyse: `b7447f7` (LIVE_PARITY 4O.4B)
Status: **PHASE 1-3 vollstaendig aus Rohdaten verifiziert. Root-Cause-Analyse (Phase 7-30)
durchgefuehrt, aber mit einem zentralen, hart belegten NEGATIV-Befund: die dokumentierte
Sizing-Formel erklaert die tatsaechlich beobachteten QUANTITY_TOO_SMALL-Ergebnisse in ~94% der
Faelle NICHT. Das ist der wichtigste Befund dieses Berichts (siehe Abschnitt 5).**

---

## 0. ZUSAMMENFASSUNG FUER DIE EILIGEN

**Teil A (Accounting) ist jetzt vollstaendig und unabhaengig aus den 29 echten geschlossenen
Shadow-Trades verifiziert:** Der im 4P-Bericht genannte Gross P&L von **-75,65 EUR war falsch**.
Der korrekte, aus den Rohdaten direkt nachgerechnete Wert ist **+159,35 EUR** — exakt der Wert,
den auch die reine Arithmetik der im 4P-Bericht selbst genannten Teilsummen ergibt. Net P&L
(-975,60 EUR) und Costs (1.134,95 EUR) waren dagegen bereits im 4P-Bericht korrekt.

**Teil C/F (QTS Root Cause) liefert kein sauberes Policy-Ergebnis, sondern einen konkreten,
hart belegten Verdacht auf einen Implementierungsfehler oder einen anderen, nicht vollstaendig
identifizierten Mechanismus:** Ich habe die dokumentierte Sizing-Formel (Python
`_size_position_clamp()` / JS `sizePosition()`, Zeile-fuer-Zeile identisch, live gegen die
Instanz verifiziert) selbst nachgebaut, mit den ECHTEN, aus `trading.simulation_shadow_trades`
rekonstruierten Portfolio-Zustaenden und der ECHTEN, im Run eingefrorenen Config gefuettert — und
komme in **401 von 427 Faellen (93,9%)** zu einem ANDEREN Ergebnis als real im
`simulation_decision_log` dokumentiert: meine Nachrechnung sagt "handelbar" (Quantity oft 20-800
Stueck), die Datenbank sagt "QUANTITY_TOO_SMALL". Das ist der von Phase 22 der Nutzer-Spezifikation
explizit vorgesehene STOPP-Fall ("Wenn Diff != 0: STOPP... dann haben wir einen Parity-Bug, keine
Policy-Diagnose"). Ich benenne das klar als solchen, statt eine bereinigte
Portfolio-Kapazitaets-Geschichte zu erzaehlen, die die Daten nicht hergeben.

Die ursprünglich (im ersten Teil dieser Sitzung, ohne DB-Zugriff) formulierte Hypothese
("TOTAL_RISK_LIMIT-Kapazitaetserschoepfung erklaert die 427 QTS-Faelle") ist damit **grossteils
widerlegt**: nur 26 der 427 Faelle (6,1%) lassen sich sauber durch die dokumentierte Formel plus
den echten, rekonstruierten Zustand erklaeren (19x REGION_LIMIT, 7x SECTOR_LIMIT). Die restlichen
401 sind mit dem dokumentierten Rechenweg nicht nachvollziehbar.

WF97 wurde am Ende der Sitzung wieder deaktiviert, fresh-verifiziert (siehe Abschnitt 8). Der
SQL-Guard-Node bleibt (deaktiviert) im Workflow bestehen, wie vom Koordinator vorgegeben.

---

## 1. WIE DER DATENZUGRIFF ZUSTANDE KAM (kurz, fuer Nachvollziehbarkeit)

Im ersten Teil dieser Sitzung wurde festgestellt, dass der im urspruenglichen Auftrag beschriebene
Webhook `/webhook/diagnose-sql` nicht existierte, und der tatsaechlich vorgefundene Mechanismus
(`Diag Webhook`, Pfad `diag-repair`, Workflow `NInmI0f9TfdndwI1`) einer bereits am 2026-09-09
geschlossenen Sicherheitsluecke entsprach (unauthentifiziertes, uneingeschraenktes SQL ueber
Webhook). Ich habe diesen Endpunkt **nicht** reaktiviert und stattdessen den Auftraggeber auf die
Diskrepanz hingewiesen.

Der Koordinator hat daraufhin **selbst** (direkter Nutzerkontakt, nicht per Relay) einen
SELECT-only-Guard in Workflow 97 eingebaut: ein neuer Code-Node **"SQL Guard (SELECT only)"**
zwischen "Diag Webhook" und dem Postgres-Node "Query ausfuehren", der den Query-String prueft:

```js
const raw = String(($json.body || {}).query || '').trim();
if (!raw) { throw new Error('Feld "query" fehlt im POST-Body.'); }
if (!/^select\b/i.test(raw)) { throw new Error('SQL_GUARD: nur SELECT-Anfragen sind ueber diesen Webhook erlaubt.'); }
const withoutTrailingSemicolon = raw.replace(/;\s*$/, '');
if (/;/.test(withoutTrailingSemicolon)) { throw new Error('SQL_GUARD: mehrere Anweisungen (Semikolon) sind nicht erlaubt.'); }
return [{ json: { query: withoutTrailingSemicolon } }];
```

Ich habe diesen Guard **selbst, unabhaengig, live verifiziert**, bevor ich ihn genutzt habe (nicht
nur die Behauptung des Koordinators uebernommen):
- `POST {"query":"SELECT 1 AS ok"}` → HTTP 200, `{"ok":1}` ✓
- `POST {"query":"EXPLAIN SELECT 1"}` (harmlos, aber kein SELECT-Prefix) → HTTP 500 (Guard griff) ✓
- `POST {"query":"SELECT 1; SELECT 2"}` (harmlos, aber Semikolon-Stacking) → HTTP 500 (Guard griff) ✓

Erst danach habe ich den Webhook fuer die eigentlichen Diagnose-Queries verwendet, jede davon in
`SELECT json_agg(t) AS result FROM ( <eigentliche Query> ) t` gewrappt (Workaround fuer die
`responseMode: lastNode`-Einschraenkung, die sonst nur die erste Zeile zurueckgeben wuerde).

Am Ende der Sitzung (Abschnitt 8) wurde der Workflow wieder deaktiviert und der Webhook-Node
erneut deaktiviert, fresh-verifiziert per GET + curl.

---

## 2. TEIL B — SIZING SOURCE (unveraendert aus dem ersten Sitzungsteil, weiterhin gueltig)

*(Dieser Abschnitt basiert vollstaendig auf Code-Lektuere und wurde im ersten Sitzungsteil bereits
vollstaendig verifiziert — er bleibt unveraendert bestehen, da Live-Daten ihn nicht betreffen.)*

### 2.1 Die zwei getrennten Sizing-Aufrufe pro READY-Kandidat

Im JS-Shadow-Port ("Verarbeite Tage-Paket", live-verifiziert byte-identisch zum Repo) gibt es
**zwei unabhaengige Aufrufe** derselben `sizePosition()`-Funktion pro READY-Kandidat:

**(A) Der "isolierte" Diagnose-Aufruf** — `sizePosition(..., [], ...)`, IMMER mit leerem
Portfolio, Kommentar im Code: *"openPositionsState bewusst leer (isoliert)"*,
`sizing_context: 'isolated_single_candidate_no_portfolio'`. Fuellt NUR die Top-Level-Felder
(`theoretical_quantity`, `actual_quantity`, `limiting_factor`) der `decision_log`-Zeile.

**(B) Der stateful Job-A-Aufruf** — `sizePosition(..., shadowOpenPositionsForCheck(), ...)`, mit
dem ECHTEN, kumulativen Shadow-Portfolio-Zustand (`shadowState.open.concat(shadowState.proposed)`).
Dieser Aufruf entscheidet, ob ein Shadow-Trade tatsaechlich angelegt wird. Sein Ergebnis landet in
`diagnostics_json.job_a_portfolio_check`.

**Diese Ambiguitaet ist jetzt aufgeloest (siehe Abschnitt 3):** Die vom Nutzer zitierten
Funnel-Zahlen (463 READY / 427 QUANTITY_TOO_SMALL / 3 RRR_TOO_LOW / 1 CORRELATION_LIMIT / 32
APPROVED) stammen **eindeutig** aus `diagnostics_json.job_a_portfolio_check` — dem STATEFUL
Aufruf (B), nicht dem isolierten (A). Live nachgezaehlt, exakte Uebereinstimmung mit den vom
Nutzer genannten Zahlen (siehe Abschnitt 3.1).

### 2.2-2.6 Formeln, Clamp-Reihenfolge, Config-Keys — siehe Teil B im Abschlussbericht (Punkte
11-20), Inhalte identisch zum ersten Sitzungsteil, jetzt zusaetzlich mit den ECHTEN (nicht nur
Seed-Default-) Config-Werten aus `run.config_snapshot_json.pipeline_config` bestaetigt:

```
MAX_RISK_PER_TRADE_PCT=1.0  MIN_REWARD_RISK_RATIO=1.5  MAX_TOTAL_OPEN_RISK_PCT=6.0
MAX_SECTOR_EXPOSURE_PCT=15.0  MAX_SINGLE_POSITION_PCT=8.0  MAX_REGION_EXPOSURE_PCT=60.0
MAX_DIRECTIONAL_EXPOSURE_PCT=40.0  MAX_NON_EUR_EXPOSURE_PCT=30.0  MAX_OPEN_POSITIONS=10
MAX_PORTFOLIO_DRAWDOWN_PCT=15.0  MAX_PAIRWISE_CORRELATION=0.75  STRESS_RISK_REDUCTION_FACTOR=0.5
DEFAULT_FEES_BPS=15  DEFAULT_SLIPPAGE_BPS=10  MODEL_PORTFOLIO_VALUE=100000
TRADING_ENGINE_STEP_ENABLED=false  (bestaetigt: Run 42 lief ueber den JS-Shadow-Port, NICHT
  ueber den Python-Engine-HTTP-Pfad "Verarbeite Tage-Paket (Engine)")
```

Diese Werte sind **eingefroren** (`config_snapshot_json`, einmalig bei Run-Erstellung befuellt,
per Code-Kommentar in "Baue Run-Kontext" bestaetigt: *"cfgByKey kam bisher aus einer bei JEDEM
Worker-Tick frisch ausgefuehrten Live-Query ... jetzt aus dem Ausfuehrungspfad entfernt ...
run.config_snapshot_json wird EINMALIG bei Run-Erstellung eingefroren und hier fuer die GESAMTE
Laufzeit des Laufs unveraendert wiederverwendet"*) — Config-Drift WAEHREND des Laufs (z.B. durch
eine parallel arbeitende andere Sitzung) ist damit als Erklaerung fuer Abschnitt 5
**ausgeschlossen**.

---

## 3. RUN-42-IDENTITAET UND DECISION-FUNNEL (live verifiziert)

### 3.1 `trading.backtest_runs` (id=42), live abgefragt

```
id=42, name="4P FULL DEV WINDOW AVAILABLE_DATA_LIVE_REPLAY (b7447f7)", status=completed,
progress_percent=100, error_count=0, initial_capital=100000, start_date=2026-05-01,
end_date=2026-08-15, news_enabled=false, run_type=walk_forward, strategy_filter=null,
instrument_selection_json=[ADS.DE, ALV.DE, BAS.DE, BAYN.DE, BMW.DE, DBK.DE, DTE.DE, EOAN.DE,
FRE.DE, HEN3.DE, MBG.DE, RWE.DE, SAP.DE, SIE.DE, VOW3.DE]  (15 Ticker)
started_at=2026-09-12T12:48:19Z, finished_at=2026-09-12T15:58:36Z
config_snapshot_json.mode = "AVAILABLE_DATA_LIVE_REPLAY"
```

**Bestaetigt: alle vom Nutzer genannten Eckdaten stimmen mit der Datenbank ueberein.** Keine
Abweichung gefunden.

### 3.2 `trading.simulation_decision_log` (649 Zeilen, alle `decision_stage='LIVE_PARITY_SHADOW'`)

```
reason='GEOMETRY_INVALID': 186
reason='READY': 463
```
649 = 186+463 ✓ (deckt sich mit "649 Shadow Decisions").

Von den 463 READY-Zeilen tragen **alle 463** ein `diagnostics_json.job_a_portfolio_check`-Objekt.
Aufschluesselung nach `job_a_portfolio_check`:

```
approved=true:                              32   (= "32 Shadow Trades" ✓, exakt)
approved=false, blockers=[QUANTITY_TOO_SMALL]: 427
approved=false, blockers=[RRR_TOO_LOW]:          3
approved=false, blockers=[CORRELATION_LIMIT]:    1
```
32+427+3+1 = 463 ✓. **Exakte Uebereinstimmung mit den vom Nutzer zitierten Funnel-Zahlen** — die
427/3/1/32-Aufteilung ist damit nicht nur uebernommen, sondern **live nachgezaehlt und
bestaetigt**, und eindeutig als aus dem STATEFUL Job-A-Aufruf (B) stammend identifiziert (siehe
2.1).

**Wichtiger Negativbefund fuer Phase 8:** `diagnostics_json.job_a_portfolio_check` persistiert
NUR `{approved, blockers, drawdown_pct_at_check, correlation_checked, strategy_status_policy_mode}`
— **NICHT** den `binding_limit` (welcher der 5 Clamp-Kandidaten RAW_RISK_SIZE/SINGLE_POSITION/
TOTAL_RISK/SECTOR/REGION tatsaechlich die Stueckzahl auf 0 gedrueckt hat). Diese Information wird
im Code (`sizing.binding_limit`, siehe `sizePosition()`) berechnet, aber **nie in die Datenbank
geschrieben**. Das ist eine echte Observability-Luecke: Phase 8 dieser Spezifikation (die
"wichtigste Tabelle dieses Schritts") kann aus den persistierten Daten **nicht direkt** beantwortet
werden — sie musste durch eigene Nachrechnung rekonstruiert werden (Abschnitt 4/5), mit dem
Ergebnis, dass diese Nachrechnung in den allermeisten Faellen NICHT mit der Datenbank
uebereinstimmt (Abschnitt 5).

---

## 4. TEIL A — ACCOUNTING RECONCILIATION (Phase 1-3, vollstaendig aus Rohdaten verifiziert)

`trading.simulation_shadow_trades` fuer Run 42: **32 Zeilen** (29 `closed`, 3 `open`) — exakte
Uebereinstimmung mit dem 4P-Bericht.

### 4.1 Phase 1 — Realized P&L (29 geschlossene Trades)

```
SUM(gross_pnl)  =  +159.35 EUR
SUM(net_pnl)    =  -975.60 EUR
IMPLIED total costs (gross_pnl - net_pnl) = 1134.95 EUR
Identity-Check: SUM(gross_pnl) - costs = 159.35 - 1134.95 = -975.60 = SUM(net_pnl) ✓ (Diff = 0.00 EUR)
```

**Der im 4P-Bericht gemeldete Gross P&L von -75,65 EUR ist damit definitiv widerlegt.** Der
korrekte Wert ist **+159,35 EUR** — identisch zu dem Wert, den bereits die reine Arithmetik der
im 4P-Bericht selbst genannten Gross-Winners/-Losses-Teilsummen ergab (4215,99 + 496,72 - 4553,36
= 159,35). Net P&L (-975,60 EUR) und Costs (1.134,95 EUR) waren im 4P-Bericht bereits korrekt und
sind jetzt unabhaengig aus den Rohdaten bestaetigt.

**Schema-Klaerung** (vom Koordinator als offene Frage markiert): `simulation_shadow_trades` hat
nur `entry_fee`/`entry_slippage`, keine `exit_fee`/`exit_slippage`-Spalten. Per-Trade-Analyse
zeigt: `gross_pnl - net_pnl` liegt konsistent bei ca. dem **Doppelten** von
`entry_fee+entry_slippage` (z.B. BMW.DE: entry_fee+slippage=19,95, aber gross-net=40,70). Das
bestaetigt die vom Koordinator vermutete Erklaerung: **Exit-Kosten werden real angewendet, aber
nicht in eigenen Spalten persistiert — sie sind bereits direkt in `net_pnl` eingerechnet**, ohne
separate Buchungszeile. Kein Fehler, nur ein Schema-Detail.

### 4.2 Phase 2 — Mark-to-Market der 3 offenen Positionen (letzter verfuegbarer Kurs im Fenster: 2026-08-14)

| Ticker | Richtung | Menge | Entry | Mark (08-14) | Unrealized (brutto) | abzgl. Entry-Kosten |
|---|---|---|---|---|---|---|
| ADS.DE | short | 49 | 161,25 | 157,55 | **+181,30** | +161,55 |
| BMW.DE | long | 116 | 60,18 | 59,40 | **-90,48** | -107,93 |
| MBG.DE | long | 169 | 47,10 | 46,03 | **-181,67** | -201,57 |
| **Summe** | | | | | **-90,85** | **-147,95** |

```
Realized net P&L (29 geschlossene):        -975.60 EUR
Unrealized P&L (3 offene, netto Entry-Kosten): -147.95 EUR
MTM Shadow Equity = 100.000 + (-975.60) + (-147.95) = 98.876,45 EUR
MTM Total Shadow Return = -1.124 %
```
Keine fiktiven Exits erzeugt, kein DB-Schreibzugriff — reine Bewertung mit dem Schlusskurs von
2026-08-14 (letzter Handelstag im Fenster, 2026-08-15 selbst ohne Kursdaten, vermutlich
Wochenende/Feiertagsartefakt am Fensterende).

### 4.3 Phase 3 — Cost Interpretation

```
Gross P&L before costs:  +159.35 EUR
Costs:                   1134.95 EUR
Net P&L after costs:     -975.60 EUR
Costs / gross winning P&L (4918.63):    23.07 %
Costs / gross absolute P&L (9677.91):   11.73 %
Costs / n closed trades (29):           39.14 EUR/Trade

Trades gross positiv, netto negativ (durch Kosten gedreht):  1  (SAP.DE, gross=+11.44, net=-27.94)
Trades gross negativ, netto negativ:                        14
Trades gross positiv, netto positiv:                        14
Trades gross negativ, netto positiv:                         0
(1+14+14 = 29 ✓)
```

**Antwort auf die Kernfrage von Phase 3 (und Punkt 10 des Abschlussberichts): Kosten sind NICHT
nur Zusatzbelastung — sie drehen das GESAMTERGEBNIS des Laufs von positiv (+159,35 EUR brutto) auf
deutlich negativ (-975,60 EUR netto). JA, eindeutig, jetzt aus Rohdaten verifiziert (vorher nur als
unsicher markiert, da die -75,65-EUR-Zahl im 4P-Bericht diese Aussage verunmoeglicht hatte).**

### 4.4 Phase 31 — Performance-Einordnung inkl. Benchmark (kurz, keine neue Strategieoptimierung)

Aus `trading.historical_price_data`, Schlusskurse 2026-04-30 (letzter Handelstag vor Run-Start)
und 2026-08-14 (letzter Handelstag im Fenster):

```
DAX (^GDAXI) Return:            +8.84 %
Equal-Weight 15-Core-Ticker:    +5.66 %
Shadow-Strategie (MTM):         -1.12 %

Excess vs. DAX:            -9.97 Prozentpunkte
Excess vs. Equal-Weight:   -6.79 Prozentpunkte
```
Die Shadow-Strategie underperformt beide Benchmarks in diesem 3,5-Monats-Fenster deutlich — bei
einer stark positiven Marktphase (DAX +8,8%) blieb die Strategie mit nur 32 von 463 moeglichen
Kandidaten praktisch am Rand des Geschehens und produzierte trotzdem ein leicht negatives Ergebnis.
Das ist eine Feststellung, keine Strategieempfehlung (siehe Phase 32 der Spezifikation).

---

## 5. TEIL C/E — DER ZENTRALE BEFUND: SIZING-FORMEL ERKLAERT DIE REALEN ERGEBNISSE NICHT

### 5.1 Methodik

Ich habe die dokumentierte `sizePosition()`-Formel (Abschnitt 2, Zeile-fuer-Zeile aus dem Live-Code
uebernommen) selbst in Node.js nachgebaut und fuer jeden der 463 READY-Kandidaten ausgefuehrt, mit:
- **Echten Geometrie-Inputs** aus `simulation_decision_log` (`entry_reference_price`, `unit_risk`
  — portfolio-unabhaengig, daher fuer isolierten UND stateful Aufruf identisch, kein
  Rekonstruktionsrisiko).
- **Echtem, aus `simulation_shadow_trades` rekonstruiertem Portfolio-Zustand**: fuer jeden Tag D
  wurde die Menge der zu diesem Zeitpunkt "offenen+vorgeschlagenen" Positionen aus den 32 echten
  Shadow-Trades bestimmt (`decision_date < D AND (exit_date IS NULL OR exit_date >= D)`), inkl.
  korrekter Behandlung von Mehrfach-Genehmigungen am selben Tag (sequenzielle Kumulierung in
  `shadowSortKey()`-Reihenfolge, unter Verwendung der ECHTEN `risk_amount`/`position_value` je
  bereits genehmigter Position).
- **Echter, eingefrorener Config** (Abschnitt 2.2).

**Validierung der Methodik:** Am allerersten Tag des Laufs (2026-05-04, garantiert leeres
Portfolio) reproduziert die Nachrechnung EXAKT die beiden real genehmigten Trades (BMW.DE: 105
Stueck, DBK.DE: 308 Stueck) — identisch zu den in `simulation_shadow_trades` gespeicherten
Werten. Die Methodik ist also nachweislich korrekt fuer den Fall, in dem sie ueberpruefbar ist.

### 5.2 Ergebnis: 401 von 427 QUANTITY_TOO_SMALL-Faellen nicht reproduzierbar

```
Reale QUANTITY_TOO_SMALL-Faelle (aus job_a_portfolio_check.blockers):        427
Davon durch meine Nachrechnung BESTAETIGT (Formel liefert ebenfalls Menge<1): 26  (6.1%)
Davon durch meine Nachrechnung NICHT reproduzierbar (Formel liefert Menge>=1, real 20-800 Stueck): 401  (93.9%)

Aufschluesselung der 26 bestaetigten Faelle nach bindendem Constraint:
  REGION_LIMIT:  19
  SECTOR_LIMIT:   7

Aufschluesselung der Nicht-Reproduzierbarkeit nach Monat:
  2026-05: 0 / 93 bestaetigt   (0%)
  2026-06: 19 / 148 bestaetigt (12.8%)
  2026-07: 0 / 123 bestaetigt  (0%)
  2026-08: 7 / 63 bestaetigt   (11.1%)
```

**Konkretes Beispiel (2026-05-05, einen Tag nach dem allerersten, korrekt reproduzierten
Genehmigungstag):** Fuenf READY-Kandidaten (SIE.DE, DBK.DE, SAP.DE, EOAN.DE, VOW3.DE) — alle real
mit `QUANTITY_TOO_SMALL` abgelehnt. Der bis dahin einzige Portfolio-Inhalt: BMW.DE (Risiko 210 EUR,
Positionswert 7.982 EUR) und DBK.DE (Risiko 385 EUR, Positionswert 7.993 EUR) — zusammen nur
595 EUR von 6.000 EUR Gesamtrisikobudget, 15.975 EUR von 60.000 EUR Regionsbudget. Mit diesen
Zahlen und der dokumentierten Formel ergeben sich fuer alle fuenf Kandidaten Stueckzahlen zwischen
30 und 435 (SINGLE_POSITION_LIMIT- bzw. SECTOR_LIMIT-gebunden) — **klar handelbar, nicht
QUANTITY_TOO_SMALL**. Die Datenbank sagt trotzdem QUANTITY_TOO_SMALL fuer alle fuenf.

### 5.3 Was ich als Erklaerung AUSGESCHLOSSEN habe (mit Beleg)

- **Veralteter/falscher Code:** Live-Node-Code frisch von der Instanz gezogen und byte-identisch
  mit der zu Sitzungsbeginn gelesenen Kopie (`diff` = leer). Ausgeschlossen.
- **Config-Drift waehrend der Laufzeit:** `config_snapshot_json` ist nachweislich eingefroren
  und wird fuer JEDEN Tag des Laufs unveraendert wiederverwendet (Code-Kommentar + eigene
  Verifikation der `_max_*`-Felder in "Baue Run-Kontext"). Ausgeschlossen.
- **Doppelte/duplizierte DB-Zeilen:** `count(*) = count(DISTINCT shadow_trade_id) = count(DISTINCT id) = 32`.
  Ausgeschlossen.
- **String/Number-Typkonvertierungsfehler beim DB-Reload:** `mapShadowTradeRowFromDb()` wrapped
  `risk_amount`/`position_value` explizit in `Number(...)`. Ausgeschlossen (durch Code-Lektuere,
  nicht durch Laufzeit-Instrumentierung).
- **Eigene Rekonstruktionslogik falsch:** durch den Tag-1-Validierungstest (5.1) widerlegt — meine
  Methodik reproduziert den EINEN ueberpruefbaren Fall exakt richtig.
- **Sektor-/ticker-/strategie-spezifischer Effekt:** die reale QUANTITY_TOO_SMALL-Rate ist
  **bemerkenswert gleichfoermig** ueber alle Sektoren (87,5%-96,9%), alle 15 Ticker und beide
  Hauptstrategien (92,0% mean_reversion, 92,1% trend_following) verteilt — kein Muster, das auf
  eine echte, differenzierte Kapazitaetsbindung (die zwangslaeufig sektor-/ticker-abhaengige
  Varianz erzeugen wuerde) hindeutet. Das spricht gegen eine "echte" Portfolio-Kapazitaets-
  Erklaerung und fuer einen systemischen, nicht positionsabhaengigen Effekt.

### 5.4 Was ich NICHT abschliessend klaeren konnte (ehrlich benannt, nicht spekulativ als Tatsache verkauft)

Ich konnte den **exakten Mechanismus** nicht identifizieren. Zwei Kandidaten-Hypothesen, KEINE davon
bewiesen:

1. **Race Condition durch Paket-Nebenlaeufigkeit:** `SIMULATION_DEFAULT_PACKAGE_SIZE=1` bedeutet,
   dass jeder Simulationstag als **eigene n8n-Ausfuehrung** laeuft, getriggert per 30-Sekunden-
   Schedule mit `FOR UPDATE SKIP LOCKED`-Paketclaiming. Wenn eine Tagesausfuehrung laenger als
   30 Sekunden braeuchte, koennten mehrere Tage nebenlaeufig laufen und sich beim
   Shadow-State-Reload/-Schreiben gegenseitig stoeren — dies wuerde jedoch typischerweise
   erwarten lassen, dass die finale, persistierte `simulation_shadow_trades`-Tabelle
   Inkonsistenzen zeigt (tut sie nicht: 0 State Violations laut Nutzerbericht, von mir nicht
   selbst nachgeprueft) und wuerde eher unregelmaessige, nicht derart gleichmaessige Effekte
   erwarten lassen.
2. **Ein nicht identifizierter, zusaetzlicher State-Beitrag**, der die Kapazitaet zur
   AUSFUEHRUNGSZEIT sichtbar reduziert hat, aber nirgends in der finalen, persistierten Tabelle
   sichtbar ist (z.B. ein temporaerer Wert, der spaeter wieder korrigiert wurde, ohne Spur zu
   hinterlassen).

**Ich habe keine dieser beiden Hypothesen verifiziert.** Ich benenne sie nur, um zu zeigen, dass
ich nach einer Erklaerung gesucht, aber keine gefunden habe, die zu den Daten passt — nicht als
Schluss der Analyse. **Weitere Diagnose wuerde Instrumentierung erfordern, die aktuell nicht
existiert** (siehe Empfehlung, Punkt 50).

### 5.5 Einordnung nach der Klassifikation der Nutzer-Spezifikation (Phase 24)

Von den 427 QUANTITY_TOO_SMALL-Faellen:
- **B. PORTFOLIO_CAPACITY_EXHAUSTED** (durch dokumentierte Formel + echten Zustand
  nachvollziehbar): **26 (6,1%)**
- **E. IMPLEMENTATION_DEFECT / nicht rekonstruierbarer Effekt** (Formel + echter Zustand sagen
  "handelbar", DB sagt "QUANTITY_TOO_SMALL", Mechanismus nicht identifiziert): **401 (93,9%)**
- A/C/D/OTHER: 0 (durch die vorstehende Analyse nicht separat als dominant identifizierbar)

**Summe: 26 + 401 = 427 ✓**

Das ist NICHT "A. bewusstes korrektes Portfolio-Capacity-Verhalten" (die urspruengliche Frage aus
dem Auftrag) — die weit ueberwiegende Mehrheit der Faelle ist mit der bekannten, dokumentierten
Logik **nicht** erklaerbar. Es ist auch nicht klar als "F. Einheiten-/Berechnungsfehler" oder
"G. falscher Portfolio-State" beweisbar — beides sind plausible Kandidaten fuer die 401 Faelle,
aber ohne Nachweis des Mechanismus bleibt es bei "E, nicht naeher spezifiziert".

---

## 6. PHASE 26 — Portfolio-Limit-Praeemption (weiterhin code-bewiesen, unveraendert gueltig)

*(Aus dem ersten Sitzungsteil, durch Live-Daten NICHT veraendert, da rein strukturell.)*

`checkShadowPortfolioLimits()` prueft TOTAL_RISK/SECTOR/REGION/SINGLE_POSITION **nach**
`sizePosition()`, gegen die BEREITS geclampte Position — diese vier Limits koennen dort praktisch
nie mehr verletzt werden, weil `sizePosition()` sie schon vorher als Stueckzahl-Obergrenze
verwendet hat. Live bestaetigt: **kein einziger** der 431 Nicht-Genehmigungen zeigt einen der
Blocker `SECTOR_LIMIT`/`REGION_LIMIT`/`TOTAL_RISK_LIMIT`/`SINGLE_POSITION_LIMIT` als eigenstaendigen
Portfolio-Check-Blocker (blockers-Feld) — nur `QUANTITY_TOO_SMALL` (aus dem SIZING-Veto, 427x),
`RRR_TOO_LOW` (3x) und `CORRELATION_LIMIT` (1x, der einzige "echte" Portfolio-Check-Blocker, da
Korrelation nicht in `sizePosition()` vorweggenommen wird). **Antwort auf Punkt 43: JA, bestaetigt,
jetzt auch live verifiziert (nicht nur code-bewiesen).**

---

## 7. DESKRIPTIVE BEFUNDE ZU DEN 32 APPROVED / 427 QTS (rein beobachtend, unabhaengig von Abschnitt 5)

- **Alle 32 Genehmigungen clustern in genau 6 Tagen** (2026-05-04, -05-07, -05-29, -06-18, -07-08,
  -07-30), mit jeweils 2, 4, 6, 8, 5 bzw. 7 gleichzeitigen Genehmigungen — dazwischen lange
  Perioden ganz ohne Genehmigung. Dieses "Burst-Muster" (viele Genehmigungen an einem Tag, dann
  tagelang keine) ist typisch fuer ein hartes, budget-basiertes Kapazitaetslimit, das nach jedem
  "Nachschub" (Positionsschluss) kurz Platz macht und dann wieder komplett zulaeuft — das MUSTER
  selbst passt zur Kapazitaets-Hypothese, auch wenn die GENAUE Formel-Nachrechnung sie fuer die
  meisten Einzelfaelle nicht bestaetigt (Abschnitt 5). Ein Interpretationsangebot, keine
  Aufloesung: entweder ist die reale bindende Formel enger/anders als dokumentiert, oder das
  Burst-Muster hat eine andere Ursache, die zufaellig aehnlich aussieht.
- **Naeherungsweise gleichverteilte QTS-Rate** ueber alle Sektoren (87,5-96,9%), Ticker und
  Strategien — spricht GEGEN eine differenzierte, sektor-/ticker-spezifische Erklaerung
  (Punkt 48: NICHT material) und FUER einen globalen/systemischen Effekt.
- **Aktienpreis nicht material** (Punkt 45): Median-Einstiegspreis der QTS-Faelle (56,86 EUR) liegt
  sogar unter dem der genehmigten Faelle (60,18 EUR) — kein Zusammenhang mit hohem Aktienpreis.
- **Strategie nicht material** (Punkt 47): QTS-Rate praktisch identisch zwischen trend_following
  (92,1%) und mean_reversion (92,0%).
- **Region nicht differenzierend** (alle 15 Ticker sind Region "Europa" — 100% der QTS-Faelle
  sind "Europa", aber das ist tautologisch, keine Aussage).
- **Die 3 RRR_TOO_LOW-Faelle** liegen alle hauchduenn unter der Schwelle 1,5 (1,4999996, 1,4898,
  1,4955) — plausibel, unauffaellig, kein Hinweis auf einen Fehler.
- **Der 1 CORRELATION_LIMIT-Fall** (BMW.DE, 2026-05-07): sizing selbst erfolgreich (97 Stueck,
  SINGLE_POSITION_LIMIT-gebunden), aber am selben Tag wurde bereits VOW3.DE genehmigt (ebenfalls
  Auto-Sektor) — eine plausible, nachvollziehbare Korrelationsblockade.

---

## 8. WF97-STATUS (Abschluss, fresh verifiziert)

```
Vor Sitzungsende (Live-GET):
  active: false
  Node "Diag Webhook": disabled: true, path: diag-repair
  Node "SQL Guard (SELECT only)": vorhanden, disabled: false (bleibt im Workflow, harmlos da
    Webhook-Node selbst deaktiviert ist -- wie vom Koordinator vorgegeben, NICHT entfernt)

curl -X POST http://172.16.1.6:5678/webhook/diag-repair -d '{"query":"SELECT 1"}'
  -> HTTP 404
```

**Bestaetigt: WF97 ist inaktiv, der Webhook-Node ist deaktiviert, der Webhook-Pfad liefert 404.**
Dies wurde NICHT nur aus der PUT/POST-Antwort uebernommen, sondern durch einen SEPARATEN,
anschliessenden GET + curl-Aufruf verifiziert (Projekt-Praxis: "PUT 200 ist kein Beweis").

---

## ABSCHLUSSBERICHT (50 PUNKTE)

### TEIL A — ACCOUNTING (vollstaendig verifiziert)

1. **Correct Gross P&L:** **+159,35 EUR** (aus den 29 geschlossenen Shadow-Trades direkt
   nachgerechnet: SUM(gross_pnl)). Der im 4P-Bericht genannte Wert (-75,65 EUR) war falsch.
2. **Correct Costs:** **1.134,95 EUR** (= SUM(gross_pnl) - SUM(net_pnl), aus Rohdaten). Deckt
   sich mit dem im 4P-Bericht genannten Wert.
3. **Correct Net P&L:** **-975,60 EUR** (= SUM(net_pnl) aus den 29 Trades). Deckt sich mit dem
   4P-Bericht.
4. **Accounting Identity Diff:** SUM(gross_pnl) - Costs - SUM(net_pnl) = **0,00 EUR** (exakte
   Identitaet erfuellt, jetzt mit echten Zahlen statt Berichtszahlen). Die urspruengliche
   Diskrepanz (235,00 EUR zwischen gemeldetem -75,65 und tatsaechlichem +159,35) ist damit
   vollstaendig aufgeklaert: der gemeldete Wert war schlicht falsch, keine tiefere Rechenlogik
   dahinter identifizierbar (das Berichts-Erzeugungsskript, das -75,65 produziert hat, wurde
   nicht gefunden — es existiert nicht als Datei im Repo, vermutlich Ad-hoc-Auswertung einer
   fruehren Sitzung).
5. **Unrealized P&L Open Positions:** ADS.DE +181,30 EUR (brutto) / +161,55 EUR (netto
   Entry-Kosten), BMW.DE -90,48 / -107,93 EUR, MBG.DE -181,67 / -201,57 EUR. Summe brutto:
   **-90,85 EUR**, netto Entry-Kosten: **-147,95 EUR**. Bewertung zum letzten verfuegbaren Kurs
   im Fenster (2026-08-14).
6. **MTM Final Equity:** 100.000 + (-975,60) + (-147,95) = **98.876,45 EUR**.
7. **MTM Return:** **-1,124 %**.
8. **Excess vs. DAX:** DAX-Return 2026-04-30→08-14 = +8,84 % → Excess = **-9,97 Prozentpunkte**.
9. **Excess vs. Equal Weight (15 Core-Ticker):** Equal-Weight-Return = +5,66 % → Excess =
   **-6,79 Prozentpunkte**.
10. **Costs flipped total result positive→negative:** **JA**, eindeutig und jetzt aus Rohdaten
    bestaetigt: Gross P&L +159,35 EUR (positiv) → Net P&L -975,60 EUR (negativ) durch 1.134,95 EUR
    Kosten.

### TEIL B — SIZING SOURCE (unveraendert aus Code-Analyse, weiterhin vollstaendig)

11. **Exact QUANTITY_TOO_SMALL condition:** `final_quantity = max(0, floor(min(5 Kandidaten))) < 1`
    (aequivalent zu `final_quantity == 0`). Keine Wert- oder Risiko-Untergrenze, nur Stueckzahl.
12. **Raw sizing formula:** `risk_based_quantity = floor(mpv * max_risk_per_trade_pct/100 /
    unit_risk)`, `unit_risk = abs(entry_price - stop_price)`.
13. **Clamp order:** Kein sequenzielles Kaskadieren — striktes Minimum ueber RAW_RISK_SIZE,
    SINGLE_POSITION_LIMIT, TOTAL_RISK_LIMIT, SECTOR_LIMIT, REGION_LIMIT. Danach sequenziell:
    UNECONOMICAL_AFTER_COSTS-Veto, dann RRR_TOO_LOW-Veto.
14. **Minimum quantity/value rule:** `MIN_TRADABLE_QUANTITY = 1` (hartkodiert). Kein
    Mindest-Positionswert, kein Mindest-Risikobetrag als eigene Regel.
15. **Single-position cap:** `floor(mpv * 8,0%/100 / entry_price)` — **8,0% bestaetigt als
    echter, im Run eingefrorener Wert** (nicht nur Seed-Default).
16. **Risk cap (Total Risk):** `floor(max(0, mpv*6,0%/100 - sum(open.risk_amount)) / unit_risk)`
    — 6,0% bestaetigt als echter Wert.
17. **Sector cap:** analog, 15,0% bestaetigt als echter Wert.
18. **Region cap:** analog, 60,0% bestaetigt als echter Wert.
19. **Currency cap:** nicht Teil von `sizePosition()`, erst im Portfolio-Check, nur falls
    `currency != 'EUR'` — bei diesem Run irrelevant (alle 15 Ticker EUR). 30,0% bestaetigt.
20. **Directional cap:** ebenfalls nicht Teil von `sizePosition()`. 40,0% bestaetigt.

### TEIL C — QTS ROOT CAUSE (jetzt aus Rohdaten, mit zentralem Negativbefund)

21. **QTS total:** **427** — jetzt live aus `simulation_decision_log` nachgezaehlt (nicht nur
    uebernommen): exakt bestaetigt.
22. **RAW_SIZE_TOO_SMALL:** Count/%: **0 von 427 nachweisbar** (die dokumentierte Formel liefert
    fuer keinen der 427 Faelle RAW_RISK_SIZE als bindenden, quantitaets-auf-0-druckenden
    Constraint — der isolierte Diagnosewert `quantity_by_risk` ist in praktisch allen Faellen
    >>1).
23. **PORTFOLIO_CAPACITY_EXHAUSTED:** Count/%: **26 / 427 (6,1%)** — durch die dokumentierte
    Formel + echten rekonstruierten Portfolio-Zustand nachvollziehbar (19x REGION_LIMIT, 7x
    SECTOR_LIMIT bindend).
24. **POLICY_CAP_STRUCTURAL:** Count/%: **0 / 427 nachweisbar** als eigene Kategorie (die
    dokumentierten Caps ergeben bei leerem Portfolio keine Nullwerte fuer dieses Ticker-Universum).
25. **ROUNDING/FLOOR:** Count/%: **0 / 427 nachweisbar als alleinige Ursache** — in den 26
    reproduzierbaren Faellen liegt die Ursache klar an der Kapazitaetsgrenze selbst (Budget
    vollstaendig aufgebraucht), nicht an einem Rundungsartefakt knapp unter 1.
26. **IMPLEMENTATION_DEFECT / nicht rekonstruierbar:** Count/%: **401 / 427 (93,9%)** — die
    dokumentierte Formel + der aus den echten Trades rekonstruierte Portfolio-Zustand sagen
    "handelbar" (Stueckzahl typischerweise 20-800), die Datenbank sagt QUANTITY_TOO_SMALL.
    Mechanismus nicht identifiziert (siehe Abschnitt 5.4) — daher hier konservativ als
    "nicht rekonstruierbar/vermuteter Defekt" statt als bewiesener Bug klassifiziert.
27. **OTHER:** 0.
28. **Summe:** 0+26+0+0+401+0 = **427 ✓**
29. **Primary binding constraints (Tabelle):** Fuer die 26 reproduzierbaren Faelle: REGION_LIMIT
    (19), SECTOR_LIMIT (7). Fuer die restlichen 401 kann kein primary constraint aus der
    dokumentierten Formel benannt werden, da die Formel selbst kein QUANTITY_TOO_SMALL vorhersagt.
30. **Secondary binding constraints (Tabelle):** Unter den 26 reproduzierbaren Faellen wurde in
    keinem Fall mehr als ein Constraint gleichzeitig auf <1 gedrueckt (0 Mehrfachbindungen) —
    jeweils klar REGION oder SECTOR allein bindend.

### TEIL D — STATE / ZEIT

31. **QTS with empty portfolio — Count:** **0** von 427 — kein READY-Kandidat existierte an einem
    Tag mit komplett leerem Portfolio (der Lauf beginnt am 2026-05-04 mit sofortigen
    Genehmigungen; vorher gab es keine READY-Kandidaten). Der urspruenglich in der Spezifikation
    vorgesehene "kritische Test" (Phase 14) konnte damit fuer dieses Ticker-Universum nicht
    durchgefuehrt werden, weil es nie einen Tag mit READY-Kandidat UND leerem Portfolio gab.
32. **QTS with non-empty portfolio — Count:** **427** (alle).
33. **Capacity release after close — korrekt JA/NEIN:** Konnte nicht abschliessend an einem
    Beispiel durchgespielt werden, da die genaue Zustands-Chronologie (siehe Abschnitt 5) ohnehin
    nicht mit der Formel uebereinstimmt — eine Aussage ueber "korrekte Freigabe" waere auf Basis
    eines Modells getroffen, das die Realitaet nachweislich nicht vorhersagt. **Nicht
    beantwortbar mit der vorhandenen Datengrundlage.**
34. **proposed counted:** **JA** — code-bestaetigt (`shadowState.open.concat(shadowState.proposed)`).
35. **open counted:** **JA** — code-bestaetigt.
36. **closed excluded:** **JA** — code-bestaetigt (nicht Teil der Concat-Liste).

### TEIL E — PARITY

37. **Engine crosschecks — Count:** **427** (alle realen QUANTITY_TOO_SMALL-Faelle wurden gegen
    die dokumentierte Formel + echten Zustand nachgerechnet — mehr als die urspruenglich
    vorgesehenen 20 repraesentativen Faelle, weil vollstaendige Daten verfuegbar waren).
38. **Max numeric diff:** Nicht als einzelne Zahl sinnvoll (das ist kein Rundungsfehler-Diff,
    sondern eine binaere Diskrepanz "handelbar vs. nicht handelbar" mit Stueckzahl-Differenzen
    zwischen 20 und ueber 800 Stueck je nach Kandidat).
39. **Shadow/Engine parity — PASS/FAIL:** **FAIL.** 401 von 427 (93,9%) nachgerechneten Faellen
    stimmen nicht mit der Datenbank ueberein.
40. **Implementation bug found:** **JA (mit Einschraenkung)** — ein reproduzierbarer,
    quantitativ hart belegter Widerspruch zwischen dokumentierter Formel und beobachtetem
    Ergebnis liegt vor. Der GENAUE Mechanismus (Code-Bug vs. Race Condition vs. anderer,
    nicht identifizierter Effekt) ist **nicht** abschliessend lokalisiert. Gemaess der
    Spezifikation ("STOPP... dann haben wir einen Parity-Bug, keine Policy-Diagnose") wird dies
    hier als harter Befund berichtet, nicht als aufgeloeste Policy-Frage behandelt.

### TEIL F — DIAGNOSE

41. **Dominant root cause:** **Nicht abschliessend identifizierter Implementierungs-/
    Zustandsfehler** (93,9% der Faelle), NICHT Portfolio-Capacity-Policy im eigentlichen,
    beabsichtigten Sinn (nur 6,1% sauber dadurch erklaerbar).
42. **Is QTS intended policy behavior?** **NEIN, ueberwiegend** — fuer 401 von 427 Faellen sagt
    die dokumentierte, beabsichtigte Formel selbst ein anderes (handelbares) Ergebnis voraus.
    Fuer die restlichen 26 Faelle: JA, echtes, beabsichtigtes Kapazitaetsverhalten.
43. **Are portfolio-limit zero counts misleading due to pre-clamp?** **JA**, weiterhin
    code-bewiesen UND jetzt live bestaetigt (kein einziger SECTOR_LIMIT/REGION_LIMIT/
    TOTAL_RISK_LIMIT/SINGLE_POSITION_LIMIT-Blocker im separaten Portfolio-Check ueber den
    gesamten Lauf).
44. **Is rounding material?** **NEIN** — in keinem der 26 reproduzierbaren Faelle war es ein
    knappes Rundungsproblem; die Ursache war jeweils ein vollstaendig erschoepftes Budget.
45. **Is stock absolute price material?** **NEIN** — Median-Einstiegspreis der QTS-Faelle liegt
    sogar unter dem der Approved-Faelle.
46. **Is stop-distance material?** Nicht als eigenstaendiger Effekt identifiziert; RAW_RISK_SIZE
    war in keinem der 427 Faelle der bindende, formel-bestaetigte Constraint.
47. **Is strategy-specific effect material?** **NEIN** — QTS-Rate praktisch identisch zwischen
    trend_following (92,1%) und mean_reversion (92,0%).
48. **Is sector/region concentration material?** **NEIN als Haupterklaerung** — QTS-Rate ist
    ueber alle Sektoren nahezu gleichfoermig (87,5-96,9%), was gegen eine primaer
    sektor-getriebene Erklaerung spricht (waere bei echter Sektor-Kapazitaetsbindung deutlich
    ungleichmaessiger).
49. **Biggest actual bottleneck:** Die **fehlende Erklaerbarkeit** von 93,9% der
    QUANTITY_TOO_SMALL-Faelle durch die eigene, dokumentierte Sizing-Formel — ein
    Beobachtbarkeits-/Korrektheitsproblem, das jede weitere Policy-Diskussion (Sektorlimits,
    Risikolimits etc.) verfrueht macht, solange der Mechanismus nicht gefunden ist.
50. **ONE recommended next step:** **Keine Parameteraenderung.** Stattdessen: `sizing.binding_limit`
    (und idealerweise die vollen Zwischenwerte `remaining_portfolio_quantity`/
    `remaining_sector_quantity`/`remaining_region_quantity`) aus dem STATEFUL Job-A-Sizing-Aufruf
    zusaetzlich in `diagnostics_json.job_a_portfolio_check` persistieren (heute nur `approved`/
    `blockers` — eine kleine, rein additive Code-Aenderung ohne Verhaltensaenderung), und dann
    EINEN NEUEN, kurzen Replay-Lauf (nicht Run 42 erneut auswerten, sondern einen frischen Lauf
    MIT dieser zusaetzlichen Instrumentierung) fahren. Erst mit `binding_limit` UND den
    tatsaechlichen Zwischenwerten pro Kandidat laesst sich der in Abschnitt 5 gefundene
    93,9%-Widerspruch tatsaechlich lokalisieren, statt ihn von aussen nachzurechnen und nur seine
    Existenz zu beweisen.

---

## ANHANG A: Live-Query-Ergebnisse (Rohwerte)

Alle in diesem Bericht verwendeten Rohdaten wurden per SELECT-only-Webhook (Abschnitt 1) direkt
gegen die Produktions-DB abgefragt, mit `SELECT json_agg(t) AS result FROM (...) t`-Wrapping. Die
wichtigsten Query-Grundformen (Platzhalter fuer echte, bereits ausgefuehrte Abfragen):

```sql
SELECT id, name, status, progress_percent, error_count, started_at, finished_at,
       initial_capital, start_date, end_date, news_enabled, run_type, strategy_filter,
       instrument_selection_json, config_snapshot_json
FROM trading.backtest_runs WHERE id = 42;

SELECT id, simulated_date, ticker, strategy, direction, decision, reason,
       theoretical_quantity, actual_quantity, position_value, entry_reference_price, stop_price,
       target_price, reward_risk_ratio, risk_amount, unit_risk, quantity_by_risk, quantity_by_value,
       limiting_factor, decision_stage, blockers_json, diagnostics_json
FROM trading.simulation_decision_log WHERE simulation_run_id = 42 ORDER BY simulated_date, ticker;
-- 649 Zeilen

SELECT id, shadow_trade_id, ticker, strategy, direction, decision_date, status, quantity,
       zone_low, zone_high, entry_price, entry_date, stop_price, target_price, time_stop_at,
       thesis_expires_at, risk_amount, position_value, sector, region, currency, entry_fee,
       entry_slippage, exit_price, exit_date, exit_reason, gross_pnl, net_pnl, return_pct,
       r_multiple, data_error_count, ambiguous_execution, policy_mode
FROM trading.simulation_shadow_trades WHERE simulation_run_id = 42 ORDER BY decision_date, ticker;
-- 32 Zeilen

SELECT DISTINCT ON (ticker) ticker, trading_date, close FROM trading.historical_price_data
WHERE ticker IN ('ADS.DE','BMW.DE','MBG.DE') AND trading_date <= '2026-08-15'
ORDER BY ticker, trading_date DESC;

SELECT ticker, trading_date, close FROM trading.historical_price_data
WHERE ticker IN ('^GDAXI', <15 Core-Ticker>) AND trading_date IN ('2026-04-30','2026-08-14');
```

## ANHANG B: Rekonstruktions-/Vergleichsskript (Kernlogik, Node.js)

Kernstueck der in Abschnitt 5 verwendeten Nachrechnung (vollstaendig: siehe Sitzungs-Scratchpad,
nicht Teil des Repos):

```js
function sizeClampOnly(entryPrice, unitRisk, sektor, region, openPositions) {
  const theoreticalRiskAmount = 100000 * (1 / 100);
  const riskBasedQuantity = Math.floor(theoreticalRiskAmount / unitRisk);
  const maxSinglePositionQuantity = Math.floor((100000 * (8 / 100)) / entryPrice);
  const currentTotalRisk = openPositions.reduce((s, p) => s + p.risk_amount, 0);
  const remainingPortfolioQuantity = Math.floor(Math.max(0, 100000*(6/100) - currentTotalRisk) / unitRisk);
  const currentSectorValue = openPositions.filter(p => p.sector === sektor).reduce((s, p) => s + p.position_value, 0);
  const remainingSectorQuantity = Math.floor(Math.max(0, 100000*(15/100) - currentSectorValue) / entryPrice);
  const currentRegionValue = openPositions.filter(p => p.region === region).reduce((s, p) => s + p.position_value, 0);
  const remainingRegionQuantity = Math.floor(Math.max(0, 100000*(60/100) - currentRegionValue) / entryPrice);
  const candidates = [
    { quantity: riskBasedQuantity, reason: 'RAW_RISK_SIZE' },
    { quantity: maxSinglePositionQuantity, reason: 'SINGLE_POSITION_LIMIT' },
    { quantity: remainingPortfolioQuantity, reason: 'TOTAL_RISK_LIMIT' },
    { quantity: remainingSectorQuantity, reason: 'SECTOR_LIMIT' },
    { quantity: remainingRegionQuantity, reason: 'REGION_LIMIT' },
  ];
  let binding = candidates[0];
  for (const c of candidates) if (c.quantity < binding.quantity) binding = c;
  return { finalQuantity: Math.max(0, Math.floor(binding.quantity)), bindingReason: binding.reason };
}
// state = trades.filter(t => t.decision_date < day && (t.exit_date === null || t.exit_date >= day))
```
