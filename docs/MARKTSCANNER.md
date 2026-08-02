# Markt-Screener (Welle 2, AP6)

Stand: 2026-08-01. Neuer Workflow `13 – Markt-Screener täglich`.

## Zweistufiges Vorgehen

**Stufe A (günstiges Screening)**: alle aktiven Ticker aus `trading.stock_instruments` (aktuell identisch mit der 15-Ticker-Watchlist — siehe "Bekannte Einschränkung" unten). Filter: aktiver Ticker, gültiger heutiger Kurs, Mindestkurs, Mindest-Tagesumsatz, keine harte Datenqualitätsstörung (`invalid`/`stale`), ausreichende Kurshistorie (≥20 Tage), bekannte Börse. Berechnet: relative Stärke 5/20/60 Tage, Volumenfaktor, Abstand zu 52-Wochen-Hoch/-Tief, Fundamentaltrend-Verfügbarkeit, News-Vorhandensein, Regime-Passung — zu einem `scan_score` (0–1) kombiniert.

**Stufe B (vertiefte Auswahl)**: Stufe-A-Überlebende mit `scan_score ≥ SCANNER_MIN_SCORE_FOR_STAGE_B` (Default 0.5), sortiert absteigend, unter drei konfigurierbaren Obergrenzen ausgewählt: `SCANNER_MAX_CANDIDATES_TOTAL` (15), `SCANNER_MAX_CANDIDATES_PER_STRATEGY` (5), `SCANNER_MAX_CANDIDATES_PER_SEKTOR` (3), zusätzlich hart gedeckelt durch `SCANNER_MAX_AI_CALLS` (15) als Sicherheitsnetz. Alle Schwellenwerte in `trading.pipeline_config`, zentral konfigurierbar (`sql/034`).

**Jeder** geprüfte Ticker (eingeschlossen oder nicht) wird mit maschinenlesbarem Grund in `trading.scan_candidates` gespeichert — keine stillen Ablehnungen (Auftragsvorgabe).

## Universum jetzt strukturell von der Watchlist getrennt (Härtung Welle 1-3, Phase 8.1, 2026-08-02)

`trading.stock_instruments` hatte bisher nur ein einziges `aktiv`-Flag — Watchlist und Scanner-Universum waren dieselbe Menge, ohne dass das eine bewusste Entscheidung war. Live-Audit bestätigte: "DB: Universum laden" war **wörtlich identisch** mit der Watchlist-Query. Seit `sql/054` existieren zwei unabhängige Flags: `watchlist_active` (vom Nutzer bewusst beobachtet) und `scanner_active` (Teil des Scanner-Universums). Beide sind aus dem alten `aktiv`-Wert befüllt — **das Scan-Ergebnis überschneidet sich also weiterhin vollständig mit der Watchlist**, aber jetzt strukturell und dokumentiert, nicht zufällig. Eine Erweiterung (DAX/MDAX/SDAX) ist eine separate, künftige, bewusste Entscheidung (neue Zeilen mit `scanner_active=TRUE, watchlist_active=FALSE` anlegen) — kein automatischer Nebeneffekt dieser Migration.

## Relative Stärke jetzt echt berechnet (Härtung Welle 1-3, Phase 8.2, 2026-08-02)

**Bestätigter Fund**: die Funktion `relativeStrength()` berechnete ausschließlich eine Absolutrendite (Kursänderung über N Tage, ohne jeden Bezug zu einem Referenzwert) — exakt das im Härtungsauftrag verbotene Muster. Umbenannt zu `absoluteReturn()`; echte relative Stärke (`Aktienrendite − Referenzindexrendite`) kommt über die neue Funktion `relativeStrengthVsIndex()`, die `stock_instruments.benchmark_symbol` nutzt. Referenzindex-Kursdaten (`^GDAXI`, `^GSPC`, `^IXIC`, `^MDAXI`, `^STOXX50E`) liegen bereits in `trading.stock_price_history` (von `02b`s Marktregime-Berechnung mitgeladen) — keine neue Datenquelle nötig. `metrics_json` trägt jetzt getrennt `absolute_return_5/20/60` UND `relative_strength_5/20/60` + `relative_strength_status` (`estimated`/`not_available`) + `benchmark_used`. `sector_relative_strength` bewusst **nicht** berechnet — kein Sektor-Referenzindex im Datenuniversum verfügbar, `not_available` wäre der einzig ehrliche Wert für praktisch jeden Ticker.

## Stage B: Analysestatus vorbereitet, echter Tiefenanalyse-Workflow bewusst nicht gebaut (Phase 8.3)

