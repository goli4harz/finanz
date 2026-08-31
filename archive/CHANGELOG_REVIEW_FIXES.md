# CHANGELOG_REVIEW_FIXES.md

Zugehörig zu `REVIEW_REPORT.md` (2026-08-18). Diese Runde umfasst die 5 als "schnell, geringes Risiko"
eingestuften Fixes. Die beiden P0-Befunde (Short-Cash-Accounting, Trailing-Stop-Look-Ahead) sowie die
Worker-Automatisierung sind bewusst NICHT Teil dieser Runde — siehe REVIEW_REPORT.md, Abschnitt
"Empfohlene Reparaturreihenfolge".

---

## 1. WF97-1 — SQL-Diagnose-Webhook deaktiviert

- **Geänderte Datei:** `97 – Einmalig – Beliebige Query ausfuehren.json`
- **Workflow:** 97 – Einmalig – Beliebige Query ausfuehren
- **Node:** "Webhook Diagnose (POST)"
- **Grund:** Aktiver, unauthentifizierter `POST /diagnose-sql`-Endpunkt konnte beliebiges SQL mit vollen
  Postgres-Credentials ausführen.
- **Alte Logik:** Webhook-Node aktiv (`disabled: false`), Workflow `active: true`.
- **Neue Logik:** Webhook-Node deaktiviert (`disabled: true`), Workflow zusätzlich auf `active: false`
  gesetzt (n8n verweigert `active: true` für einen Workflow ohne automatischen Trigger — ein reiner
  Manual Trigger zählt dafür nicht, braucht aber auch kein `active: true`, um manuell ausführbar zu
  bleiben).
- **Fachliche Auswirkung:** Diagnose-SQL nur noch über den bestehenden "Manueller Start"-Trigger in der
  n8n-UI möglich, keine externe Erreichbarkeit mehr.
- **Regressionstest:** Live verifiziert — `GET /workflows/{id}` zeigt `active: false`,
  `Webhook Diagnose (POST)`-Node `disabled: true`. Manueller Trigger-Node unverändert vorhanden und
  nicht deaktiviert.
- **Testergebnis:** OK.

---

## 2. WF14-8 — `MAX_DATA_ERROR_RETRIES` wird jetzt geladen

- **Geänderte Datei:** `14 – Portfolio-Risiko und Paper-Trading.json`
- **Workflow:** 14 – Portfolio-Risiko und Paper-Trading
- **Node:** "DB: Portfolio-Konfiguration laden (Exec)"
- **Grund:** Code las `CFG.MAX_DATA_ERROR_RETRIES ?? 5`, die vorgelagerte Query lud den Key nie — Fallback
  griff immer, Wert war faktisch nicht konfigurierbar.
- **Alte Logik:** `WHERE config_key IN ('DEFAULT_FEES_BPS','DEFAULT_SLIPPAGE_BPS','AMBIGUOUS_BAR_POLICY_CODE')`
- **Neue Logik:** `WHERE config_key IN ('DEFAULT_FEES_BPS','DEFAULT_SLIPPAGE_BPS','AMBIGUOUS_BAR_POLICY_CODE','MAX_DATA_ERROR_RETRIES')`
- **Fachliche Auswirkung:** Falls `MAX_DATA_ERROR_RETRIES` in `trading.pipeline_config` gesetzt ist, wirkt
  der Wert jetzt tatsächlich. Ist er nicht gesetzt, bleibt der bisherige Fallback (5) unverändert aktiv —
  kein Verhaltensänderungsrisiko für den aktuellen Live-Zustand.
- **Regressionstest:** Live verifiziert — Query enthält jetzt den Key.
- **Testergebnis:** OK.

---

## 3. P17-5 — Mini-Future-Config-Keys werden jetzt geladen

- **Geänderte Datei:** `17 – Historische Simulation (Walk-Forward, Pilot ohne Nachrichten).json`
- **Workflow:** 17 – Historische Simulation
- **Node:** "DB: Simulations-Konfiguration laden"
- **Grund:** `MINI_FUTURE_LEVERAGE`, `MINI_FUTURE_SPREAD_PCT`, `MINI_FUTURE_FINANCING_PCT_PA` wurden im
  Code über `cfgByKey` gelesen, aber nie von der Query geladen — immer Fallback-Werte (4 / 0.4 / 2.5)
  verwendet, unabhängig von der tatsächlichen DB-Konfiguration.
- **Alte Logik:** `IN (..., 'MAX_REGION_EXPOSURE_PCT')`
- **Neue Logik:** `IN (..., 'MAX_REGION_EXPOSURE_PCT', 'MINI_FUTURE_LEVERAGE', 'MINI_FUTURE_SPREAD_PCT', 'MINI_FUTURE_FINANCING_PCT_PA')`
- **Fachliche Auswirkung:** Werte jetzt aus `pipeline_config` konfigurierbar. Da dort aktuell (Stand
  Prüfzeitpunkt) keine abweichenden Werte gesetzt sind, keine Verhaltensänderung für laufende/künftige
  Simulationen in dieser Runde — nur die Konfigurierbarkeit ist jetzt real.
- **Regressionstest:** Live verifiziert — Query enthält jetzt alle drei Keys.
- **Testergebnis:** OK.

---

## 4. P17-4 — `initial_capital` hat jetzt Vorrang vor globaler `MODEL_PORTFOLIO_VALUE`

