-- ============================================================================
-- Paket 8 (Phase 5/6/7 der fachlichen Ueberarbeitung, erster Schritt):
-- Point-in-Time-Historie fuer Fundamentaldaten/Marktumfeld/Technische Signale
-- ============================================================================
-- Additiv, parallel zu den bestehenden n8n Data Tables (stock_fundamentals/
-- stock_market_context/stock_technical_signals), die weiterhin unveraendert von
-- 01/02/02b beschrieben und von 00/06/07/10 gelesen werden - KEIN Consumer wird
-- in diesem Paket umgestellt. Konvention wie trading.stock_price_history
-- (sql/004): natuerlicher Schluessel + UNIQUE, fetched_at-Audit-Spalte, Upsert
-- via ON CONFLICT. Alle Quellspalten als TEXT (Data Tables selbst sind komplett
-- string-typisiert, keine Typen erfinden).

CREATE TABLE IF NOT EXISTS trading.fundamentals_history (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  snapshot_date DATE NOT NULL,
  name TEXT,
  kgv TEXT,
  "kgvForward" TEXT,
  kbv TEXT,
  "dividendeRendite" TEXT,
  "dividendeJe" TEXT,
  "exDividendeDatum" TEXT,
  "dividendenDatum" TEXT,
  "naechsterBericht" TEXT,
  beta TEXT,
  marktkapitalisierung TEXT,
  verschuldungsgrad TEXT,
  eigenkapitalrendite TEXT,
  gewinnmarge TEXT,
  kursziel TEXT,
  empfehlung TEXT,
  zeitstempel TEXT,
  quelle TEXT,
  status TEXT,
  fehler TEXT,
  letzter_fehler_zeitpunkt TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_fundamentals_history_ticker_date UNIQUE (ticker, snapshot_date)
);

CREATE TABLE IF NOT EXISTS trading.market_context_history (
  id BIGSERIAL PRIMARY KEY,
  symbol TEXT NOT NULL,
  snapshot_date DATE NOT NULL,
  name TEXT,
  markt_typ TEXT,
  region TEXT,
  waehrung TEXT,
  referenz_fuer TEXT,
  zeitstempel TEXT,
  type TEXT,
  aktueller_kurs TEXT,
  veraenderung_abs TEXT,
  veraenderung_pct TEXT,
  rsi TEXT,
  rsi_signal TEXT,
  macd TEXT,
  macd_signal_linie TEXT,
  macd_histogramm TEXT,
  macd_signal TEXT,
  trend TEXT,
  ema20 TEXT,
  bb_oben TEXT,
  bb_mitte TEXT,
  bb_unten TEXT,
  kurs_bei_bollinger TEXT,
  signal_punkte TEXT,
  signal_gruende TEXT,
  signal_staerke TEXT,
  markt_status TEXT,
  risk_level TEXT,
  markt_hinweis TEXT,
  quelle TEXT,
  status TEXT,
  fehler TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_market_context_history_symbol_date UNIQUE (symbol, snapshot_date)
);

CREATE TABLE IF NOT EXISTS trading.technical_signals_history (
  id BIGSERIAL PRIMARY KEY,
  ticker TEXT NOT NULL,
  snapshot_date DATE NOT NULL,
  name TEXT,
  sektor TEXT,
  zeitstempel TEXT,
  type TEXT,
  aktueller_kurs TEXT,
  veraenderung TEXT,
  rsi TEXT,
  rsi_signal TEXT,
  macd TEXT,
  macd_signal_linie TEXT,
  macd_histogramm TEXT,
  macd_signal TEXT,
  macd_kreuzung TEXT,
  macd_null_linie TEXT,
  macd_histogramm_trend TEXT,
  trend TEXT,
  ema20 TEXT,
  bb_oben TEXT,
  bb_mitte TEXT,
  bb_unten TEXT,
  kurs_bei_bollinger TEXT,
  hoch_52w TEXT,
  tief_52w TEXT,
  abstand_vom_tief TEXT,
  volumen_faktor TEXT,
  signal_punkte TEXT,
  signal_gruende TEXT,
  signal_staerke TEXT,
  richtung TEXT,
  handels_status TEXT,
  handels_status_text TEXT,
  entscheidung_kurz TEXT,
  entscheidung_lang TEXT,
  ziel_kurs TEXT,
  stop_kurs TEXT,
  ziel_logik TEXT,
  stop_logik TEXT,
  gebuehren_puffer_pct TEXT,
  min_brutto_potenzial_pct TEXT,
  brutto_potenzial_pct TEXT,
  netto_potenzial_pct TEXT,
  risiko_pct TEXT,
  crv TEXT,
  potenzial_ausreichend TEXT,
  potenzial_gut TEXT,
  crv_ok TEXT,
  macd_bestaetigt_richtung TEXT,
  referenz_index TEXT,
  referenz_index_name TEXT,
  index_veraenderung_pct TEXT,
  index_trend TEXT,
  index_markt_status TEXT,
  relative_staerke_pct TEXT,
  markt_bestaetigt_signal TEXT,
  markt_hinweis TEXT,
  hinweis TEXT,
  status TEXT,
  fehler TEXT,
  extra_kontext_hinweis TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_technical_signals_history_ticker_date UNIQUE (ticker, snapshot_date)
);

CREATE INDEX IF NOT EXISTS ix_fundamentals_history_ticker_date ON trading.fundamentals_history (ticker, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS ix_market_context_history_symbol_date ON trading.market_context_history (symbol, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS ix_technical_signals_history_ticker_date ON trading.technical_signals_history (ticker, snapshot_date DESC);

COMMENT ON TABLE trading.fundamentals_history IS
    'Additive taegliche Historie von stock_fundamentals (Data Table), die selbst keine Historie haelt. Kein Consumer liest hieraus in diesem Paket.';
COMMENT ON TABLE trading.market_context_history IS
    'Additive taegliche Historie von stock_market_context (Data Table), die selbst keine Historie haelt. Kein Consumer liest hieraus in diesem Paket.';
COMMENT ON TABLE trading.technical_signals_history IS
    'Additive taegliche Historie von stock_technical_signals (Data Table), die selbst keine Historie haelt. Kein Consumer liest hieraus in diesem Paket.';
