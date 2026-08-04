# Umsetzungsbericht: Historische Daten, Walk-Forward-Simulation und Web-Steuerzentrale

Stand: 2026-08-04. Lebendes Dokument (wird nach jeder Phase aktualisiert, wie in
`HISTORISCHE_SIMULATION_KONZEPT.md` Abschnitt 8.5 vorgesehen) - Gegenstück zum Konzeptdokument,
das den *aktuellen tatsächlichen* Umsetzungsstand zeigt statt der ursprünglichen Planung.

## Status je Phase

| Phase | Inhalt | Status | Details |
|---|---|---|---|
| 1 | Konzept + Bestandsaufnahme | ✅ fertig | `HISTORISCHE_SIMULATION_KONZEPT.md`, commit `50bcd26` |
| 2 | SQL-Migration (`sql/057`) | ✅ fertig, ausgeführt | 15 neue/erweiterte Tabellen, live via Workflow 97 verifiziert |
| 3 | Workflow 15 (Marktdaten-Import) | ✅ fertig, live verifiziert | 33 Nodes, Job-/Worker-Muster, End-zu-Ende mit echtem Import bestätigt |
| 4 | Workflow 17 Kern (Walk-Forward ohne Nachrichten) | ✅ fertig, live verifiziert | 40+ Unit-Tests vor Einbettung, Positionsgrößen-Kappung (`sql/060`), atomarer Lauf-Lock |
| 5 | Workflow 16 (historische Nachrichten, GDELT) + 16b (KI-Bewertung) | ✅ fertig, live verifiziert | `sql/058`; 6+6 echte Bugs gefunden+behoben; **echte Root Cause eines wiederkehrenden Import-Fehlers erst 2026-08-04 gefunden** (siehe unten) |
| 6 | News-Integration in Workflow 17 (`news_event`-Signal + Widersprüchliche-News-Veto) | ✅ fertig, live verifiziert | Wiring live bestätigt; echtes Feuern eines News-Signals steht noch aus (Datenabdeckung) |
| 7 | Lern-/Out-of-Sample-Trennung | ✅ fertig, live verifiziert (mechanisch) | Neuer Workflow `09c`, `sql/061`; OOS-Gate live in beide Richtungen bewiesen (blockiert ohne OOS-Lauf, öffnet mit); noch kein echter Vorschlag entstanden (Fallzahl) |
| 8 | Web-Steuerzentrale | 🟡 teilweise (3 von ~8 Bereichen) | Übersicht, Lauf-Detail, Vergleich fertig; Datenqualität/Konfiguration/weitere offen |

## Phase 5/6 — am 2026-08-04 gefundene Root Cause (wichtig für künftige Sitzungen)

Ein wiederkehrender Fehler ("5 von 7 Tagen eines GDELT-Imports schlagen dauerhaft fehl") wurde
zunächst fälschlich einer `.item`-Paired-Item-Fragilität in Workflow 15 zugeschrieben (echter,
aber nicht ursächlicher Bug, trotzdem behoben). Die tatsächliche Ursache: Workflow 15s
Job-Auswahl-Query filterte **nie** nach `job_type` und griff sich dadurch gelegentlich
News-Import-Jobs von Workflow 16, die es dann fälschlich als Kursimport mit dem Fake-Ticker
"GDELT-GLOBAL" verarbeitete. Fix: `job_type = 'market_data'` ergänzt (Workflow 16 filterte
bereits korrekt nach `job_type = 'news'`). Seitdem läuft der Import fehlerfrei durch.

## Phase 7 — Details

