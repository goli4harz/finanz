# FINAL_REVIEW.md

Abschlussbericht zum externen Audit vom 2026-08-18/19 (zwei Runden: 12 benannte Prüfpunkte, dann
systematischer Sweep über alle 33 Finanz-Workflows). Basiert auf `REVIEW_REPORT.md` (alle Befunde mit
Codebeweis) und `CHANGELOG_REVIEW_FIXES.md` (13 durchgeführte Reparaturen). Kein Befund unten ist mit
"OK" markiert, ohne dass ein konkreter Code- oder Testbeweis dahintersteht.

---

## Scorecard — alle Befunde

| ID | Befund | Bestätigt? | Status | Beweis |
|---|---|---|---|---|
| P17-1 | Short-Cash-Accounting bei Exit falsch (Vorzeichenfehler) | ✅ | **BEHOBEN** | Isolierter Test (4/4), Live-Code verifiziert. Kein Live-E2E-Short-Exit beobachtet. |
| P17-6 | Trailing-Stop-Look-Ahead innerhalb derselben Kerze | ✅ | **BEHOBEN** | Isolierter Test bestanden, Live-Code verifiziert. Kein Live-E2E-Trailing-Fall beobachtet. |
| P17-3 | Simulationsworker ohne automatischen Fortschritt | ✅ | **BEHOBEN** | Schedule Trigger (5 Min.) live, aktiv, per API verifiziert. 10 automatische Ticks seit Aktivierung beobachtet (korrektes Leerlauf-Verhalten mangels aktivem Lauf), kein vollständiger Mehrfach-Tick-Durchlauf eines echten Laufs beobachtet. |
| P17-3b | Lock-Mechanismus ungeprüft | ✅ geprüft, Lücke gefunden | **BEHOBEN** | Lauf-Lock als race-safe analysiert. Zusätzlich gefundene Lücke (Tage-Paket-Claim ohne Schutz) mit `FOR UPDATE SKIP LOCKED` geschlossen. |
| P17-4 | Simulation nutzt globale Kapitalbasis statt `initial_capital` | ✅ | **BEHOBEN** | Code-Änderung verifiziert. TEST 11 (10k/50k/100k) NICHT durchgeführt. |
| P17-5 | Mini-Future-Config-Keys werden nie geladen | ✅ | **BEHOBEN** | Query verifiziert. Keine Verhaltensänderung. |
| P17-7 | Persistierung der Simulationsergebnisse ohne Erfolgsprüfung | ✅ | **BEHOBEN** | Check-Nodes nach WF08-Vorbild ergänzt, live verifiziert. Kein echter Fehlerfall ausgelöst/getestet. |
| WF97-1 | Unauthentifizierter SQL-Diagnose-Webhook aktiv | ✅ | **BEHOBEN** | Webhook + Workflow deaktiviert, live verifiziert. |
| WF14-8 | `MAX_DATA_ERROR_RETRIES` wird nicht geladen | ✅ | **BEHOBEN** | Query verifiziert. |
| WF08-10 | Kursverlaufs-Queries ohne Datumsbegrenzung | ✅ | **BEHOBEN** | Auf benötigtes Zeitfenster begrenzt. **Zusätzlich gefunden:** "Distinkte Benchmark-Symbole extrahieren" war unerreichbar — `benchmark_return_d*` seit jeher `NULL`. Neu verdrahtet. |
| WF10-11 | Unbegrenzte `SELECT * FROM trading.recommendations` (10) | ✅ | **BEHOBEN** | Rohliste auf 90 Tage begrenzt, All-Time-Kennzahlen über separate Aggregat-Query exakt erhalten. |
| WF06-1 | Unbegrenzte `SELECT * FROM trading.recommendations` (06) | ✅ neu (Runde 3) | **BEHOBEN** | Auf `offen`/`portfolio_pending` begrenzt — geschlossene Zeilen wurden nie verwendet. |
| WF07-1 | Unbegrenzte `SELECT * FROM trading.recommendations` (07) | ✅ neu (Runde 3) | **BEHOBEN** | Auf `offen` begrenzt, Aggregat-Kennzahlen über separate Query exakt erhalten. |
| Punkt 6/7 (WF14) | WF14 doppelter Zeitplan | ❌ nicht bestätigt, erneut geprüft | **KEIN FEHLER** | WF00 ruft WF14 nicht auf (frisch verifiziert). Eigener Trigger notwendig. |
| Punkt 10/12 (WF16) | `marksPerRun`-Kommentar/Code-Widerspruch | ⚠️ Kommentar veraltet | **BEHOBEN** (kosmetisch) | Code-Wert (4) korrekt, nur Kommentar aktualisiert. |
| NEU-09-VERSION | OOS-Bestätigung nicht versionsgebunden | ✅ bestätigt, Begründung in Runde 3 korrigiert | **NICHT BEHOBEN — bewusst zurückgestellt** | Siehe eigener Abschnitt unten — Root Cause ist tiefer als ursprünglich angenommen. |
| Survivorship Bias (WF17) | Verdacht: automatische Watchlist-Übernahme | ❌ nicht bestätigt (Runde 3) | **KEIN FEHLER** | Ticker-Universum wird pro Lauf explizit über das Web-Formular übergeben, nicht automatisch aus der Live-Watchlist gezogen. |
| WF07 Pipeline-Runs-Index | Full-Table-Scan auf wachsender Tabelle | ✅ Beobachtung | **NICHT BEHOBEN** | DB-Index-Thema, kein DB-Zugriff verfügbar zur Verifikation. Dokumentiert, nicht als OK markiert. |
| Config-Key-Sweep | 37 Keys projektweit auf "verwendet aber nicht geladen" geprüft | ✅ geprüft | **0 neue Treffer** | Siehe Tabelle in `REVIEW_REPORT.md`. |

