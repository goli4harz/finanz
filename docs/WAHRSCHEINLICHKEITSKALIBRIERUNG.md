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

## Nachtrag 2026-08-28 — Regime-Befüllung repariert, Backfill, Fix D (regime-agnostischer Fallback)

Verifikation von 08-27 ergab: `trading.probability_estimates` war **leer** und alle 237
geschlossenen `simulation_trades` hatten `market_regime_at_entry = NULL` (bis auf 4). Kette also
komplett tot.

**Ursache**: die Point-in-time-Regime-Berechnung existierte nur im WF17-Knoten
`Verarbeite Tage-Paket (Engine)`. `pipeline_config.TRADING_ENGINE_STEP_ENABLED = false`
(bewusst, bis Vergleichslauf bestätigt) → es lief der Legacy-Knoten `Verarbeite Tage-Paket`,
der **gar keine Regime-Logik** hatte → `pgStr(undefined)` = `'NULL'`. Nebenbug: `deriveRegion()`
mappte nur über `stock_instruments.exchange`; `BAS.DE` hatte `exchange = NULL` → `'global'` →
kein Regime.

**Fixes (live auf `172.16.1.17`, danach ins Repo gezogen):**
1. **WF17 `Verarbeite Tage-Paket`**: Regime-Helfer (`emaValue/emaSeries/realizedVol20/
   symbolRegimeContext/regionRegimeHistorical` + `REGIME_SYMBOLS` + `barsUpTo`) 1:1 aus dem
   Engine-Knoten portiert, in sauberem UTF-8 (der Engine-Knoten hat dort 7× U+FFFD-Mojibake,
   das nur funktioniert, weil Erzeuger und Vergleich denselben kaputten String nutzen). Der
   Legacy-Tagesloop berechnet jetzt `europaRegime`/`usaRegime` und schreibt
   `market_regime_at_entry` in die neue Trade-Zeile — Parität zwischen Legacy- und Engine-Pfad.
2. **WF17 `deriveRegion(exchange, ticker)`**: Ticker-Suffix-Fallback (`.DE`/`.PA`/`.AS`/… →
   `'Europa'`), damit fehlendes `exchange` nicht mehr nach `'global'` kippt. Zusätzlich
   `UPDATE trading.stock_instruments SET exchange='XETRA' WHERE ticker='BAS.DE'`.
3. **Backfill** der 234 bestehenden NULL-Trades: Regime lokal mit derselben Formel aus
   `historical_price_data` je `as_of_date` gerechnet und per `UPDATE … FROM (VALUES …)` gesetzt
   (`AND market_regime_at_entry IS NULL`, die 4 guten Zeilen unangetastet). Gegengeprüft an den
   4 Engine-Pfad-Trades (2026-01-05/06 → `bull_trend_low_vol`, exakt gleich). Ergebnis:
   160× `bull_trend_low_vol`, 78× `bear_trend`, 0× NULL.
4. **WF19 `SQL: Aggregation (Simulation)`**:
   - `p_target_before_stop` erkannte nur `'target_reached'` — die Simulation schreibt aber
     `'take_profit'` (`checkExit` in WF17). Beide Vokabeln werden jetzt akzeptiert; der Wert war
     vorher systematisch 0, jetzt z.B. 0.16–0.38.
   - **Fix D**: zusätzlich zu den regime-spezifischen Segmenten ein **regime-agnostisches
     Rollup** je `strategy × direction` (`segment_market_regime = NULL`), via `UNION ALL`.
5. **Trading-Entscheidungszentrale `Baue Query (Liste/Detail)`** (LATERAL): Regime-Bedingung
   auf `(pe.segment_market_regime = COALESCE(...) OR pe.segment_market_regime IS NULL)` gelockert,
   `ORDER BY … , (pe.segment_market_regime IS NOT NULL) DESC` — exakter Regime-Match vor Rollup.

**Verifiziert**: `probability_estimates` hat jetzt 6 Zeilen (4 regime-spezifisch + 2 Rollup),
5× `estimated`. Die LATERAL-Query matcht 4 der 5 Empfehlungen (alle `mean_reversion`, Regime
`'unknown'`) über das Rollup; die 5. (`trend_following`) bleibt ohne Match, weil es **keine**
`trend_following`-Sim-Trades gibt — korrektes, ehrliches Verhalten.

**Noch offen**: (a) warum tragen die Live-`recommendations` Regime `'unknown'`? (Live-02b/06-
Regimeerkennung, separat). (b) `TRADING_ENGINE_STEP_ENABLED` bleibt `false` — der Legacy-Pfad
ist jetzt der maßgebliche und regime-fähige; der Engine-Pfad-Vergleichslauf ist davon
unabhängig. (c) `simulation_trades` schließt nie per `take_profit` mit positivem EV in den
großen Segmenten — mean_reversion ist in der Sim durchweg Verlust (p_win 0.18–0.24), eigener
Prüfpunkt für die Strategie-/Exit-Logik.
