# Markt-Screener (Welle 2, AP6)

Stand: 2026-08-01. Neuer Workflow `13 – Markt-Screener täglich`.

## Zweistufiges Vorgehen

**Stufe A (günstiges Screening)**: alle aktiven Ticker aus `trading.stock_instruments` (aktuell identisch mit der 15-Ticker-Watchlist — siehe "Bekannte Einschränkung" unten). Filter: aktiver Ticker, gültiger heutiger Kurs, Mindestkurs, Mindest-Tagesumsatz, keine harte Datenqualitätsstörung (`invalid`/`stale`), ausreichende Kurshistorie (≥20 Tage), bekannte Börse. Berechnet: relative Stärke 5/20/60 Tage, Volumenfaktor, Abstand zu 52-Wochen-Hoch/-Tief, Fundamentaltrend-Verfügbarkeit, News-Vorhandensein, Regime-Passung — zu einem `scan_score` (0–1) kombiniert.

**Stufe B (vertiefte Auswahl)**: Stufe-A-Überlebende mit `scan_score ≥ SCANNER_MIN_SCORE_FOR_STAGE_B` (Default 0.5), sortiert absteigend, unter drei konfigurierbaren Obergrenzen ausgewählt: `SCANNER_MAX_CANDIDATES_TOTAL` (15), `SCANNER_MAX_CANDIDATES_PER_STRATEGY` (5), `SCANNER_MAX_CANDIDATES_PER_SEKTOR` (3), zusätzlich hart gedeckelt durch `SCANNER_MAX_AI_CALLS` (15) als Sicherheitsnetz. Alle Schwellenwerte in `trading.pipeline_config`, zentral konfigurierbar (`sql/034`).

**Jeder** geprüfte Ticker (eingeschlossen oder nicht) wird mit maschinenlesbarem Grund in `trading.scan_candidates` gespeichert — keine stillen Ablehnungen (Auftragsvorgabe).

## Bekannte, bewusste Einschränkung: Datenuniversum == Watchlist

`trading.stock_instruments` enthält aktuell exakt die 15 DAX-Werte der bestehenden Watchlist (`sql/002`). Der Scanner-Mechanismus liest generisch `WHERE aktiv = TRUE` — er würde automatisch mehr Ticker erfassen, sobald der Nutzer MDAX/SDAX-Werte in `stock_instruments` einträgt (Auftragsvorgabe: "später erweiterbar"). **Heute** überschneidet sich das Scan-Ergebnis deshalb praktisch vollständig mit der Watchlist selbst — der Scanner liefert in diesem Zustand noch keinen eigenständigen Mehrwert an NEUEN Tickern, sondern vor allem eine unabhängige Zweitbewertung der bestehenden 15.

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

- ✅ Umgesetzt: beide Stufen, Konfiguration, Persistenz, Ausschlussgründe.
- 🔴 Nicht live getestet (siehe `docs/TESTPLAN_WELLE_2.md`).
- 🔴 Bewusst offen: Tiefenanalyse für Ticker außerhalb der täglichen `02`-Pipeline (nur relevant bei Universums-Erweiterung, siehe oben).
