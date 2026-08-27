# Marktregime (Welle 2, AP3)

Stand: 2026-08-01. Berechnet in `02b` aus den 8 bereits vorhandenen Referenzsymbolen (DAX, MDAX, Euro Stoxx 50, Nasdaq, S&P 500, EUR/USD, Öl, Gold — siehe Node "Markt-Watchlist laden").

## Datengrundlage — was tatsächlich vorhanden ist

| Merkmal | Quelle | Status |
|---|---|---|
| Indextrend | `trend`/EMA20/EMA200 aus `Marktanalyse berechnen` | ✅ real berechnet |
| Realisierte Volatilität | 20-Tage-log-Returns aus den (seit Welle 2 auf `period=1y` umgestellten) Kursreihen | ✅ real berechnet |
| Relative Lage zu EMA20/EMA200 | EMA200 neu in Welle 2 ergänzt (benötigt ≥200 Handelstage, `period=1y` liefert ~252) | ✅ real berechnet, EMA200 `null` bei zu kurzer Historie statt Näherungswert |
| VIX/VSTOXX | — | ❌ **nicht im Datenuniversum vorhanden** — `stress_regime` wird stattdessen aus realisierter Volatilität + `markt_status`-Anteil (`risk_off`) abgeleitet, ein Proxy, kein Ersatz |
| Markt-/Makro-Nachrichten (EZB, Fed, Zinsen, Inflation, Konjunktur …) | `03`s bereits vorhandene Klassifikation (`wirkungsebene IN ('markt','makro')`, umfangreiche Keyword-Erkennung + KI-Einstufung) | ✅ **seit `regime-v2`** (2026-08-01, Folgeauftrag): mindestens eine stark negative Markt-/Makro-Nachricht desselben Tages löst `stress_regime='stress'` zusätzlich zur Kurs-/Volatilitätsprüfung aus — dieselbe Nachrichtenlage gilt bewusst für Europa und USA (keine Regionstrennung in den Nachrichtendaten vorhanden). Anzahl/Titel in `inputs_json.makro_news` nachvollziehbar. |
| EUR/USD, Öl, Gold | `Marktanalyse berechnen` (bereits vorhanden) | ✅ als `global`-Cross-Asset-Kontext (kein eigenes Trend-/Vol-Regime, nur ein grober Risk-Off-Hinweis aus starkem Goldanstieg) |
| Marktbreite (Advance/Decline etc.) | — | ❌ **nicht vorhanden**, `breadth_regime` bleibt immer `NULL`, absichtlich NICHT erfunden |
| Liquiditätsregime (aggregiert) | — | ❌ **nicht vorhanden**, `liquidity_regime` bleibt immer `NULL` |
| Sitzungsstatus | vereinfachte Wochentag+Uhrzeit-Prüfung je Region (Europe/Berlin bzw. America/New_York) | ✅ berechnet, aber vereinfacht — siehe unten |

Fehlende Merkmale werden **nicht** durch die KI oder eine Heuristik ersetzt, sondern bleiben `NULL`/`not_available` (Auftragsvorgabe, wörtlich befolgt).

## Regionen

- **Europa**: Durchschnitt/Mehrheitsentscheid aus `^GDAXI` + `^STOXX50E`.
- **USA**: aus `^IXIC` + `^GSPC`.
- **global**: Cross-Asset-Kontext aus EUR/USD, Öl, Gold — kein eigenes Trend-/Volatilitätsregime (dafür nicht konzipiert), `combined_regime` ist immer `'cross_asset_context'`, dient nur als Modifikator/Beobachtungswert, nicht als eigenständiges Handelsregime.

## Regime-Ableitung (`rule_version = 'regime-v1'`)

1. `trend_regime` = `bull`, wenn ≥50% der Region-Symbole über EMA20 stehen (`trend='Aufwärts'`), sonst `bear`.
2. `volatility_regime` = `high_vol`, wenn die durchschnittliche 20-Tage-realisierte-Volatilität > 30% p.a., sonst `low_vol`.
3. `stress_regime` = `stress`, wenn die Volatilität > 45% p.a. **und** mindestens die Hälfte der Symbole `markt_status='risk_off'` zeigen — sonst `none`.
4. `combined_regime`: `stress` sticht alles; sonst `bear_trend` bei klarer Bärenmehrheit (`bull_share ≤ 0.3`); sonst `bull_trend_low_vol`/`bull_trend_high_vol`/`sideways_low_vol`/`sideways_high_vol` je nach Trend×Volatilität; sonst `unknown`.
5. `regime_confidence` = Anteil tatsächlich verfügbarer Symbole × (1.0 falls Volatilität berechenbar, sonst 0.5).

