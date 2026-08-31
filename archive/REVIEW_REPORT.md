# REVIEW_REPORT.md

Stand: 2026-08-18/19. Externe Analyse-Hinweise (12 Punkte + Kategorien A-J) gegen den tatsächlichen
Live-/Repo-Code verifiziert. Methodik: Code direkt gelesen (n8n-Workflow-JSON, `jsCode`-Inhalte,
SQL-Queries), keine Annahmen aus Kommentaren oder Doku ungeprüft übernommen.

**Update 2026-08-19 (Runde 3):** Der ursprünglich zurückgestellte vollständige Sweep über alle
33 Finanz-Workflows (Kategorien A-J: Look-Ahead, Survivorship, Data Leakage, Idempotenz, Transaktionen,
Statusautomaten, `onError:continueRegularOutput`+falscher Success, unbounded `SELECT *`, große
`$input.all()`/Merge-Nodes) wurde jetzt durchgeführt — siehe Abschnitt "Runde 3 — Systematischer Sweep"
am Ende dieses Dokuments für Methodik, Ergebnisse und neue Befunde (WF06-1, WF07-1, P17-7, sowie eine
korrigierte, vertiefte Einschätzung zu NEU-09-VERSION).

---

# Gesamturteil

Das System ist an mehreren Stellen fachlich solide gebaut (Claim/Lease-Muster, Idempotenz-Schutz bei
Lernvorschlägen, durchdachte Fehlerbehandlung bei Datenlücken). Es gibt aber **zwei bestätigte P0-Befunde**,
die die Aussagekraft der historischen Simulation direkt verfälschen (Short-Cash-Accounting,
Trailing-Stop-Look-Ahead), sowie mehrere bestätigte P1-Befunde (Simulationsworker ohne Automatik,
Kapitalbasis-Verwechslung, offener SQL-Diagnose-Webhook). Mehrere Verdachtsfälle haben sich NICHT
bestätigt oder waren bereits als bekannte, bewusste Lücken im Code selbst dokumentiert.

---

# Bestätigte Probleme

### ID: P17-1 — Short-Cash-Accounting bei Exit fehlerhaft
**Priorität:** P0
**Workflow:** 17 – Historische Simulation
**Node:** "Verarbeite Tage-Paket" (Exit-Block, Zeile ~511-525 im Node-Code)

**Problem:** Beim Schließen einer Position wird unabhängig von der Richtung
`cash += (exitNotional - exitSpreadFee - financingCost)` gerechnet, wobei `exitNotional = exitPrice * quantity`.
Diese Formel ist nur für Long korrekt (Aktien "zurückverkaufen"). Für Short (das System modelliert
Mini-Futures/CFD-artig, kein echter Aktienbesitz) müsste der Cash-Zufluss beim Exit
`positionValue + grossPnl` sein (= `2*positionValue - exitNotional`) — exakt die Formel, die für die
**tägliche Bewertung offener Short-Positionen bereits korrekt verwendet wird** (Zeile 596:
`markValue = (2 * entryPrice - currentClose) * quantity`).

**Beweis aus Code:**
```js
// Entry (Zeile 459), identisch für long/short:
cash -= (positionValue + fee + slippage);

// Exit (Zeile 512-525):
const grossPnl = pos.direction === 'long'
  ? (exitCheck.price - (pos.position_value / pos.quantity)) * pos.quantity
  : ((pos.position_value / pos.quantity) - exitCheck.price) * pos.quantity;  // korrekt richtungsabhängig
const exitNotional = exitCheck.price * pos.quantity;
...
cash += (exitNotional - exitSpreadFee - financingCost);  // NICHT richtungsabhängig — Bug
```

**Durchgerechnetes Beispiel (Short, Entry 100, 10 Stück, Exit 80, Gewinn erwartet +200):**
- Entry: `cash -= 1000`
- Exit: `cash += 800` (statt korrekt `+1200`)
- Netto-Cash-Effekt: **-200**, obwohl `grossPnl` korrekt `+200` zeigt.
- Unmittelbar vor dem Exit zeigte `total_equity` (via der korrekten Tages-Markwert-Formel) bereits
  `startkapital + 200`. Direkt nach dem Exit fällt `total_equity` auf `startkapital - 200` — ein
  künstlicher Sprung von 400, der real nie stattgefunden hat.

**Fachliche Auswirkung:** Jeder geschlossene Short-Trade in JEDER bisherigen und künftigen historischen
Simulation verfälscht `cash`/`total_equity` um `2 × grossPnl` in die falsche Richtung. Drawdown-Berechnung,
Equity-Kurve und alle daraus abgeleiteten Kennzahlen sind für Strategien mit Short-Trades nicht belastbar.
`grossPnl`/`net_pnl` selbst (in `simulation_trades`) sind korrekt — nur die Cash-Fortschreibung ist betroffen.

**Technische Auswirkung:** Equity-Kurve zeigt bei jedem Short-Exit einen Strukturbruch, unabhängig von
Gewinn/Verlust der Einzelposition.

**Änderung erforderlich:** ja

**Geplante Reparatur:** Exit-Cash-Formel richtungsabhängig machen:
```js
const cashDelta = pos.direction === 'long'
  ? (exitNotional - exitSpreadFee - financingCost)
  : (2 * pos.position_value - exitNotional - exitSpreadFee - financingCost);
cash += cashDelta;
```
`grossPnl`/`net_pnl`-Berechnung bleibt unverändert (bereits korrekt).

---

### ID: P17-6 — Trailing-Stop-Look-Ahead innerhalb derselben Tageskerze
**Priorität:** P0
**Workflow:** 17 – Historische Simulation
**Node:** "Verarbeite Tage-Paket" (Exit-Block, Zeile ~498-510)

**Problem:** Der Trailing-Stop wird für den aktuellen Tag anhand von `bar.high`/`bar.low` DESSELBEN Tages
aktualisiert und **danach** wird mit demselben `bar` geprüft, ob Stop/Ziel getroffen wurden.

