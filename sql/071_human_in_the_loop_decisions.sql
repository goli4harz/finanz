-- ============================================================================
-- Human-in-the-Loop Phase 3, Schritt 1: Kern-Tabellen der Entscheidungsschicht
-- ============================================================================
-- Siehe HUMAN_IN_THE_LOOP_REVIEW.md (Phase 1) und HUMAN_IN_THE_LOOP_ARCHITECTURE.md
-- (Phase 2, Abschnitte 3+4) fuer die vollstaendige Begruendung. Additiv, referenziert
-- ausschliesslich bestehende Tabellen, keine Aenderung an recommendations/paper_trades
-- selbst.

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. trading.recommendation_decisions (Modul 2: Annehmen/Ablehnen/Beobachten/Spaeter)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trading.recommendation_decisions (
  id                     BIGSERIAL PRIMARY KEY,
  recommendation_id      BIGINT NOT NULL REFERENCES trading.recommendations(id),
  entscheidung           TEXT NOT NULL CHECK (entscheidung IN ('angenommen','abgelehnt','beobachten','spaeter')),
  ablehnungsgruende_json JSONB,
  freitext               TEXT,
  system_werte_json      JSONB NOT NULL,
  meine_werte_json       JSONB,
  paper_trade_id         TEXT REFERENCES trading.paper_trades(trade_id),
  status                 TEXT NOT NULL DEFAULT 'aktuell' CHECK (status IN ('aktuell','ueberholt')),
  version                INTEGER NOT NULL DEFAULT 1,
  config_snapshot_json   JSONB,
  entschieden_am         TIMESTAMPTZ NOT NULL DEFAULT now(),
  entschieden_von        TEXT NOT NULL DEFAULT 'nutzer',
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendation_decisions_aktuell
  ON trading.recommendation_decisions (recommendation_id) WHERE status = 'aktuell';
CREATE INDEX IF NOT EXISTS ix_recommendation_decisions_recommendation
  ON trading.recommendation_decisions (recommendation_id, entschieden_am DESC);

COMMENT ON TABLE trading.recommendation_decisions IS
  'Human-in-the-Loop Modul 2: Nutzerentscheidung zu einer Empfehlung, getrennt von der '
  'Empfehlung selbst gespeichert. system_werte_json ist ein EINGEFRORENER Snapshot des '
  'Systemvorschlags zum Entscheidungszeitpunkt und wird NIE nachtraeglich geaendert - '
  'recommendations selbst kann sich weiterentwickeln (Status/performance_pct), diese Zeile '
  'beantwortet dauerhaft "was hat das System damals vorgeschlagen". Eine erneute Entscheidung '
  'zur selben Empfehlung legt eine NEUE Zeile an (status=aktuell) und setzt die alte auf '
  'ueberholt - identisches Muster wie trading.strategy_regime_matrix (sql/067).';
COMMENT ON COLUMN trading.recommendation_decisions.ablehnungsgruende_json IS
  'JSON-Array aus: risiko_zu_hoch, stop_unlogisch, einstieg_gefaellt_nicht, news_nicht_ueberzeugend, '
  'technik_nicht_ueberzeugend, portfolio_exponiert, hebel_zu_hoch, ereignisrisiko, '
  'andere_einschaetzung, sonstiges. Mehrfachauswahl moeglich, nur bei entscheidung=abgelehnt sinnvoll.';
COMMENT ON COLUMN trading.recommendation_decisions.meine_werte_json IS
  'NULL = Systemvorschlag unveraendert uebernommen. Sonst die vom Nutzer manuell geaenderten '
  'Felder (z.B. entry/stop/target/hebel) - niemals system_werte_json ueberschreiben, siehe Tabellenkommentar.';

-- ----------------------------------------------------------------------------
-- 2. trading.trade_reviews (Modul 3: Bewertung nach Trade-Abschluss)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trading.trade_reviews (
  id                  BIGSERIAL PRIMARY KEY,
  trade_id            TEXT NOT NULL UNIQUE REFERENCES trading.paper_trades(trade_id),
  vorschlag_sinnvoll  TEXT CHECK (vorschlag_sinnvoll IN ('ja','teilweise','nein')),
  entry_sinnvoll      TEXT CHECK (entry_sinnvoll IN ('ja','teilweise','nein')),
  stop_sinnvoll       TEXT CHECK (stop_sinnvoll IN ('ja','teilweise','nein')),
  target_sinnvoll     TEXT CHECK (target_sinnvoll IN ('ja','teilweise','nein')),
  hebel_sinnvoll      TEXT CHECK (hebel_sinnvoll IN ('ja','teilweise','nein')),
  richtung_richtig    TEXT CHECK (richtung_richtig IN ('ja','teilweise','nein')),
  begruendung_korrekt TEXT CHECK (begruendung_korrekt IN ('ja','teilweise','nein')),
  kommentar           TEXT,
  reviewed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_von        TEXT NOT NULL DEFAULT 'nutzer'
);

COMMENT ON TABLE trading.trade_reviews IS
  'Human-in-the-Loop Modul 3: strukturierte Rueckschau nach Trade-Abschluss. Ein Review je '
  'Trade (UNIQUE trade_id) - anders als recommendation_decisions bewusst ueberschreibbar bei '
  'erneutem Absenden, da eine nachtraegliche Einschaetzung, kein Audit-kritischer Systemwert.';

-- ----------------------------------------------------------------------------
-- 3. trading.news_false_negative_flags (Modul 4: vom Filter verworfen, aber evtl. relevant)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trading.news_false_negative_flags (
  id                   BIGSERIAL PRIMARY KEY,
  news_id              BIGINT NOT NULL REFERENCES trading.news_items(id),
  markiert_von         TEXT NOT NULL DEFAULT 'nutzer',
  grund                TEXT,
  status               TEXT NOT NULL DEFAULT 'possible_false_negative'
                       CHECK (status IN ('possible_false_negative','filter_revision_required','bestaetigt_kein_fehler','bestaetigt_false_negative')),
  ausloesende_regel_id BIGINT REFERENCES trading.news_match_exclusions(id),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at          TIMESTAMPTZ,
  reviewed_von         TEXT
);

CREATE INDEX IF NOT EXISTS ix_news_false_negative_flags_news
  ON trading.news_false_negative_flags (news_id);
CREATE INDEX IF NOT EXISTS ix_news_false_negative_flags_status
  ON trading.news_false_negative_flags (status);

COMMENT ON TABLE trading.news_false_negative_flags IS
  'Human-in-the-Loop Modul 4: die bisher komplett fehlende Gegenrichtung zum bestehenden '
  'False-Positive-System (news_match_exclusion_candidates). status=filter_revision_required '
  'loest NICHTS automatisch aus - siehe HUMAN_IN_THE_LOOP_ARCHITECTURE.md Abschnitt 6 '
  '(Feedbackmodell): erst Mustererkennung ueber mehrere Faelle, dann learning_rule_proposals, '
  'dann regulaere Freigabe.';

-- ----------------------------------------------------------------------------
-- 4. trading.news_items.status: neuer Wert 'filtered' fuer Modul 4
-- ----------------------------------------------------------------------------
-- Idempotentes Muster wie sql/038 (activation_failed-Status): nur aendern, wenn 'filtered'
-- noch nicht Teil der bestehenden CHECK-Bedingung ist.
DO $body$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_news_items_status'
          AND pg_get_constraintdef(oid) LIKE '%filtered%'
    ) THEN
        ALTER TABLE trading.news_items
            DROP CONSTRAINT IF EXISTS chk_news_items_status;
        ALTER TABLE trading.news_items
            ADD CONSTRAINT chk_news_items_status
            CHECK (status IN ('pending','processing','evaluated','retry','failed','discarded','filtered'));
    END IF;
