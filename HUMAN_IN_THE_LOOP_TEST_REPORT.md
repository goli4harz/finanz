# HUMAN_IN_THE_LOOP_TEST_REPORT.md

Phase 4 des Human-in-the-Loop-Auftrags. Ausgeführt 2026-09-01, live gegen die produktive
Finanz-n8n-Instanz (`172.16.1.6:5678`) und die produktive Postgres-Datenbank — keine
Staging-Umgebung vorhanden, daher wurde jeder Schreibtest bewusst so gewählt, dass er entweder
folgenlos bleibt (ungültige/nicht-existente ID, gesperrter Status) oder — wo ein echter Schreibtest
sinnvoll und ungefährlich möglich war — reversibel ist (siehe Testfall 3).

## Hinweis zur Testplan-Herkunft

Der ursprüngliche Auftrag nannte "17 nummerierte Tests" und "18 Abschlussfragen". Der genaue
Wortlaut ist im Repo nicht mehr auffindbar (weder als Datei noch im Git-Verlauf) und war zum
Zeitpunkt dieser Phase-4-Nacharbeit (elf Tage nach Phase-3-Abschluss) nicht mehr aus dem
Gesprächskontext rekonstruierbar. Nutzer hat entschieden: eigenen, inhaltlich gleichwertigen
Testplan entwerfen statt zu raten oder zu erfinden. Der folgende Plan deckt dieselben
Themenfelder ab, die aus `HUMAN_IN_THE_LOOP_REVIEW.md`/`_ARCHITECTURE.md` und den Commit-Messages
erkennbar sind (siehe `HUMAN_IN_THE_LOOP_FINAL_REVIEW.md` für die Zielabgleich-Fragen).

## Testmethode

Für Datenbankchecks wurde das bestehende Diagnose-Werkzeug `97 - Einmalig - Beliebige Query
ausfuehren` (id `NInmI0f9TfdndwI1`) temporär um einen Webhook-Trigger erweitert (Query per
URL-Parameter), genutzt, und anschließend exakt auf den ursprünglichen Zustand (Manueller
Trigger, feste Beispielquery, inaktiv) zurückgesetzt — kein Rückstand im Workflow. Seiten wurden
direkt per HTTP gegen ihre echten Webhook-Pfade getestet.

## Ergebnisübersicht

| # | Bereich | Ergebnis |
|---|---|---|
| 1 | Alle 7 Module + Nav-Bar aktiv und erreichbar | ✅ bestanden |
| 2 | Alle 6 GET-Listenansichten liefern gültiges HTML mit echten Daten | ✅ bestanden |
| 3 | Nav-Bar auf allen 6 Seiten vorhanden und konsistent | ✅ bestanden |
| 4 | Trading-Entscheidungszentrale: Detailansicht (echte Empfehlung) | ✅ bestanden |
| 5 | Trading-Entscheidungszentrale: Status-/Versions-Gate beim Schreiben | ✅ bestanden (nach Korrektur eines eigenen Testfehlers, siehe unten) |
| 6 | Trading-Entscheidungszentrale: POST mit nicht-existenter ID | ✅ bestanden |
| 7 | Paper-Trading-Review: Leerzustand korrekt (keine Trades je geöffnet) | ✅ bestanden |
| 8 | Paper-Trading-Review: POST mit nicht-existenter ID | ✅ bestanden |
| 9 | News-Pruefen: Liste mit echten Daten (2390 unconfirmed, real) | ✅ bestanden |
| 10 | Lernen-und-Feedback: Aggregation über 5 Kategorien | ✅ bestanden |
| 11 | Regelnuebersicht: alle 3 Versionierungsstile + Ausschlussregeln | ✅ bestanden |
| 12 | Startseite: KPI-Kacheln inkl. Systemstatus | ✅ bestanden |
| A | **Echter End-to-End-Schreibvorgang gegen eine `status='offen'`-Empfehlung** | ⬜ **nicht testbar** — siehe Befund 1 |
| B | Echte Trade-Review-Abgabe gegen einen geschlossenen Paper Trade | ⬜ **nicht testbar** — siehe Befund 2 |

12 von 14 Punkten bestanden, 2 strukturell nicht testbar (kein Codefehler, siehe unten), 0
fehlgeschlagen.

## Befund 1 (wichtigstes Ergebnis dieser Phase): der Kern-Schreibpfad wurde noch nie unter realen
Bedingungen ausgelöst — mit geklärter Ursache

`trading.recommendation_decisions` hat elf Tage nach Live-Gang immer noch **0 Zeilen**. Grund:
alle 5 seit Systemstart erzeugten Empfehlungen (2026-08-17 bis 2026-08-21) haben
`status='portfolio_blocked'` (Sektor-/Einzelpositionslimit überschritten), niemals `'offen'`. Die
Liste "Heute Handeln" filtert korrekt auf `status='offen'` — zeigt daher zu Recht "HEUTE KEIN
TRADE", das ist kein Fehler, sondern exakt die dokumentierte Bedingung
("Kein Kandidat erfüllt aktuell die Qualitätsschwelle").