- **Geänderte Datei:** `17 – Historische Simulation (Walk-Forward, Pilot ohne Nachrichten).json`
- **Workflow:** 17 – Historische Simulation
- **Node:** "Baue Run-Kontext"
- **Grund:** Positionsgrößen-/Risikolimit-Berechnung (`sizePosition`, `checkHardLimits`) nutzte
  `cfg.modelPortfolioValue`, das bisher IMMER den globalen `pipeline_config.MODEL_PORTFOLIO_VALUE`-Wert
  bevorzugte — der Lauf-eigene `initial_capital` griff nur, wenn der globale Key fehlte (tat er nicht).
- **Alte Logik:** `_model_portfolio_value: num('MODEL_PORTFOLIO_VALUE', run.initial_capital || 100000)`
- **Neue Logik:** `_model_portfolio_value: run.initial_capital || num('MODEL_PORTFOLIO_VALUE', 100000)`
- **Fachliche Auswirkung:** **Verhaltensänderung für künftige Simulationsläufe:** Positionsgrößen und
  Risikolimits werden jetzt tatsächlich proportional zum deklarierten `initial_capital` des jeweiligen
  Laufs berechnet, nicht mehr pauschal gegen den globalen Wert. Bereits abgeschlossene, historische
  Läufe sind davon nicht rückwirkend betroffen (nur künftige Berechnungen).
- **Regressionstest:** Code-Verifikation live bestätigt (String-Vergleich der neuen Zeile). **TEST 11
  (unterschiedliches initial_capital, 10.000/50.000/100.000) wurde in dieser Runde NICHT durchgeführt** —
  empfohlen vor dem nächsten produktiven Simulationslauf mit einem von der globalen `MODEL_PORTFOLIO_VALUE`
  abweichenden `initial_capital`.
- **Testergebnis:** Code-Änderung verifiziert, funktionaler Test noch ausstehend (siehe oben).

---

## 5. P12 — Veralteter Kommentar in Workflow 16 korrigiert

- **Geänderte Datei:** `16 – Historische Nachrichten importieren (GDELT).json`
- **Workflow:** 16 – Historische Nachrichten importieren (GDELT)
- **Node:** "Baue Marken-Kandidaten"
- **Grund:** Kommentar beschrieb noch die Entscheidung vom 17.08. ("immer nur 1 Marke pro Tick"), obwohl
  der Code bereits am 18.08. (in dieser Session, nach Behebung der n8n-Scheduler-Regression und Umstellung
  auf External Task Runner) bewusst auf `marksPerRun = 4` geändert wurde. Keine Logikänderung, reine
  Dokumentationskorrektur.
- **Alte Logik:** Kommentar verwies auf 1-Marke-Entscheidung vom 17.08.
- **Neue Logik:** Kommentar verweist auf die tatsächliche 4-Marken-Entscheidung vom 18.08. und deren
  Begründung (External Runner, mehr Kapazität).
- **Fachliche Auswirkung:** Keine — `marksPerRun = 4` war bereits vor dieser Änderung aktiv.
- **Regressionstest:** Live verifiziert — Kommentar aktualisiert, `marksPerRun = 4` unverändert.
- **Testergebnis:** OK.

---

## Zusammenfassung (Runde 1 — schnelle Fixes)

| # | Fix | Datei | Risiko | Getestet |
|---|---|---|---|---|
| 1 | SQL-Webhook deaktiviert | 97 | keins (nur Zugriffsweg entfernt) | ja, live |
| 2 | MAX_DATA_ERROR_RETRIES geladen | 14 | keins (Fallback unverändert korrekt) | ja, live |
| 3 | Mini-Future-Keys geladen | 17 | keins (Fallback unverändert korrekt) | ja, live |
| 4 | initial_capital-Priorität | 17 | echte Verhaltensänderung künftiger Läufe | Code ja, TEST 11 offen |
| 5 | Kommentar-Korrektur | 16 | keins | ja, live |

Alle 5 Änderungen wurden per n8n-API live gepusht, verifiziert, und die lokalen Repo-Dateien
(`97…json`, `14…json`, `17…json`, `16…json`) wurden anschließend vom Live-Stand neu synchronisiert.
Backups der jeweiligen Vor-Zustände liegen im Scratchpad dieser Session.

---

## 6. P17-1 — Short-Cash-Accounting bei Exit korrigiert

- **Geänderte Datei:** `17 – Historische Simulation (Walk-Forward, Pilot ohne Nachrichten).json`
- **Workflow:** 17 – Historische Simulation
- **Node:** "Verarbeite Tage-Paket" (Exit-Block)
- **Grund:** `cash += exitNotional` beim Exit war nur für Long korrekt. Bei Short (Mini-Future-Modell,
  kein echter Aktienbesitz) kehrte diese Formel das Vorzeichen des tatsächlichen Trade-Ergebnisses in
  der Cash-Fortschreibung um.
- **Alte Logik:**
  ```js
  cash += (exitNotional - exitSpreadFee - financingCost);
  ```
- **Neue Logik:**
  ```js
  const exitCashInflow = pos.direction === 'long' ? exitNotional : (2 * pos.position_value - exitNotional);
  cash += (exitCashInflow - exitSpreadFee - financingCost);
  ```
  Für Short entspricht das `position_value + grossPnl` — identisch zur bereits korrekten täglichen
  Markwert-Formel für offene Short-Positionen (Zeile ~596), die Formel ist jetzt intern konsistent.
