# Testplan Welle 3

Stand: 2026-08-01. Deckt die 22 im Auftrag geforderten Testfälle ab.

## Ergebnis des lokalen Testlaufs

```
node tests/test_welle3_reine_funktionen.js
--- Ergebnis: 18 bestanden, 0 fehlgeschlagen ---
```

## Testfälle

| # | Szenario | Status | Nachweis |
|---|---|---|---|
| 1 | Long-Trade erreicht Stop | ✅ getestet (lokal) | `stop_loss @ 95` bei Kerze mit Low ≤ Stop |
| 2 | Long-Trade erreicht Ziel | ✅ getestet (lokal) | `target_reached @ 110` |
| 3 | Short-Trade erreicht Stop | ✅ getestet (lokal) | `stop_loss @ 105` |
| 4 | Short-Trade erreicht Ziel | ✅ getestet (lokal) | `target_reached @ 90` |
| 5 | Stop und Ziel in derselben Tageskerze | ✅ getestet (lokal) | `ambiguous_execution=true`, konservativ `stop_loss` gewählt, `target_reached` bleibt in `exit_reasons_all_json` sichtbar |
| 6 | Gap durch den Stop | ✅ getestet (lokal) | Exit exakt am Stop-Preis, kein optimistischer Gap-Preis |
| 7 | Einstiegszone nie erreicht | ✅ getestet (lokal) | bleibt `proposed`, kein Fill |
| 8 | Zeitstop | ✅ getestet (lokal) | `time_stop` bei abgelaufenem `time_stop_at` |
| 9 | Ablauf der These | ✅ getestet (lokal) | `thesis_expired` bei abgelaufenem `thesis_expires_at` |
| 10 | Trailing-Stop | 🔴 **nicht implementiert** | Test dokumentiert die Lücke explizit statt sie zu verstecken — siehe `docs/AUSFUEHRUNGSMODELL.md` |
| 11 | Gebühren machen Bruttogewinn netto negativ | ✅ getestet (lokal) | Bruttogewinn 5 EUR, Kosten 10 EUR → Nettoergebnis −5 EUR |
| 12 | Portfoliolimit blockiert Trade | ✅ getestet (lokal) | `TOTAL_RISK_LIMIT` bei 6,1% > Limit 6,0% |
| 13 | Sektorlimit blockiert Trade | ✅ getestet (lokal) | `SECTOR_LIMIT` bei 16% > Limit 15% |
| 14 | Drawdownlimit blockiert neue Trades | ✅ getestet (lokal) | `DRAWDOWN_LIMIT` bei 18% > Limit 15% |
| 15 | Stressszenario | ✅ getestet (lokal) | −5%-Indexschock auf 8.000 EUR Position → −400 EUR |
| 16 | Walk-forward-Trennung | 🟡 Schema-only | Backtesting-Modul dormant (`docs/BACKTESTING_UND_WALK_FORWARD.md`), kein Ausführungs-Workflow vorhanden — nicht sinnvoll lokal testbar ohne echte Daten |
| 17 | Out-of-Sample ohne Look-ahead | 🟡 Schema-only | gleiche Begründung wie 16 |
| 18 | Zu kleine Fallzahl | ✅ getestet (lokal) | `proposal_eligible=false` bei n=12 < Mindestfallzahl 30 |
| 19 | Schlechte Kalibrierung | 🟡 Schema-only | Kalibrierungsmodul dormant (`docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md`), 0 abgeschlossene Trades |
| 20 | Lernvorschlag ohne OOS-Bestätigung wird verworfen | ✅ getestet (lokal) | `proposal_eligible=false` trotz ausreichender Fallzahl und starkem Erwartungswert, wenn `oos_confirmed=false` |
| 21 | DRY_RUN | 🟡 nicht erneut getestet | Mechanismus unverändert aus Welle 1/2 (dort live getestet) |
| 22 | Wiederholung eines Laufs ohne doppelte Trades | ✅ getestet (lokal) | `trade_id` ist deterministisch (ticker+business_date+strategy), `ON CONFLICT DO NOTHING` |

## Nicht lokal testbar — benötigt einen echten n8n-Lauf

- Der komplette Datenfluss durch Workflow `14` (Job A/B/C) mit echten `recommendations`/`paper_trades`-Zeilen.
- `09b`s vollständiger Lauf inkl. KI-Interpretation — aktuell ohnehin 0 Vorschläge erwartbar (OOS-Gate nie erfüllt).
- `12`s vier neue Aktivierungspfade — real erst prüfbar, sobald ein echter Vorschlag existiert.
- Die neuen Dashboard-Sektionen in `07`/`10` — erst mit echten Ledger-Daten sichtbar.
- Ein vollständiger Tageslauf: `00` → `02b`/`02` → `06` → `14` in DRY_RUN, gefolgt von einem echten Fill-Zyklus über mehrere Tage.

## Warum Trailing-Stop nicht umgesetzt wurde

AP3 nennt einen ATR-Trailing-Stop für Trend Following als **optional**. Angesichts der bereits sehr großen Menge an Kernfunktionalität in Welle 3 (Ledger, Ausführung, Exit-Engine, Portfoliorisiko, Stressszenarien, Lernagent) wurde er bewusst zurückgestellt, statt eine unvollständige/ungetestete Version zu bauen. `stop_price_current` existiert bereits als Spalte (vorbereitet für eine künftige Nachzieh-Logik), wird aber aktuell nur einmal bei der Füllung gesetzt und danach nie verändert.

## Empfehlung

Nach dem Live-Push den ersten echten Fill-Zyklus (mehrere Tage) beobachten, bevor der Trailing-Stop und die Backtesting-/Kalibrierungs-Ausführungs-Workflows angegangen werden — diese brauchen ohnehin echte Daten, die erst mit der Zeit entstehen.