END $body$;

COMMENT ON COLUMN trading.news_items.status IS
  'pending/processing/evaluated/retry/failed = normaler KI-Bewertungspfad. discarded = nach '
  'KI-Bewertung als irrelevant verworfen. filtered = NEU (Human-in-the-Loop Modul 4): vom '
  'Regex-Vorfilter in Workflow 03 verworfen, BEVOR eine KI-Bewertung stattfand - vorher wurden '
  'diese Artikel gar nicht persistiert (siehe HUMAN_IN_THE_LOOP_REVIEW.md Fund 4), jetzt fuer '
  'die False-Negative-Pruefung sichtbar. discarded_reason traegt die zutreffende Filterkategorie.';

-- ----------------------------------------------------------------------------
-- 5. trading.probability_estimates: data_source-Spalte (paper_trades | simulation_trades)
-- ----------------------------------------------------------------------------
ALTER TABLE trading.probability_estimates
  ADD COLUMN IF NOT EXISTS data_source TEXT NOT NULL DEFAULT 'paper_trades'
    CHECK (data_source IN ('paper_trades','simulation_trades'));

-- Der bestehende Unique-Constraint (ohne data_source) muss um data_source erweitert werden,
-- sonst koennten sich Paper-Trade- und Simulations-Statistiken fuer dasselbe Segment
-- gegenseitig ueberschreiben. Name wird dynamisch ermittelt statt geraten (Postgres vergibt
-- bei einer inline UNIQUE(...)-Klausel in CREATE TABLE einen automatischen Namen).
DO $body$
DECLARE
    old_constraint_name TEXT;
BEGIN
    SELECT conname INTO old_constraint_name
    FROM pg_constraint
    WHERE conrelid = 'trading.probability_estimates'::regclass
      AND contype = 'u'
      AND pg_get_constraintdef(oid) NOT LIKE '%data_source%';

    IF old_constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE trading.probability_estimates DROP CONSTRAINT %I', old_constraint_name);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'trading.probability_estimates'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) LIKE '%data_source%'
    ) THEN
        ALTER TABLE trading.probability_estimates
          ADD CONSTRAINT uq_probability_estimates_segment
          UNIQUE (segment_strategy, segment_direction, segment_market_regime, segment_risk_bucket,
                  segment_evidence_bucket, segment_time_horizon, rule_version, data_source);
    END IF;
END $body$;

COMMENT ON COLUMN trading.probability_estimates.data_source IS
  'paper_trades (Default, echte Trades) oder simulation_trades (Human-in-the-Loop-Erweiterung '
  '2026-08-20: mehr Datenbasis fuer historische Vergleichsfaelle, solange echte Paper-Trades '
  'noch selten sind). Bewusst Teil des Unique-Constraints, NICHT nur Info-Spalte - reale und '
  'simulierte Statistik fuer dasselbe Segment duerfen sich nicht stillschweigend vermischen '
  '(Grundregel 9, keine Scheingenauigkeit). Ein Konsument zeigt die Quelle immer sichtbar an.';

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('071', 'Human-in-the-Loop Phase 3: recommendation_decisions, trade_reviews, news_false_negative_flags, news_items.filtered-Status, probability_estimates.data_source')
ON CONFLICT (version) DO NOTHING;

COMMIT;