- **Fachliche Auswirkung:** **Echte Verhaltensänderung.** Ab sofort verbuchte und künftige Short-Trade-
  Exits verändern `cash`/`total_equity` korrekt in Höhe des tatsächlichen Gewinns/Verlusts, statt mit
  umgekehrtem Vorzeichen. Bereits in der Vergangenheit gelaufene Simulationen mit Short-Trades bleiben
  in der DB unverändert (keine rückwirkende Korrektur der Bestandsdaten in dieser Runde) — deren
  `cash`/`total_equity`-Werte für Short-Trades sind weiterhin fehlerhaft und sollten bei Bedarf separat
  neu berechnet oder die betroffenen Läufe neu simuliert werden.
- **Regressionstest:** Isolierter Logiktest (`test_short_cash_fix.js`, TEST 1-4 aus dem Auftrag) VOR dem
  Live-Push durchgeführt:
  - TEST 1 (Long Gewinn, Entry 100→Exit 120, 10 Stk.): erwartet +200, alte Formel +200, neue Formel +200 — beide OK.
  - TEST 2 (Long Verlust, Entry 100→Exit 80, 10 Stk.): erwartet -200, alte Formel -200, neue Formel -200 — beide OK.
  - TEST 3 (Short Gewinn, Entry 100→Exit 80, 10 Stk.): erwartet +200, **alte Formel -200 (FALSCH, Vorzeichen
    umgekehrt)**, neue Formel +200 (KORREKT).
  - TEST 4 (Short Verlust, Entry 100→Exit 120, 10 Stk.): erwartet -200, **alte Formel +200 (FALSCH,
    Vorzeichen umgekehrt)**, neue Formel -200 (KORREKT).
  Live-Push danach per `GET /workflows/9JWDOTXFQWHYkypO` verifiziert — Code enthält die neue Formel,
  Workflow bleibt aktiv.
- **Testergebnis:** OK (isolierter Test bestanden, Live-Code-Stand verifiziert). **Kein Live-Simulationslauf
  mit echtem Short-Trade in dieser Session durchgeführt** — nächster echter Short-Exit in einer laufenden
  Simulation sollte zur zusätzlichen End-zu-Ende-Bestätigung beobachtet werden.

---

## 7. P17-6 — Trailing-Stop-Look-Ahead-Bias behoben

- **Geänderte Datei:** `17 – Historische Simulation (Walk-Forward, Pilot ohne Nachrichten).json`
- **Workflow:** 17 – Historische Simulation
- **Node:** "Verarbeite Tage-Paket" (Exit-Block)
- **Grund:** Trailing-Stop wurde anhand des Tages-High/Low DERSELBEN Kerze nachgezogen und die
  Exit-Prüfung lief danach mit dem bereits nachgezogenen, engeren Stop gegen dieselbe Kerze — echter
  Intraday-Look-Ahead ohne Intraday-Daten.
- **Alte Logik:** Erst `extreme_price`/`stop_price` mit `bar.high`/`bar.low` von heute aktualisieren,
  dann `checkExit(pos, bar, ...)` mit dem neuen Stop aufrufen.
- **Neue Logik:** Erst `checkExit(pos, bar, ...)` mit dem Stop-Stand von VOR der heutigen Nachführung
  aufrufen. Nur falls die Position den Tag überlebt (`!exitCheck.exit`), wird `extreme_price`/
  `stop_price` anhand des heutigen High/Low nachgezogen — wirkt dann erst für die nächste Kerze.
  `checkExit()` selbst wurde nicht verändert (nutzt ohnehin nur `stop_price`/`target_price`, nicht
  `extreme_price`).
- **Fachliche Auswirkung:** **Echte Verhaltensänderung.** Trades, die bisher an Tagen mit großer
  Handelsspanne fälschlich zu früh/zu oft ausgestoppt wurden, können den Tag jetzt überleben und erst
  ab der Folgekerze vom nachgezogenen Stop betroffen sein. Betrifft Long und Short gleichermaßen
  (symmetrische Fallunterscheidung unverändert). Bereits abgeschlossene historische Läufe bleiben in
  der DB unverändert.
- **Regressionstest:** Isolierter Logiktest (`test_trailing_stop_fix.js`, TEST 6 aus dem Auftrag) VOR
  dem Live-Push:
  - Long-Position, Bar: Open 100, Low 96, High 110, Close 108. Alter Stop 90 (vom Tages-Low NICHT
    berührt), `trail_distance` 10 (→ neuer Stop anhand Tages-High wäre 100).
  - **Alte Logik:** stoppt fälschlich aus bei Preis 100, obwohl das Tages-Low (96) den ursprünglichen
    Stop (90) nie berührt hat.
  - **Neue Logik:** Position bleibt heute offen (96 > 90); Stop zieht trotzdem auf 100 nach, gilt aber
    erst ab morgen.
  Live-Push danach per `GET /workflows/9JWDOTXFQWHYkypO` verifiziert — Code enthält die neue
  Reihenfolge, Workflow bleibt aktiv.
- **Testergebnis:** OK (isolierter Test bestanden, Live-Code-Stand verifiziert). **TEST 5 (Stop und
  Target in derselben Kerze) nicht erneut nötig** — `checkExit()` selbst wurde nicht verändert, nur der
  Aufrufzeitpunkt relativ zur Trailing-Nachführung. Kein Live-Simulationslauf mit echtem Trailing-Stop-
  Szenario in dieser Session durchgeführt — nächster betroffener Fall in einer laufenden Simulation
  sollte zur zusätzlichen End-zu-Ende-Bestätigung beobachtet werden.