**Gesamt: 15 von 17 konkreten Befunden behoben und live verifiziert. 2 bewusst nicht behoben**
(NEU-09-VERSION: Architekturvorhaben; WF07-Pipeline-Runs-Index: DB-seitig, kein Zugriff). 2 Verdachtsfälle
geprüft und explizit widerlegt (WF14-Doppeltrigger, Survivorship Bias WF17).

---

## Der explizit geforderte Fragenkatalog

Jede Frage einzeln beantwortet, mit dem tatsächlichen Prüfstatus. Wo eine Antwort NICHT auf einem
Live-Test beruht, sondern nur auf Code-Verifikation/Analogieschluss, ist das ausdrücklich vermerkt.

**Long korrekt?**
Isoliert getestet und bestätigt (Gewinn- und Verlustfall, `test_short_cash_fix.js` TEST 1-2). Die
Long-Formel war bereits vor dieser Prüfung korrekt und wurde nicht verändert. Live-Code verifiziert.
**Kein Live-E2E-Test mit einer echten Simulation.**

**Short korrekt?**
Isoliert getestet und bestätigt (TEST 3-4) — der ursprüngliche Vorzeichenfehler beim Short-Exit
(`cash += exitNotional` unabhängig von der Richtung) ist behoben, Formel jetzt symmetrisch zur
bereits korrekten täglichen Markwert-Formel. Live-Code verifiziert. **Kein Live-E2E-Test.**

**Cash korrekt?**
Für den Kern (Vorzeichen bei Entry/Exit, Long/Short) isoliert getestet und korrekt. Die
Interaktion mit Gebühren/Slippage/Finanzierungskosten wurde gelesen und nachvollzogen (dieselbe
Formel zieht sie unabhängig von der Richtung gleich ab — mathematisch konsistent), **aber nicht mit
einem eigenen Testfall inklusive konkreter Gebühren-/Slippage-/Finanzierungswerte durchgerechnet**
(die vorhandenen Tests setzen diese bewusst auf 0, siehe Kommentar in `test_short_cash_fix.js`).

