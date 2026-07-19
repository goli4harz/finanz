-- ============================================================================
-- 001_agenten_architektur.sql
--
-- Grundschema fuer die kontrollierte Agentenarchitektur des Aktienanalyse-
-- Systems. Enthaelt Orchestrator-Laufprotokoll, Agentenprotokoll, zentrale
-- Instrumententabelle, News-Zustandsmodell, News-Wirkungsanalyse sowie die
-- versionierten Lernregeln/Prompts.
--
-- Wiederholbar/idempotent: nutzt ausschliesslich CREATE ... IF NOT EXISTS.
-- Loescht oder veraendert KEINE bestehenden Tabellen/Daten. Kann gefahrlos
-- mehrfach gegen dieselbe Datenbank ausgefuehrt werden.
--
-- Zielsystem: PostgreSQL. Schema-Name bewusst "trading" gewaehlt, um nicht in
-- die internen n8n-Systemtabellen einzugreifen (siehe Auftrag: "Verwende
-- nicht unkontrolliert die internen n8n-Systemtabellen").
--
-- Verbindungsdetails (Host/Port/Datenbankname/Credential) sind zum Zeitpunkt
-- dieser Migration NICHT bekannt -- siehe README.md,
-- Abschnitt "Benoetigte Umgebungsvariablen/Credentials". Diese Datei selbst
-- enthaelt keine Zugangsdaten.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS trading;

-- Postgres besitzt keinen nativen "CREATE TYPE IF NOT EXISTS" -- alle Status-
-- /Enum-Werte werden daher bewusst als TEXT mit CHECK-Constraint modelliert
-- statt als natives ENUM, damit diese Datei wiederholbar bleibt und neue
-- zulaessige Werte spaeter per einfachem ALTER TABLE ... DROP/ADD CONSTRAINT
-- ergaenzt werden koennen, ohne ALTER TYPE-Migrationen zu benoetigen.

-- ============================================================================
-- 1. trading.stock_instruments -- zentrale Instrumenten-/Konfigurationstabelle
--    (Phase 3: loest die heute mehrfach im Code hinterlegte Watchlist ab)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.stock_instruments (
    id                   BIGSERIAL PRIMARY KEY,
    ticker               TEXT NOT NULL,
    name                 TEXT NOT NULL,
    sektor               TEXT,
    aktiv                BOOLEAN NOT NULL DEFAULT TRUE,
    sortierung           INTEGER NOT NULL DEFAULT 0,
    aliases_json         JSONB NOT NULL DEFAULT '[]'::JSONB,
    exclude_patterns_json JSONB NOT NULL DEFAULT '[]'::JSONB,
    benchmark_symbol     TEXT,
    news_enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    technical_enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    fundamental_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    report_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    currency             TEXT NOT NULL DEFAULT 'EUR',
    exchange             TEXT,
    metadata_json        JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_instruments_ticker UNIQUE (ticker)
);

CREATE INDEX IF NOT EXISTS ix_stock_instruments_aktiv
    ON trading.stock_instruments (aktiv);

COMMENT ON TABLE trading.stock_instruments IS
    'Zentrale Watchlist/Instrumentenliste. Ersetzt schrittweise die bisher in '
    '01/02/02b/03/06 separat hartkodierten Ticker-Listen (siehe MIGRATIONSPLAN_AGENTEN.md).';

-- ============================================================================
-- 2. trading.pipeline_runs -- Orchestrator-Laufprotokoll (Phase 2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.pipeline_runs (
    id             BIGSERIAL PRIMARY KEY,
    run_id         TEXT NOT NULL,
    workflow_name  TEXT NOT NULL,
    stage_name     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CONSTRAINT chk_pipeline_runs_status
                   CHECK (status IN ('pending','running','success','warning','failed','skipped','retrying')),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    duration_ms    INTEGER,
    input_count    INTEGER,
    output_count   INTEGER,
    warning_count  INTEGER NOT NULL DEFAULT 0,
    error_count    INTEGER NOT NULL DEFAULT 0,
    error_message  TEXT,
    retry_count    INTEGER NOT NULL DEFAULT 0,
    metadata_json  JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pipeline_runs_run_id ON trading.pipeline_runs (run_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_status ON trading.pipeline_runs (status);
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_workflow_stage
    ON trading.pipeline_runs (workflow_name, stage_name);

COMMENT ON TABLE trading.pipeline_runs IS
    'Ein Eintrag pro Stufe (Sub-Workflow) eines Orchestrator-Gesamtlaufs (run_id). '
    'Mehrere Zeilen teilen sich dieselbe run_id.';

-- ============================================================================
-- 3. trading.agent_runs -- Agenten-Protokollierung
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.agent_runs (
    id                BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL,
    agent_name        TEXT NOT NULL,
    agent_role        TEXT,
    model_name        TEXT,
    prompt_version    TEXT,
    input_reference   TEXT,
    output_reference  TEXT,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CONSTRAINT chk_agent_runs_status
                      CHECK (status IN ('pending','running','success','warning','failed','skipped','retrying')),
    confidence        NUMERIC(5,2),
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    duration_ms       INTEGER,
    error_message     TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    estimated_cost    NUMERIC(10,4),
    metadata_json     JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_agent_runs_run_id ON trading.agent_runs (run_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_agent_name ON trading.agent_runs (agent_name);
CREATE INDEX IF NOT EXISTS ix_agent_runs_run_agent ON trading.agent_runs (run_id, agent_name);

COMMENT ON TABLE trading.agent_runs IS
    'Ein Eintrag pro einzelnem Agentenaufruf (News-Recherche-Agent, Lernagent, '
    'Report-Agent, Pruef-Agent, ...). token/cost-Felder werden nur befuellt, '
    'wenn der jeweilige AI-Node diese Werte liefert.';

-- ============================================================================
-- 4. trading.prompt_versions -- Prompt-Versionierung
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.prompt_versions (
    id             BIGSERIAL PRIMARY KEY,
    prompt_name    TEXT NOT NULL,
    version        INTEGER NOT NULL,
    prompt_hash    TEXT NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT FALSE,
    prompt_text    TEXT NOT NULL,
    change_reason  TEXT,
    approved_by    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_prompt_versions_name_version UNIQUE (prompt_name, version)
);

-- Nur maximal EINE aktive Version pro Prompt-Name gleichzeitig zulassen.
CREATE UNIQUE INDEX IF NOT EXISTS uq_prompt_versions_one_active_per_name
    ON trading.prompt_versions (prompt_name)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS ix_prompt_versions_name ON trading.prompt_versions (prompt_name);

COMMENT ON TABLE trading.prompt_versions IS
    'Jede Agentenausgabe referenziert die hier gespeicherte prompt_version. '
    'Der Lernagent darf ausschliesslich Zeilen mit active=false (Vorschlaege) '
    'einfuegen -- die Aktivierung (active=true setzen) erfolgt ausschliesslich '
    'durch einen separaten, deterministischen Freigabe-Workflow, niemals durch '
    'den Agenten selbst.';

-- ============================================================================
-- 5. trading.scoring_weights -- produktive Gewichtungen (getrennt von Vorschlaegen)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.scoring_weights (
    id                    BIGSERIAL PRIMARY KEY,
    weight_key            TEXT NOT NULL,
    weight_value          NUMERIC(10,4) NOT NULL,
    version               INTEGER NOT NULL DEFAULT 1,
    active                BOOLEAN NOT NULL DEFAULT FALSE,
    source_proposal_id    BIGINT,
    activated_at          TIMESTAMPTZ,
    activated_by          TEXT,
    metadata_json         JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scoring_weights_key_version UNIQUE (weight_key, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_scoring_weights_one_active_per_key
    ON trading.scoring_weights (weight_key)
    WHERE active = TRUE;

COMMENT ON TABLE trading.scoring_weights IS
    'Produktive Gewichtungen (z.B. Quellen-/Kategorie-Gewichte fuer die News-'
    'Bewertung). Getrennt von learning_rule_proposals, damit ein Vorschlag nie '
    'versehentlich sofort produktiv wirkt.';

-- ============================================================================
-- 6. trading.learning_rule_proposals -- versionierte Lernregel-Vorschlaege
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.learning_rule_proposals (
    id              BIGSERIAL PRIMARY KEY,
    proposal_type   TEXT NOT NULL,
    target_type     TEXT NOT NULL,
    target_value    TEXT NOT NULL,
    current_value   TEXT,
    proposed_value  TEXT NOT NULL,
    sample_size     INTEGER NOT NULL,
    metric_name     TEXT,
    metric_value    NUMERIC(10,4),
    reason          TEXT NOT NULL,
    confidence_level TEXT
                    CONSTRAINT chk_learning_rule_proposals_confidence
                    CHECK (confidence_level IN ('niedrig','mittel','hoch') OR confidence_level IS NULL),
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CONSTRAINT chk_learning_rule_proposals_status
                    CHECK (status IN ('proposed','approved','rejected','activated','expired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT,
    activated_at    TIMESTAMPTZ,
    version         INTEGER NOT NULL DEFAULT 1,
    metadata_json   JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS ix_learning_rule_proposals_status_type
    ON trading.learning_rule_proposals (status, proposal_type);
CREATE INDEX IF NOT EXISTS ix_learning_rule_proposals_target
    ON trading.learning_rule_proposals (target_type, target_value);

COMMENT ON TABLE trading.learning_rule_proposals IS
    'Ausschliesslich vom Lernagenten befuellt, ausschliesslich mit status=proposed. '
    'Menschliche/Matrix-Freigabe setzt status=approved oder rejected. Ein separater '
    'deterministischer Aktivierungs-Workflow setzt status=activated und schreibt '
    'die eigentliche Aenderung nach trading.scoring_weights bzw. trading.prompt_versions.';

-- ============================================================================
-- 7. trading.news_items -- Roh-News + Verarbeitungs-Zustandsmodell (Phase 4)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.news_items (
    id                 BIGSERIAL PRIMARY KEY,
    news_key           TEXT NOT NULL,
    title              TEXT NOT NULL,
    url                TEXT,
    source             TEXT,
    published_at       TIMESTAMPTZ,
    fetched_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_content        TEXT,
    status             TEXT NOT NULL DEFAULT 'pending'
                       CONSTRAINT chk_news_items_status
                       CHECK (status IN ('pending','processing','evaluated','retry','failed','discarded')),
    retry_count        INTEGER NOT NULL DEFAULT 0,
    last_error         TEXT,
    last_attempt_at    TIMESTAMPTZ,
    next_retry_at      TIMESTAMPTZ,
    discarded_reason   TEXT,
    metadata_json      JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_news_items_news_key UNIQUE (news_key)
);

CREATE INDEX IF NOT EXISTS ix_news_items_status ON trading.news_items (status);
CREATE INDEX IF NOT EXISTS ix_news_items_next_retry
    ON trading.news_items (next_retry_at) WHERE status = 'retry';
CREATE INDEX IF NOT EXISTS ix_news_items_published_at ON trading.news_items (published_at);

COMMENT ON TABLE trading.news_items IS
    'Eine Zeile pro eingesammelter Roh-News. status=pending/processing/retry sind '
    'NICHT abgeschlossen -- eine News gilt erst mit status=evaluated oder '
    'status=discarded als fertig verarbeitet (siehe Phase 4 der Migration).';

-- ============================================================================
-- 8. trading.news_assessments -- strukturierte KI-Bewertung pro News
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.news_assessments (
    id                    BIGSERIAL PRIMARY KEY,
    news_id               BIGINT NOT NULL REFERENCES trading.news_items (id),
    relevant               BOOLEAN NOT NULL,
    wirkungsebene          TEXT,
    betroffene_ticker_json JSONB NOT NULL DEFAULT '[]'::JSONB,
    betroffene_sektoren_json JSONB NOT NULL DEFAULT '[]'::JSONB,
    wirkungsrichtung        TEXT
                            CONSTRAINT chk_news_assessments_wirkungsrichtung
                            CHECK (wirkungsrichtung IN ('positiv','negativ','neutral','unklar') OR wirkungsrichtung IS NULL),
    wirkung_staerke         TEXT
                            CONSTRAINT chk_news_assessments_staerke
                            CHECK (wirkung_staerke IN ('niedrig','mittel','hoch','unklar') OR wirkung_staerke IS NULL),
    sentiment               TEXT,
    konfidenz                SMALLINT CHECK (konfidenz BETWEEN 0 AND 100),
    news_kategorie           TEXT,
    ticker_begruendung       TEXT,
    wirkungs_begruendung     TEXT,
    ist_wiederholung         BOOLEAN NOT NULL DEFAULT FALSE,
    referenz_news_ids_json   JSONB NOT NULL DEFAULT '[]'::JSONB,
    unsicherheiten_json      JSONB NOT NULL DEFAULT '[]'::JSONB,
    modell_version           TEXT,
    prompt_version           TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_news_assessments_news_id ON trading.news_assessments (news_id);
CREATE INDEX IF NOT EXISTS ix_news_assessments_relevant ON trading.news_assessments (relevant);

COMMENT ON TABLE trading.news_assessments IS
    'Strukturierte Ausgabe des News-Recherche-Agenten (Phase 5), eine Zeile pro '
    'Bewertungsversuch einer News. betroffene_ticker_json kann mehrere Ticker '
    'enthalten -- die Aufspaltung in Einzelbeobachtungen je Ticker erfolgt in '
    'trading.news_impact_tracking.';

-- ============================================================================
-- 9. trading.news_impact_tracking -- Wirkungsanalyse (Phase 6+7)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.news_impact_tracking (
    id                          BIGSERIAL PRIMARY KEY,
    news_id                     BIGINT NOT NULL REFERENCES trading.news_items (id),
    news_key                    TEXT NOT NULL,
    ticker                      TEXT NOT NULL,
    news_date                   DATE NOT NULL,
    news_time                   TIME,
    publication_timestamp       TIMESTAMPTZ,
    first_trading_date          DATE,

    predicted_direction         TEXT
                                CONSTRAINT chk_impact_predicted_direction
                                CHECK (predicted_direction IN ('positiv','negativ','neutral','unklar') OR predicted_direction IS NULL),
    predicted_strength          TEXT
                                CONSTRAINT chk_impact_predicted_strength
                                CHECK (predicted_strength IN ('niedrig','mittel','hoch','unklar') OR predicted_strength IS NULL),
    prediction_confidence       SMALLINT CHECK (prediction_confidence BETWEEN 0 AND 100),
    news_category                TEXT,
    impact_level                 TEXT,
    source                        TEXT,

    baseline_price                NUMERIC(18,6),
    baseline_timestamp             TIMESTAMPTZ,
    benchmark_symbol                TEXT,
    benchmark_baseline_price         NUMERIC(18,6),

    price_d1   NUMERIC(18,6), price_d3  NUMERIC(18,6), price_d5  NUMERIC(18,6),
    price_d10  NUMERIC(18,6), price_d20 NUMERIC(18,6),

    return_d1  NUMERIC(10,6), return_d3  NUMERIC(10,6), return_d5  NUMERIC(10,6),
    return_d10 NUMERIC(10,6), return_d20 NUMERIC(10,6),

    benchmark_return_d1  NUMERIC(10,6), benchmark_return_d3  NUMERIC(10,6),
    benchmark_return_d5  NUMERIC(10,6), benchmark_return_d10 NUMERIC(10,6),
    benchmark_return_d20 NUMERIC(10,6),

    abnormal_return_d1  NUMERIC(10,6), abnormal_return_d3  NUMERIC(10,6),
    abnormal_return_d5  NUMERIC(10,6), abnormal_return_d10 NUMERIC(10,6),
    abnormal_return_d20 NUMERIC(10,6),

    max_positive_move   NUMERIC(10,6),
    max_negative_move   NUMERIC(10,6),
    observed_direction  TEXT
                        CONSTRAINT chk_impact_observed_direction
                        CHECK (observed_direction IN ('positiv','negativ','neutral','unklar') OR observed_direction IS NULL),
    observed_strength   TEXT
                        CONSTRAINT chk_impact_observed_strength
                        CHECK (observed_strength IN ('niedrig','mittel','hoch','unklar') OR observed_strength IS NULL),

    direction_correct    BOOLEAN,
    strength_correct     BOOLEAN,
    quality_score         NUMERIC(6,2),

    confounded             BOOLEAN NOT NULL DEFAULT FALSE,
    confounding_reason      TEXT,
    additional_news_count    INTEGER NOT NULL DEFAULT 0,

    status TEXT NOT NULL DEFAULT 'pending'
           CONSTRAINT chk_impact_status
           CHECK (status IN ('pending','waiting_d1','waiting_d3','waiting_d5','waiting_d10','waiting_d20','completed','confounded','failed')),

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at  TIMESTAMPTZ,

    CONSTRAINT uq_news_impact_tracking_news_ticker UNIQUE (news_id, ticker)
);

CREATE INDEX IF NOT EXISTS ix_news_impact_tracking_status ON trading.news_impact_tracking (status);
CREATE INDEX IF NOT EXISTS ix_news_impact_tracking_ticker ON trading.news_impact_tracking (ticker);
CREATE INDEX IF NOT EXISTS ix_news_impact_tracking_news_date ON trading.news_impact_tracking (news_date);
CREATE INDEX IF NOT EXISTS ix_news_impact_tracking_confounded ON trading.news_impact_tracking (confounded);

COMMENT ON TABLE trading.news_impact_tracking IS
    'Eine Zeile pro (News, Ticker)-Paar. Wird von 08 - News-Wirkungsanalyse '
    'schrittweise befuellt (D+1/D+3/D+5/D+10/D+20), status verfolgt den '
    'Beobachtungsfortschritt. confounded=true markiert durch Stoerfaktoren '
    'verunreinigte Faelle (Phase 7) -- diese Zeilen duerfen in Berichten '
    'erscheinen, aber nicht ungefiltert als Lerndaten fuer den Lernagenten dienen.';

-- ============================================================================
-- Ende 001_agenten_architektur.sql
-- ============================================================================