---

## Zusammenfassung (gesamt)

| # | Fix | Datei | Risiko | Getestet |
|---|---|---|---|---|
| 1 | SQL-Webhook deaktiviert | 97 | keins | ja, live |
| 2 | MAX_DATA_ERROR_RETRIES geladen | 14 | keins | ja, live |
| 3 | Mini-Future-Keys geladen | 17 | keins | ja, live |
| 4 | initial_capital-Priorität | 17 | echte Verhaltensänderung künftiger Läufe | Code ja, TEST 11 offen |
| 5 | Kommentar-Korrektur | 16 | keins | ja, live |
| 6 | Short-Cash-Accounting-Fix | 17 | echte Verhaltensänderung künftiger Short-Exits | Isolierter Test ja, Live-E2E offen |
| 7 | Trailing-Stop-Look-Ahead-Fix | 17 | echte Verhaltensänderung künftiger Trailing-Stop-Fälle | Isolierter Test ja, Live-E2E offen |
| 8 | Worker-Automatisierung + atomarer Tage-Paket-Claim | 17 | neue Funktionalität + Race-Fix, echte Verhaltensänderung (autom. Fortschritt) | Live-Aktivierung ja, Mehrfach-Tick-E2E offen |
| 9 | Kursverlauf-Datumsbegrenzung + toter Benchmark-Zweig repariert | 08 | Performance-Fix + echte Verhaltensänderung (Benchmark-Kennzahlen erstmals befüllt) | Isolierter Test ja, Live-Erreichbarkeit ja, E2E-Beobachtung offen |
| 10 | Empfehlungs-Query begrenzt, All-Time-Kennzahlen ausgelagert | 10 | reiner Performance-Fix, Kennzahlen unverändert | Live-Erreichbarkeit ja, Live-Wertvergleich offen |

Damit sind alle 12 ursprünglichen Prüfpunkte bearbeitet bis auf NEU-09-VERSION — siehe `REVIEW_REPORT.md`
für die Begründung, warum das als eigenständiges Architekturvorhaben zurückgestellt bleibt.

---

## Runde 3 (2026-08-19) — Systematischer Sweep (Punkt 12 des Folgeauftrags)

### 11. WF06-1 — Unbegrenzte Empfehlungs-Query begrenzt

- **Geänderte Datei:** `06 – Empfehlungswatchlist – Agent V1.json`
- **Node:** "DB: Bestehende Empfehlungen laden"
- **Alte Logik:** `SELECT * FROM trading.recommendations ORDER BY id;`
- **Neue Logik:** `SELECT * FROM trading.recommendations WHERE status IN ('offen','portfolio_pending') ORDER BY id;`
- **Grund:** Verbrauch in "Empfehlungen: Abgleich berechnen" geprüft — nur `status IN ('offen',
  'portfolio_pending')` wird tatsächlich verwendet (Duplikat-/Konfliktprüfung offener Positionen je
  Ticker), geschlossene Zeilen werden geladen und nie angefasst.
- **Fachliche Auswirkung:** Keine — identisches Ergebnis, weniger geladene/verworfene Zeilen.
- **Regressionstest:** Code-Grep bestätigt `empfehlungRows` nur auf `offen`/`portfolio_pending`
  gefiltert genutzt. Live gepusht (`versionId e1d7a859-0371-493a-801d-67cf5e6cf572`), Erreichbarkeits-
  Check über alle Nodes: keine toten Knoten.
- **Testergebnis:** OK.

---

### 12. WF07-1 — Unbegrenzte Empfehlungs-Query im Dashboard begrenzt, Kennzahlen ausgelagert

- **Geänderte Datei:** `07 – Status-Uebersicht – Agent V1.json`
- **Nodes:** "DB: Empfehlungen laden" (geändert), neue Nodes "DB: Empfehlungs-Statistik laden
  (Uebersicht)" + "Merge Status 29", "Baue Uebersicht" (geändert)
- **Alte Logik:** `SELECT * FROM trading.recommendations ORDER BY id;` — `geschlossen`-Teilmenge nur
  zu `avgPerf`/`hitRate` verdichtet, Rohliste nirgends angezeigt.
- **Neue Logik:** Query auf `WHERE status = 'offen'` begrenzt (geschlossene Zeilen komplett
  weggelassen, anders als bei Fix 10/WF10-11 wird hier keine Rohliste irgendwo gebraucht). Neue
  Aggregat-Query liefert `avg_perf`/`hit_rate` weiterhin über die volle, ungefilterte Historie.
  Verdrahtet nach dem etablierten "Merge Status N"-Muster dieses Workflows.
- **Fachliche Auswirkung:** Keine — `avgPerf`/`hitRate` bleiben exakt identisch (separate,
  ungefilterte Aggregat-Query), nur weniger Datenvolumen pro Dashboard-Aufruf.
- **Regressionstest:** Code-Grep bestätigt `geschlossen` (die Rohliste) im gesamten Node nur zur
  Berechnung von `avgPerf`/`hitRate` verwendet, nie gerendert. Live gepusht
  (`versionId afb37bd2-7a00-49c6-8013-4a78056bfdc5`), Erreichbarkeits-Check: keine toten Knoten.