**Beweis aus Code:**
```js
if (pos.direction === 'long') {
  if (bar.high > pos.extreme_price) pos.extreme_price = bar.high;   // nutzt Tages-High
  const trailStop = pos.extreme_price - pos.trail_distance;
  if (trailStop > pos.stop_price) pos.stop_price = trailStop;        // Stop wird SOFORT nachgezogen
} else { /* analog fürs Low bei Short */ }
const exitCheck = checkExit(pos, bar, day, ambiguousBarPolicyCode, oppositeSignal); // prüft denselben Tag
```

**Konkretes Beispiel (wie im Audit-Hinweis):** Open 100, Low 94, High 110, Close 108, alter Stop 95,
`trail_distance` z.B. 10. Der Code aktualisiert `extreme_price` auf 110 (Tages-High), zieht den Stop auf
100 nach, und prüft DANACH mit demselben Balken, ob Low 94 den (jetzt neuen) Stop 100 unterschritten hat.
Das wird als Exit gewertet — obwohl in der Realität, falls das Low VOR dem High eintrat, der ursprüngliche
Stop von 95 nie berührt wurde und die Position den Tag überlebt hätte.

**Fachliche Auswirkung:** Systematischer Bias zugunsten häufigerer/früherer Stop-Auslösung an Tagen mit
großer Handelsspanne — verfälscht Exit-Zeitpunkt, Haltedauer, realisierten PnL und alle abgeleiteten
Kennzahlen. Betrifft Long und Short gleichermaßen (spiegelbildlich).

**Technische Auswirkung:** Keine — reiner Logikfehler, keine Absturzgefahr.

**Änderung erforderlich:** ja

**Geplante Reparatur:** Den aus der aktuellen Kerze neu berechneten Trailing-Stop **erst für den
nächsten Tag wirksam werden lassen**. Konkret: `checkExit` muss mit dem Stop-Wert VOR der
heutigen Nachführung geprüft werden; die Nachführung (extreme_price/stop_price-Update) erfolgt weiterhin
heute, wirkt sich aber erst am nächsten Handelstag auf die Exit-Prüfung aus. Reihenfolge tauschen:
zuerst `checkExit` mit dem alten `pos.stop_price`, danach erst `extreme_price`/`stop_price` nachziehen.

---

### ID: P17-3 — Simulationsworker hat keinen automatischen Fortschritt
**Priorität:** P1
**Workflow:** 17 – Historische Simulation
**Node:** "Manueller Trigger: Simulations-Worker"

**Problem:** Der einzige Eingang in die Worker-Kette (`DB: Naechsten aktiven Lauf finden` → ... →
`Verarbeite Tage-Paket`) ist ein `manualTrigger`. Weder der GET-Webhook (Ansichtsseite) noch der
POST-Webhook (Formular/create_run) verbinden in diese Kette — bestätigt durch vollständige
Connections-Analyse des Workflows.

**Beweis aus Code:** `wf.connections` zeigt exakt eine eingehende Kante in
`DB: Naechsten aktiven Lauf finden`, Quelle `Manueller Trigger: Simulations-Worker`.

**Fachliche Auswirkung:** Eine gestartete Simulation läuft nur voran, wenn jemand wiederholt manuell
"Execute workflow" klickt — bei mehrjährigen Backtests mit hunderten/tausenden Handelstagen praktisch
nicht durchführbar. Erklärt plausibel, warum bisherige Simulationsläufe lange gedauert haben bzw. auf
manuelle Anstöße angewiesen waren.

**Technische Auswirkung:** Kein automatischer Fortschritt, kein Crash-Risiko.

**Änderung erforderlich:** ja

**Geplante Reparatur:** Schedule Trigger (1-2 Min. Intervall) hinzufügen, der in dieselbe Kette wie der
Manual Trigger mündet. Das bestehende Lock-Verfahren (`DB: Lauf-Lock beanspruchen` + `Pruefe
Lock-Ergebnis`, nutzt vermutlich `FOR UPDATE SKIP LOCKED`) übernimmt die Race-Condition-Sicherheit
bereits — muss nur verifiziert werden, dass es wirklich atomar ist (siehe unten, P17-3b).

---

### ID: P17-3b — Lock-Mechanismus des Simulationsworkers noch nicht separat verifiziert
**Priorität:** P2 (Voraussetzung für P17-3-Fix)
**Workflow:** 17
**Node:** "DB: Lauf-Lock beanspruchen"

**Problem:** Bevor ein Schedule Trigger ergänzt wird, muss die tatsächliche SQL hinter "DB: Lauf-Lock
beanspruchen" auf `FOR UPDATE SKIP LOCKED` bzw. eine äquivalente atomare Absicherung geprüft werden,
sonst würden mehrere gleichzeitige Worker-Ticks (nach Hinzufügen des Schedule Triggers) denselben Lauf
doppelt bearbeiten können.

**Änderung erforderlich:** Nur Prüfung, noch keine Änderung — wird vor Umsetzung von P17-3 nachgeholt.

---

### ID: P17-4 — Simulation nutzt globale Kapitalbasis statt eigenem `initial_capital`
**Priorität:** P1
**Workflow:** 17
**Node:** "Baue Run-Kontext"

**Problem:**
```js
_model_portfolio_value: num('MODEL_PORTFOLIO_VALUE', run.initial_capital || 100000),
```
`MODEL_PORTFOLIO_VALUE` (globaler `pipeline_config`-Wert, seit Monaten für Workflow 14 gepflegt und mit
Sicherheit gesetzt) hat Vorrang vor `run.initial_capital`. Der Fallback auf `run.initial_capital`
greift nur, wenn der globale Key fehlt — was er nicht tut.

**Beweis aus Code:** siehe oben, Zeile in "Baue Run-Kontext". `cfg.modelPortfolioValue` wird in
`sizePosition()` (Positionsgrößen-/Risikoberechnung) und `checkHardLimits()`
(Sektor-/Regions-/Richtungslimits) ausschließlich verwendet — `runCtx.initial_capital` fließt NUR in
den Start-Cash-Wert (Zeile 382) ein, nicht in die Risikoregeln.

