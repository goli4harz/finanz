-- ============================================================================
-- Welle 1, Arbeitspaket 4: zentrale Boersensitzungs-Status-View
-- ============================================================================
-- Nutzt die bereits bestehenden, bisher von keinem Workflow gelesenen
-- Referenzdaten aus sql/015 (trading.market_reference, stock_instruments.
-- exchange - seit Paket 5 fuer alle 15 Bestandsticker auf 'XETRA' befuellt).
-- Einzige zentrale Stelle fuer den Sitzungsstatus - 02 und 06 fragen diese
-- View ab, statt die Logik in JS zu duplizieren.
--
-- Bekannte, bewusste Einschraenkung (siehe docs/DATENQUALITAET_UND_SESSIONS.md):
-- es existiert kein echter Feiertagskalender. trading_days_iso erkennt nur
-- Wochenenden zuverlaessig. Ein echter Feiertag (z.B. Karfreitag) wird daher
-- NICHT als 'holiday' erkannt, sondern faellt in die Frische-Pruefung und
-- landet dort korrekt als 'stale' (erwartete neue Kerze fehlt), sobald die
-- lokale Zeit nach Sitzungsschluss liegt. 'stale' ist der sichere Default:
-- es blockiert im Zweifel eher zu vorsichtig als zu freizuegig.

CREATE OR REPLACE VIEW trading.v_market_session_status AS
WITH letzte_kerze AS (
  SELECT symbol, MAX(trading_date) AS letztes_datum
  FROM trading.stock_price_history
  WHERE valid_to IS NULL
  GROUP BY symbol
)
SELECT
  si.ticker,
  si.exchange AS market_code,
  mr.exchange_timezone,
  mr.session_open_local,
  mr.session_close_local,
  mr.trading_days_iso,
  CASE WHEN mr.exchange_timezone IS NOT NULL
       THEN (now() AT TIME ZONE mr.exchange_timezone)::date END AS lokales_datum,
  CASE WHEN mr.exchange_timezone IS NOT NULL
       THEN (now() AT TIME ZONE mr.exchange_timezone)::time END AS lokale_zeit,
  CASE WHEN mr.exchange_timezone IS NOT NULL
       THEN extract(isodow FROM (now() AT TIME ZONE mr.exchange_timezone))::int END AS lokaler_wochentag,
  lk.letztes_datum AS letztes_verfuegbares_handelsdatum,
  CASE
    WHEN si.exchange IS NULL OR mr.exchange_timezone IS NULL THEN 'unknown'
    WHEN NOT (extract(isodow FROM (now() AT TIME ZONE mr.exchange_timezone))::int = ANY (mr.trading_days_iso)) THEN 'holiday'
    WHEN (now() AT TIME ZONE mr.exchange_timezone)::time < mr.session_open_local THEN 'closed_complete'
    WHEN (now() AT TIME ZONE mr.exchange_timezone)::time < mr.session_close_local THEN 'open_intraday'
    WHEN lk.letztes_datum IS NULL THEN 'stale'
    WHEN lk.letztes_datum < (now() AT TIME ZONE mr.exchange_timezone)::date THEN 'stale'
    ELSE 'closed_complete'
  END AS session_status
FROM trading.stock_instruments si
LEFT JOIN trading.market_reference mr ON mr.market_code = si.exchange
LEFT JOIN letzte_kerze lk ON lk.symbol = si.ticker
WHERE si.aktiv = TRUE;

COMMENT ON VIEW trading.v_market_session_status IS
    'AP4 der Welle-1-Ueberarbeitung: zentrale Sitzungsstatus-Ermittlung je aktivem Ticker. '
    'closed_complete = Sitzung heute planmaessig beendet UND heutige Kerze bereits vorhanden; '
    'open_intraday = Sitzung laeuft noch (Kursdaten waeren untertaegig, nicht abgeschlossen); '
    'holiday = kein planmaessiger Handelstag laut trading_days_iso (aktuell nur Wochenenden); '
    'unknown = kein exchange/market_reference-Eintrag vorhanden; '
    'stale = planmaessiger Handelstag, Sitzung sollte laut Uhrzeit beendet sein, aber keine '
    'aktuelle Kerze vorhanden (echter Feiertag ohne Kalendereintrag ODER ein Datenproblem - '
    'sicherheitshalber gleich behandelt).';