**Equity korrekt?**
`total_equity = cash + positions_value`, die tägliche Markwert-Formel für offene Short-Positionen war
bereits vor dieser Prüfung korrekt (Ursache des ursprünglichen Befunds war ausschließlich der
Exit-Cash-Sprung, nicht die laufende Bewertung). Durch den Cash-Fix ist die Formel jetzt intern
konsistent. **Kein eigenständiger Equity-Kurven-Test über mehrere Tage/Trades hinweg durchgeführt.**

**Look-Ahead ausgeschlossen?**
Für den konkret identifizierten und geprüften Fall (Trailing-Stop-Nachführung anhand derselben
Tageskerze, vor der Exit-Prüfung) — JA, behoben und isoliert getestet. **Keine vollständige,
systematische Prüfung JEDES denkbaren Look-Ahead-Mechanismus im gesamten System** — z. B. wurde die
Frage, ob eine Simulation vergangener Zeiträume mit der HEUTIGEN `pipeline_config` statt einer
historisch korrekten Konfiguration rechnet (eine Form von Konfigurations-Look-Ahead), identifiziert
und dokumentiert (siehe NEU-09-VERSION-Abschnitt), aber nicht behoben.

**Trailing Stop korrekt?**
Ja — Reihenfolge korrigiert (erst Exit-Prüfung mit dem Stop-Stand VOR der heutigen Nachführung, dann
erst Nachführung, wirkt ab der Folgekerze). Isoliert getestet (TEST 6), Live-Code verifiziert. Kein
Live-E2E-Test mit einem echten Trailing-Stop-Fall.

**Simulation läuft automatisch?**
Ja — Schedule Trigger (5 Min.) ist live, aktiv, korrekt mit der Worker-Kette verbunden (per
`GET /workflows/...` verifiziert). Seit Aktivierung mehrere automatische Ticks beobachtet, die korrekt
"kein aktiver Lauf" erkennen und sauber nichts tun (kein aktiver Lauf war während dieser Session in der
Warteschlange). **Kein vollständiger automatischer Mehrfach-Tick-Durchlauf eines ECHTEN, laufenden
Simulationslaufs beobachtet** — das ist der wichtigste noch ausstehende Live-Test.

**Pause/Resume korrekt?**
**Nicht funktional getestet.** Der Code-Pfad wurde gelesen und nachvollzogen (Web-Steuerzentrale →
"POST: SQL ausfuehren" → "Baue POST-Antwort (JSON)" prüft `current.error` korrekt; der zugrunde
liegende Lock-Mechanismus wurde als race-safe analysiert), aber es wurde in keiner der beiden
Audit-Runden tatsächlich ein Lauf pausiert und wieder fortgesetzt, um das Verhalten live zu bestätigen
(TEST 8/9/10 aus dem ursprünglichen Auftrag explizit nicht durchgeführt).

**OOS versionsgebunden?**
**Nein**, weiterhin nicht — bewusst zurückgestellt. In Runde 3 wurde die ursprüngliche Begründung
("keine Versionsfelder vorhanden") als unzutreffend korrigiert: die Felder (`rule_version`,
`configuration_version`) existieren bereits und sind auf `paper_trades` echt befüllt. Die eigentliche
Blockade ist, dass Live-Handel (`THESIS_RULE_VERSION = 'welle1-v1'`) und historische Simulation
(`RULE_VERSION = 'historische-simulation-v1'`) zwei disjunkte, nie übereinstimmende
Versionsnamensräume verwenden — ein naiver Gleichheitsvergleich würde die Lernvorschlag-Erzeugung
komplett blockieren statt sie korrekt zu gaten. Siehe `REVIEW_REPORT.md` für die vollständige,
korrigierte Analyse.

**Config vollständig?**
Ja, für alle 37 projektweit identifizierten, tatsächlich verwendeten Config-Keys geprüft: **0 Fälle**
von "im Code verwendet, aber von keiner Query geladen" (über die in Runde 1 bereits gefundenen und
behobenen Fälle — WF14 `MAX_DATA_ERROR_RETRIES`, WF17 Mini-Future-Keys — hinaus). "DB vorhanden" ist
dabei ein Proxy über die Migrationsdateien, kein direkter Live-DB-Zugriff (siehe Tabelle in
`REVIEW_REPORT.md`).