**Fachliche Auswirkung:** Ein Simulationslauf mit z.B. 25.000€ `initial_capital` wird trotzdem so
dimensioniert, als hätte er die globale `MODEL_PORTFOLIO_VALUE` (vermutlich 100.000€). Positionsgrößen
und Risikolimits sind dadurch NICHT proportional zum deklarierten Kapital des Laufs — genau das in
TEST 11 geforderte Verhalten ist aktuell nicht gegeben.

**Änderung erforderlich:** ja

**Geplante Reparatur:** `_model_portfolio_value: run.initial_capital || num('MODEL_PORTFOLIO_VALUE', 100000)`
— Reihenfolge umkehren, damit der laufspezifische Wert Vorrang hat und der globale Wert nur als
echter Fallback dient.

---

### ID: P17-5 — Mini-Future-Konfigurationswerte werden nie aus der DB geladen
**Priorität:** P2
**Workflow:** 17
**Node:** "DB: Simulations-Konfiguration laden"

**Problem:** Die Query filtert per `WHERE config_key IN (...)` auf eine feste Liste, die
`MINI_FUTURE_LEVERAGE`, `MINI_FUTURE_SPREAD_PCT`, `MINI_FUTURE_FINANCING_PCT_PA` **nicht enthält**.

**Beweis aus Code:** vollständige `IN (...)`-Liste enthält 13 Keys, keiner davon `MINI_FUTURE_*`.
"Baue Run-Kontext" liest diese drei Keys trotzdem per `num('MINI_FUTURE_LEVERAGE', 4)` — da sie nie in
`cfgByKey` landen, greift IMMER der Fallback (4 / 0.4 / 2.5), unabhängig davon, was in
`pipeline_config` tatsächlich konfiguriert sein mag.

**Fachliche Auswirkung:** Aktuell praktisch folgenlos, weil die Fallback-Werte (Hebel 4x, Spread 0,4%,
Finanzierung 2,5% p.a.) laut Notiz vom 04.08. den tatsächlich gewünschten Werten entsprechen — die
Werte sind aber faktisch nicht konfigurierbar, ohne den Code zu ändern.

**Änderung erforderlich:** ja (geringes Risiko, da Fallback ohnehin korrekt)

**Geplante Reparatur:** Die drei Keys zur `IN (...)`-Liste der Query ergänzen.

---

### ID: WF97-1 — Aktiver, unauthentifizierter SQL-Diagnose-Webhook
**Priorität:** P1 (Security)
**Workflow:** 97 – Einmalig – Beliebige Query ausfuehren
**Node:** "Webhook Diagnose (POST)"

**Problem:** `POST /webhook/diagnose-sql`, `active: true`, `disabled: false`, keine erkennbare
Authentifizierung, Antwort gibt alle eingehenden Items (= Query-Ergebnis) zurück.

**Beweis aus Code:** `{"httpMethod":"POST","path":"diagnose-sql","responseMode":"responseNode","options":{}}`
— kein `authentication`-Parameter gesetzt.

**Fachliche Auswirkung:** Wurde am 04.08. bewusst als dauerhafter Diagnose-Zugang eingerichtet (auch von
mir in dieser Session mehrfach ähnlich genutzt) — Komfortgewinn ist real, aber der Endpunkt kann
beliebiges SQL (inkl. UPDATE/DELETE/DROP) mit den vollen Postgres-Credentials der Instanz ausführen,
wenn er erreichbar ist.

**Technische Auswirkung:** Bei LAN-Erreichbarkeit (172.16.1.14:5678) ist das ein vollständiger
Datenbank-Vollzugriff für jeden, der den Endpunkt kennt oder errät.

**Änderung erforderlich:** ja

**Geplante Reparatur:** Webhook-Node deaktivieren (`disabled: true`) oder entfernen. Manueller Trigger
(bereits vorhanden) bleibt für gelegentliche Diagnose-SQLs über die n8n-UI erhalten. Keine
Auth-Lösung bauen, wie im Auftrag gefordert.

---

### ID: WF14-8 — `MAX_DATA_ERROR_RETRIES` wird nicht geladen
**Priorität:** P2
**Workflow:** 14 – Portfolio-Risiko und Paper-Trading
**Node:** "DB: Portfolio-Konfiguration laden (Exec)"

**Problem:** Query lädt nur `DEFAULT_FEES_BPS, DEFAULT_SLIPPAGE_BPS, AMBIGUOUS_BAR_POLICY_CODE`.
`MAX_DATA_ERROR_RETRIES` wird im Code (`CFG.MAX_DATA_ERROR_RETRIES ?? 5`) referenziert, aber nie
aus der DB geladen — Fallback 5 greift immer.

**Fachliche Auswirkung:** Wert faktisch nicht konfigurierbar. Fallback-Wert (5) selbst ist plausibel,
kein akutes Problem.

**Änderung erforderlich:** ja (klein)

**Geplante Reparatur:** Key zur Query ergänzen.

---

### ID: WF08-10 — Vollständige Kursverlaufs-Ladung ohne Datumsbegrenzung
**Priorität:** P2 (nach heutigem Claim/Lease-Fix entschärft, aber weiterhin ineffizient)
**Workflow:** 08 – News-Wirkungsanalyse
**Node:** "DB: Kursverlauf je Ticker laden", "DB: Benchmark-Kursverlauf laden"

**Problem:** Beide Queries laden die komplette Kurshistorie eines Symbols ohne `WHERE trading_date >= ...`.

**Beweis aus Code:**
```sql
SELECT symbol AS ticker, trading_date AS datum, close AS aktueller_kurs
FROM trading.stock_price_history
WHERE symbol = '...' AND valid_to IS NULL
ORDER BY trading_date;
```

**Fachliche Auswirkung:** Die Analyse braucht nur Baseline bis max. D+20 Handelstage. Bei heute bereits
auf max. 500 Zeilen pro Lauf begrenztem Batch (siehe heutige Claim/Lease-Änderung) ist das Risiko einer
erneuten Task-Runner-Überlastung deutlich geringer als vor dem heutigen Fix, aber die Grundineffizienz
bleibt und würde bei wachsender Kurshistorie (mehr Jahre) wieder zunehmen.

