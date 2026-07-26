-- ============================================================================
-- 008_rss_sources.sql
--
-- Konfigurierbare RSS-Quellenliste fuer Workflow "03 - News Ingestion". Loest
-- das bisher fest im Code hinterlegte `feeds`-Array in "RSS-Feeds laden &
-- filtern" ab (analog zu trading.watchlist, die die frueher hartkodierte
-- Ticker-Liste abgeloest hat) - Verwaltung ueber den neuen Workflow
-- "RSS-Quellen verwalten" (Webhook /webhook/rss-quellen).
--
-- Wiederholbar/idempotent: CREATE ... IF NOT EXISTS, ON CONFLICT DO NOTHING.
-- Loescht oder veraendert KEINE bestehenden Tabellen/Daten.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS trading;

CREATE TABLE IF NOT EXISTS trading.rss_sources (
    id                    BIGSERIAL PRIMARY KEY,
    name                  TEXT NOT NULL,
    url                   TEXT NOT NULL UNIQUE,
    active                BOOLEAN NOT NULL DEFAULT TRUE,
    last_test_at          TIMESTAMPTZ,
    last_test_status      TEXT
                          CONSTRAINT chk_rss_sources_test_status
                          CHECK (last_test_status IN ('ok', 'fehler') OR last_test_status IS NULL),
    last_test_message     TEXT,
    last_test_item_count  INTEGER,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_rss_sources_active ON trading.rss_sources (active);

COMMENT ON TABLE trading.rss_sources IS
    'Konfigurierbare RSS-Feed-Quellen fuer 03 - News Ingestion. Ersetzt das '
    'vorher hartkodierte feeds-Array in dessen Node "RSS-Feeds laden & filtern". '
    'last_test_* wird vom Validierungs-Button in "RSS-Quellen verwalten" befuellt, '
    'nicht von 03 selbst.';

-- Seed: die bisher hartkodierten 7 Feeds unveraendert uebernehmen, damit die
-- Migration keine Verhaltensaenderung an 03 bewirkt, solange 03 noch nicht
-- umgestellt ist.
INSERT INTO trading.rss_sources (name, url) VALUES
    ('Tagesschau', 'https://www.tagesschau.de/xml/rss2'),
    ('Tagesschau Wirtschaft', 'https://www.tagesschau.de/wirtschaft/index~rss2.xml'),
    ('Die Welt', 'https://www.welt.de/feeds/latest.rss'),
    ('Spiegel Wirtschaft', 'https://www.spiegel.de/wirtschaft/index.rss'),
    ('Stern', 'https://www.stern.de/feed/standard/all/'),
    ('Zeit Wirtschaft', 'https://newsfeed.zeit.de/wirtschaft/index'),
    ('n-tv Wirtschaft', 'https://www.n-tv.de/wirtschaft/rss')
ON CONFLICT (url) DO NOTHING;
