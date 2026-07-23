-- Führt die nach 004 produktiv ergänzten Tabellen und Spalten im Repository
-- nach. Alle Operationen sind additiv und wiederholbar.

CREATE SCHEMA IF NOT EXISTS trading;

CREATE TABLE IF NOT EXISTS trading.watchlist (
    id               BIGSERIAL PRIMARY KEY,
    ticker           TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    sektor           TEXT,
    keywords         TEXT[] NOT NULL DEFAULT '{}',
    exclude_keywords TEXT[] NOT NULL DEFAULT '{}',
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_watchlist_active
    ON trading.watchlist (active);

CREATE TABLE IF NOT EXISTS trading.recommendations (
    id                    BIGSERIAL PRIMARY KEY,
    ticker                TEXT NOT NULL,
    name                  TEXT,
    sektor                TEXT,
    richtung              TEXT NOT NULL
                          CHECK (richtung IN ('kauf', 'verkauf')),
    status                TEXT NOT NULL DEFAULT 'offen'
                          CHECK (status IN ('offen', 'geschlossen')),
    entry_datum           DATE NOT NULL,
    entry_kurs            NUMERIC(18,6) NOT NULL,
    entry_grund           TEXT,
    exit_datum            DATE,
    exit_kurs             NUMERIC(18,6),
    exit_grund            TEXT,
    performance_pct       NUMERIC(10,4),
    letzte_aktualisierung TIMESTAMPTZ,
    hebelprodukt_typ      TEXT,
    hebel_spanne          TEXT,
    basispreis_hebel_3    NUMERIC(18,6),
    basispreis_hebel_4    NUMERIC(18,6),
    onvista_link          TEXT,
    hebelprodukt_hinweis  TEXT,
    run_id                TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_recommendations_one_open_per_ticker
    ON trading.recommendations (ticker)
    WHERE status = 'offen';

CREATE INDEX IF NOT EXISTS ix_recommendations_status
    ON trading.recommendations (status);

ALTER TABLE trading.news_assessments
    ADD COLUMN IF NOT EXISTS usage_type TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'news_assessments_usage_type_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_usage_type_check
            CHECK (
                usage_type IN ('matrix_alert', 'tagesreport', 'speichern', 'verwerfen')
                OR usage_type IS NULL
            );
    END IF;
END
$$;

ALTER TABLE trading.news_impact_tracking
    ADD COLUMN IF NOT EXISTS baseline_quality TEXT,
    ADD COLUMN IF NOT EXISTS direction_correct_d1 BOOLEAN,
    ADD COLUMN IF NOT EXISTS direction_correct_d3 BOOLEAN,
    ADD COLUMN IF NOT EXISTS direction_correct_d5 BOOLEAN,
    ADD COLUMN IF NOT EXISTS direction_correct_d10 BOOLEAN,
    ADD COLUMN IF NOT EXISTS direction_correct_d20 BOOLEAN,
    ADD COLUMN IF NOT EXISTS has_major_followup_news BOOLEAN NOT NULL DEFAULT FALSE;

INSERT INTO trading.watchlist
    (ticker, name, sektor, keywords, exclude_keywords, active)
SELECT
    si.ticker,
    si.name,
    si.sektor,
    ARRAY(SELECT jsonb_array_elements_text(si.aliases_json)),
    ARRAY(SELECT jsonb_array_elements_text(si.exclude_patterns_json)),
    si.aktiv
FROM trading.stock_instruments si
ON CONFLICT (ticker) DO NOTHING;