**Änderung erforderlich:** ja, aber niedrige Priorität nach dem heutigen Bounded-Workset-Fix

**Geplante Reparatur:** `WHERE trading_date >= (Baseline-Datum - Sicherheitspuffer)` ergänzen. Braucht
das Baseline-Datum aus dem Tracking-Kontext VOR dieser Query — kleine Umstellung der Datenflussreihenfolge,
kein fachlicher Eingriff in die D+1..D+20-Berechnung selbst.

---

### ID: WF10-11 — Unbegrenzte Abfrage aller Empfehlungen
**Priorität:** P2
**Workflow:** 10 – Report- und Prüfagent
**Node:** enthält `SELECT * FROM trading.recommendations ORDER BY id;`

**Problem:** Kein Datums-/Status-Filter, kein LIMIT.

**Fachliche Auswirkung:** Wächst unbegrenzt mit der Zeit. Ob der Agent wirklich die volle Historie
braucht, ist ohne Verständnis von "10"s eigentlicher Prüf-Logik (Was macht der Report-/Prüfagent genau
mit diesen Daten?) noch nicht abschließend beurteilbar — das müsste vor der Reparatur geklärt werden,
um keine für die Prüfung tatsächlich benötigte Historie zu kappen.

**Änderung erforderlich:** ja, aber erst nach Klärung des tatsächlichen Datenbedarfs

**Geplante Reparatur:** noch offen, siehe oben.

---

# Nicht bestätigte Verdachtsfälle

### Punkt 7 — Workflow 14 doppelter Zeitplan
**Ursprünglicher Verdacht:** Workflow 14 hat einen eigenen Schedule Trigger UND wird von "00 –
Tagesabschluss-Orchestrator" aufgerufen.

**Warum nicht bestätigt:** Workflow 14 hat tatsächlich einen aktiven, nicht deaktivierten Schedule
Trigger (`0 15 18 * * 1-5`, 18:15 Uhr werktags). Eine gezielte Suche nach `executeWorkflow`-Nodes in
"00", die auf Workflow 14s ID (`H0iZrWQy1HQi6iro`) verweisen, ergab **keinen Treffer** — "00" ruft
Workflow 14 nicht auf. Kein Doppel-Trigger, keine Änderung nötig.

**Relevante Code-Stelle:** `wf00.nodes.filter(executeWorkflow-Nodes mit Ziel H0iZrWQy1HQi6iro)` → leer.

---

### Punkt 12 — Workflow 16 marksPerRun-Widerspruch
**Ursprünglicher Verdacht:** Kommentar sagt "immer nur 1 Marke pro Tick", Code setzt `marksPerRun = 4`.

**Warum nicht als Regression zu werten:** Der Widerspruch existiert tatsächlich im Code — ABER: dieser
Wert wurde in der laufenden Session am selben Tag (18.08.) bewusst und einvernehmlich von 1 auf 4
angehoben, nachdem die eigentliche Ursache der vorangegangenen n8n-Instabilität (n8n-2.21.7-
Scheduler-Regression, siehe separate Memory) behoben und der Task Runner auf External Mode mit mehr
Kapazität umgestellt wurde. Der Code-Wert (4) ist aktuell gewollt; nur der Kommentartext ist veraltet.

**Geplante Reparatur:** Kommentar aktualisieren, damit er den aktuellen Stand (4 Marken/Tick, seit
18.08., nach External-Runner-Umstellung) korrekt beschreibt. Keine Logikänderung.

---

# Neue zusätzlich gefundene Probleme

### ID: NEU-09-VERSION — OOS-Bestätigung nur strategienamen-, nicht versionsgebunden
**Priorität:** P1
**Workflow:** 09b, 09c, zur Einordnung auch 06, 14, 17
**Node:** "Mindestfallzahlen klassifizieren (Trades)" (`oosConfirmedFor`), "SQL: Je Dimension (Trades)",
"Vorschlag speichern (SQL bauen, Trades)"