## Strategie-Regime-Matrix (`trading.strategy_regime_matrix`, `rule_version = 'regime-matrix-v1'`)

Vollständige, versionierte Tabelle in `sql/032` — 4 Strategien × 7 Regime-Zustände (`bull_trend_low_vol`, `bull_trend_high_vol`, `sideways_low_vol`, `sideways_high_vol`, `bear_trend`, `stress`, `unknown`), je Eintrag ein `fit_multiplier` (0–1) und ein `blocked`-Flag. Beispiele: `mean_reversion` bei `stress`/`bear_trend` **blockiert** (`blocked=TRUE`), `trend_following` bei `bull_trend_low_vol`/`bear_trend` volle Eignung (1.0), `breakout` bei `stress` blockiert. `06` liest diese Tabelle direkt statt die Logik im JS zu duplizieren — eine Änderung der Matrix erfordert keinen Code-Push.

## Bekannte, bewusste Vereinfachung: Sitzungsstatus im Regime-Kontext

`02b`s `session_status` je Region ist eine **vereinfachte** Wochentag+Uhrzeit-Prüfung (kein Feiertagskalender, kein `stale`-Frischecheck) — bewusst getrennt von der **autoritativen** `trading.v_market_session_status`-View aus Welle 1 (die pro Einzelticker für harte Vetos genutzt wird und die Frische echter Kursdaten prüft). Der Regime-Sitzungsstatus dient nur der groben Einordnung ("ist die europäische/US-Sitzung gerade offen"), nicht als Veto-Grundlage.

## Status

- ✅ Umgesetzt: Trend-/Volatilitäts-/Stress-Regime je Region, kombiniertes Regime, versionierte Strategie-Regime-Matrix.
- 🔴 Bewusst nicht umgesetzt (keine Datenquelle): `breadth_regime`, `liquidity_regime` — Schema vorbereitet (`sql/032`), für Welle 3.
- 🔴 Nicht live getestet (siehe `docs/TESTPLAN_WELLE_2.md`).

## Nachtrag 2026-08-25 — historische Pilot-Variante in Workflow 17

Bis dahin berechnete die historische Simulation (Workflow `17`) gar kein Marktregime — `is_stress_regime` war im Aufruf der Trading-Engine hart auf `false` verdrahtet, unabhängig vom simulierten Datum. Grund: `17` ist explizit "Pilot ohne Nachrichten", das bezog sich aber nur auf News, nicht auf Regime — die Regime-Berechnung existierte dort schlicht noch nicht.

Für den `probability_estimates`-Producer aus `simulation_trades` (siehe `docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md`-Nachtrag) wurde die obige Regel-Version 1:1 in `17`s Code-Node "Verarbeite Tage-Paket (Engine)" nachgebaut, Point-in-time (aus `barsUpTo(ticker, day)` statt einem Live-FastAPI-Kursabruf), mit einer bewussten Abweichung:

- **Die Markt-/Makro-News-Stress-Bedingung (Punkt 3 oben, `regime-v2`-Folgeauftrag) wurde NICHT übernommen** — nur die ursprüngliche `regime-v1`-Bedingung (Volatilität + `risk_off`-Anteil) bleibt. Grund: `17` ist "ohne Nachrichten", und `historical_news` hat einen offenen, noch unreparierten Zukunftsdatum-Bug.
- `session_status`/`vorlaeufig` entfällt — historische Tageskerzen sind immer abgeschlossen, keine Intraday-Unterscheidung nötig.
- EMA200/`ueber_ema200` wird nicht nachgebaut — beeinflusst `combined_regime` auch live nachweislich nicht, nur `inputs_json`-Metadaten.
- Referenzticker-Universum identisch (7 der 8 Symbole — MDAX wird auch live nicht in der Regime-Formel verwendet), müssen aber erst per Workflow `15` für den jeweils simulierten Zeitraum importiert werden (kein automatischer Import).

`market_regime_at_entry` wird bei jedem neu eröffneten `simulation_trades`-Datensatz aus dem `combined_regime` der zur Trade-Region (Europa/USA) passenden Regionsberechnung gesetzt; bei anderen/fehlenden Regionswerten bleibt es `NULL` statt geraten.
