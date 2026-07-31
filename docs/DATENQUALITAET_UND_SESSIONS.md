# Datenqualität und Börsensitzungen (Welle 1)

Stand: 2026-07-31, Arbeitspakete 1-4 des Auftrags "Welle 1 – Verlässliche Datenbasis, harte Vetos und Einzeltrade-Risiko". Dieses Dokument beschreibt die tatsächliche Kursdatenquelle, die Kerzenbildung/Qualitätsklassifikation in `02` und die Sitzungsstatus-Ermittlung.

## 1. Der lokale FastAPI-Kursdienst (`http://172.16.1.14:8099`)

Live geprüft am 2026-07-31 (`GET /chart/{symbol}?period=1y&interval=1d`, getestet mit `AAPL` und `SAP.DE`):

- Antwortformat: Yahoo-Finance-Chart-Schema (`chart.result[0].meta`, `.timestamp[]`, `.indicators.quote[0].{open,high,low,close,volume}[]`).
- `meta` enthält **`symbol`, `currency`, `regularMarketPrice`, `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`** — aber **NICHT** `exchangeName`, `exchangeTimezoneName`, `regularMarketTime`, `marketState`, `gmtoffset`. Der Dienst reicht also einen echten, quellenseitig gepflegten 52-Wochen-Wert durch (unabhängig vom Abrufzeitraum), liefert aber keine Session-/Zeitzonen-Metadaten.
- `indicators.adjclose` ist **nicht vorhanden** — `adjusted_close` bleibt in `trading.stock_price_history` deshalb strukturell immer `NULL`. Kein Fehler, sondern eine Quelleneigenschaft.
- Mit `period=1y&interval=1d`: **252 Tageskerzen für AAPL, 254 für SAP.DE**, alle Arrays gleich lang, keine `null`-Werte, keine Duplikate/unsortierten Zeitstempel — für beide getesteten Ticker sauber. `period=3mo` (der bisherige Wert in `02`/`02b`) lieferte nur **~63 Handelstage** — zu wenig für eine korrekte 52-Wochen-Aussage, falls das Meta-Feld einmal fehlt.
- **Änderung**: `02` und `02b` rufen jetzt `period=1y` statt `period=3mo` ab.

**Für Welle 2 relevant, falls der Dienst angepasst werden soll**: `adjusted_close` und echte Session-/Timezone-Metadaten (`exchangeTimezoneName`, `regularMarketTime`, `marketState`) wären die naheliegenden Ergänzungen, falls AP4 später präziser werden soll (siehe Abschnitt 4, bekannte Einschränkung). Nicht in Welle 1 umgesetzt, da der FastAPI-Dienst außerhalb dieses Repos liegt und nicht direkt bearbeitet werden konnte.

## 2. Kerzenbildung (AP2) — `02`, Node "Technische Analyse (RSI/MACD/BB)"

**Vorher**: `close`/`high`/`low`/`volume` wurden **unabhängig voneinander** gefiltert (vier separate `.filter(v => v != null)`-Aufrufe). Fehlt an einem Tag nur `high`, verschieben sich ab dort alle Folgetage in `high[]` gegenüber `close[]` um eine Position — ATR/Bollinger/52-Wochen-Berechnungen hätten falsch gepaarte Werte verwendet. Live an AAPL/SAP.DE nicht reproduziert (beide sauber), aber ein reales, dokumentiertes Risiko bei anderen Tickern oder Datenanomalien.

**Jetzt**: Kerzen werden über den gemeinsamen `timestamp`-Index gebildet. Jede Kerze durchläuft folgende Prüfungen, bevor sie in `closes`/`highs`/`lows` (und damit in RSI/MACD/BB/ATR/52-Wochen) einfließt:

| Prüfung | Ergebnis bei Verstoß |
|---|---|
| Schlusskurs fehlt | Kerze verworfen |
| High oder Low fehlt | Kerze verworfen |
| High < Low | Kerze verworfen |
| Open/Close außerhalb [Low, High] | Kerze verworfen |
| Negatives Volumen | Kerze verworfen |
| Doppelte Zeitstempel | dedupliziert (letzter Wert gewinnt), vermerkt |
| Unsortierte Zeitstempel | sortiert, vermerkt |
| Abweichende Roharray-Längen | vermerkt (`abweichende_arraylaenge`) |
| Tagesbewegung > 40% | vermerkt (`moegliche_split_oder_datenanomalie`), **nicht** automatisch verworfen (könnte real sein) |
| Letzte gültige Kerze > 5 Tage alt | `data_quality_status = 'stale'` |

