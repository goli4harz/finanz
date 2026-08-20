-- ============================================================================
-- Human-in-the-Loop Phase 3, Schritt 2: News-Review-Notizen (Modul 4)
-- ============================================================================
-- sql/071 deckt die relevant/irrelevant-Bestaetigung bereits ueber den bestehenden,
-- bisher ungenutzten Hook trading.news_assessments.confirmation_status ab (sql/012),
-- und die "vom Filter zu Unrecht verworfen"-Richtung ueber news_false_negative_flags.
-- Es fehlt eine Ablage fuer die verbleibenden Faelle "unsicher" und "falsch bewertet"
-- (Bewertung selbst fragwuerdig, nicht die Relevanz) samt Freitext-Kommentar -
-- confirmation_status kennt nur 3 feste Werte und hat keine Kommentarspalte.
-- Additiv, gleiches Muster wie trading.trade_reviews (sql/071): ein Datensatz pro
-- News, ueberschreibbar bei erneutem Absenden (keine Audit-kritische Systemgroesse).

BEGIN;

CREATE TABLE IF NOT EXISTS trading.news_review_notes (
  id           BIGSERIAL PRIMARY KEY,
  news_id      BIGINT NOT NULL UNIQUE REFERENCES trading.news_items(id),
  urteil       TEXT NOT NULL CHECK (urteil IN ('relevant','irrelevant','unsicher','falsch_bewertet')),
  kommentar    TEXT,
  reviewed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_von TEXT NOT NULL DEFAULT 'nutzer'
);

CREATE INDEX IF NOT EXISTS ix_news_review_notes_news ON trading.news_review_notes (news_id);

COMMENT ON TABLE trading.news_review_notes IS
  'Human-in-the-Loop Modul 4: Freitext-faehige Notiz zu einer News-Bewertung. Ergaenzt (ersetzt '
  'nicht) trading.news_assessments.confirmation_status: relevant/irrelevant setzen zusaetzlich '
  'confirmation_status auf manually_confirmed/manually_rejected (bestehender Hook aus sql/012, '
  'damit trading.v_news_latest_assessment sofort profitiert); unsicher/falsch_bewertet haben dort '
  'keine passende Auspraegung und werden ausschliesslich hier gehalten. Ueberschreibbar bei '
  'erneutem Absenden, gleiches Muster wie trading.trade_reviews.';

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('072', 'Human-in-the-Loop Phase 3: news_review_notes (Modul 4, unsicher/falsch_bewertet + Freitext)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