`scan_candidates.analysis_status='pending'` (statt nur `included=true`) macht den Übergabezustand jetzt explizit abfragbar — aber **kein Workflow verarbeitet ihn aktuell**. Ein echter Tiefenanalyse-Workflow (Kursvalidierung, Strategiesignale, News, Fundamentaltrend, Regime, Opportunity/Risk/Evidence für Ticker außerhalb der täglichen `02`-Pipeline) wäre ein eigenständiges, größeres Projekt in der Größenordnung eines Teils von `02`/`06` — bewusst nicht als Unterpunkt dieser bereits sehr umfangreichen Härtungssitzung hineingepresst, um keine unvollständige/ungetestete Version zu bauen (gleiches Prinzip wie der zurückgestellte Trailing-Stop aus Welle 3). Eigenständiges Vorhaben für eine künftige Sitzung, sobald das Universum tatsächlich über die Watchlist hinaus erweitert wird.

## Zeitliche Reihenfolge (Phase 8.4) — siehe Phase 14

`13`s eigener Schedule-Trigger (18:20 Werktage) feuert bereits HEUTE nach `06`s tatsächlicher Ausführung (`06` läuft über `00` um 17:50, nicht über seinen eigenen — deaktivierten — 18:10-Trigger). Da `13` nicht in `00`s Orchestrator-Kette eingebunden ist, hat der Scanner faktisch schon jetzt einen T+1-Charakter innerhalb desselben Kalendertages: seine Ergebnisse fließen nie in denselben `06`-Lauf ein. Die eigentliche Korrektur (Scanner vor `06` in `00`s Kette einreihen) ist Teil von Phase 14.

## Bekannte, bewusste Vereinfachung: keine neuen FastAPI-Aufrufe

Sowohl Stufe A als auch Stufe B laufen **ausschließlich** aus bereits vorhandenen DB-Daten (`technical_signals_history`, `strategy_signals`, `stock_price_history`, `fundamentals_history`, `market_regime`, News) — für das aktuelle Datenuniversum korrekt, da jeder Ticker bereits täglich von `01`/`02`/`02b` vollständig verarbeitet wird ("Der Scanner darf nicht ungefiltert alle Titel durch teure KI-Aufrufe schicken" — hier bereits durch Konstruktion erfüllt: 0 zusätzliche Aufrufe für das aktuelle Universum).

**Für ein größeres Universum** (Ticker außerhalb der täglichen `02`-Pipeline) fehlt Stufe B aktuell eine Tiefenanalyse-Fähigkeit: ein Kandidat ohne heutige `strategy_signals`-Zeilen wird mit dem expliziten Grund `"Ticker außerhalb der täglichen 02-Pipeline"` von Stufe B ausgeschlossen, statt einen Ad-hoc-FastAPI-Aufruf und eine parallele Kopie der technischen Analyse zu bauen. Das hätte eine tiefere Restrukturierung von `02` (dynamische statt feste Watchlist) vorausgesetzt — bewusst auf Welle 3 verschoben, wenn das Universum tatsächlich über die aktuelle Watchlist hinaus erweitert wird.

## Keine automatische Wirkung auf die Watchlist oder auf `06`

Der Scanner **schreibt nicht** in `trading.recommendations`, **aktiviert oder löscht keine** `stock_instruments`/`watchlist`-Zeilen (Auftragsvorgabe wörtlich befolgt) und wird von `06`s automatischer Öffnen-/Schließen-Logik **nicht** gelesen. Er ist ein rein beobachtendes, historisiertes Werkzeug für Dashboard/Report — jede Konsequenz (z. B. einen Scan-Kandidaten zur Watchlist hinzuzufügen) bleibt eine manuelle Entscheidung des Nutzers.

## Datenmodell

`trading.scan_runs` (ein Lauf, mit Universumsgröße/Stufen-Zählern/Konfigurations-Snapshot) und `trading.scan_candidates` (jeder geprüfte Ticker je Stufe, `run_id`-verknüpft statt Fremdschlüssel — vermeidet eine Zwei-Phasen-Schreibreihenfolge im n8n-Workflow, gleiches Muster wie `trading.recommendation_veto_log` aus Welle 1).

## Trigger

`Manueller Start` (Test) + `Trigger: Scanner (18:20 Werktage)` — nach `02`/`02b` (18:00/17:55) und `06` (18:10), damit alle Datenquellen für den Lauftag bereits vollständig sind.

## Status

- ✅ Umgesetzt: beide Stufen, Konfiguration, Persistenz, Ausschlussgründe, echte Universums-Trennung (Phase 8.1), echte relative Stärke (Phase 8.2), Stage-B-Analysestatus (Phase 8.3, strukturell).
- 🔴 Nicht live getestet (siehe `docs/TESTPLAN_WELLE_2.md`).
- 🔴 Bewusst offen: der eigentliche Tiefenanalyse-Workflow für Stufe B (Phase 8.3) und die Orchestrator-Einreihung vor `06` (Phase 8.4/14).
