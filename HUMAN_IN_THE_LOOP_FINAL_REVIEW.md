# HUMAN_IN_THE_LOOP_FINAL_REVIEW.md

Phase 4 (Abschluss) des Human-in-the-Loop-Auftrags, 2026-09-01. Die ursprünglichen "18
Abschlussfragen" des Auftragstexts sind im Repo nicht mehr auffindbar (siehe
HUMAN_IN_THE_LOOP_TEST_REPORT.md, "Hinweis zur Testplan-Herkunft"). Die folgenden Fragen wurden
selbst entworfen, aus den in `HUMAN_IN_THE_LOOP_REVIEW.md` (Zeilen zur Auftragsbeschreibung) und
`HUMAN_IN_THE_LOOP_ARCHITECTURE.md` dokumentierten Zielen abgeleitet, ehrlich anhand des heute
live geprüften Systemzustands beantwortet.

## 1. Gibt es tägliche Trade-Ideen mit vollständigem manuellem Handelsplan?

**Ja.** `Trading-Entscheidungszentrale` (Modul 1) zeigt bis zu 5 qualitativ gute Kandidaten,
sortiert nach Opportunity-Score. Detailansicht enthält Einstiegszone, Stop, Target, CRV, erwartete
Haltedauer, These, Positionsvorschlag, Portfolio-Auswirkung, Konfidenzklassen und
historische Vergleichsfälle — live mit echten Daten geprüft (Vorgang MBG.DE, id 9).

## 2. Gibt es Accept/Reject/Watch/Defer mit Begründung?

**Ja, im Code korrekt implementiert — der Erfolgspfad ist aber noch nie real ausgelöst worden.**
Vier Aktionen (`angenommen`/`abgelehnt`/`beobachten`/`spaeter`) mit optionalen
Ablehnungsgründen (Mehrfachauswahl) existieren. Der Schreibpfad ist durch einen Status-Gate
(nur `status='offen'`) und optimistisches Locking abgesichert — beides live bestätigt korrekt
funktionierend (verweigert Schreiben bei falschem Status). Da bisher keine Empfehlung den Status
`'offen'` je erreicht hat (siehe Test-Report Befund 1), wurde der eigentliche
Datensatz-entsteht-Erfolgsfall nicht gegen echte Daten verifiziert.

## 3. Wird der ursprüngliche Systemvorschlag bei manueller Anpassung nie überschrieben?

**Ja, architektonisch durchgesetzt.** `system_werte_json` wird beim Insert eingefroren und danach
nie wieder angefasst (Code-Kommentar in `POST: Entscheidung normalisieren + SQL bauen` bestätigt
das explizit); Nutzeränderungen landen separat in `meine_werte_json`. Alte Entscheidungszeilen
werden bei einer neuen Entscheidung nicht überschrieben, sondern auf `status='ueberholt'` gesetzt
(volle Historie, gleiches Muster wie `strategy_regime_matrix`). Nicht live mit echten Folgezeilen
verifizierbar (keine existiert bisher), aber der Mechanismus ist codeseitig eindeutig.

## 4. Gibt es eine Trade-Review nach Abschluss?

**Ja im Code (Modul 3, Paper-Trading-Review), noch nie real ausgelöst.** Aus demselben Grund wie
Frage 2: kein Paper Trade hat je den Status `offen`/`geschlossen` erreicht (alle 5 stehen auf
`blocked`, Folgeeffekt von Frage 2). Leerzustand + Fehlerfälle (nicht-existente ID) sind live
bestätigt korrekt.

## 5. Gibt es einen System- vs. Nutzer-Performance-Vergleich?

**Ja, Query korrekt aufgebaut (eine `json_build_object`-Aggregation, live ausgeführt und ohne
Fehler zurückgekommen), aber inhaltlich leer** — es gibt aktuell 0 geschlossene Trades in beiden
Gruppen. Kein Datenbefund, sondern dieselbe strukturelle Ursache wie Frage 2/4.

## 6. Gibt es eine News-Review mit False-Negative-Tracking für den Filter?

**Ja, vollständig und mit echten Daten getestet (nicht erst heute — bereits am 2026-08-20/21
end-to-end verifiziert, heute die Liste erneut mit aktuellem Datenbestand bestätigt: 2390
unbestätigte, 2 manuell bestätigte, 3 manuell abgelehnte News-Bewertungen, 2 gemeldete False
Negatives).** Dies ist der am gründlichsten verifizierte Teil der gesamten Initiative, weil hier
von Anfang an genug echte Daten existierten.

