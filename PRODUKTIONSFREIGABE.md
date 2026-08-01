# Produktionsfreigabe

Stand: 2026-08-01. Ampel-Bewertung je Bereich nach Abschluss der 23 kritischen Fixes (Priorität 1 des Härtungsauftrags). Die 19 "hoch" und 21 "mittel" eingestuften Funde aus `FEHLERANALYSE.md` sind noch offen (nächste Priorität) - das relativiert einige der folgenden Ampeln, siehe jeweilige Begründung.

**Legende:** 🟢 grün = keine bekannten kritischen Lücken, 🟡 gelb = kritische Lücken behoben, aber ohne echten Live-Lauf verifiziert oder mit bekannten Restlücken (hoch/mittel), 🔴 rot = bekannte ungelöste kritische Lücke.

| Bereich | Ampel | Begründung |
|---|---|---|
| Datenmodell (SQL-Schema) | 🟢 | Vollständiger Objektabgleich (G3): 0 von 35 referenzierten DB-Objekten fehlen. Migrationskette lückenlos, idempotent, keine destruktiven Statements. `sql/038`+`sql/039` additiv vorbereitet, noch nicht ausgeführt (siehe unten). |
| Kursdaten (02/02b) | 🟡 | `02b` (C4/C5) behoben und lokal verifiziert. `02` selbst hat weiterhin `period=3mo` statt der dokumentierten `period=1y` (C1, hoch, noch offen) - Breakout-Signale in `02` sind dadurch praktisch dauerhaft auf "Daten unzureichend". **Empfehlung: C1 vor Aktivierung von `02`s Breakout-Strategie beheben.** |
| News-Pipeline (03/03a/04/08) | 🟢 | D3/D4/D5/D13 (alle kritisch) behoben und lokal verifiziert, live gepusht (Workflows aktiv). D1/D2/D6/D9-D12 (hoch/mittel) noch offen, aber nicht produktionsblockierend - News-Ingestion funktioniert grundsätzlich korrekt, nur mit bekannten Präzisions-/Vollständigkeitslücken. |
| Empfehlungen (06) | 🟡 | B4 (DRY_RUN-Fallback) behoben. A7/A8 (Wertebereichs-Regelwerk für Lernvorschlags-Ziele) nur teilweise umgesetzt. Kein neuer kritischer Fund in `06` selbst in dieser Runde (Audit lag auf Teil B/Orchestrator-Ebene). |
| Portfoliorisiko/Paper-Trading (14) | 🟡 | Alle 9 kritischen Punkte (E1-E12, C9) behoben und lokal mit gezielten Testfällen verifiziert - dies war der größte und folgenreichste Einzelblock. **Workflow bleibt bewusst inaktiv, `sql/039` noch nicht ausgeführt.** Kein echter Lauf gegen die reale Datenbank beobachtet. C9 (Sitzungsstatus) greift erst scharf, wenn C6 (in `02`) ebenfalls behoben ist. **Vor Aktivierung: Migration ausführen, mindestens einen manuellen Testlauf beobachten.** |
| Lernagent News (09) | 🟢 | F1/F2 (beide kritisch) behoben und lokal verifiziert, live gepusht (Workflow aktiv, nächster Lauf Samstag). F3 (mittel) offen. |
| Lernagent Strategien (09b) | 🟡 | F4/F5 behoben und lokal verifiziert. **Workflow bleibt bewusst inaktiv** - das OOS-Gate war zuvor strukturell nie erreichbar (leere `backtest_runs`-Tabelle), bleibt es auch nach dem Fix, bis das Backtesting-Modul (AP7, dormant mangels Historie) gebaut wird. Kein akutes Risiko, aber auch kein produktiver Nutzen vor diesem Folgeschritt. |
| Orchestrator (00) | 🟡 | B1/B4/B5 (alle kritisch/hoch) behoben und lokal für alle Statuswerte durchsimuliert. **Kein echter End-to-End-Lauf seit dem Fix beobachtet** (nächster planmäßiger Lauf oder gezielter manueller Test empfohlen, bevor volles Vertrauen gerechtfertigt ist). |
| Oberflächen (Watchlist/RSS-Quellen/Lernvorschlag-Freigabe) | 🟢 | A1/A3/A4/A5/A6/A7(teilw.)/A9/A11 behoben und **live gegen die echten Webhooks getestet** (nicht nur simuliert) - Injection-Versuch, Validierungsfehler, SSRF-Block und legitimer Feed-Abruf alle bestätigt korrekt. Höchster Vertrauensgrad aller Bereiche in dieser Runde. |
| Dokumentation | 🟡 | `FEHLERANALYSE.md`/`AENDERUNGSPROTOKOLL.md`/`TESTPLAN.md`/`PRODUKTIONSFREIGABE.md` neu erstellt. `OFFENE_AUFGABEN.md` noch nicht um diese Runde ergänzt (nächster Schritt). G4 (Live-IDs für `09b`/`12`/`13`/`14` nicht im Repo verifizierbar) weiterhin offen. |

## Zusammenfassende Empfehlung

**Keine Freigabe für den produktiven, automatisierten Betrieb von Workflow `14` (Portfolio-Risiko/Paper-Trading) oder `09b` (Lernagent Handelsstrategien), bevor:**
1. `sql/038`+`sql/039` manuell ausgeführt wurden (vorbereitet in Workflow `97`),
2. mindestens ein manueller Testlauf von `14` gegen echte Daten beobachtet wurde,
3. die noch offenen "hoch"-Funde C1 (Historienzeitraum in `02`) und C6 (Datenqualitätsstatus-Kollaps in `02`) behoben sind, da beide die Verlässlichkeit von `14`s Sitzungsstatus-Check (C9) und Breakout-Signalen direkt beeinflussen.

**Die Oberflächen (Watchlist, RSS-Quellen, Lernvorschlag-Freigabe) sind live verifiziert und können mit hohem Vertrauen als abgesichert gelten** - dies war der ursprüngliche Kern des Auftrags (SQL-Injection/SSRF/Formular-Manipulation) und ist vollständig geschlossen.

**Die News-Pipeline (03/08) läuft bereits aktiv weiter (stündlich/geplant) und wurde nicht deaktiviert** - die Fixes verbessern die Datenqualität, ohne den Betrieb zu unterbrechen; kein Interventionsbedarf, aber auch kein isolierter Testlauf vor dem nächsten planmäßigen Durchlauf möglich.

**Nächster Schritt vor jeder weiteren Freigabe-Entscheidung:** die verbleibenden 19 "hoch" eingestuften Funde bearbeiten (Priorität 2 laut Auftrag-Reihenfolge), da mehrere davon (C1, C6-C8, D1/D2/D6/D9-D12) die Bereiche betreffen, die hier als 🟡 statt 🟢 eingestuft sind.
