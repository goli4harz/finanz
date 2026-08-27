# Wahrscheinlichkeiten und Kalibrierung (Welle 3, AP8)

Stand: 2026-08-01. Schema (`trading.probability_estimates`/`calibration_checks`, `sql/037`) vollständig funktionsfähig, **dormant** — 0 abgeschlossene Paper Trades zum Zeitpunkt dieser Migration.

## Grundprinzip

`probability_status` ist entweder `estimated` (Fallzahl ≥ `PROBABILITY_MIN_SAMPLE_SIZE`, Default 30) oder `insufficient_data` — **niemals** eine KI-Ersatzschätzung (Auftragsvorgabe wörtlich befolgt). Da `paper_trades` aktuell 0 geschlossene Zeilen hat, wäre JEDES Segment heute `insufficient_data` — korrektes, erwartbares Verhalten, kein Fehler.

## Segmentierung

`strategy × direction × market_regime × risk_bucket × evidence_bucket × time_horizon` — Auftragsvorgabe "Vermeide zu feine Segmentierung bei wenigen Fällen" wird über die Mindestfallzahl je vollständiger Segment-Kombination erzwungen: eine zu feine Kombination fällt automatisch unter die Mindestfallzahl und bleibt `insufficient_data`, ohne dass eine separate Grobheits-Heuristik nötig ist.

`risk_bucket`/`evidence_bucket`: geplant als Terzile von `risk_score`/`evidence_confidence` (Welle 2, AP4) — `niedrig`/`mittel`/`hoch` — noch nicht mit echten Daten befüllt (keine Trades).

## Berechnungsverfahren (Mechanismus vollständig implementierbar, aber ungetestet mangels Daten)

- **p_win**: Anteil `net_pnl > 0` im Segment.
- **p_positive_return**: identisch zu p_win (Namensklarheit für den Auftrags-Wortlaut).
- **p_target_before_stop**: Anteil `exit_reason='target_reached'` unter allen `IN ('target_reached','stop_loss')`-Exits.
- **expected_value_r**: Mittelwert `realized_r_multiple` im Segment.
- **Brier Score**: `mean((predicted_probability - observed_outcome)^2)` je Bucket.
- **Calibration Error**: `abs(predicted_probability - observed_frequency)`.
- **Konfidenzintervall**: Wilson-Score-Intervall (robust bei kleinen Fallzahlen, keine Normalverteilungsannahme).

## Warum kein Mechanismus-Workflow in Welle 3 gebaut wurde

Gleiche Priorisierungsentscheidung wie beim Backtesting-Modul (`docs/BACKTESTING_UND_WALK_FORWARD.md`): ohne abgeschlossene Trades gibt es nichts zu berechnen — ein Workflow, der heute liefe, würde nur `insufficient_data`-Zeilen erzeugen. Das Schema und die Formeln sind vollständig spezifiziert (oben), die eigentliche Berechnung sollte gebaut werden, sobald `paper_trades` eine dreistellige Zahl abgeschlossener Trades zeigt.

## Status

- 🟡 `paper_trades`-Quelle: Schema + Formeln vollständig spezifiziert, Berechnungs-Workflow weiterhin nicht gebaut (bewusste Priorisierung, 0 abgeschlossene Paper Trades).
- 🟢 `simulation_trades`-Quelle: siehe Nachtrag unten — gebaut und live (Workflow 19, Konsument-Anpassung in der Trading-Entscheidungszentrale). Testlauf/Verifikation gegen eine echte Empfehlung noch offen.

## Nachtrag 2026-08-25 — Berechnungs-Workflow für die `simulation_trades`-Quelle

Fortsetzung von [[finanz_paper_trading_flags_resolved_2026-08-24]]: echte Paper Trades bleiben selten, daher V1-Producer für `data_source='simulation_trades'` (sql/071) gebaut statt weiter auf `paper_trades` zu warten.

**Neuer Workflow `19 – Wahrscheinlichkeitskalibrierung (Simulation)`**: aggregiert `trading.simulation_trades` (`status='closed'`, Läufe mit `data_category='out_of_sample'` bewusst ausgeschlossen — Konsistenz mit dem Prinzip, Out-of-Sample-Läufe nicht für Kalibrierung/Training anzufassen, `out_of_sample_locked`, sql/057) nach `strategy × direction × market_regime_at_entry`. `direction` wird von `long`/`short` (simulation_trades-Vokabular) auf `kauf`/`verkauf` übersetzt (`trading.recommendations.richtung`-Vokabular) — sonst würde der Konsument nie matchen.

