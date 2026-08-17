-- ============================================================================
-- 064: Historische Newswirkungs-Verfolgung (Spiegel von news_impact_tracking)
-- ============================================================================
-- Ziel: den Lernagenten (Workflow 09, liest bisher nur trading.news_impact_
-- tracking) auch mit den bereits importierten historischen GDELT-Bewertungen
-- (trading.historical_news_assessments) fuettern koennen, statt Wochen auf
-- genug frische Live-Faelle zu warten - bei historischen Daten liegt der
-- komplette Kursverlauf danach ja bereits vor.
--
-- BEWUSST eine eigene, gespiegelte Tabelle statt Wiederverwendung von
-- news_impact_tracking: dessen news_id hat einen harten Fremdschluessel auf
-- trading.news_items (die Live-Tabelle) - historische News leben in einer
-- eigenen Tabelle (historical_news) mit eigener ID-Vergabe und wuerden dort
-- nicht passen. Gleiches Muster wie ueberall sonst im Projekt (historical_
-- news/news_items, simulation_recommendations/recommendations, ...).
--
-- Schema 1:1 gespiegelt von news_impact_tracking (siehe Workflow 08 fuer die
-- Berechnungslogik: Baseline-Bestimmung per Handelssitzung, D+1/3/5/10/20
-- Kurs-/Rendite-/Benchmark-bereinigte "Abnormal Return"-Berechnung,
-- Stoerfaktor-Erkennung) - einziger struktureller Unterschied: FK auf
-- historical_news statt news_items. Bei historischen Daten ist der
-- gesamte Kursverlauf bereits vorhanden, daher werden die "waiting_dN"-
-- Zwischenzustaende praktisch nie gebraucht (ein Durchlauf reicht), das
-- CHECK bleibt trotzdem identisch fuer maximale Kompatibilitaet mit
-- bestehenden Auswertungen.

BEGIN;

CREATE TABLE IF NOT EXISTS trading.historical_news_impact_tracking (
    id                       BIGSERIAL PRIMARY KEY,
    news_id                  BIGINT NOT NULL REFERENCES trading.historical_news(id),
    news_key                 TEXT NOT NULL,
    ticker                   TEXT NOT NULL,
    news_date                DATE NOT NULL,
    news_time                TIME,
    publication_timestamp    TIMESTAMPTZ,
    first_trading_date       DATE,
    predicted_direction      TEXT CHECK (predicted_direction IN ('positiv','negativ','neutral','unklar') OR predicted_direction IS NULL),
    predicted_strength       TEXT CHECK (predicted_strength IN ('niedrig','mittel','hoch','unklar') OR predicted_strength IS NULL),
    prediction_confidence    SMALLINT CHECK (prediction_confidence >= 0 AND prediction_confidence <= 100),
    news_category            TEXT,
    impact_level              TEXT,
    source                   TEXT,
    baseline_price            NUMERIC,
    baseline_timestamp        TIMESTAMPTZ,
    benchmark_symbol          TEXT,
    benchmark_baseline_price  NUMERIC,
    price_d1 NUMERIC, price_d3 NUMERIC, price_d5 NUMERIC, price_d10 NUMERIC, price_d20 NUMERIC,
    return_d1 NUMERIC, return_d3 NUMERIC, return_d5 NUMERIC, return_d10 NUMERIC, return_d20 NUMERIC,
    benchmark_return_d1 NUMERIC, benchmark_return_d3 NUMERIC, benchmark_return_d5 NUMERIC,
    benchmark_return_d10 NUMERIC, benchmark_return_d20 NUMERIC,
    abnormal_return_d1 NUMERIC, abnormal_return_d3 NUMERIC, abnormal_return_d5 NUMERIC,
    abnormal_return_d10 NUMERIC, abnormal_return_d20 NUMERIC,
    max_positive_move         NUMERIC,
    max_negative_move         NUMERIC,
    observed_direction        TEXT CHECK (observed_direction IN ('positiv','negativ','neutral','unklar') OR observed_direction IS NULL),
    observed_strength         TEXT CHECK (observed_strength IN ('niedrig','mittel','hoch','unklar') OR observed_strength IS NULL),
    direction_correct          BOOLEAN,
    strength_correct           BOOLEAN,
    quality_score              NUMERIC,
    confounded                 BOOLEAN NOT NULL DEFAULT FALSE,
    confounding_reason         TEXT,
    additional_news_count      INTEGER NOT NULL DEFAULT 0,
    status                     TEXT NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending','waiting_d1','waiting_d3','waiting_d5','waiting_d10','waiting_d20','completed','confounded','failed')),
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at               TIMESTAMPTZ,
    baseline_quality           TEXT CHECK (baseline_quality IN ('high','medium','limited') OR baseline_quality IS NULL),
    direction_correct_d1 BOOLEAN, direction_correct_d3 BOOLEAN, direction_correct_d5 BOOLEAN,
    direction_correct_d10 BOOLEAN, direction_correct_d20 BOOLEAN,
    has_major_followup_news    BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (news_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_historical_news_impact_tracking_ticker
    ON trading.historical_news_impact_tracking (ticker);

CREATE INDEX IF NOT EXISTS idx_historical_news_impact_tracking_news_date
    ON trading.historical_news_impact_tracking (news_date);

INSERT INTO trading.schema_migrations (version, description)
VALUES ('064', 'Historische Newswirkungs-Verfolgung (Spiegel von news_impact_tracking, FK auf historical_news statt news_items) - fuettert den Lernagenten mit bereits importierten historischen GDELT-Bewertungen')
ON CONFLICT (version) DO NOTHING;

COMMIT;
