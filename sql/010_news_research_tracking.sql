-- ============================================================================
-- 010_news_research_tracking.sql
--
-- Paket 1 (Phase 3 der "Fachlichen Ueberarbeitung", Schema-Teil): verhindert
-- wiederholte Recherche fuer News, die bereits erfolgreich recherchiert
-- wurden. Legt nur die Tracking-Spalten an - die eigentliche Auswahl-Logik
-- in 03a folgt in einem eigenen Paket.
--
-- Bewusst eine EIGENE Spaltenfamilie, getrennt von den bestehenden
-- retry_count/status/last_error/last_attempt_at/next_retry_at, die die
-- Ingestion-/Erstbewertungs-Statemachine in 03 steuern - Wiederverwendung
-- dieser Felder wuerde deren bereits getestete Semantik durcheinanderbringen.
-- ============================================================================

ALTER TABLE trading.news_items
    ADD COLUMN IF NOT EXISTS research_status TEXT,
    ADD COLUMN IF NOT EXISTS research_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_research_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS next_research_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS research_error TEXT,
    ADD COLUMN IF NOT EXISTS reprocess_requested BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_items_research_status_check'
          AND conrelid = 'trading.news_items'::regclass
    ) THEN
        ALTER TABLE trading.news_items
            ADD CONSTRAINT news_items_research_status_check
            CHECK (
                research_status IN ('not_needed', 'pending', 'in_progress', 'success', 'failed', 'max_attempts_reached')
                OR research_status IS NULL
            );
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_news_items_research_status ON trading.news_items (research_status);
CREATE INDEX IF NOT EXISTS ix_news_items_next_research_at
    ON trading.news_items (next_research_at) WHERE research_status IN ('pending', 'failed');

COMMENT ON COLUMN trading.news_items.research_status IS
    'Eigener Zustandsautomat fuer den Recherche-Agenten (03a), unabhaengig vom Ingestion-status-Feld. '
    'NULL = noch nie recherchebeduerftig gewesen.';
COMMENT ON COLUMN trading.news_items.reprocess_requested IS
    'Manuelles Flag: erzwingt eine erneute Recherche unabhaengig von research_status/research_attempts.';