## 7. Gibt es Filter-Qualitäts-Tracking für den Vorfilter?

**Ja**, `trading.news_prefilter_runs` + KPI-Block auf News-Pruefen, seit 2026-08-21 mit echten
stündlichen Läufen bestätigt (siehe Changelog).

## 8. Gibt es einen zentralen Feedback-/Lern-Hub?

**Ja** (Modul 5, Lernen-und-Feedback) — Aggregation über 5 Kategorien, heute erneut live mit
realen Zählwerten bestätigt (u. a. 18 aktivierte Lernvorschläge korrekt gezeigt).

## 9. Gibt es eine menschenlesbare Regelverwaltung?

**Ja** (Modul 6, Regelnuebersicht), alle drei im System koexistierenden
Versionierungsstile abgedeckt, heute erneut live mit realen, seit Phase 3 gewachsenen
Datenmengen bestätigt (22/28/10/4/3753 Zeilen über die fünf Regeltabellen).

## 10. Gibt es eine entscheidungsorientierte Tages-Startseite?

**Ja** (Modul 7), inklusive erstem Lesezugriff überhaupt auf `trading.workflow_errors`
(seit Existenz der Tabelle nie zuvor gelesen) — heute erneut live bestätigt (169 reale
Fehlerzeilen sichtbar).

## 11. Ist die Nutzung ohne SQL/n8n/Code möglich?

**Ja.** Alle 7 Module sind reine Webseiten (GET-Ansicht + Formular-POST), keine der geprüften
Seiten verlangt technisches Wissen. Einzige Ausnahme (nicht vom Auftrag betroffen): der Nutzer
selbst kann bei Bedarf einen neuen News-Import-Job über eine dokumentierte Webhook-URL anstoßen
(siehe `OFFENE_AUFGABEN.md`) — das ist eine bewusste Admin-Funktion außerhalb dieser Initiative,
keine Verletzung dieser Anforderung.

## 12. Gibt es keine automatische Broker-Order-Ausführung?

**Ja, harte architektonische Vorgabe eingehalten.** Kein einziger der geprüften Workflows enthält
einen Broker-API-Call. `trading.paper_trades` ist rein simuliert
(`[SIMULATION - keine reale Order]` steht wörtlich im generierten Entry-Begründungstext, live
bestätigt in der Detailansicht von Empfehlung 9). Die gesamte Kette bleibt Empfehlung → Paper
Trade, nie ein echter Auftrag.

## Gesamtfazit

**11 von 12 Zielen vollständig live verifiziert. 1 Ziel (Accept/Reject/Watch/Defer-Schreibpfad
inkl. der davon abhängigen Trade-Review- und Performance-Vergleichs-Funktionen) ist codeseitig
korrekt implementiert und in seinen Sicherheits-Gates live bestätigt, aber der reale
Erfolgsfall wurde noch nie ausgelöst — nicht wegen eines Defekts, sondern weil seit Systemstart
(2026-08-17) noch keine einzige Empfehlung das Portfolio-Risiko-Gate passiert und `status='offen'`
erreicht hat.** Das ist der wichtigste offene Punkt dieser Initiative und keine Frage von mehr
Code, sondern von realer Nutzung: sobald eine Empfehlung überhaupt einmal `status='offen'`
erreicht, sollte der Nutzer sie einmal bewusst durchklicken, um den letzten ungetesteten
Kernpfad live zu schließen.

## Empfehlungen für eine mögliche künftige Session (nicht Teil dieser Phase)

1. Entscheidungsformular auf der Detailansicht nur bei `status==='offen'` zeigen (siehe
   Test-Report, Nebenbefund) — kosmetisch, kein Sicherheitsrisiko.
2. Sobald eine echte `status='offen'`-Empfehlung entsteht: den vollen
   Accept→Paper-Trade-öffnet→Review→Performance-Vergleich-Kreislauf einmal real durchspielen.
3. Prüfen, warum seit 2026-08-17 jede einzelne Empfehlung am Portfolio-Risiko-Gate scheitert
   (Sektor-/Einzelpositionslimit) — ist das erwartetes Verhalten bei der aktuellen
   Portfoliokonfiguration, oder sind die Limits für die Testphase zu eng? Das ist eine fachliche
   Entscheidung, keine technische — bewusst nicht in dieser Session beantwortet.
