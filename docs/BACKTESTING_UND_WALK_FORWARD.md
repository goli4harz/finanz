# Backtesting und Walk-Forward (Welle 3, AP7)

Stand: 2026-08-01. Schema (`trading.backtest_runs`/`backtest_trades`, `sql/037`) vollständig funktionsfähig, aber **bewusst dormant** — siehe Begründung unten.

## Warum dormant, nicht Platzhalter

Das System (Watchlist, `strategy_signals`, `paper_trades`) ist zum Zeitpunkt dieser Migration rund zwei Wochen alt. Ein Walk-Forward-Test verlangt mindestens ein Trainingsfenster, ein Validierungsfenster und ein Testfenster — mit `BACKTEST_MIN_WINDOW_DAYS=180` (Auftragsvorgabe: konservativ, keine Schein-Aussagekraft aus zu kurzen Fenstern) sind das mindestens 540 Tage Historie für einen einzigen sinnvollen Lauf. Ein Backtest, der heute gebaut und "leer" ausgeführt würde, hätte keine Aussagekraft und würde nur Scheingenauigkeit vortäuschen. Das Schema ist stattdessen so angelegt, dass es **organisch aktiv wird**, sobald genug Historie existiert — kein späterer Umbau nötig.

## Kein Rückwirkend-Anwenden des aktuellen Workflows (explizit ausgeschlossen)

Der Auftrag verbietet ausdrücklich, den aktuellen `06`/`14`-Workflow einfach rückwirkend auf heutige Daten anzuwenden — das wäre Look-ahead-Bias in Reinform (heutiges Wissen über Regime-Matrix-Feintuning, Strategieparameter etc. hätte damals nicht existiert). Ein echter Backtest-Lauf muss stattdessen:

1. Point-in-Time-Daten verwenden: `technical_signals_history`/`fundamentals_history`/`market_regime` **mit ihrem jeweiligen `valid_to`-Fenster zum simulierten Zeitpunkt**, nicht dem heutigen Stand.
2. Die damals gültige `rule_version`/`configuration_version` verwenden (siehe `docs/PAPER_TRADING_LEDGER.md`, AP10-Versionierung) — nicht die aktuelle.
3. `trading.backtest_trades.known_at_entry_json` als Nachweis pro Trade führen: ein Snapshot dessen, was zum simulierten Entscheidungszeitpunkt bekannt war.

## Testarten (Schema vorbereitet)

- **Walk-forward**: `train_window_*`/`validation_window_*`/`test_window_*` auf `backtest_runs`, rollierend.
- **Out-of-Sample**: `run_type='out_of_sample'`, ein festes, unangetastetes Testfenster — genau diese Läufe sind es, die `09b`s Lernvorschläge als Voraussetzung benötigen (`docs/LERNAGENT_HANDELSSTRATEGIEN.md`).
- **Baselines**: `run_type IN ('baseline_buy_hold','baseline_random','baseline_unfiltered_signal','baseline_old_logic','current_logic')` — die neue Logik gilt laut Auftrag nur dann als besser, wenn sie risikoadjustiert und nach Kosten Vorteile zeigt, nicht nur weniger Trades erzeugt.

## Was fehlt, um den Mechanismus tatsächlich zu befüllen

Kein neuer Workflow für die Backtest-**Ausführung** wurde in Welle 3 gebaut (bewusste Priorisierung: das Paper-Trading-Ledger selbst — die Datengrundlage jedes künftigen Backtests — hatte Vorrang). Sobald genug Historie vorliegt, ist der nächste Schritt ein Workflow, der `trading.strategy_signals`/`trading.market_regime`/`trading.fundamentals_history` mit ihren `valid_to`-Zeitstempeln reproduzierbar durchläuft und `backtest_runs`/`backtest_trades` befüllt.

## Status

- 🟡 Schema vollständig, Mechanismus/Workflow für die eigentliche Ausführung noch nicht gebaut (siehe oben — bewusste Priorisierung, kein Versehen).
- 🔴 Keine Testdaten, keine Läufe — erwartungsgemäß bei einem 2 Wochen alten System.