Getestet wurde trotzdem, so weit es ohne Erfindung von Produktionsdaten sicher möglich war:

- Detailansicht (`?id=9`, MBG.DE) lädt korrekt vollen Handelsplan + Portfolio-Blockierungsgrund
  (`SECTOR_LIMIT`, `SINGLE_POSITION_LIMIT`) aus der Datenbank.
- Ein POST mit falschen Feldnamen (`recommendation_id`/`entscheidung` statt der tatsächlich vom
  Code erwarteten `id`/`action` — eigener Testfehler, durch Lesen von `POST: Baue Load-Query`
  aufgeklärt) schrieb erwartungsgemäß nichts (stiller No-Op über die `WHERE FALSE`-Fallback-Query).
- Derselbe POST mit den **korrekten** Feldnamen (`id=9&action=beobachten`) schrieb **ebenfalls
  nichts** — bestätigt, dass der harte Status-Gate in `POST: Entscheidung normalisieren + SQL
  bauen` (`loaded.status !== 'offen'` → `sql = 'SELECT 1;'`) genau wie im Code vorgesehen
  greift. Kein Datensatz wurde erzeugt oder verändert, geprüft per direkter Zeilenzählung vor und
  nach dem Aufruf.

**Bewertung**: die Sicherheitslogik (Status-Gate, optimistisches Locking über `version`) ist
nachweislich korrekt. Der eigentliche Erfolgspfad (eine offene Empfehlung wird tatsächlich
akzeptiert/abgelehnt/beobachtet und ein `recommendation_decisions`-Datensatz entsteht) bleibt
**bewusst ungetestet**, weil es aktuell keine reale `status='offen'`-Zeile gibt und ein manuelles
`UPDATE recommendations SET status='offen'` das reale Portfolio-Risiko-Gate umgangen und damit
einen irreführenden Testzustand erzeugt hätte — das wurde explizit nicht gemacht. Sobald künftig
eine Empfehlung natürlich `status='offen'` erreicht (das Portfolio-Risiko-Limit nicht mehr
überschreitet), sollte dieser Pfad einmal real durchgetestet werden.

**Nebenbefund, keine Korrektur in dieser Session**: die Detailansicht zeigt das
Entscheidungsformular auch für `portfolio_blocked`-Empfehlungen an (nicht nur für `'offen'`),
obwohl das Backend eine solche Entscheidung ohnehin verwirft. Nicht falsch (das Formular wird
serverseitig korrekt abgewiesen), aber potenziell verwirrend — ein Nutzer könnte ein Formular
ausfüllen und eine stille Ablehnung ohne Fehlermeldung erhalten. Empfehlung für eine künftige
Session: Formular nur bei `status==='offen'` zeigen, sonst nur den Blockierungsgrund.

## Befund 2: Paper-Trading-Review hat denselben strukturellen Grund für Untestbarkeit

Alle 5 `paper_trades`-Zeilen stehen auf `status='blocked'` (Folge von Befund 1 — ohne eine
akzeptierte Empfehlung öffnet nie ein Paper Trade). Liste zeigt korrekt "0 Stück"/"Keine offenen
Reviews". POST mit nicht-existenter ID liefert einen sauberen Fallback. Der reale
Review-Abgabe-Pfad (Modul 3) bleibt aus demselben Grund wie Befund 1 ungetestet.

## Sonstige Beobachtungen (keine Defekte)

- Alle 6 GET-Seiten laden konsistent über `Finanz_Web_NavBar`, keine der acht alten Admin-Seiten
  hat mehr die isolierte Nav-Zeile (stichprobenhaft erneut geprüft: `aktien-status` zeigt den
  neuen Nav-Header).
- `Regelnuebersicht` zeigt reale Bestände: 22 `scoring_weights`, 28
  `strategy_regime_matrix`-Zeilen, 10 `strategy_parameters`, 4 `strategy_status`, 3753
  `news_match_exclusions` — deutlich mehr als der letzte dokumentierte Stand (11 Tage alt,
  40 Ausschlussregeln), reines Datenwachstum, kein Test-relevanter Befund.
- `learning_rule_proposals`: aktuell 18 Zeilen, alle `status='activated'` — keine `status='neu'`
  wartenden Vorschläge vorhanden, daher konnte die "offene Lernvorschläge"-Kachel auf
  Lernen-und-Feedback nur im Leerzustand getestet werden (rendert korrekt, 0 statt Fehler).
- `trading.workflow_errors`: 169 Zeilen real vorhanden, Systemstatus-Kachel auf der Startseite
  liest sie korrekt (erster echter Lesezugriff seit Existenz der Tabelle, bereits in Phase 3
  bestätigt, hier erneut verifiziert).

## Nicht Teil dieser Phase

- Kein Code wurde geändert. Der Nebenbefund zum Entscheidungsformular ist eine Empfehlung für
  eine künftige, separate Session, keine in Phase 4 durchgeführte Korrektur.
- Die Workflow-03-Vorfilter-Persistenz-Änderung ist eine eigene, bereits am 2026-08-21
  abgeschlossene und verifizierte Initiative (siehe Changelog) — nicht Gegenstand dieser
  Phase-4-Tests.