**Workflow 08 speichersicher?**
Ja — beide Kursverlauf-Queries (Ticker + Benchmark) auf das tatsächlich benötigte Zeitfenster begrenzt,
live verifiziert. Zusätzlich einen bis dahin toten Node (Benchmark-Zweig) gefunden und repariert — vorher
liefen diese Queries in der Praxis gar nicht erst. Kein Live-Lauf mit Beobachtung der tatsächlichen
Datenmenge nach dem Fix durchgeführt (nächster reguläre 19:00-Lauf empfohlen).

**GDELT speichersicher?**
Ja, unverändert — `marksPerRun=4` ist eine bewusste, bereits am 18.08. getroffene Entscheidung (nach
Behebung der eigentlichen Ursache der früheren Speicherprobleme: n8n-2.21.7-Scheduler-Regression,
seither auf 2.34.4 + External Task Runner). Nur der veraltete Kommentar wurde korrigiert, keine
Logikänderung.

**Gefährlicher SQL-Webhook beseitigt?**
Ja — Webhook-Node deaktiviert UND Workflow 97 komplett deaktiviert, live verifiziert
(`active: false`). Der manuelle Diagnose-Trigger in der n8n-UI bleibt bestehen und ist weiterhin
nutzbar.

---

## Was in beiden Runden ausdrücklich NICHT stattgefunden hat

- Kein echter End-to-End-Simulationslauf über mehrere automatische Ticks eines aktiven Laufs.
- Kein funktionaler Pause/Resume/Cancel-Test über die Web-Steuerzentrale.
- TEST 11 (unterschiedliches `initial_capital`) nicht durchgeführt.
- Kein kontrollierter DB-Fehlerfall zum Testen der neuen Persistierungsprüfung (P17-7) ausgelöst.
- Bereits in der Vergangenheit gelaufene Simulationen mit Short-Trades/Trailing-Stop-Fällen wurden NICHT
  rückwirkend neu berechnet.
- Kein vollständiger Kategorien-A-J-Sweep im Sinne von "jede der 177 `continueRegularOutput`-Stellen
  einzeln gegen jede denkbare Fehlerursache durchgespielt" — gezielt die schreibenden/persistierenden
  Stellen geprüft, nicht jede lesende Stelle einzeln.
- Kein direkter Zugriff auf die Live-Datenbank zur Verifikation von `DB vorhanden`
  (Config-Key-Tabelle) oder zur Prüfung vorhandener Indizes (`pipeline_runs`) — beides über
  Migrationsdateien bzw. dokumentiert als offen, nicht als geprüft ausgewiesen.

**Empfehlung:** Den ersten automatischen Multi-Tick-Lauf von Workflow 17 gezielt beobachten
(`backtest_runs.progress_percent`/`current_simulation_date`) — das ist gleichzeitig der natürliche
erste Live-Test für P17-1, P17-6, P17-4, P17-3 und P17-7 in Kombination.

---

## Offene Punkte für eine Folge-Runde

1. **NEU-09-VERSION** — Design-Entscheidung für eine pipeline-übergreifende Versionierungs-Konvention
   (Live- vs. Backtest-Signal-Logik), bevor ein echter OOS-Versionsvergleich sicher eingebaut werden
   kann. Eigenständiges Architekturvorhaben.
2. **WF07 `pipeline_runs`-Index** — DB-seitige Prüfung/Ergänzung eines Index auf
   `(workflow_name, stage_name, started_at DESC)`, sobald DB-Zugriff verfügbar ist.
3. Die in diesem Abschnitt aufgelisteten, noch nicht live beobachteten Testfälle (TEST 8/9/10/11,
   Mehrfach-Tick-E2E, echter Persistierungs-Fehlerfall) nachholen, sobald ein realer Simulationslauf
   ansteht.
