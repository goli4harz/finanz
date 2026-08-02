# Paper-Trading-Ledger (Welle 3, AP1)

Stand: 2026-08-01. `trading.paper_trades` (+ `paper_trade_events`/`_valuations`/`_costs`, `sql/035`) ist das autoritative Ledger für theoretische Trades — getrennt von `trading.recommendations` (Welle 1/2), das als Kandidaten-/Signal-Ebene unverändert bestehen bleibt.

## Warum zwei Tabellen (`recommendations` und `paper_trades`)?

`recommendations` (seit Welle 1) ist das Ergebnis von `06`s Strategieentscheidung — ein Kandidat mit Stop/Ziel/These, aber **ohne** Portfoliorisiko-Prüfung und **ohne** realistische Ausführungssimulation (jede Eröffnung wurde bisher sofort als "offen" behandelt, ohne zu prüfen, ob der Kurs die Einstiegszone überhaupt erreicht). `paper_trades` (neu, Welle 3) ist die nachgelagerte, portfoliorisiko-geprüfte, ausführungssimulierte Ebene: Workflow `14` liest `06`s neue Empfehlungen und entscheidet erst danach, ob und wie ein Trade tatsächlich "passiert". Diese Trennung vermeidet einen riskanten Umbau von `06`s bereits in Welle 1/2 getesteter Logik.

## Statusmodell

`proposed` (Portfoliorisiko genehmigt, wartet auf Einstiegszonen-Berührung) → `open` (gefüllt) → `closed` (Exit-Grund erfasst). Alternativ: `blocked` (Portfoliorisiko lehnt ab, Trade existiert trotzdem im Ledger mit vollständiger Begründung), `expired_unfilled` (Einstiegszone nie erreicht, Zeitstop/These abgelaufen), `data_error` (fehlende Kursdaten bei einem offenen Trade — sicherer manueller Prüfpfad statt automatischem Schließen), `cancelled` (schema-vorbereitet, aktuell kein Producer).

## Ereignis-Historie

Jede Statusänderung erzeugt zusätzlich eine Zeile in `paper_trade_events` (`event_type`, `old_status`, `new_status`, `details_json`) — `paper_trades` selbst wird laufend aktualisiert (UPDATE), aber nie als einzige Quelle der Wahrheit behandelt. Ein Audit kann jederzeit den vollständigen Verlauf eines Trades rekonstruieren.

## Trade-ID und Wiederholungssicherheit (Test 22)

`trade_id = ticker + '-' + business_date + '-' + strategy` (z.B. `SAP.DE-2026-08-01-trend_following`). `ON CONFLICT (trade_id) DO NOTHING` beim Anlegen — ein wiederholter Lauf von Workflow `14` am selben Tag für denselben Ticker/Strategie erzeugt **keinen** doppelten Trade.

## Kostenkomponenten

`paper_trade_costs` speichert jede Kostenkomponente einzeln (`entry_fee`, `exit_fee`, `entry_slippage`, `exit_slippage`) mit Modellname — reproduzierbar, nicht als ein einziger Pauschalbetrag verrechnet.

## Status

- ✅ Umgesetzt: vollständiges Schema, Statusmodell, Ereignis-Historie, Wiederholungssicherheit.
- 🔴 Nicht live getestet (0 Trades zum Zeitpunkt dieser Migration — das Ledger ist fabrikneu, siehe `docs/TESTPLAN_WELLE_3.md`).

## Update Härtung Welle 1-3 (2026-08-02)

- **`data_error`-Wiederherstellung** (Phase 4, `sql/051`): neue Spalte `pre_data_error_status` sichert den Status vor Eintritt eines Datenfehlers; nach Wiederherstellung gültiger Kursdaten wird daraus restauriert statt eines festen Rückfallwerts. Eskalation zu `data_error_final` nach `MAX_DATA_ERROR_RETRIES` (strukturell terminal, taucht nicht mehr in der Ladequery auf).
- **Phase 16 (Idempotenz-Audit)**: die hier bereits dokumentierte `trade_id`+`ON CONFLICT DO NOTHING`-Wiederholungssicherheit wurde im Rahmen des großen Härtungsauftrags erneut unabhängig bestätigt (siehe `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md`, Phase 16, sowie `tests/welle_1_3_testsuite.js`, Suite B/E) — kein neuer Fund, weiterhin korrekt.
- **Gap-through-Stop-Audit-Felder** (Phase 5): `raw_exit_price`, `effective_exit_price`, `gap_through_stop`, `gap_amount`, `execution_quality` ergänzt — siehe `docs/AUSFUEHRUNGSMODELL.md` für Details.