## 3. Qualitätsklassen (`technical_signals_history.data_quality_status`)

Fünf Klassen wie im Auftrag gefordert, **hartes Statusfeld sticht einen hohen Score**:

- `valid`: ≥252 gültige Handelstage (oder Meta-52-Wochen-Wert vorhanden) **und** ≥60 **und** ≥20, keine Zeilenfehler, keine Duplikate/Unsortierung.
- `limited`: Grunddaten nutzbar (≥20 Tage), aber eine der Zusatzbedingungen fehlt (z.B. keine 252-Tage-Historie, oder einzelne verworfene Kerzen).
- `invalid`: < 20 gültige Handelstage, oder > 20% der Kerzen verworfen, oder abweichende Roharray-Längen.
- `stale`: letzte gültige Kerze älter als 5 Tage.
- `session_incomplete`: die aktuelle Börsensitzung läuft laut `v_market_session_status` noch (siehe Abschnitt 4) — überschreibt `valid`/`limited`.

Zusätzlich `data_quality_score` (0-100, informativ) und `data_quality_issues_json` (Array der gefundenen Probleme als Begründung — keine freie KI-Bewertung, rein regelbasiert).

## 4. Mindest-Zeiträume (AP3)

- `kurzfrist_history_ausreichend`: `closes.length >= 20`.
- `volatility_history_ausreichend`: `closes.length >= 60`.
- `breakout_history_ausreichend`: `meta.fiftyTwoWeekHigh` vorhanden **ODER** `closes.length >= 252`. Ohne beides gilt ein 52-Wochen-Hoch/-Tief als **nicht belegt** — das Breakout-Strategiesignal (Phase 6) und der neue harte Veto `HISTORY_252_MISSING` (AP5) greifen in diesem Fall.

## 5. Börsensitzungs-Status (AP4) — `trading.v_market_session_status`

Zentrale View (sql/027), nutzt die seit Paket 5 vorhandenen, bis Welle 1 ungenutzten Tabellen `trading.market_reference` und `stock_instruments.exchange`.

Status-Werte: `closed_complete`, `open_intraday`, `holiday`, `unknown`, `stale`.

**Bekannte, bewusste Einschränkung**: Es existiert **kein echter Feiertagskalender**. `trading_days_iso` erkennt zuverlässig nur Wochenenden. Ein echter Feiertag (z.B. Karfreitag) wird **nicht** als `holiday` erkannt, sondern läuft in die Frische-Prüfung und landet dort korrekt als `stale` (erwartete neue Kerze fehlt), sobald die lokale Zeit nach Sitzungsschluss liegt. Das ist der sichere Default: `stale` blockiert im Zweifel eher zu vorsichtig als zu freizügig — aber die Meldung "Feiertag" wäre fachlich präziser. Ein echter Feiertagskalender ist **bewusst zurückgestellt** (siehe Abschlussbericht, Restpunkte).

Alle 15 Bestandsticker sind XETRA (09:00-17:30 Europe/Berlin), der Orchestrator läuft 17:50/17:55/18:00/18:10 CET — die Sitzung ist zu diesem Zeitpunkt an einem normalen Handelstag planmäßig bereits beendet, `open_intraday`/`session_incomplete` sollte im Normalbetrieb praktisch nie auftreten. Vorwärtsabsicherung für künftige nicht-europäische Ticker (wie schon in Paket 5 dokumentiert).

## Status

- ✅ Umgesetzt: FastAPI-Periode auf 1y, Kerzenbildung/Zeilenprüfung, 5 Qualitätsklassen, 3 Mindest-Zeiträume, `v_market_session_status`.
- 🟡 Nur teilweise getestet: live gegen AAPL/SAP.DE verifiziert (Struktur, Längen, Nullwerte); die Zeilen-Fehlerpfade (High<Low, negatives Volumen, abweichende Arraylängen) sind **nicht** mit absichtlich kaputten Testdaten durchlaufen worden, siehe `docs/TESTPLAN_WELLE_1.md`.
- 🔴 Bewusst offen: echter Feiertagskalender, echte Session-Metadaten vom FastAPI-Dienst (adjclose, exchangeTimezoneName).
