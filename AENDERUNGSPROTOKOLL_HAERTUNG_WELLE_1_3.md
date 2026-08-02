# Änderungsprotokoll — Härtung Welle 1-3

Stand: 2026-08-02. Kompakte Übersicht aller geänderten Dateien je Phase. Details/Begründung
je Fund in `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md`.

## Workflows

| Workflow | Phase(n) | Änderung | Live-Status |
|---|---|---|---|
| `07 – Status-Uebersicht` | 2, 12 | 12 Wrap-Nodes (Merge-Sicherheit); neuer Query-Node + Datenfrische-Banner in "Baue Uebersicht" | ✅ live, end-to-end getestet |
| `10 – Report- und Pruefagent` | 2 | 9 Wrap-Nodes (Merge-Sicherheit) | ✅ live, nicht end-to-end getestet (reale Seiteneffekte) |
| `13 – Markt-Screener` | 2, 8, 14 | 8 Wrap-Nodes; Universum-Trennung + echte relative Stärke; Execute Workflow Trigger + Envelope + Status-Fix in "Scan-Run: SQL bauen"; Eigen-Schedule deaktiviert | ✅ live (Workflow bleibt inaktiv) |
| `14 – Portfolio-Risiko und Paper-Trading` | 2, 4, 5, 6+7, 14 | 14 Wrap-Nodes; `data_error`-Retry-Wiederherstellung; Gap-through-Stop; `portfolio_pending`-Auflösung + Dead-Letter; Execute Workflow Trigger + konsolidiertes Envelope; Eigen-Schedule deaktiviert | ✅ live (Workflow bleibt inaktiv) |
| `02 – Technische Signale` | 9 | Mean-Reversion/Breakout-Direktionslogik gehärtet (echte UND-Bedingungen) | ✅ live (aktiv) |
| `05 – Tagesreport` | 11 | Hebelprodukt-Textzeile entfernt | ✅ live (aktiv) |
| `06 – Empfehlungswatchlist` | 6+7, 10, 11 | `portfolio_pending`-Status; `quantityByValue`/`QUANTITY_ZERO`-Veto; `hebelHinweis()` neutralisiert | 🟡 **fertig, nicht live** (Aktivierungsplan Stufe 2) |
| `00 – Tagesabschluss-Orchestrator` | 14 | 2 neue Feature-Flag-gated Stufen (13/14), Config-Erweiterung, Warnungs-/Teilstatus-Erweiterung | 🟡 **fertig, nicht live** (n8n-Publish-Constraint, Aktivierungsplan Stufe 1) |

## SQL-Migrationen

| Migration | Phase | Inhalt | Live ausgeführt |
|---|---|---|---|
| `sql/051_data_error_retry_reload.sql` | 4 | `paper_trades.pre_data_error_status` | ✅ |
| `sql/052_gap_through_stop.sql` | 5 | `raw_exit_price`, `effective_exit_price`, `gap_through_stop`, `gap_amount`, `execution_quality` | ✅ |
| `sql/053_recommendation_portfolio_status.sql` | 6+7 | `portfolio_pending`-Statusmodell, `ux_recommendations_one_active_per_ticker`, `MAX_PORTFOLIO_CHECK_ATTEMPTS` | ✅ |
| `sql/054_scanner_universum_relative_staerke.sql` | 8 | `watchlist_active`/`scanner_active`, `analysis_status` | ✅ |
| `sql/055_positionsgroesse_wertlimit.sql` | 10 | `risk_amount_before_limit`, `quantity_by_risk`, `quantity_by_value`, `position_size_limiting_factor` | ✅ |
| `sql/056_orchestrator_feature_flags.sql` | 14 | `ENABLE_MARKET_SCANNER`/`ENABLE_PAPER_TRADING`/`ENABLE_TRADE_LEARNING` (alle `FALSE`) | ✅ |

## Dokumentation

| Datei | Phase | Änderung |
|---|---|---|
| `docs/MARKTSCANNER.md` | 8, 14 | Universum-Trennung, relative Stärke, Orchestrator-Einreihung, Trigger-Update |
| `docs/PORTFOLIORISIKO.md` | 18 | `portfolio_pending`-Statusmodell, Rückstandsverarbeitung, `data_error`-Wiederherstellung |
| `docs/AUSFUEHRUNGSMODELL.md` | 18 | Gap-through-Stop |
| `docs/PAPER_TRADING_LEDGER.md` | 18 | `data_error`-Wiederherstellung, Phase-16-Bestätigung |
| `OFFENE_AUFGABEN.md` | 6, 14 | Sonderfall-Hinweise für `06` und `00` (Live/Repo-Divergenz) |
| `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md` | 1-17 | Laufendes Detailprotokoll |
| `TESTPLAN_HAERTUNG_WELLE_1_3.md` / `TESTERGEBNISSE_HAERTUNG_WELLE_1_3.md` | 17 | Testumfang/-ergebnisse |
| `AKTIVIERUNGSPLAN_PAPER_TRADING.md` | 18 | Stufenweise Aktivierung |
| `PRODUKTIONSFREIGABE_PAPER_TRADING.md` | 18 | Ampel-Bewertung |
| `ABSCHLUSSBERICHT_HAERTUNG_WELLE_1_3.md` | 18 | Gesamtbericht + Empfehlung |

## Neue Dateien

- `tests/welle_1_3_testsuite.js` (Phase 17)
- `n8n_live_backup/*_PRE_PHASE{2,12,14}_*.json` (PRE-Backups vor jedem Live-Push)