**Korrektur gegenüber Runde 1 (wichtig):** Die ursprüngliche Einschätzung ("keine eigene
Versionsangabe auf den Findings vorhanden, echte Versionsbindung bräuchte ein bisher nicht
existierendes Feld/Konzept") war **unvollständig recherchiert und in dieser Form falsch**. Bei der
erneuten Prüfung in Runde 3 (auf explizite Anweisung, bestehende Schemafelder zu bevorzugen, statt
Doku ungeprüft zu übernehmen) zeigt sich:

- `trading.paper_trades` hat laut `sql/050_ap10_versionierung.sql` **bereits alle relevanten
  Versionsfelder** (`rule_version`, `configuration_version`, u.a.) — Zitat aus der Migration: *"Nur
  paper_trades hatte bisher alle relevanten Felder."* Bestätigt live: "Job A: Portfoliopruefung +
  Trade-Anlage" (Workflow 14) schreibt `rule_version: empf.thesis_rule_version` und
  `configuration_version` aus einem echten `configuration_snapshot_json`-Wert der Empfehlung — kein
  Platzhalter, sondern ein pro Empfehlung tatsächlich gesetzter Wert.
- `trading.backtest_runs` hat ebenfalls `rule_version`/`configuration_version` (bereits von
  "DB: OOS-Backtests laden" geladen, aber bisher ungenutzt).
- **Die eigentliche, tiefere Ursache, warum eine echte Versionsbindung heute NICHT sinnvoll
  implementierbar ist:** Live-Handel (Workflow 06, Konstante `THESIS_RULE_VERSION = 'welle1-v1'`) und
  historische Simulation (Workflow 17, Konstante `RULE_VERSION = 'historische-simulation-v1'`)
  vergeben ihre Versionskennung aus **zwei komplett getrennten, unabhängig voneinander fest codierten
  Namensräumen** — die eine kennzeichnet "kam aus der Live-Empfehlungslogik", die andere "kam aus dem
  Backtest-Pfad". Diese beiden Strings sind **strukturell niemals gleich**, unabhängig davon, ob die
  zugrundeliegende Handelslogik tatsächlich identisch ist oder nicht. Ein direkter
  Gleichheitsvergleich `paper_trades.rule_version = backtest_runs.rule_version` würde deshalb
  **immer** `false` liefern — die Lernvorschlag-Pipeline würde dauerhaft komplett blockiert
  (schlimmer als der heutige Zustand), nicht korrekt gegated.
- Zusätzlich pooling-Problem in "SQL: Je Dimension (Trades)" (Workflow 09b/09c): `GROUP BY strategy`
  fasst ALLE `paper_trades` einer Strategie zusammen, unabhängig von `rule_version`/
  `configuration_version` — Trades aus unterschiedlichen Regel-/Konfigurationsständen werden
  statistisch vermischt, bevor überhaupt eine OOS-Prüfung stattfindet.

**Fachliche Auswirkung:** Die Diagnose aus Runde 1 (Vorschlag/Befund) bleibt im Ergebnis richtig — OOS
gilt aktuell nur je Strategie, nicht je Version. Aber die Begründung war falsch, und ein naiver Fix
("einfach rule_version vergleichen") wäre eine **echte Verschlechterung** gewesen. Die Lücke ist damit
präziser: es fehlt kein Datenfeld, sondern eine **einheitliche, pipeline-übergreifende
Versionierungs-Konvention** für "welche konkrete Handelslogik wurde verwendet" — Live- und
Backtest-Signalberechnung sind zwei unabhängig gepflegte Code-Pfade (Workflow 06 vs. die
`computeSignals()`-Funktion in Workflow 17) ohne gemeinsame Versionsquelle.

**Änderung erforderlich:** Weiterhin NICHT in dieser Runde — jetzt aus einem präziseren, belegten
Grund: es braucht zuerst eine bewusste Design-Entscheidung (z. B. gemeinsame Versionierungs-Konvention
für Signal-/Regelverwendung über beide Pfade, oder eine explizite Zuordnungstabelle
Backtest-Version→Live-Version), bevor ein Versionsvergleich sinnvoll UND sicher eingebaut werden kann.
Ein Vergleich auf Basis der heutigen, disjunkten Konstanten würde die Lernvorschlag-Erzeugung komplett
lahmlegen. Empfehlung unverändert: separates Architekturvorhaben, analog A2/F9 aus dem Härtungsauftrag
vom 02.08. — jetzt aber mit konkretem, verifiziertem Ausgangsbefund statt einer Vermutung.

---

# Look-Ahead-/Backtest-Risiken

1. **P17-6 (Trailing-Stop, oben)** — bestätigter, echter Look-Ahead-Bias innerhalb einer Tageskerze.
2. **P17-1 (Short-Cash, oben)** — kein Look-Ahead im engeren Sinne, aber verfälscht die Backtest-Aussage
   genauso schwerwiegend.
3. **NEU-09-VERSION (oben)** — potenzielles Data-Leakage-Risiko bei OOS-Bestätigung über Strategieversionen
   hinweg, bereits bekannt/dokumentiert, nicht in dieser Runde behoben.
4. **Survivorship Bias (Kategorie B):** nicht systematisch geprüft in dieser Runde — würde erfordern, zu
   klären, ob `trading.stock_instruments`/Watchlist rückwirkend für historische Simulationszeiträume
   Änderungen nachvollzieht oder nur den heutigen Stand verwendet. Empfehlung: eigener Prüfpunkt für
   eine Folge-Runde.

---

# Performance-Risiken

- WF08-10 (Kursverlauf ohne Datumsbegrenzung) — siehe oben, P2.
- WF10-11 (unbegrenzte Empfehlungsabfrage) — siehe oben, P2.
- Kategorie J (SELECT *, unbegrenzte ORDER BY, große Merge-/Code-Nodes) wurde nicht systematisch über
  alle ~30 Workflows gesucht — nur die beiden oben durch die 12 Punkte aufgefallenen Stellen.

---

# Security-Risiken

- **WF97-1 (SQL-Diagnose-Webhook)** — einziger in dieser Runde gefundener konkreter Security-Befund,
  P1, siehe oben.
- Keine weiteren Webhook-Endpunkte wurden in dieser Runde systematisch auf Authentifizierung geprüft
  (außerhalb des explizit benannten Verdachtspunkts 2).

---

# Empfohlene Reparaturreihenfolge

1. **WF97-1** (SQL-Webhook deaktivieren) — trivial, sofortiges Sicherheitsrisiko, keine Regressionsgefahr.
2. **P17-1** (Short-Cash-Fix) — höchste fachliche Priorität, überschaubare Codeänderung, aber
   zwingend mit TEST 1-4 (Long/Short Gewinn/Verlust) abzusichern vor Vertrauen in historische Ergebnisse.
3. **P17-6** (Trailing-Stop-Look-Ahead-Fix) — ähnlich hohe Priorität, TEST 5+6 (Same-Bar, Trailing-Stop-
   Reihenfolge) zwingend.
4. **P17-4** (initial_capital-Priorität) — einfache Änderung, TEST 11 (unterschiedliches Kapital) danach.
5. **WF14-8, P17-5** (fehlende Config-Keys ergänzen) — trivial, kein Verhaltensrisiko, da Fallback-Werte
   bereits korrekt sind.
6. **P12** (Kommentar-Korrektur Workflow 16) — kosmetisch, keine Logik.
7. **P17-3 + P17-3b** (Simulationsworker-Automatisierung) — größerer Eingriff, braucht vorherige
   Lock-Verifikation, danach TEST 8+9+10 (Pause/Resume, parallele Worker, Retry).
8. **WF08-10, WF10-11** (Performance) — niedrige Priorität, kein Korrektheitsrisiko.
9. **NEU-09-VERSION** — bewusst NICHT in dieser Runde, eigenständiges Folgevorhaben.

Punkte 1-6 sind aus meiner Sicht mit vertretbarem Risiko in dieser Session umsetzbar. Punkt 7 würde ich
erst nach expliziter Rücksprache angehen (größerer struktureller Eingriff in einen produktiv genutzten
Workflow). Punkt 9 explizit zurückgestellt wie oben begründet.

---

# Runde 3 — Systematischer Sweep (2026-08-19, Punkt 12 des Auftrags)

## Methodik

Alle 33 Finanz-Workflows (Projektabgrenzung: numerisch benannte Workflows 00-17/97/99 +
Watchlist/RSS-Quellen/Simulation-Steuerzentrale/Goslarsche-Login/GDELT-Diagnose-Hilfsworkflows;
ALLRIS/Oliver-Adler-Workflows auf derselben Instanz explizit NICHT Teil dieses Systems) frisch von
n8n live geladen (nicht aus dem lokalen Repo, wegen des bekannten Stale-Tab-Risikos). Automatisiert
durchsucht nach:

- `SELECT *`/`SELECT ...` ohne `LIMIT` gegen bekannte, kontinuierlich wachsende Tabellen
  (`recommendations`, `news_assessments`, `stock_price_history`, `simulation_trades`,
  `simulation_orders`, `simulation_run_steps`, `paper_trades`, `news_impact_tracking`,
  `backtest_runs`, `pipeline_runs`, `learning_rule_proposals`, `recommendation_veto_log`), danach
  jeder Treffer einzeln gegen seinen tatsächlichen Verbrauch im Code geprüft (nicht pauschal als Bug
  gewertet) — reine "heute"/Konfigurations-/Watchlist-Abfragen sind by design klein und wurden nicht
  als Befund gezählt.
- `onError: continueRegularOutput` auf allen 177 Fundstellen gesichtet, davon gezielt die
  schreibenden/persistierenden Nodes (INSERT/UPDATE/UPSERT) auf fehlende Erfolgsprüfung downstream
  geprüft.
- Punkt 6 (WF14-Trigger-Dopplung) und Punkt 7 (OOS-Versionierung) erneut, unabhängig von der
  Dokumentation aus Runde 1/2, gegen den frischen Live-Stand nachvollzogen.
- Survivorship-Bias-Frage für Workflow 17 konkret geprüft (nicht nur als offener Punkt stehen
  gelassen).

Kein Anspruch auf lückenlose Vollständigkeit über jede der zwölf in Kategorie A-J genannten
Bug-Klassen hinweg (z. B. wurde nicht jede der 177 `continueRegularOutput`-Stellen einzeln gegen jede
denkbare Fehlerursache durchgespielt) — aber jeder unten aufgeführte Befund ist am tatsächlichen Code
verifiziert, keine Vermutung.

## Neue bestätigte Befunde

### ID: WF06-1 — Unbegrenzte Empfehlungs-Query, obwohl nur offene/pending gebraucht werden
**Priorität:** P2
**Workflow:** 06 – Empfehlungswatchlist – Agent V1
**Node:** "DB: Bestehende Empfehlungen laden"

**Beweis:** `SELECT * FROM trading.recommendations ORDER BY id;` — Verbrauch in "Empfehlungen:
Abgleich berechnen" geprüft: `for (const row of empfehlungRows) if ((row.status === 'offen' ||
row.status === 'portfolio_pending') && row.ticker) offenByTicker[...] = row;` — geschlossene Zeilen
werden geladen, aber nirgends im Node verwendet.

**Fix:** `WHERE status IN ('offen','portfolio_pending')` ergänzt. Keine Verhaltensänderung (identisches
Ergebnis, weniger geladene/verworfene Zeilen). Live gepusht, verifiziert (`versionId
e1d7a859-0371-493a-801d-67cf5e6cf572`), alle Nodes weiterhin erreichbar.

---

### ID: WF07-1 — Unbegrenzte Empfehlungs-Query im Status-Dashboard, identisches Muster wie WF10-11
**Priorität:** P2
**Workflow:** 07 – Status-Uebersicht – Agent V1
**Node:** "DB: Empfehlungen laden"

**Beweis:** `SELECT * FROM trading.recommendations ORDER BY id;` — Verbrauch in "Baue Uebersicht"
geprüft: `offen` (gefiltert auf `status==='offen'`) wird als vollständige HTML-Tabelle gerendert;
`geschlossen` (gefiltert auf `status==='geschlossen'`) wird NUR zu zwei Aggregatzahlen verdichtet
(`avgPerf`, `hitRate`) — die Rohliste selbst erscheint nirgends im Dashboard.

**Fix:** Query auf `WHERE status = 'offen'` begrenzt (geschlossene Zeilen werden hier, anders als in
WF10, nirgends als Liste gebraucht — komplett weggelassen statt nur zeitlich begrenzt). Neue,
ungefilterte Aggregat-Query "DB: Empfehlungs-Statistik laden (Uebersicht)" liefert `avg_perf`/
`hit_rate` weiterhin über die komplette Historie — beide angezeigten Kennzahlen bleiben exakt
unverändert, nur der Rohdaten-Transfer sinkt. Verdrahtet nach dem etablierten
"Merge Status N"-Sequenzierungsmuster dieses Workflows (neuer "Merge Status 29"). Live gepusht,
verifiziert (`versionId afb37bd2-7a00-49c6-8013-4a78056bfdc5`), alle Nodes erreichbar.

---

### ID: P17-7 — Persistierung der Simulationsergebnisse ohne Erfolgsprüfung
**Priorität:** P1
**Workflow:** 17 – Historische Simulation
**Nodes:** "DB: Paket-Ergebnisse speichern", "DB: Metriken speichern + Lauf abschliessen"

**Beweis:** Beide Nodes sind `onError: continueRegularOutput` UND echte Sackgassen im Graph (keine
ausgehende Verbindung, letzte Nodes ihrer jeweiligen Zweige). Zum Vergleich: an der strukturell
identischen Stelle in Workflow 08 ("Tracking-Zeile upserten (ausfuehren)") folgt ein expliziter Node
"Persistierung pruefen (sonst werfen)", der bei `j.error` einen `throw new Error(...)` auslöst — exakt
dasselbe SQL-Builder-Muster (`BEGIN;...;COMMIT;` als ein Code-Node gebaut, ein Postgres-Node
ausgeführt), aber ohne die Prüfung. Zusätzlich bestätigt: der Node "Baue POST-Antwort (JSON)"
(Web-Steuerzentrale, `pause`/`resume`/`cancel`) prüft `current.error` bereits korrekt — die
Prüf-Logik ist im selben Workflow an anderer Stelle bekannt und richtig umgesetzt, hier aber schlicht
vergessen worden.

**Fachliche Auswirkung:** Schlägt die Transaktion fehl (z. B. Constraint-Verletzung, kurzer
Verbindungsabbruch), zeigt die n8n-Ausführung trotzdem "Erfolg" — ohne dass ein Tages-Paket-Ergebnis
tatsächlich gespeichert wurde. Der betroffene `simulation_run_steps`-Schritt bleibt dabei korrekt auf
`status='running'` mit veraltendem `heartbeat_at` stehen (die Transaktion, die ihn auf `'completed'`
setzen würde, ist ja Teil derselben fehlgeschlagenen COMMIT) — durch den in dieser Session gebauten
atomaren Claim (P17-3b) wird er nach 2 Minuten automatisch erneut versucht (kein Datenverlust im
Normalfall), aber der Fehlschlag bleibt **unsichtbar** (Ausführung zeigt "Erfolg"), was eine dauerhaft
fehlschlagende Ursache (kein transientes Problem) unnötig lange unentdeckt lassen könnte.

**Fix:** Neue Nodes "Persistierung pruefen (Paket-Ergebnisse, sonst werfen)" und "Persistierung pruefen
(Metriken, sonst werfen)" nach demselben Muster wie Workflow 08 ergänzt (`mode:
runOnceForEachItem`, wirft bei `j.error`). Dadurch zeigt eine fehlgeschlagene Persistierung ab sofort
korrekt `status=error` in der n8n-Ausführungshistorie, während der Selbstheilungsmechanismus (Retry via
Heartbeat-Reclaim) unverändert erhalten bleibt. Live gepusht, verifiziert (`versionId
80cfff92-7441-427a-9b82-53a8a4f82a24`), beide neuen Nodes vorhanden, alle Nodes erreichbar.
**Kein echter Fehlerfall in dieser Session ausgelöst** (kein Zugriff auf einen kontrollierten
DB-Fehler ohne Eingriff in die Produktivdatenbank) — die Absicherung stützt sich auf die exakte
Analogie zum bereits produktiv bewährten Muster in Workflow 08, nicht auf einen eigenen Live-Test
dieses spezifischen Fehlerpfads.

---

### ID: NEU-09-VERSION — siehe korrigierten Eintrag oben unter "Bestätigte Probleme"

Wesentliche neue Erkenntnis dieser Runde — nicht wiederholt, siehe oben.

## Erneut geprüft, Befund bestätigt unverändert

- **Punkt 6 (WF14-Trigger):** Frisch am Live-Stand von Workflow 00 nachvollzogen —
  `executeWorkflow`-Nodes in Workflow 00 rufen exakt 02b, 02, 06, 10, 05 auf. Workflow 14
  (`H0iZrWQy1HQi6iro`) ist NICHT darunter. Der eigene Schedule Trigger in Workflow 14 (18:15 Werktage)
  ist der einzige Eingang in die Portfolio-Risiko-/Paper-Trading-Kette — Deaktivierung würde das
  gesamte Paper-Trading lahmlegen. Keine Doppelverarbeitung, keine Änderung nötig.

## Neu geprüft und NICHT als Bug bestätigt

### Survivorship Bias (Workflow 17, Ticker-Universum)
Geprüft: Das Ticker-Universum eines Simulationslaufs wird beim Erstellen über das Web-Formular
("POST: Formular normalisieren + SQL bauen", `MAX_INSTRUMENTS=30`, `TICKER_REGEX`-Validierung)
explizit vom Bedienenden übergeben — es wird NICHT automatisch aus der aktuellen, heutigen Watchlist
gezogen. Damit besteht kein automatischer/versteckter Survivorship-Bias-Mechanismus im Code; das
Risiko liegt (falls überhaupt) in der bewussten Wahl des Anwenders, welche Ticker er für einen
Backtest einträgt — kein Codefehler.

## Beobachtung ohne Fix in dieser Runde (P3, DB-seitig)

### WF07 "DB: Letzte Pipeline-Laeufe je Stufe"
`SELECT DISTINCT ON (workflow_name, stage_name) ... FROM trading.pipeline_runs ORDER BY workflow_name,
stage_name, ...` — das Ergebnis selbst ist klein (eine Zeile je Workflow/Stufe-Kombination), aber jede
Ausführung erfordert einen vollständigen Sortier-Scan der gesamten, mit jeder einzelnen Ausführung
JEDES Workflows kontinuierlich wachsenden `pipeline_runs`-Tabelle. Das ist ein DB-seitiges
Index-Thema (z. B. `CREATE INDEX ... ON pipeline_runs(workflow_name, stage_name, started_at DESC)`),
keine n8n-Query-Änderung — ohne direkten DB-Zugriff (der SQL-Diagnose-Webhook wurde in dieser Session
bewusst stillgelegt, siehe WF97-1) kann ich weder die aktuelle Zeilenzahl noch einen vorhandenen Index
verifizieren. Nicht als "OK" markiert, nicht behoben — Empfehlung: bei Gelegenheit per n8n-UI-Manual-
Trigger von Workflow 97 prüfen und ggf. Index ergänzen.

## Config-Key-Übersicht (Punkt 4 des Folgeauftrags, projektweit)

Automatisiert über alle 33 Finanz-Workflows ermittelt: jeder per `num('KEY', default)` bzw.
`cfgByKey['KEY']`/`_cfgByKey['KEY']`-Muster verwendete Config-Key gegen jede
`pipeline_config`-Ladequery (`config_key IN (...)`) abgeglichen. "DB vorhanden" ist ein Proxy — geprüft
gegen `INSERT INTO trading.pipeline_config`-Blöcke in `sql/*.sql` (Migrations-Historie), NICHT gegen
den tatsächlichen aktuellen Live-DB-Inhalt (kein Zugriff ohne den bewusst deaktivierten
SQL-Diagnose-Webhook, siehe WF97-1). "—" bei "DB vorhanden" heißt: kein Migrations-INSERT gefunden,
nicht zwingend "fehlt in der DB" (könnte auch manuell/über die UI gesetzt worden sein).

**Ergebnis: 37 verwendete/geladene Keys geprüft, 0 neue Fälle von "verwendet aber nicht geladen"**
(über die in Runde 1 bereits gefundenen und gefixten WF14-8/P17-5-Fälle hinaus, die in dieser Tabelle
bereits korrekt mit "geladen von" erscheinen).

| CONFIG_KEY | verwendet in | geladen von | Default | DB vorhanden (Migration) | Problem |
|---|---|---|---|---|---|
| AMBIGUOUS_BAR_POLICY_CODE | 17 | 14, 17 | 1 | ja | nein |
| CORRELATION_LOOKBACK_DAYS | — | 14 | — | ja | nein |
| DEFAULT_FEES_BPS | 17 | 14, 06, 17 | 15 | ja | nein |
| DEFAULT_SLIPPAGE_BPS | 17 | 14, 06, 17 | 10 | ja | nein |
| DRY_RUN | 06 | 14, 06 | — | ja | nein |
| ENABLE_PAPER_TRADING | 06 | 06 | — | ja | nein |
| GDELT_EARLIEST_DATE | — | 16 | — | ja | nein |
| GDELT_MARKS_PER_WORKER_RUN | — | 16 | — | ja | nein |
| GDELT_PROBE_WINDOW_MINUTES | 16 | 16 | — | ja | nein |
| GDELT_REQUEST_DELAY_MS | 16 | 16 | — | ja | nein |
| IMPORT_DEFAULT_PACKAGE_SIZE | 15 | 15 | — | ja | nein |
| IMPORT_MAX_RETRY_ATTEMPTS | 16, 15 | 16, 15 | — | ja | nein |
| LEARNING_MIN_TRADE_SAMPLE_SIZE | 09b, 09c | 09b, 09c | — | ja | nein |
| MAX_AMBIGUOUS_PCT_FOR_PROPOSAL | 09b, 09c | 09b, 09c | — | ja | nein |
| MAX_DATA_AGE_MINUTES | — | 06 | — | ja | nein |
| MAX_DATA_ERROR_RETRIES | (14, `??`-Muster) | 14 | 5 | — | nein (Fix aus Runde 1, hier bestätigt weiterhin geladen) |
| MAX_DIRECTIONAL_EXPOSURE_PCT | 17 | 14, 17 | 40.0 | ja | nein |
| MAX_NON_EUR_EXPOSURE_PCT | — | 14 | — | ja | nein |
| MAX_OPEN_POSITIONS | 17 | 14, 17 | 10 | ja | nein |
| MAX_PAIRWISE_CORRELATION | — | 14 | — | ja | nein |
| MAX_PORTFOLIO_CHECK_ATTEMPTS | — | 14 | — | ja | nein |
| MAX_PORTFOLIO_DRAWDOWN_PCT | — | 14 | — | ja | nein |
| MAX_POSITION_VALUE_PCT | — | 06 | — | ja | nein |
| MAX_REGION_EXPOSURE_PCT | 17 | 14, 17 | 60.0 | ja | nein |
| MAX_RISK_PER_TRADE_PCT | 17 | 06, 17 | 1.0 | ja | nein |
| MAX_SECTOR_EXPOSURE_PCT | 17 | 14, 17 | 15.0 | ja | nein |
| MAX_SINGLE_POSITION_PCT | 17 | 14, 17 | 8.0 | ja | nein |
| MAX_TOTAL_OPEN_RISK_PCT | 17 | 14, 17 | 6.0 | ja | nein |
| MINI_FUTURE_FINANCING_PCT_PA | 17 | 17 | 2.5 | ja | nein (Fix aus Runde 1, hier bestätigt) |
| MINI_FUTURE_LEVERAGE | 17 | 17 | 4 | ja | nein (Fix aus Runde 1, hier bestätigt) |
| MINI_FUTURE_SPREAD_PCT | 17 | 17 | 0.4 | ja | nein (Fix aus Runde 1, hier bestätigt) |
| MIN_REWARD_RISK_RATIO | 17 | 06, 17 | 1.5 | ja | nein |
| MODEL_PORTFOLIO_VALUE | 17 | 14, 06, 17 | 100000 | ja | nein |
| REQUIRE_CONFIRMATION | 06 | 06 | — | ja | nein |
| SIMULATION_DEFAULT_PACKAGE_SIZE | 17 | 17 | 20 | ja | nein |
| STRESS_RISK_REDUCTION_FACTOR | — | 14 | — | ja | nein |
| TREND_KONFLIKT_SCHWELLE | — | 06 | — | ja | nein |

## Zusammenfassung Runde 3

| ID | Befund | Bestätigt? | Status |
|---|---|---|---|
| WF06-1 | Unbegrenzte Empfehlungs-Query (06) | ✅ | Behoben, live verifiziert |
| WF07-1 | Unbegrenzte Empfehlungs-Query (07) | ✅ | Behoben, live verifiziert |
| P17-7 | Persistierung ohne Erfolgsprüfung (17) | ✅ | Behoben, live verifiziert (kein echter Fehlerfall getestet) |
| NEU-09-VERSION | OOS-Versionierung | ✅ (Begründung korrigiert) | Weiterhin zurückgestellt, jetzt präziser begründet |
| Punkt 6 | WF14-Trigger-Dopplung | Erneut geprüft, nicht bestätigt | Kein Fix nötig |
| Survivorship Bias (WF17) | — | Nicht bestätigt (operator-gesteuert) | Kein Fix nötig |
| WF07 Pipeline-Runs-Index | Performance-Beobachtung | Nicht abschließend geprüft (kein DB-Zugriff) | Nicht behoben, dokumentiert |
| Config-Key-Sweep (37 Keys, projektweit) | Punkt 4 des Folgeauftrags | Geprüft, 0 neue Treffer | Kein Fix nötig (Runde-1-Fixes bestätigt) |
