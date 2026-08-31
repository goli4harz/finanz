# Testplan Welle 2

Stand: 2026-08-01. Deckt die 16 im Auftrag geforderten Testfälle ab. 14 als lokal ausführbare Unit-Tests umgesetzt (`tests/test_welle2_reine_funktionen.js`), 2 unverändert aus Welle 1 übernommen.

## Ergebnis des lokalen Testlaufs

```
node tests/test_welle2_reine_funktionen.js
--- Ergebnis: 14 bestanden, 0 fehlgeschlagen ---
```

## Testfälle

| # | Szenario | Status | Nachweis |
|---|---|---|---|
| 1 | Mean Reversion im Seitwärtsmarkt | ✅ getestet (lokal) | `fit_multiplier=1.00`, nicht blockiert |
| 2 | Mean Reversion im starken Abwärtstrend | ✅ getestet (lokal) | `blocked=TRUE` in der Regime-Matrix |
| 3 | Trendfolge mit Marktbestätigung | ✅ getestet (lokal) | `fit_multiplier=1.00` |
| 4 | Trendfolge gegen Marktregime | ✅ getestet (lokal) | `fit_multiplier=0.30`, eingeschränkt statt blockiert |
| 5 | Breakout mit 252 Tagen und Volumen | ✅ getestet (lokal) | kein `HISTORY_252_MISSING`-Blocker |
| 6 | Breakout mit nur 90 Tagen | ✅ getestet (lokal) | `HISTORY_252_MISSING` bereits im Strategiesignal |
| 7 | News/Event mit aktueller Nachricht | ✅ getestet (lokal) | 2h < 12h-Schwelle, kein Veto |
| 8 | News/Event mit alter Nachricht | ✅ getestet (lokal) | 20h > 12h-Schwelle → `NEWS_STALE` |
| 9 | Widersprüchliche Strategien bei einem Ticker | ✅ getestet (lokal) | höherer `adjustedScore` gewinnt, andere bleibt als Alternative erhalten |
| 10 | Hohe Opportunity bei hohem Risiko | ✅ getestet (lokal) | beide Dimensionen unabhängig, kein eingebauter Trade-off |
| 11 | Hohe Evidenz bei niedriger Opportunity | ✅ getestet (lokal) | `evidence_confidence` unabhängig von `opportunity_score` |
| 12 | Breite Scannerliste mit Limit | ✅ getestet (lokal) | 30 Kandidaten → genau 15 (Limit) erreichen Stufe B |
| 13 | Sektorale Begrenzung | ✅ getestet (lokal) | 4 Kandidaten desselben Sektors, Limit 3 → 1 ausgeschlossen |
| 14 | Datenbankfehler | ✅ getestet (lokal) | leere `strategy_signals` → `dbLesefehler=true` |
| 15 | DRY_RUN | 🟡 nicht erneut getestet | Mechanismus unverändert aus Welle 1 (dort live getestet, siehe `docs/TESTPLAN_WELLE_1.md`) — Welle 2 ändert nur, WELCHE Felder simuliert werden, nicht das Gating selbst |
| 16 | REQUIRE_CONFIRMATION | 🟡 nicht erneut getestet | gleiche Begründung wie 15 |

## Nicht lokal testbar — benötigt einen echten n8n-Lauf

- Der komplette Datenfluss durch `02`/`02b` (FastAPI-Abruf → Strategiesignale/Marktregime → DB-Schreibung).
- `06`s vollständige Ticker-Schleife inkl. `evaluateTickerStrategies()`, Regime-Lookup aus der echten `trading.market_regime`-Tabelle, `recommendations`-Schreibung mit allen neuen Spalten.
- Workflow `13` als Ganzes (Merge-Kette, Stufe-A/B-Übergabe, `scan_runs`/`scan_candidates`-Schreibung).
- Die neuen Dashboard-Sektionen in `07` und die neuen Prüf-Agent-Regeln in `10` — beides erst mit echten Daten sichtbar.
- Ein vollständiger Tageslauf in DRY_RUN (Abnahmekriterium) — nicht durchgeführt, gleiche Einschränkung wie in Welle 1 (`06` läuft nur über `00` oder einen nicht risikofrei fernauslösbaren UI-Trigger; `13` ist neu und wurde noch nie ausgeführt).

**Empfehlung**: nach dem Live-Push den nächsten planmäßigen Lauf (Montag, `00` für `06`, separat `13` einmal manuell) beobachten und `trading.strategy_signals`/`trading.market_regime`/`trading.scan_candidates` sowie die neuen Dashboard-Sektionen live gegenprüfen.
