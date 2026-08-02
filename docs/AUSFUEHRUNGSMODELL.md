# Ausführungsmodell (Welle 3, AP2+AP3)

Stand: 2026-08-01. Beschreibt Workflow `14`s Job B (`w14_execution_exit`) — konservativ und deterministisch, ausschließlich auf Tageskerzen (`trading.stock_price_history`, Welle 1), keine Intraday-Daten verfügbar.

## Grundprinzip: kein Fill am Signaltag

Ein von `06` heute erzeugter Kandidat (Signal aus dem heutigen Kursschluss) darf frühestens **am nächsten Handelstag** gefüllt werden — "keine Nutzung von Daten, die zum damaligen Zeitpunkt noch nicht bekannt waren" (Grundregel 2). Umgesetzt über einen harten Filter in Job Bs Ladequery: `status='open' OR (status='proposed' AND decision_time::date < CURRENT_DATE)`. Ein heute frisch angelegter `proposed`-Trade wird von Job B **desselben Laufs** technisch gar nicht erst geladen.

## ENTRY_EXECUTION_MODEL = `zone_touch_conservative`

Ein Trade füllt, sobald die Tageskerze die Einstiegszone berührt (`low <= zone_high AND high >= zone_low`). Fülllogik:

| Fall | Fill-Preis | Begründung |
|---|---|---|
| Eröffnung bereits in der Zone | `open` | realistischer, tatsächlich erzielbarer Kurs |
| Gap unter die Zone (günstiger für Long) | `zone_low` | **konservativ**: kein rückwirkend optimaler Kurs, auch wenn real ein besserer möglich gewesen wäre |
| Eröffnung über der Zone, Tagesverlauf zurück in die Zone | für Long `zone_high` (der ungünstigste Punkt der Zone) | Tageskerzen zeigen nicht, wann genau die Zone berührt wurde — `ambiguous_execution=true` gesetzt |

Ohne Berührung: bleibt `proposed`. Läuft `time_stop_at`/`thesis_expires_at` ab, ohne dass die Zone je erreicht wurde → `expired_unfilled`.

## STOP_EXECUTION_MODEL / TARGET_EXECUTION_MODEL

Stop/Ziel gelten als erreicht, wenn die Tageskerze sie berührt (`low <= stop`/`high >= target` für Long, gespiegelt für Short). Exit-Preis = der Stop-/Zielwert selbst (kein zusätzlicher Schlupf über die reine Kursberührung hinaus — der ist separat im `SLIPPAGE_MODEL` erfasst).

## AMBIGUOUS_BAR_POLICY = `conservative_stop_first`

Berührt eine Tageskerze **sowohl** Stop als auch Ziel, ist aus einer Tageskerze allein nicht rekonstruierbar, welcher zuerst erreicht wurde. Implementiertes (einziges) Modell: der Stop gilt als zuerst erreicht — die konservativere, für den Trade ungünstigere Annahme. Der Trade wird zusätzlich mit `ambiguous_execution=true` und `exit_reasons_all_json` (beide Gründe) markiert, damit dies im Dashboard sichtbar bleibt, auch wenn ein eindeutiger `exit_reason` gespeichert wird.

## SLIPPAGE_MODEL / FEE_MODEL

Wiederverwendet Welle 1s `DEFAULT_SLIPPAGE_BPS`/`DEFAULT_FEES_BPS` (`trading.pipeline_config`) — Basispunkte auf den Handelswert, bei Entry **und** Exit separat berechnet und in `paper_trade_costs` gespeichert (`model_name='fee_bps_v1'`/`'slippage_bps_v1'`).

## Was konservativ ist (explizit benannt)

- Gap-unter-die-Zone: Fill am Zonenrand statt am tatsächlich besseren Kurs.
- Ambiguous-Bar: Stop-zuerst-Annahme statt Ziel-zuerst.
- Kein Fill am Signaltag, selbst wenn die Zone rein rechnerisch am selben Tag noch erreichbar gewesen wäre.
- `data_error`-Trades werden **nicht** automatisch geschlossen, sondern bleiben markiert bis ein manueller/nachfolgender Lauf wieder gültige Daten hat.

## Finanzierungskosten (`financing_cost`, Welle-3-Abgleich Fund 1/5)

Der Auftrag nennt `financing_cost` explizit als zu berechnende Kennzahl. Formel ist vollständig implementiert (bereits von `net_pnl` subtrahiert), der Wert ist aber **konstant 0** — kein konkretes Produkt/Broker mit definiertem Finanzierungssatz wird simuliert, konsistent mit dem bereits bestehenden Hebelprodukt-Disclaimer (Phase 9: „kein konkretes Produkt – Emittent/Spread/Finanzierungskosten selbst prüfen"). Eine erfundene Zahl (z. B. ein pauschaler Basispunktsatz ohne reale Grundlage) wäre eine Scheingenauigkeit gewesen, die Grundregel 9 widerspricht.

## Status

- ✅ Umgesetzt: Entry-/Stop-/Target-Modell, Ambiguous-Bar-Policy, Kostenmodell inkl. `financing_cost`-Formel, Gap-Behandlung.
- 🔴 Nicht live getestet (siehe `docs/TESTPLAN_WELLE_3.md`) — nur als lokale Unit-Tests der Kernlogik verifiziert.
- 🔴 Bewusst nicht umgesetzt: ein echtes Intraday-Ausführungsmodell (keine Datenquelle mit Minutenauflösung vorhanden).