- **Testergebnis:** OK (Live-Code-Stand + Erreichbarkeit verifiziert, kein Live-Wertvergleich
  alter/neuer `avgPerf`/`hitRate` in dieser Session durchgeführt).

---

### 13. P17-7 — Persistierungs-Erfolgsprüfung für Simulationsergebnisse ergänzt

- **Geänderte Datei:** `17 – Historische Simulation (Walk-Forward, Pilot ohne Nachrichten).json`
- **Neue Nodes:** "Persistierung pruefen (Paket-Ergebnisse, sonst werfen)", "Persistierung pruefen
  (Metriken, sonst werfen)"
- **Grund:** "DB: Paket-Ergebnisse speichern" und "DB: Metriken speichern + Lauf abschliessen" hatten
  `onError: continueRegularOutput` UND waren echte Sackgassen (keine ausgehende Verbindung) — ein
  fehlgeschlagenes `COMMIT` hätte die n8n-Ausführung trotzdem als "Erfolg" gezeigt, ohne dass
  irgendetwas gespeichert wurde. Workflow 08 hat an der strukturell identischen Stelle bereits die
  richtige Prüfung ("Persistierung pruefen (sonst werfen)") — hier fehlte sie schlicht.
- **Alte Logik:** kein nachgelagerter Check, Node war letzter Knoten seines Zweigs.
- **Neue Logik:** `if (j.error) throw new Error(...)` nach jedem der beiden Nodes, identisch zum
  bereits produktiv bewährten Muster aus Workflow 08.
- **Fachliche Auswirkung:** Ein fehlgeschlagenes Speichern zeigt jetzt korrekt `status=error` in der
  n8n-Ausführungshistorie statt fälschlich "Erfolg". Der bestehende Selbstheilungsmechanismus (der
  betroffene `simulation_run_steps`-Schritt bleibt bei einem Fehlschlag ohnehin auf `status='running'`
  mit veraltendem `heartbeat_at` stehen und wird durch den P17-3b-Claim automatisch erneut versucht)
  bleibt unverändert erhalten — die Änderung macht den Fehlschlag nur sichtbar, ändert nichts am
  Retry-Verhalten.
- **Regressionstest:** Direkter Vergleich mit dem produktiv bewährten Analog-Muster aus Workflow 08.
  **Kein echter Fehlerfall in dieser Session ausgelöst** (kein kontrollierter DB-Fehler ohne Eingriff
  in die Produktivdatenbank verfügbar) — Live gepusht (`versionId
  80cfff92-7441-427a-9b82-53a8a4f82a24`), beide neuen Nodes vorhanden, Erreichbarkeits-Check: keine
  toten Knoten, Workflow bleibt aktiv.
- **Testergebnis:** Struktur-/Live-Stand verifiziert, funktionaler Fehlerfall-Test noch ausstehend
  (siehe oben).

---

## Zusammenfassung (gesamt, inkl. Runde 3)

| # | Fix | Datei | Risiko | Getestet |
|---|---|---|---|---|
| 1-10 | siehe oben | 97,14,17,16,08,10 | — | — |
| 11 | WF06 Empfehlungs-Query begrenzt | 06 | keins (identisches Ergebnis) | ja, live |
| 12 | WF07 Empfehlungs-Query begrenzt + Kennzahlen ausgelagert | 07 | keins (Kennzahlen unverändert) | Live-Erreichbarkeit ja, Wertvergleich offen |
| 13 | Persistierungs-Erfolgsprüfung ergänzt | 17 | keins (macht nur Fehler sichtbar) | Struktur ja, echter Fehlerfall offen |

Alle 13 Fixes live gepusht, per `GET /workflows/{id}` verifiziert, lokale Repo-Kopien synchronisiert.
Nach Runde 3 verbleibt nur NEU-09-VERSION offen (jetzt mit vertiefter, korrigierter Begründung) sowie
die dokumentierte, nicht behobene Performance-Beobachtung zu `pipeline_runs` (kein DB-Index-Zugriff
möglich, siehe REVIEW_REPORT.md).

---

## 9. WF08-10 — Kursverlaufs-Queries auf Datumsfenster begrenzt + toter Benchmark-Zweig repariert

- **Geänderte Datei:** `08 – News-Wirkungsanalyse.json`
- **Workflow:** 08 – News-Wirkungsanalyse
- **Nodes:** "Distinkte Ticker extrahieren", "DB: Kursverlauf je Ticker laden",
  "Distinkte Benchmark-Symbole extrahieren", "DB: Benchmark-Kursverlauf laden" + neue Verbindung

**Dabei gefundener zusätzlicher Bug (nicht Teil der ursprünglichen 12 Prüfpunkte):** "Distinkte
Benchmark-Symbole extrahieren" hatte **keine eingehende Verbindung** im Workflow-Graph — bestätigt sowohl
statisch (Connections-Analyse) als auch live (der Node taucht in keiner der letzten 5 erfolgreichen
Ausführungen als ausgeführter Node auf, per `GET /executions?includeData=true` geprüft). Dadurch lief
"DB: Benchmark-Kursverlauf laden" nie, `benchmarkverlauf` blieb für jeden Ticker leer (durch die
`safeGrouped()`-Fehlerabfangung, die eigentlich nur den Fall "einzelner Ticker ohne Kurshistorie"
abfangen sollte, aber auch diesen strukturellen Fall stillschweigend maskierte), und
**`benchmark_return_d*`/`abnormal_return_d*` waren für JEDE Tracking-Zeile `NULL`** — die
"abnormale Rendite ggü. Markt"-Kennzahl, der analytische Kern von Workflow 08, wurde faktisch nie
berechnet. Da WF08-10 ohnehin beide Kursverlauf-Queries betrifft (Ticker UND Benchmark), wäre eine reine
Datumsbegrenzung der Benchmark-Query sonst eine Reparatur von totem Code gewesen — beides zusammen
behoben.

