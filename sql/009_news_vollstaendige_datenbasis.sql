-- ============================================================================
-- 009_news_vollstaendige_datenbasis.sql
--
-- Paket 1 (Phase 1 der "Fachlichen Ueberarbeitung", Schema-Teil): vollstaendige
-- News-Datenbasis. Bisher sah die KI-Erstbewertung teilweise nur die Ueber-
-- schrift; Beschreibung, Vorfilter-Ticker, Match-Grund und Volltext wurden
-- nicht zuverlaessig durchgereicht (siehe docs/FACHLICHE_BESTANDSAUFNAHME.md).
-- Diese Migration legt nur die Spalten an - die Workflow-Aenderungen, die sie
-- tatsaechlich befuellen (03/03a), folgen in einem eigenen Paket.
--
-- Rein additiv: ADD COLUMN IF NOT EXISTS, keine bestehenden Zeilen/Spalten
-- veraendert, kein Consumer liest diese Spalten in diesem Schritt.
-- ============================================================================

ALTER TABLE trading.news_items
    ADD COLUMN IF NOT EXISTS article_text TEXT,
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS language TEXT,
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS preclassified_type TEXT,
    ADD COLUMN IF NOT EXISTS preclassified_tickers JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS match_reason TEXT,
    ADD COLUMN IF NOT EXISTS publication_time_quality TEXT,
    ADD COLUMN IF NOT EXISTS event_cluster_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_items_publication_time_quality_check'
          AND conrelid = 'trading.news_items'::regclass
    ) THEN
        ALTER TABLE trading.news_items
            ADD CONSTRAINT news_items_publication_time_quality_check
            CHECK (
                publication_time_quality IN ('exact', 'date_only', 'estimated', 'missing')
                OR publication_time_quality IS NULL
            );
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_news_items_content_hash ON trading.news_items (content_hash);
CREATE INDEX IF NOT EXISTS ix_news_items_event_cluster_id ON trading.news_items (event_cluster_id);

COMMENT ON COLUMN trading.news_items.article_text IS
    'Volltext des Artikels, soweit abgerufen (kontrolliert, nicht fuer jede News - siehe 03/03a). Kann leer/gekuerzt sein.';
COMMENT ON COLUMN trading.news_items.content_hash IS
    'Normalisierter Hash (klein geschrieben, Whitespace vereinheitlicht, HTML entfernt) ueber Titel+Beschreibung, '
    'verhindert Doppelbewertung desselben Inhalts unter zwei URLs/Tracking-Parametern.';
COMMENT ON COLUMN trading.news_items.last_seen_at IS
    'Zeitpunkt des letzten erneuten Antreffens derselben News (z.B. erneut im RSS-Feed). '
    'first_seen_at/ingested_at werden bewusst NICHT als neue Spalten angelegt, sondern durch die bereits '
    'vorhandenen created_at/fetched_at abgedeckt (keine Doppel-Spalten mit identischer Bedeutung).';
COMMENT ON COLUMN trading.news_items.preclassified_type IS
    'Ergebnis der deterministischen Vorfilterung in 03 (z.B. stock_news/market_news/market_candidate), bevor die KI sie ggf. korrigiert.';
COMMENT ON COLUMN trading.news_items.event_cluster_id IS
    'Nullable, vorerst nur trivial befuellt (kein echtes Multi-Quellen-Clustering) - Platzhalter fuer eine spaetere Ausbaustufe.';
