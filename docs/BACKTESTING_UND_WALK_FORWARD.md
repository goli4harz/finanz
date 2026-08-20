# Backtesting und Walk-Forward (Welle 3, AP7)

> **⚠️ VERALTET (Stand dieses Dokuments: 2026-08-01).** Der unten beschriebene "dormant"-Zustand
> ist seit `sql/057`/Workflow 17 (2026-08-03/04) überholt: die Backtest-**Ausführung** ist gebaut,
> live und wird aktiv genutzt (Web-Steuerzentrale, Worker-Zyklus, Lernvorschläge aus
> Simulationsläufen). Für den aktuellen Stand siehe stattdessen:
> - `docs/HISTORISCHE_SIMULATION_KONZEPT.md` und `docs/HISTORISCHE_SIMULATION_UMSETZUNGSBERICHT.md`
>   — das tatsächlich gebaute Konzept/System (Workflow 17, `sql/057`ff.).
> - `TRADING_ENGINE_ARCHITECTURE.md` — die Python-`trading_engine`-Neuimplementierung (2026-08-19/20),
>   die WF17/WF14s Logik testbar/versioniert nachbildet (noch nicht produktiv angebunden, siehe
>   Phase-8-Migration in `EXPERIMENT_PLATFORM_REVIEW.md`).
> - `EXPERIMENT_PLATFORM_REVIEW.md` — Bestandsaufnahme + Erweiterungen der Experimentierplattform
>   (Config-Snapshots, Point-in-Time, Champion/Challenger, Experiment-Register, Monitoring),
>   Stand 2026-08-20.
>
> Der Rest dieser Datei ist als historisches Dokument stehengelassen (zeigt die ursprüngliche
> Design-Absicht und die explizite Look-ahead-Bias-Vermeidung, die im späteren System eingehalten
> wurde), beschreibt aber nicht mehr den aktuellen Zustand.

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

## Status (zum Zeitpunkt 2026-08-01 — siehe Veraltet-Hinweis oben für den aktuellen Stand)

- 🟡 Schema vollständig, Mechanismus/Workflow für die eigentliche Ausführung noch nicht gebaut (siehe oben — bewusste Priorisierung, kein Versehen).
- 🔴 Keine Testdaten, keine Läufe — erwartungsgemäß bei einem 2 Wochen alten System.

**Nachtrag 2026-08-20:** beides überholt — Ausführung ist seit `sql/057`/Workflow 17 gebaut und
live, es existieren reale Läufe. Siehe Verweise im Veraltet-Hinweis am Dateianfang.