- **Alte Logik ("DB: Kursverlauf je Ticker laden" / "DB: Benchmark-Kursverlauf laden"):** `SELECT ...
  WHERE symbol = '...' AND valid_to IS NULL ORDER BY trading_date;` — komplette Historie, kein
  Startdatum.
- **Neue Logik:** "Distinkte Ticker extrahieren" berechnet jetzt je Ticker das früheste `news_date`
  aller offenen/neuen Tracking-Fälle und zieht 15 Kalendertage als Sicherheitspuffer ab (deckt auch
  längere Feiertags-/Wochenend-Lücken für die Rückwärtssuche des Baseline-Kurses sicher ab). Beide
  Queries bekommen `AND trading_date >= '{{ $json.lookback_from }}'::date`. "Distinkte Benchmark-Symbole
  extrahieren" wurde neu verdrahtet (Eingang: "Distinkte Ticker extrahieren", zusätzlich zur bestehenden
  Verbindung zu "DB: Kursverlauf je Ticker laden") und berechnet das früheste `lookback_from` je
  Benchmark-Symbol über alle zugeordneten Ticker (via Kreuzreferenz auf "DB: Instrumente
  (Benchmark-Zuordnung)"), inkl. Fallback `^GDAXI` bei fehlender Zuordnung.
- **Fachliche Auswirkung:** **Zwei echte Verhaltensänderungen.** (1) Beide Kursverlauf-Queries laden ab
  sofort nur noch den tatsächlich benötigten Zeitraum statt der kompletten Historie — deutlich weniger
  Datenvolumen pro Lauf, Grundineffizienz aus dem Audit behoben. (2) Der Benchmark-Zweig läuft ab sofort
  überhaupt zum ersten Mal — **künftige Tracking-Zeilen werden `benchmark_return_d*`/`abnormal_return_d*`
  tatsächlich befüllt bekommen**, was vorher nie der Fall war. Bereits bestehende Tracking-Zeilen mit
  `NULL`-Benchmark-Feldern bleiben unverändert (keine rückwirkende Neuberechnung in dieser Runde).
- **Regressionstest:** Isolierter Logiktest (`test_wf08_p8.js`, 3 Testfälle) vor dem Live-Push: TEST 1
  (frühestes `news_date` je Ticker korrekt gewählt + 15-Tage-Puffer), TEST 2 (gemeinsames
  Benchmark-Symbol nutzt das frühere von zwei Ticker-Lookback-Daten), TEST 3 (Ticker ohne
  Instrument-Mapping fällt auf `^GDAXI` zurück) — alle bestanden. Live-Push danach per
  `GET /workflows/EvJKlqkuSIu9CHmR` verifiziert: beide Queries enthalten `lookback_from`, neue
  Verbindung vorhanden, **vollständige Erreichbarkeits-Prüfung über alle Nodes des Workflows zeigt keinen
  unerreichbaren Node mehr** (vorher: "Distinkte Benchmark-Symbole extrahieren" + nachgelagert
  "DB: Benchmark-Kursverlauf laden"/"Benchmarkverlauf gruppieren" praktisch tot).
- **Testergebnis:** OK (isolierter Test bestanden, Live-Code-Stand + Erreichbarkeit verifiziert). **Kein
  Live-Lauf mit echter Beobachtung erstmals befüllter `benchmark_return_d*`-Werte in dieser Session
  durchgeführt** — nächster regulärer 19:00-Lauf (Werktage) sollte das bestätigen.

---

## 10. WF10-11 — Unbegrenzte Empfehlungs-Query begrenzt, All-Time-Kennzahlen bleiben exakt

- **Geänderte Datei:** `10 – Report- und Prüfagent.json`
- **Workflow:** 10 – Report- und Prüfagent
- **Nodes:** "DB: Empfehlungen laden" (geändert), neue Nodes "DB: Empfehlungs-Statistik laden" +
  "Wrap: DB: Empfehlungs-Statistik laden" + "Merge Grunddaten 19", "Reportdaten aufbereiten" (geändert)

**Vorab geklärter Datenbedarf (lt. REVIEW_REPORT.md nötig vor der Reparatur):** Live-Analyse ergab zwei
unterschiedliche Verwendungen derselben `SELECT * FROM trading.recommendations`-Zeilen in "Reportdaten
aufbereiten": (a) die komplette Rohliste geschlossener Positionen wird 1:1 in `empfehlungswatchlist`
verpackt und landet per `JSON.stringify(d.empfehlungswatchlist)` vollständig im Prüf-Agent-Prompt — wächst
unbegrenzt mit der Zeit, ohne fachlichen Mehrwert für einen Tagesreport; (b) `durchschnitt_performance_
geschlossen`/`trefferquote_geschlossen` (Trefferquote/Ø-Performance) werden aus ALLEN geschlossenen
Positionen aller Zeit berechnet — das sind echte, sinnvolle All-Time-Kennzahlen, deren Wert sich NICHT
ändern sollte, nur weil die Datenmenge begrenzt wird.

- **Alte Logik ("DB: Empfehlungen laden"):** `SELECT * FROM trading.recommendations ORDER BY id;` — alle
  Zeilen, egal wie alt.
- **Neue Logik:** `SELECT * ... WHERE status = 'offen' OR (status = 'geschlossen' AND exit_datum >=
  CURRENT_DATE - 90) ORDER BY id;` — offene Positionen (durch den bestehenden Unique-Index "ein offener
  Trade je Ticker" ohnehin klein) bleiben vollständig, geschlossene Positionen nur noch die letzten 90
  Tage (Rohliste für den Prompt).
- **Neuer Node "DB: Empfehlungs-Statistik laden"** (Aggregat-Query, ungefiltert über ALLE geschlossenen
  Positionen, liefert nur 3 Zahlen statt ganzer Zeilen):
  ```sql
  SELECT COUNT(*) AS anzahl_geschlossen_gesamt,
         ROUND(AVG(performance_pct), 2) AS durchschnitt_performance_geschlossen,
         ROUND(100.0 * COUNT(*) FILTER (WHERE performance_pct > 0) / NULLIF(COUNT(*), 0), 1) AS trefferquote_geschlossen
  FROM trading.recommendations WHERE status = 'geschlossen';
  ```
  Verdrahtet wie die übrigen "DB: X (Report)"-Zusatzquellen dieses Workflows: direkt am "Execute Workflow
  Trigger" hängend, über "Wrap: DB: Empfehlungs-Statistik laden" + neuen "Merge Grunddaten 19" in die
  bestehende Sequenzierungs-Kette vor "Reportdaten aufbereiten" eingehängt (identisches Muster wie z.B.
  "DB: Portfolio-Drawdown (Report)").
- **Code-Änderung in "Reportdaten aufbereiten":** `durchschnitt_performance_geschlossen`/
  `trefferquote_geschlossen` kommen jetzt aus `safeAll('DB: Empfehlungs-Statistik laden')[0]` statt aus
  einer JS-Berechnung über die (jetzt 90-Tage-begrenzte) `empfehlungenRows`-Liste — dadurch bleiben beide
  Kennzahlen exakt All-Time-korrekt, unabhängig von der Datumsbegrenzung der Rohliste. Neues Feld
  `anzahl_geschlossen_gesamt` ergänzt (echte Gesamtzahl); `anzahl_geschlossen` bleibt wie bisher die
  Größe der (jetzt begrenzten) Rohliste.
- **Fachliche Auswirkung:** Prompt-Umfang für den Prüf-Agenten wächst nicht mehr unbegrenzt mit der Zeit.
  `durchschnitt_performance_geschlossen`/`trefferquote_geschlossen` liefern **exakt dieselben Werte wie
  vorher** (reine Performance-Optimierung, keine Änderung der berichteten Kennzahlen) — verifiziert durch
  die Trennung von Rohdaten-Query (begrenzt) und Aggregat-Query (unbegrenzt). Die im Prompt sichtbare
  Rohliste `empfehlungswatchlist.geschlossen` zeigt ab sofort nur noch die letzten 90 Tage statt der
  kompletten Historie.
- **Regressionstest:** Code-Grep bestätigt `anzahl_geschlossen` nur in "Reportdaten aufbereiten"
  referenziert (kein anderer Node hätte durch die Umbenennung/Ergänzung brechen können). Live-Push
  zunächst mit fehlender Verbindung zum neuen Statistik-Node gepusht (Node ohne Eingang, per
  Erreichbarkeits-Check sofort gefunden), korrigiert (Verbindung "Execute Workflow Trigger" →
  "DB: Empfehlungs-Statistik laden" ergänzt, wie bei allen anderen "DB: X (Report)"-Nodes), erneut
  gepusht und verifiziert. **Vollständige Erreichbarkeits-Prüfung über alle Nodes zeigt keinen
  unerreichbaren Node mehr.**
- **Testergebnis:** OK (Live-Code-Stand + Erreichbarkeit verifiziert). **Kein Live-Report-Lauf mit
  echtem Vergleich alter/neuer Kennzahlenwerte in dieser Session durchgeführt** — beim nächsten
  regulären Report-Lauf sollten `durchschnitt_performance_geschlossen`/`trefferquote_geschlossen` mit den
  zuletzt bekannten Werten übereinstimmen.

---

## 8. P17-3 / NEU-P17-3b — Worker-Automatisierung + atomarer Tage-Paket-Claim

- **Geänderte Datei:** `17 – Historische Simulation (Walk-Forward, Pilot ohne Nachrichten).json`
- **Workflow:** 17 – Historische Simulation
- **Betroffene Nodes:** "DB: Naechstes Tage-Paket laden" (geändert), neuer Node "Schedule Trigger:
  Simulations-Worker" (neu hinzugefügt)

**Vorprüfung (P17-3b, vor jeder Änderung durchgeführt):**
Der bestehende Lauf-Lock ("DB: Lauf-Lock beanspruchen") wurde analysiert: ein einzelnes atomares
`UPDATE ... WHERE (heartbeat IS NULL OR heartbeat < now() - interval '2 minutes') RETURNING id`.
Postgres serialisiert konkurrierende UPDATEs auf dieselbe Zeile (Row-Lock, Re-Check der WHERE-Klausel
nach dem Warten) — dieses Pattern ist für sich genommen race-safe. Zusätzlich bestätigt:
`settings.executionTimeout` des Workflows steht auf 120 Sekunden — n8n selbst killt eine Ausführung
spätestens nach 2 Minuten, was zur Heartbeat-Schwelle des Locks passt.

**Dabei gefundene neue Lücke (nicht Teil der ursprünglichen 12 Prüfpunkte):** "DB: Naechstes Tage-Paket
laden" war eine reine `SELECT ... WHERE status IN ('pending','running') LIMIT package_size` — ganz ohne
eigene Absicherung (kein `FOR UPDATE SKIP LOCKED`, kein Claim). Die Tabelle `simulation_run_steps` besitzt
bereits eine `heartbeat_at`-Spalte, die aber nirgends für einen Claim genutzt wurde (nur beim Abschluss
eines Steps auf `now()` gesetzt). Solange nur ein einziger Worker-Trigger existierte (Manual Trigger),
war das irrelevant. Mit einem automatischen Schedule Trigger wäre diese Query der einzige Schutzmechanismus
gegen doppeltes Verarbeiten desselben Tage-Pakets bei zwei zeitlich nah beieinander liegenden Ticks gewesen
— und sie bot keinen.

- **Alte Logik:**
  ```sql
  SELECT * FROM trading.simulation_run_steps
  WHERE simulation_run_id = {{ $json.id }} AND status IN ('pending','running')
  ORDER BY sequence_number LIMIT {{ $json._package_size }};
  ```
- **Neue Logik:**
  ```sql
  UPDATE trading.simulation_run_steps SET status = 'running', heartbeat_at = now()
  WHERE id IN (
    SELECT id FROM trading.simulation_run_steps
    WHERE simulation_run_id = {{ $json.id }}
      AND (status = 'pending' OR (status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < now() - interval '2 minutes')))
    ORDER BY sequence_number LIMIT {{ $json._package_size }}
    FOR UPDATE SKIP LOCKED
  ) RETURNING *;
  ```
  Nutzt dasselbe Heartbeat-Muster wie der bestehende Lauf-Lock, plus `FOR UPDATE SKIP LOCKED` für echte
  Postgres-seitige Nebenläufigkeitssicherheit (zwei parallele Claims auf dieselben Zeilen sind damit
  unmöglich, unabhängig von Timing-Annahmen). Downstream ("Baue Paket-Kontext") filtert bereits
  Items ohne `.id` heraus, wodurch der `{"success":true}`-Platzhalter bei 0 zurückgegebenen Zeilen
  (wie bei anderen UPDATE...RETURNING-Claims in diesem Projekt) bereits korrekt abgefangen wird — keine
  zusätzliche Änderung dort nötig.
- **Neuer Node "Schedule Trigger: Simulations-Worker":** `n8n-nodes-base.scheduleTrigger`, Intervall
  ursprünglich 1 Minute, nach Rückfrage des Nutzers ("ist jede Minute nicht zu viel?") auf **5 Minuten**
  reduziert — Grund: ein 1-Minuten-Trigger erzeugt Dauerlast auf der Instanz auch bei inaktivem Lauf
  (jeder Tick durchläuft trotzdem "nächsten aktiven Lauf finden" + Zustandsprüfung), was direkt nach der
  heutigen Scheduler-Überlastungs-Krise vermeidbar unnötiges Risiko gewesen wäre. Bei `_package_size` = 20
  Tagen/Tick bedeutet 5 Min. Intervall ~125 Min. Gesamtlaufzeit für einen 500-Tage-Backtest — für eine
  nicht zeitkritische Hintergrund-Simulation unproblematisch. Gleiche Zielverbindung wie "Manueller
  Trigger: Simulations-Worker" (→ "DB: Naechsten aktiven Lauf finden"). Beide Trigger bleiben nebeneinander
  bestehen (manueller Trigger weiterhin für gezielte Einzelläufe nutzbar).
- **Aufräumen:** verwaiste `staticData`-Einträge zweier zuvor gelöschter Schedule-Trigger-Versuche
  ("... alle 1 Min", "... alle 3 Min") entfernt.
- **Fachliche Auswirkung:** Historische Simulationsläufe schreiten künftig automatisch alle ~1 Minute
  ein Tage-Paket weiter voran, ohne dass jemand manuell den Trigger klicken muss. Durch den atomaren
  Claim ist das auch dann sicher, wenn ein einzelner Tick sich der 2-Minuten-Grenze nähert.
- **Regressionstest:** Workflow per PUT aktualisiert, danach deaktiviert/reaktiviert (damit n8n den
  neuen Trigger-Node im Scheduler registriert — ein neuer Trigger-Node, der per API-PUT in einen
  bereits aktiven Workflow eingefügt wird, wird sonst nicht zuverlässig scharf geschaltet). Live per
  `GET /workflows/9JWDOTXFQWHYkypO` verifiziert: `active: true`, Schedule-Trigger-Node vorhanden mit
  5-Minuten-Intervall, korrekt verbunden, Claim-Query enthält `FOR UPDATE SKIP LOCKED`.
- **Testergebnis:** Code-Änderung und Live-Aktivierung verifiziert. **Kein Live-Simulationslauf über
  mehrere automatische Ticks hinweg in dieser Session beobachtet** — erster automatischer Lauf sollte
  beobachtet werden (Fortschritt in `backtest_runs.progress_percent` / `current_simulation_date` prüfen).
