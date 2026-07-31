# Strategiemodell (Welle 2)

Stand: 2026-08-01, Arbeitspakete 1+2+7. Beschreibt das normalisierte Strategiesignal-Schema und die vier Strategiefamilien.

## Ausgangsbefund

`02` berechnete bereits seit Paket 18 (fachliche Überarbeitung) drei getrennte technische Strategiesignale (`mean_reversion`, `trend_following`, `breakout`) als JSONB-Spalten auf `trading.technical_signals_history` — aber `06` las diese Felder **nie** (nur `dominant_strategy` für einen einzelnen Welle-1-Veto). Die eigentliche Kauf-/Verkauf-Entscheidung kam ausschließlich aus der Kombination "starke News UND gleichgerichtetes Tagessignal (`handels_status`/`richtung`)" — eine fünfte, unbenannte Mischlogik, keine der vier im Auftrag genannten Strategien.

## Normalisiertes Schema (AP1)

`trading.strategy_signals` (sql/031), Point-in-Time revisioniert wie `fundamentals_history`: `ticker, business_date, strategy, direction, raw_score, regime_fit, data_quality_score, entry_zone_low/high, stop_price, target_price, expected_horizon_days, time_stop_at, evidence_json, blockers_json, rule_version, known_at/valid_from/valid_to/revision_number`.

Auch neutrale/blockierte Signale werden gespeichert (Auftragsvorgabe) — `direction='neutral'` oder ein nicht-leeres `blockers_json` verhindert nur die Verwendung als Handelskandidat in `06`, nicht das Speichern selbst.

## Die vier Strategien

### mean_reversion, trend_following, breakout — berechnet in `02`

Unverändert aus Paket 18 übernommen (RSI-Extremwert+Bollinger für Mean-Reversion, MACD+EMA20 für Trendfolge, 52-Wochen-Nähe+Volumen für Breakout). **Neu in Welle 2**: jedes Signal bekommt strategie-spezifisches Stop/Ziel/Entry-Zone/Zeitstop statt nur `expected_horizon_days`:

| Strategie | Stop (ATR-Multiplikator) | Ziel (ATR-Multiplikator) | Horizont |
|---|---|---|---|
| mean_reversion | 1.0x | 1.5x | 3 Tage |
| trend_following | 1.5x | 2.5x | 15 Tage |
| breakout | 1.0x | 3.0x | 7 Tage |

Begründung: Mean-Reversion braucht einen engen Stop (die These ist widerlegt, sobald der Kurs weiter in die "falsche" Richtung läuft), Breakout ein weiteres Ziel (zielt auf eine größere Fortsetzungsbewegung), Trendfolge liegt dazwischen. Diese Multiplikatoren sind **getrennt** von den bestehenden `ATR_STOP_MULTIPLIER`/`ATR_TARGET_MULTIPLIER` (1.5/2.5) aus Welle 1, die weiterhin für den kombinierten Signalwert (`handelsBewertung.atrStop/atrTarget`) gelten (Rückwärtskompatibilität, kein Consumer geändert).

`breakout` bekommt zusätzlich einen strukturierten `blockers_json`-Eintrag (`HISTORY_252_MISSING`), wenn `breakout_history_ausreichend` (Welle 1, AP3) `false` ist — "kein Breakoutsignal aus nur drei Monaten Ersatzhistorie" (Auftragsvorgabe) ist damit direkt im Signal selbst sichtbar, nicht erst als Veto in `06`.

### news_event — berechnet in `06`

Bewusst **nicht** in `02` berechnet, da die Strategie sowohl aktuelle News als auch die technische Bestätigung braucht — beide liegen erst in `06` gemeinsam vor. Entsteht nur, wenn: eine starke News vorliegt (`wirkung_staerke='hoch'`), das technische Tagessignal nicht widerspricht, und keine widersprüchliche zweite starke News existiert (bestehende `widerspruechlich`-Prüfung aus Welle 1). Kein eigenes technisches Stopmodell — nutzt bei Bedarf den bestehenden ATR-Stop/-Ziel aus Welle 1 als Fallback ("News/Event darf technische Daten als Bestätigung verwenden", Auftragsvorgabe). Wird nach der Berechnung ebenfalls nach `trading.strategy_signals` geschrieben (eigener `_aktion`-Output-Typ in `06`, eigener SQL-Builder/Writer-Node).

## Dominante Strategie + Alternativen (AP7)

Pro Ticker sammelt `06` alle nicht-neutralen, nicht-blockierten Strategiesignale (technische aus `02` + ggf. `news_event`), gewichtet jedes mit dem `fit_multiplier` aus der Strategie-Regime-Matrix (`docs/MARKTREGIME.md`) und wählt die mit dem höchsten `adjustedScore = raw_score × fit_multiplier` als dominante Strategie. Alle anderen brauchbaren Kandidaten werden als `alternative_strategies_json` auf der geschriebenen `recommendations`-Zeile gespeichert ("Bewahre andere passende Strategien als Alternativszenarien", Auftragsvorgabe) — sichtbar, aber nicht gewählt.

Ein Ticker ohne jede brauchbare (nicht regime-blockierte, Score ≥ 0.15) Strategie bleibt Beobachtung: kein `recommendations`-Eintrag, aber falls mindestens ein Signal vorlag und ALLE Kandidaten regime-blockiert waren, wird ein neuer struktureller Veto-Log-Eintrag `REGIME_BLOCKED` geschrieben (Transparenz statt stillem Verschwinden).

## Rückwärtskompatibilität

Das bestehende Gesamtpunktesystem (`signal_punkte`/`signal_gruende`/`signal_staerke` auf `technical_signals_history`) bleibt vollständig unverändert bestehen und wird weiterhin geschrieben — es ist nur nicht mehr alleinige Grundlage einer Eröffnung (Auftragsvorgabe), sondern informativer Kontext.

## Status

- ✅ Umgesetzt: normalisiertes Schema, alle 4 Strategien, dominante Strategie + Alternativen.
- 🔴 Nicht live gegen einen echten Trigger getestet (siehe `docs/TESTPLAN_WELLE_2.md`).