**Kernbefund:** Workflow `09b` (Lernagent Handelsstrategien, LIVE) hatte bereits ein
Out-of-Sample-Bestätigungs-Gate eingebaut, das seit Systemstart blockiert war (0 geschlossene
Live-Paper-Trades) - der eigentliche Zweck der historischen Simulation ("schneller lernen als
in Echtzeit") wurde dadurch nicht erreicht.

**Umsetzung:** neuer Workflow `09c` als kontrollierter Klon von `09b` (gleiches Prinzip wie
Workflow 16b als Klon von `03`s KI-Bewertung - keine Änderung an der laufenden `09b` nötig
oder riskiert):
- Datenquelle `simulation_trades` statt `paper_trades`, per `simulation_run_id`-Parameter
  (`GET /webhook/lernagent-simulation?simulation_run_id=X`).
- OOS-Gate verschärft: der Bestätigungslauf muss zeitlich NACH dem Explorationszeitraum liegen
  (`start_date > Quelllauf.end_date`) - eine reine Existenzprüfung hätte erlaubt, eine
  Simulation durch sich selbst zu bestätigen.
- `learning_rule_proposals` um `data_source`/`source_run_id` erweitert (`sql/061`) - Audit-Trail
  für die manuelle Freigabe (Workflow 12).
- `Workflow 17` um `run_type`/`strategy_filter` erweitert (Formular + `create_run`-Handler +
  Kernlogik-Filter) inkl. Überschneidungs-Sperre (dieselbe Strategie darf nicht zweimal über
  denselben Zeitraum als Out-of-Sample bestätigt werden - p-hacking-Schutz).

**Live-Verifikation (Run 6, 72 echte Simulations-Trades):**
1. Ohne Out-of-Sample-Lauf: "Out-of-Sample-Bestätigung: nein" → 0 Vorschläge (Gate blockiert korrekt).
2. Nach Anlegen+Abschluss eines echten OOS-Testlaufs (`trend_following`, 2026-07-01–03,
   Lauf-ID 8): "Out-of-Sample-Bestätigung: ja" → Gate öffnet korrekt, aber weiterhin 0
   Vorschläge, weil die Fallzahl je Einzelstrategie (< 30 Trades bei 72 Trades über 4
   Strategien) nicht reicht - erwartetes, ehrliches Ergebnis.
3. Echter KI-Node (`GPT-5.4-mini`) angebunden und verifiziert (Execution 28241): Antwort
   `{"decisions":[]}`, korrekt leer.

**Zwei Live-Bugs dabei gefunden+behoben:**
- `Baue POST-Antwort (JSON)` (Workflow 17) stürzte nach Einführung der OOS-Sperre ab
  (`Cannot read properties of undefined (reading 'pairedItem')`) - die zusätzliche
  `SELECT EXISTS(...)`-Abfrage änderte die Item-Anzahl der Postgres-Antwort; behoben durch
  `runOnceForAllItems` + `.all()` statt `.item`.
- Beim manuellen Einfügen des echten KI-Node in `09c` (nach Anleitung in
  `workflow09c_lernagent_prompt.txt`) gingen zwei Dinge schief: der Referenztext landete als
  eine Nachricht ohne Rollentrennung statt der `systemPrompt`/`userPrompt`-Ausdrücke, und
  `Baue Lernagent-Prompt (Trades)` wurde versehentlich mitgelöscht. Per API-Parameter-Fix
  behoben (sicher, da der Node bereits existierte).

**Noch offen:** ein tatsächlich entstehender Vorschlag braucht entweder einen längeren
Explorationslauf (mehr Trades je Einzelstrategie) oder einen gezielt mit `strategy_filter`
eingeschränkten Explorationslauf; Steuerzentrale-Button ("Lernvorschlag aus diesem Lauf
ableiten") ist noch nicht gebaut (Webhook aber direkt nutzbar).

## Phase 8 — Details

Neuer Workflow `Simulation-Steuerzentrale`, 3 GET-Seiten nach dem etablierten Muster
(RSS-Quellen/Watchlist verwalten):
- **Übersicht** (`/webhook/simulation-uebersicht`): aktive Importe/Läufe, Datenumfang, letzte Läufe.
- **Lauf-Detail** (`/webhook/simulation-lauf?run_id=X`): KPIs, Equity-Kurve (Balkendiagramm),
  Trades, Fehler.
- **Vergleich** (`/webhook/simulation-vergleich`): Kennzahlen mehrerer abgeschlossener Läufe
  nebeneinander.

Bewusst nur Lesezugriff - Starten/Pausieren/Abbrechen bleibt auf den bestehenden
Workflow-15/16/17-Seiten (aus der gemeinsamen Navigation verlinkt).

**Live-Bug beim Bau gefunden+behoben:** mehrere parallele n8n-Verbindungen auf denselben
Zielnode führen NICHT zu einem "warte auf alle Quellen"-Merge, sondern lassen den Zielnode bei
jedem einzelnen Trigger nur mit EINER Quelle laufen ("Node X hasn't been executed"). Auf
sequentielle Kette umgestellt (identisches Muster zu Workflow 15/16/17s eigenen Seiten).

**Noch offen:** Datenqualität, Konfiguration und die übrigen im ursprünglichen Auftrag genannten
Bereiche (der vollständige Auftragstext mit der 8-Bereiche-Liste liegt nicht mehr komplett vor,
nur Teilzitate im Konzeptdokument Abschnitt 6).

## Methodik-Lektionen dieser Sitzung (projektübergreifend relevant)

1. **Bei mehreren plausiblen Ursachen für dasselbe Symptom nicht beim ersten Fund aufhören,
   wenn das Symptom danach weiter auftritt** - die `.item`-Fragilität in Workflow 15 war ein
   echter, aber nicht der ursächliche Bug für den GDELT-Import-Fehler; erst der Vergleich mit
   dem tatsächlichen Fehler-Item deckte die echte Ursache (fehlender `job_type`-Filter) auf.
2. **Mehrere parallele n8n-Verbindungen auf denselben Zielnode sind kein Merge** - immer
   sequentiell verketten, wenn mehrere Datenquellen vor einem gemeinsamen Verarbeitungs-Node
   gebraucht werden.
3. **Änderungen an der Rückgabeform eines Postgres-Multi-Statement-Blocks können nachgelagerte
   `.item`-Referenzen brechen**, auch wenn der eigentliche Bugfix nichts mit Paired-Items zu tun
   hatte - nach jeder SQL-Änderung, die die Anzahl zurückgegebener Zeilen/Statements ändert, die
   nachgelagerten Nodes erneut auf `.item`-Nutzung prüfen.
4. **Frisch importierte LangChain-Nodes per API sind absturzgefährdet** - Platzhalter-Pattern
   (Code-Node mit vollständigem Prompt als Kommentar + separate Textdatei) bewährt sich weiter;
   beim manuellen Ersetzen durch den Nutzer in der n8n-UI aber prüfen, ob dabei versehentlich
   ein benachbarter Node mitgelöscht oder die Rollentrennung verloren wurde (zweimal in diesem
   Projekt beobachtet: Workflow 16b und 09c).
5. **Workflow 97 lässt sich für Ad-hoc-SQL-Diagnosen temporär auf einen Webhook-Trigger
   umbauen** (PUT, aktivieren, curl, danach auf den Original-Zustand zurücksetzen) - reversibel,
   mehrfach in dieser Sitzung genutzt, wenn kein Nutzer-Klick verfügbar ist.
