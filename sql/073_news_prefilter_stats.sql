-- ============================================================================
-- Human-in-the-Loop Phase 3, Ergaenzung: Vorfilter-Wirksamkeit sichtbar machen
-- ============================================================================
-- Leichtgewichtige Alternative zur vollen Artikel-Persistierung (urspruenglich als
-- Modul-4-Erweiterung geplant, siehe HUMAN_IN_THE_LOOP_ARCHITECTURE.md Abschnitt 10):
-- nur EINE Zeile Summen-Statistik pro Workflow-03-Lauf, kein einzelner Artikeltext.
-- Beantwortet "wie viele Artikel kommen durch, wie viele werden aus welchem Grund
-- verworfen" ohne zusaetzliche Datenbanklast durch Volltext-Persistierung jedes
-- verworfenen Artikels.

BEGIN;

CREATE TABLE IF NOT EXISTS trading.news_prefilter_runs (
  id                               BIGSERIAL PRIMARY KEY,
  run_at                           TIMESTAMPTZ NOT NULL DEFAULT now(),
  feeds_ok                         INTEGER NOT NULL,
  feeds_fehler                     INTEGER NOT NULL,
  total_artikel_geprueft           INTEGER NOT NULL,
  total_durchgelassen              INTEGER NOT NULL,
  total_hart_ausgeschlossen        INTEGER NOT NULL,
  total_soft_noise_ausgeschlossen  INTEGER NOT NULL,
  total_kein_treffer               INTEGER NOT NULL,
  created_at                       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_news_prefilter_runs_run_at
  ON trading.news_prefilter_runs (run_at DESC);

COMMENT ON TABLE trading.news_prefilter_runs IS
  'Human-in-the-Loop-Ergaenzung: eine Zeile pro Lauf von Workflow 03s Regex-Vorfilter '
  '("RSS-Feeds laden & filtern"), NUR Summenzahlen, keine einzelnen Artikel. Beantwortet '
  '"wie effektiv ist der Vorfilter" ohne die (bewusst zurueckgestellte) volle '
  'Artikel-Persistierung. total_artikel_geprueft = total_durchgelassen + '
  'total_hart_ausgeschlossen + total_soft_noise_ausgeschlossen + total_kein_treffer.';

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('073', 'Human-in-the-Loop Ergaenzung: news_prefilter_runs (Vorfilter-Wirksamkeit, nur Summenzahlen)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
