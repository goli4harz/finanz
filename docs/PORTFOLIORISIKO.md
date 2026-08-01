# Portfoliorisiko (Welle 3, AP5+AP6)

Stand: 2026-08-01. Workflow `14`, Job A (`portfolio_risk_checks`) prüft **jede** von `06` neu vorgeschlagene Position, bevor sie im Ledger den Status `proposed` erreicht.

## Neun Limits (alle in `trading.pipeline_config`, `sql/036`)

| Limit | Default | Prüfung |
|---|---|---|
| `MAX_TOTAL_OPEN_RISK_PCT` | 6,0% | Summe aller offenen `risk_amount` / Modell-Portfolio, inkl. `STRESS_RISK_REDUCTION_FACTOR` (halbiert das Limit bei `combined_regime='stress'` in der Region der Position) |
| `MAX_SECTOR_EXPOSURE_PCT` | 15,0% | Summe `position_value` je Sektor |
| `MAX_SINGLE_POSITION_PCT` | 8,0% | Einzelposition (schärfer als Welle 1s `MAX_POSITION_VALUE_PCT`, das nur den Einzeltrade isoliert betrachtet) |
| `MAX_OPEN_POSITIONS` | 10 | Anzahl gleichzeitig offener/vorgeschlagener Positionen |
| `MAX_DIRECTIONAL_EXPOSURE_PCT` | 40,0% | Summe `position_value` je Richtung (long/short) |
| `MAX_PORTFOLIO_DRAWDOWN_PCT` | 15,0% | Realisierter Drawdown seit Systemstart (aus `net_pnl` aller geschlossenen Trades, Equity-Kurve/Peak-Verfahren) — blockiert **alle** neuen Eröffnungen, nicht nur die aktuelle |
| `MAX_PAIRWISE_CORRELATION` | 0,75 | Pearson-Korrelation der Tagesrenditen (`CORRELATION_LOOKBACK_DAYS`, Default 60) zwischen Kandidat und jeder offenen Position |
| `STRESS_RISK_REDUCTION_FACTOR` | 0,5 | Multiplikator auf das Gesamtrisiko-Limit im Stress-Regime |

## Entscheidungsausgabe

Exakt das im Auftrag vorgegebene Schema (`portfolio_approved`, `portfolio_risk_before/after`, `blockers[]` mit `code`/`message`), gespeichert in `trading.portfolio_risk_checks` — **auch genehmigte** Prüfungen werden gespeichert (Nachvollziehbarkeit, nicht nur Ablehnungen).

## Blockierte Trades bleiben im Ledger

Ein vom Portfoliorisiko abgelehnter Kandidat bekommt trotzdem eine `paper_trades`-Zeile mit `status='blocked'` — vollständige Historie statt stillem Verwerfen, konsistent mit Welle 1s `recommendation_veto_log`-Prinzip.

## Stressszenarien (AP6) — bewusst einfach

Sieben transparente Szenarien (`trading.stress_scenarios`), **keine** vorgetäuschte Optionspreis-/Vega-Modellierung:

- Referenzindex −3%/−5%/−10%, Sektor −7%: alle offenen Positionen bewegen sich **1:1** mit dem angenommenen Schock (kein Einzel-Beta pro Ticker verfügbar — explizit benannte, konservative Vereinfachung).
- Volatilitätssprung / Gap durch Stop: eine zusätzliche Bewegung um eine weitere Stop-Distanz gegen die Position.
- Gleichzeitige Mehrfach-Stop-Auslösung: Summe aller `risk_amount` offener Positionen (Extremfall-Obergrenze).
- Währungsschock: aktuell **0 Wirkung** dokumentiert (alle Bestandsticker EUR-denominiert), Schema für künftige Nicht-EUR-Positionen vorbereitet.

## Bewusste Grenzen

- Kein echtes Beta/keine Faktor-Exposition pro Ticker — 1:1-Marktbewegung ist eine grobe, aber transparent benannte Näherung.
- Korrelation nutzt nur Kursdaten der letzten 60 Tage (kurzes Fenster angesichts eines ~2 Wochen alten Systems — wird mit wachsender Historie aussagekräftiger).
- Sektor-Stressszenario wird pauschal auf **alle** offenen Positionen angewendet statt nur auf den betroffenen Sektor (keine sektorspezifischen Referenzindizes im Datenuniversum).

## Status

- ✅ Umgesetzt: alle 9 Limits, Blocker-Schema, 7 Stressszenarien.
- 🔴 Nicht live getestet (0 offene Positionen zum Zeitpunkt der Migration).
