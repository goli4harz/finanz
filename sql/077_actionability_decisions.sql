-- ============================================================================
-- 077: Tabelle actionability_decisions - Protokoll des Actionability-Gate
-- ============================================================================
-- Kap. 10 des Audit-Konzepts (2026-08-24): protokolliert jede Entscheidung des
-- neuen "Actionability Gate"-Subworkflows (Kap. 13/18, Schritt 7) - ALERT/WATCH/
-- INFO/IGNORE, mit Begruendung. Kap. 18 Schritt 7 ist bewusst nur "INFO/WATCH
-- erzeugend, ALERT noch nicht scharf" - computed_decision haelt fest, was die
-- Logik EIGENTLICH entschieden haette (kann schon ALERT sein), decision ist der
-- tatsaechlich wirksame, ggf. gedeckelte Wert (nie ALERT vor Schritt 9). Das
-- erlaubt spaeter, ALERT scharf zu schalten, ohne die Entscheidungslogik selbst
-- nochmal anzufassen - nur alert_capped-Deckelung entfernen.

CREATE TABLE IF NOT EXISTS trading.actionability_decisions (
  id                  BIGSERIAL PRIMARY KEY,
  news_id             BIGINT,
  recommendation_id   BIGINT,
  ticker              TEXT,
  computed_decision   TEXT NOT NULL CHECK (computed_decision IN ('ALERT','WATCH','INFO','IGNORE')),
  decision            TEXT NOT NULL CHECK (decision IN ('ALERT','WATCH','INFO','IGNORE')),
  alert_capped        BOOLEAN NOT NULL DEFAULT FALSE,
  reasons_json        JSONB,
  decided_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_actionability_decisions_news_id
  ON trading.actionability_decisions (news_id);
CREATE INDEX IF NOT EXISTS ix_actionability_decisions_ticker_decided
  ON trading.actionability_decisions (ticker, decided_at DESC);
CREATE INDEX IF NOT EXISTS ix_actionability_decisions_decision
  ON trading.actionability_decisions (decision);

COMMENT ON TABLE trading.actionability_decisions IS
  'Historical Evidence Engine (Audit-Konzept 2026-08-24, Kap. 13/18): Protokoll jeder Actionability-Gate-Entscheidung. computed_decision = was die Regellogik ergeben hat (kann ALERT sein); decision = tatsaechlich wirksamer Wert (bis Kap.18 Schritt 9 nie ALERT, siehe alert_capped). Einzige Stelle, die kuenftig einen Matrix-Trading-Alert ausloesen darf (Abnahmekriterium Kap. 20) - noch nicht angebunden, siehe Schritt 7 vs. 9.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('077', 'Tabelle actionability_decisions - Protokoll fuer den Actionability-Gate-Subworkflow (Audit-Konzept 2026-08-24, Kap. 10/13/18)')
ON CONFLICT (version) DO NOTHING;
