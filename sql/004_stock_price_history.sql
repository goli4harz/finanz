-- Dedizierte Tageskurshistorie für Wirkungsanalyse und Dashboard.
-- Ein Datensatz pro Symbol und Handelstag.

CREATE SCHEMA IF NOT EXISTS trading;

CREATE TABLE IF NOT EXISTS trading.stock_price_history (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT NOT NULL,
    trading_date DATE NOT NULL,
    open         NUMERIC(18,6),
    high         NUMERIC(18,6),
    low          NUMERIC(18,6),
    close        NUMERIC(18,6) NOT NULL,
    volume       NUMERIC(24,4),
    currency     TEXT,
    source       TEXT,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_price_history_symbol_date
        UNIQUE (symbol, trading_date)
);

CREATE INDEX IF NOT EXISTS ix_stock_price_history_symbol_date
    ON trading.stock_price_history (symbol, trading_date DESC);
