# Finanz-Analyse-System

## Was ist das – und was bringt es mir?

**Kurz gesagt:** Dieses System beobachtet automatisiert Aktienkurse, Marktumfeld und Finanznachrichten für eine feste Beobachtungsliste von Aktien, bewertet sie mit Hilfe von KI und macht daraus konkrete, nachvollziehbar begründete Handelsvorschläge – inklusive Einstieg, Stop-Loss, Kursziel und Positionsgröße. **Es platziert niemals selbstständig eine echte Order bei einem Broker** – das ist eine bewusst fest eingebaute Grenze, keine Einstellung, die sich versehentlich ändern ließe.

Diese Dokumentation richtet sich zunächst an alle, die wissen wollen, was das System tut und welche Sicherheitsgarantien gelten – nicht an Techniker. Der technische Teil weiter unten ist für die Wartung gedacht und kann übersprungen werden.

### Was das konkret bedeutet

- **Kontinuierliche Beobachtung ohne manuellen Aufwand.** Tägliche Kursanalyse, Marktumfeld-Einschätzung und laufende Nachrichtenauswertung – ohne dass jemand von Hand Kurse verfolgen oder Nachrichten durchsuchen muss.
- **Nachvollziehbare Vorschläge statt Bauchgefühl.** Jede Handelsidee kommt mit Begründung, Chance-Risiko-Verhältnis und einem konkreten Positionsgrößenvorschlag – keine Blackbox-Empfehlung ohne Beleg.
- **Übt nur mit simuliertem Geld.** Das System führt selbstständig ausschließlich simulierte ("Paper-Trading") Positionen, um die eigene Trefferquote ehrlich zu messen. Dabei bewegt sich zu keinem Zeitpunkt echtes Geld.
- **Der Mensch entscheidet.** Jede Empfehlung wird angezeigt und muss von Hand angenommen, abgelehnt oder zurückgestellt werden – eine automatische Order-Ausführung an einen echten Broker existiert nicht.
- **Lernt aus der eigenen Historie.** Vergangene Einschätzungen werden gegen den tatsächlichen Kursverlauf geprüft; daraus abgeleitete Regel-Anpassungen werden vorgeschlagen, aber ebenfalls erst nach menschlicher Freigabe aktiv.
- **Volle Nachvollziehbarkeit.** Jede Entscheidung, jeder verwendete Datenpunkt und jede Regeländerung wird protokolliert und lässt sich im Nachhinein einsehen.

### Wie das grob funktioniert (ohne Technik-Details)

1. Kursdaten, Fundamentaldaten und Finanznachrichten werden automatisch eingesammelt.
2. Eine KI bewertet Marktumfeld, Einzeltitel und Nachrichtenrelevanz.
3. Daraus entstehen konkrete Handelsvorschläge mit Begründung und Risikoprofil.
4. Ein Mensch prüft jeden Vorschlag und entscheidet – das System selbst führt am echten Markt nichts aus.
5. Angenommene/abgelehnte Entscheidungen sowie die Ergebnisse simulierter Testläufe fließen zurück ins System, das daraus lernt.

Für alles Weitere – wie das im Detail technisch aufgebaut ist – richtet sich der Rest dieser Dokumentation an Personen, die das System warten oder weiterentwickeln.

## Technische Dokumentation

### Repo-Struktur

- **Workflows** liegen als n8n-Exporte im Repo-Root, nummeriert `00`–`19` plus Buchstaben-Varianten für eng verwandte Teilaufgaben (z.B. `02b`, `03a`, `09b`/`09c`, `16b`/`16c`/`16d`) sowie einige unnummerierte Web-UI-Seiten (Watchlist, RSS-Quellen, Trading-Entscheidungszentrale u.a.). Der Dateiname beschreibt jeweils die Funktion.
- **`sql/`** — alle Datenbank-Migrationen, fortlaufend nummeriert, Schema `trading`.
- **`docs/`** — fachliche Konzept-Dokumente (Strategiemodell, Risikomodell, Marktregime, Paper-Trading-Ledger, Backtesting, Ausführungsmodell u.a.) sowie einzelne laufend aktualisierte Umsetzungsberichte.
- **`trading_engine/`** — separater Python/FastAPI-Dienst, der Teile der Simulations-/Ausführungslogik nachbildet (schrittweise Migration von n8n-interner JS-Logik auf getesteten Python-Code).
- **`tools/`, `tests/`, `scratch/`** — Hilfsskripte, automatisierte Tests, Wegwerf-Debug-Skripte.
- **`n8n_live_backup/`** — Snapshots einzelner Workflows unmittelbar vor einer Live-Änderung.
- **`archive/`** — abgeschlossene, historische Planungs-, Audit- und Migrationsdokumente (siehe unten).

### Aktueller Stand

**[`OFFENE_AUFGABEN.md`](OFFENE_AUFGABEN.md)** ist die laufend gepflegte Liste offener Punkte und der verlässlichste Einstieg in den aktuellen Stand. Bei Unsicherheit dort nachsehen, nicht in den archivierten Dokumenten unten.

Weitere aktuell noch aktive Planungsdokumente: [`AKTIVIERUNGSPLAN_PAPER_TRADING.md`](AKTIVIERUNGSPLAN_PAPER_TRADING.md) / [`PRODUKTIONSFREIGABE_PAPER_TRADING.md`](PRODUKTIONSFREIGABE_PAPER_TRADING.md) (Freigabestatus des Paper-Trading-Betriebs, wird per datierten Nachträgen fortgeschrieben) und [`TRADING_ENGINE_MIGRATION.md`](TRADING_ENGINE_MIGRATION.md) (Umstellung von n8n-interner Simulationslogik auf den Python-Dienst, teilweise abgeschlossen).

### Historie

Die ursprüngliche Migration vom alten "Aktienanalyse-System" zur aktuellen Multi-Agenten-Architektur (Juli 2026) sowie mehrere seither abgeschlossene Härtungs-, Reparatur- und Review-Zyklen (u.a. "Härtung Welle 1–3", der externe Code-Audit vom August 2026, die ursprüngliche Agenten-Migration) sind vollständig in [`archive/`](archive/) dokumentiert und dort archiviert, statt hier laufend mitgeführt zu werden.
