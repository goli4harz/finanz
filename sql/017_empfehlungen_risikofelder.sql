-- ============================================================================
-- Paket 7 (Phase 8 der fachlichen Ueberarbeitung): Empfehlungs-Risikofelder
-- ============================================================================
-- Ergaenzt die in der Bestandsaufnahme (Abschnitt 6) als fehlend bestaetigten
-- Spalten. AUSDRUECKLICH NICHT Teil dieses Pakets: echte Entscheidungslogik in
-- "06 - Empfehlungswatchlist" verdrahten, die hat eine dokumentierte Historie
-- sensibler Merge-/Konvergenz- und DRY_RUN-Gating-Stellen - ein eigenes, separat
-- abzunehmendes Paket mit eigenem Testplan.

ALTER TABLE trading.recommendations
    ADD COLUMN IF NOT EXISTS stop_price NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS target_price NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS thesis_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS expected_holding_days INTEGER,
    ADD COLUMN IF NOT EXISTS data_quality_score NUMERIC(5,2)
        CONSTRAINT chk_recommendations_data_quality_score CHECK (data_quality_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS market_regime TEXT,
    ADD COLUMN IF NOT EXISTS decision_score NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS decision_blockers JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS invalidation_reason TEXT,
    ADD COLUMN IF NOT EXISTS is_theoretical BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN trading.recommendations.is_theoretical IS
    'DEFAULT TRUE bewusst gewaehlt: jede heutige Empfehlung ist bereits de facto '
    'theoretisch (Hebelprodukt-Naeherung, "[SIMULATION - keine reale Order]"-Text in '
    'entry_grund) - korrekt fuer Bestandszeilen UND fuer 06s unveraenderten Code, ohne '
    'dass 06 selbst etwas schreiben muss.';
COMMENT ON COLUMN trading.recommendations.decision_blockers IS
    'Schema-only in diesem Paket - kein Consumer/Producer verdrahtet, 06 unveraendert.';
