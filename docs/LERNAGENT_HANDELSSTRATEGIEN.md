# Lernagent Handelsstrategien (Welle 3, AP9)

Stand: 2026-08-01. Neuer Workflow `09b – Lernagent Handelsstrategien`, getrennt von `09 – Lernagent Newswirkung` (dessen Logik unverändert bleibt) — fachlich und technisch sauber trennbar, da beide auf unterschiedlichen Datenquellen (News-Wirkung vs. Paper-Trade-Ergebnisse) arbeiten.

## Vier Gates, alle müssen erfüllt sein

Ein Finding wird nur dann überhaupt zu einem Vorschlagskandidaten, wenn:

1. **Mindestfallzahl** erreicht (`LEARNING_MIN_TRADE_SAMPLE_SIZE`, Default 30, `trading.pipeline_config`).
2. **Out-of-Sample bestätigt** — mindestens ein abgeschlossener `trading.backtest_runs`-Lauf mit `run_type='out_of_sample'`. Da das Backtesting-Modul (`docs/BACKTESTING_UND_WALK_FORWARD.md`) mangels Historie aktuell dormant ist, ist diese Tabelle IMMER leer — `09b` erzeugt deshalb aktuell **grundsätzlich keine Vorschläge**, unabhängig von der Fallzahl. Das ist korrektes, konservatives Verhalten (Grundregel 8: "Kleine Fallzahlen dürfen keine produktive Regeländerung auslösen" — hier zusätzlich verschärft: auch eine ausreichende Fallzahl reicht ohne OOS nicht).
3. **Keine Dominanz durch einen einzelnen Ticker** — der Trade-stärkste Ticker darf nicht mehr als 50% der Trades einer Strategie stellen.
4. **Klar von 0 verschiedener Erwartungswert** — `expectancy_r ≤ -0.15` oder `≥ 0.3` (kein Vorschlag bei einem neutralen Ergebnis nahe 0R).

## Grundregel 9 strikt umgesetzt: KI berechnet nichts

Anders als bei `09` (wo die KI innerhalb eines Korridors einen `proposed_value` wählen darf) berechnet `09b` **Vorschlagstyp UND `proposed_value` vollständig deterministisch**, bevor die KI überhaupt aufgerufen wird (`candidate_proposal` je Finding). Die KI bekommt nur noch die fertige Kandidatenliste und entscheidet ausschließlich `include: true/false` mit Begründungstext — sie kann keine Zahl erfinden, weil sie keine Zahl mehr wählt. Ein Sicherheitsnetz (`Vorschlaege gegen Fallzahlen validieren (Trades)`) verwirft jede KI-Entscheidung, die zu keinem bekannten, vorbereiteten Kandidaten passt.

## Fünf Vorschlagstypen, deterministisch aus dem Finding abgeleitet

| Finding | `proposal_type` | Ziel |
|---|---|---|
| Strategie, `expectancy_r ≤ -0.15` | `strategy_deactivation` | `trading.strategy_status.aktiv = FALSE` |
| Strategie, `expectancy_r ≥ 0.3` | `threshold_adjustment` | `trading.pipeline_config.MAX_RISK_PER_TRADE_PCT` moderat erhöhen |
| Strategie×Regime, `expectancy_r ≤ -0.15` | `regime_restriction` | `trading.strategy_regime_matrix.fit_multiplier` auf 0.1 senken |

(Die Auftrags-Vorschlagstypen "Gewichtsanpassung" und "Änderung des Zeitstops/CRV-Mindestanforderung" existieren als Aktivierungspfad in `12` — `weight_adjustment` (unverändert aus `09`) und `strategy_parameter_change`/`threshold_adjustment` — werden von `09b` aber noch nicht als eigene Findings erzeugt, da die zugrunde liegenden Segmentierungen (CRV-Verteilung, Zeitstop-Sensitivität) mehr Trade-Historie brauchen als heute vorhanden ist.)

## Aktivierungspfade in `12` (alle real, mit einer dokumentierten Ausnahme)

`12`s "POST: Formular normalisieren + SQL bauen" wurde um vier neue, echte Aktivierungspfade erweitert (siehe Commit-Historie): `threshold_adjustment` → `UPDATE trading.pipeline_config`, `regime_restriction` → `UPDATE trading.strategy_regime_matrix`, `strategy_deactivation` → `UPDATE trading.strategy_status` (von `06` vor jeder Kandidatenauswahl geprüft), `strategy_parameter_change` → `UPDATE trading.strategy_parameters`.

**Dokumentierte Ausnahme**: `strategy_parameter_change` schreibt korrekt nach `trading.strategy_parameters`, aber `02` **liest diese Tabelle noch nicht** (Stop-/Ziel-Multiplikatoren und Zeitstop-Horizonte sind dort weiterhin als JS-Konstanten hartkodiert, seit Welle 2). Ein darüber freigegebener Vorschlag ist speicherbar und sichtbar, aber ohne Wirkung, bis `02` entsprechend erweitert wird (Welle 4, falls gewünscht).

## Governance unverändert

`09b` schreibt ausschließlich `status='proposed'` in dieselbe `trading.learning_rule_proposals`-Tabelle wie `09` — `12 – Lernvorschlag-Freigabe` bleibt die einzige Freigabestelle, keine automatische Aktivierung.

## Status

- ✅ Umgesetzt: vollständiger Workflow, vier Gates, fünf Aktivierungspfade (davon vier real wirksam).
- 🔴 Erzeugt aktuell erwartungsgemäß **keine** Vorschläge (OOS-Gate niemals erfüllt, siehe oben) — kein Fehler, korrektes konservatives Verhalten.