**Bewusste Lücke**: `segment_risk_bucket`/`segment_evidence_bucket`/`segment_time_horizon` bleiben `NULL` — `simulation_trades` hat keine Entsprechung zu `risk_score`/`evidence_confidence` (die existieren nur auf `trading.recommendations`). Keine Scheingenauigkeit durch erfundene Buckets.

**DELETE+INSERT statt ON CONFLICT**: Postgres behandelt `NULL <> NULL` in UNIQUE-Constraints — ein `ON CONFLICT` auf dem sql/071-Constraint würde bei `NULL`-Risk/Evidence-Buckets nie greifen und bei jedem Lauf Duplikate statt Updates erzeugen. Workflow 19 löscht daher vor jedem Lauf alle Zeilen mit `data_source='simulation_trades' AND rule_version='wahrscheinlichkeitskalibrierung-simulation-v1'` und schreibt frisch (voller Refresh, unproblematisch, da ohnehin komplett neu aggregiert wird).

**Konsument angepasst** (`Trading-Entscheidungszentrale.json`, Detail-Query): der bisherige `LEFT JOIN` mit exakter Gleichheit auf alle sechs Segmentspalten hätte `NULL`-Risk/Evidence-Zeilen nie gematcht (Orphan-Daten). Umgestellt auf `LEFT JOIN LATERAL ... ORDER BY (data_source='paper_trades') DESC LIMIT 1`: matcht `paper_trades`-Zeilen weiterhin exakt, `simulation_trades`-Zeilen nur über strategy/direction/regime (Risk/Evidence-Bucket ignoriert), bevorzugt bei Überschneidung die echte `paper_trades`-Kalibrierung.

**Voraussetzung für echte (nicht `unknown`) Regime-Werte**: Workflow `17` berechnet jetzt Point-in-time-Marktregime (Europa/USA/global, 1:1 aus `02b` übernommen, siehe `docs/MARKTREGIME.md`-Nachtrag) — braucht historische Kursdaten für 7 Referenzticker (`^GDAXI, ^STOXX50E, ^IXIC, ^GSPC, EURUSD=X, CL=F, GC=F`) in `trading.historical_price_data`. Falls diese für den simulierten Zeitraum fehlen, bleibt `market_regime_at_entry` `NULL`/`unknown` — Import über Workflow `15` (freies Instrumentenfeld, keine Codeänderung nötig).

**Noch offen (Stand 2026-08-25)**: Live-Push aller drei geänderten/neuen Workflows, Vorbedingungs-Check der 7 Referenzticker, Testlauf über `Simulation-Steuerzentrale.json`, Verifikation der `probability_estimates`-Zeilen und der LATERAL-Konsumenten-Query gegen eine echte Empfehlung.

## Nachtrag 2026-08-27 — Repo-Abgleich, alle drei Workflows bereits live

Diese Session fand die obigen Änderungen als unverändert-uncommittete lokale Arbeitskopie vor
(nie gepusht *und* nie committed), obwohl Workflow `19` laut Live-Abfrage bereits seit
2026-08-25 existiert und zuletzt 2026-08-26 aktualisiert wurde — die "Noch offen"-Liste oben war
also bereits überholt. Repo jetzt 1:1 mit Live synchronisiert (nicht andersrum gepusht):

- **`BEGIN;...COMMIT;`-Transaktionswrapper um das DELETE+INSERT in `Baue Upsert-SQL (Simulation)`
  wurde bewusst wieder entfernt** (Nutzerangabe: führte zu Problemen) — live/repo nutzen jetzt die
  Version ohne expliziten Transaktionswrapper.
- **Workflow `17` ist seit dieser Session deutlich weiter divergiert** als nur um die
  Marktregime-Ergänzung: eine separate, ebenfalls nie committete Session hat wegen
  Performance-Problemen ein Ticker-Batching für die Signalberechnung ergänzt (`Baue Ticker-Liste
  fuer Signal-Batching`, `Batch: 15 Ticker pro Signal-Berechnung`, `Berechne Signale (Batch)`,
  `Signale zusammenfuehren` — 4 neue Knoten, 25 von 52 Knoten insgesamt gegenüber dem
  08-25-Stand verändert). Laut Nutzer ist die Live-Version die korrekte, verifizierte Version.
- Trading-Entscheidungszentrale (LATERAL-Join) war ebenfalls schon live, nur 1 Knoten Differenz
  zum lokalen Stand, jetzt synchronisiert.

**Weiterhin offen**: Testlauf/Verifikation der `probability_estimates`-Zeilen und der
LATERAL-Konsumenten-Query gegen eine echte Empfehlung — das war nie der eigentliche Blocker,
sondern die Repo-Drift selbst.
