# Einzeltrade-Risikomodell (Welle 1, AP6)

Stand: 2026-07-31. Deterministisches Modell für theoretische Positionsgrößen in `06 – Empfehlungswatchlist`. Das gesamte System bleibt Simulation — es gibt kein echtes Depot, keine reale Order, keinen echten Broker-Zugriff.

## Konfiguration (`trading.pipeline_config`, sql/029)

| Key | Default | Bedeutung |
|---|---|---|
| `MODEL_PORTFOLIO_VALUE` | 100.000 EUR | Fiktiver Modell-Portfoliowert |
| `MAX_RISK_PER_TRADE_PCT` | 1,0 % | Maximal riskierter Portfolioanteil je Trade |
| `MIN_REWARD_RISK_RATIO` | 1,5 | Mindest-Chance-Risiko-Verhältnis, sonst hartes Veto `RRR_TOO_LOW` |
| `MAX_POSITION_VALUE_PCT` | 20,0 % | Maximaler Positionsanteil (informativ, siehe unten — kein hartes Veto) |
| `DEFAULT_SLIPPAGE_BPS` | 10 (0,10 %) | Angenommene Slippage |
| `DEFAULT_FEES_BPS` | 15 (0,15 %) | Angenommene Gebühren |
| `MAX_DATA_AGE_MINUTES` | 1440 (24h) | Schema-seitig vorbereitet, siehe „Nicht umgesetzt“ unten |

Werte sind konservativ gewählt und über SQL (`UPDATE trading.pipeline_config SET value_numeric = ... WHERE config_key = ...`) veränderbar, ohne Code-Änderung. `06` liest sie bei jedem Lauf frisch (`Kontext ergaenzen`, gleiches Muster wie `TREND_KONFLIKT_SCHWELLE`).

## Formeln (exakt wie im Auftrag)

```
risk_amount            = MODEL_PORTFOLIO_VALUE × (MAX_RISK_PER_TRADE_PCT / 100)
unit_risk               = abs(entry_price − stop_price)
theoretical_quantity    = floor(risk_amount / unit_risk)
position_value           = theoretical_quantity × entry_price
position_value_pct       = position_value / MODEL_PORTFOLIO_VALUE × 100
reward_risk_ratio        = abs(target_price − entry_price) / unit_risk
estimated_fees            = position_value × (DEFAULT_FEES_BPS / 10000)
estimated_slippage        = position_value × (DEFAULT_SLIPPAGE_BPS / 10000)
max_planned_loss          = unit_risk × theoretical_quantity + estimated_fees + estimated_slippage
```

`entry_price` = heutiger technischer Signalkurs, `stop_price`/`target_price` = ATR-basierte Werte aus Phase 7 (Paket 16) — **kein neuer Stop/Ziel-Mechanismus**, Welle 1 nutzt bewusst die bereits vorhandenen, live verifizierten ATR-Werte statt eine zweite Quelle einzuführen.

Bei `unit_risk <= 0` (Stop == Entry) liefert `computeRisk()` `null` — kein theoretischer Trade wird eröffnet (fließt in den Veto `STOP_TARGET_INVALID`/`STOP_WRONG_SIDE` ein, siehe `docs/HARTE_VETOS.md`).

## Speicherung (`trading.recommendations`, sql/029)

Neue Spalten: `risk_amount`, `unit_risk`, `theoretical_quantity`, `position_value`, `position_value_pct`, `reward_risk_ratio`, `estimated_fees`, `estimated_slippage`, `max_planned_loss`, `risk_model_version` (aktuell `"welle1-v1"`, für spätere Formeländerungen ohne die Bedeutung alter Zeilen zu verfälschen).

**Gefundener und behobener Bestandsfehler**: `stop_price`/`target_price` existierten bereits seit Paket 7 als Spalten und wurden seit Paket 17 im JS-Objekt berechnet — aber nie in die `INSERT`-Spaltenliste von `Oeffnen: SQL bauen` aufgenommen. Die Werte kamen bei jeder bisherigen Eröffnung als `NULL` in der DB an, ohne dass ein Fehler sichtbar wurde. In Welle 1 mitkorrigiert.

## MAX_POSITION_VALUE_PCT — bewusst kein hartes Veto

Der Auftrag listet `MAX_POSITION_VALUE_PCT` als Konfigurationswert, aber nicht explizit als einen der 12 harten Vetos. Eine zu hohe theoretische Positionsgröße ist bei diesem Modell (kleines Portfolio, größerer ATR-Abstand bei volatilen Werten) eher ein Konfigurations-/Dimensionierungsfall als ein Datenqualitätsproblem. Wird deshalb als **weicher, informativer Blocker** (`POSITION_SIZE_HOCH`, `severity: "soft"`) in `decision_blockers` der geschriebenen Zeile vermerkt, blockiert die Eröffnung aber nicht. Kann in Welle 2 zu einem harten Veto hochgestuft werden, falls gewünscht.

## Nicht umgesetzt / bewusst offen

- `MAX_DATA_AGE_MINUTES` ist schema-seitig vorbereitet (Config-Wert existiert, wird geladen), aber **nicht** gegen einen tatsächlichen "Kurs ist N Minuten alt"-Zeitstempel geprüft — die aktuelle Datenquelle liefert nur Tageskerzen, keinen Intraday-Zeitstempel mit Minutenauflösung für den *aktuellen* Kurs. Würde einen echten Intraday-Kursabruf voraussetzen (siehe Welle 2, falls gewünscht).
- Keine automatische Neuberechnung offener Positionen bei einer Änderung der Konfigurationswerte — `risk_model_version` markiert, mit welcher Formelversion eine Zeile berechnet wurde, eine rückwirkende Neuberechnung ist nicht vorgesehen.

## Status

- ✅ Umgesetzt: Formel, Konfiguration, Speicherung, gefundener stop/target-Bug behoben.
- 🔴 Nicht live gegen einen echten Trigger getestet (wie schon Pakete 15/17 zuvor — `06` läuft nur über `00` oder einen nicht risikofrei fernauslösbaren UI-Trigger). Nur Syntax-/Formel-Prüfung, siehe `docs/TESTPLAN_WELLE_1.md`.
