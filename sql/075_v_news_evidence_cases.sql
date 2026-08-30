-- ============================================================================
-- 075: View v_news_evidence_cases - News-Evidenz-Lesesicht (Historical Evidence Engine)
-- ============================================================================
-- Erster Baustein aus dem Audit-Konzept "Persoenlicher KI-Trading-Analyst"
-- (2026-08-24, Kap. 9/18 Umsetzungsreihenfolge, Schritt 4: "reine View, kein
-- Risiko fuer Live-Daten"). Vereinheitlichte Lesesicht historischer + live
-- abgeschlossener News-Wirkungsfaelle fuer das kuenftige deterministische
-- Ticker/Kategorie/Sektor-Matching des noch zu bauenden Subworkflows
-- "Historical Evidence Lookup". Reine Lesesicht, keine Datenduplizierung -
-- baut auf der bereits vorhandenen trading.v_news_impact_tracking_combined
-- (sql/065) auf. Noch OHNE Consumer - das ist der naechste Schritt.
--
-- Abweichung vom Rohentwurf im Audit-Artefakt: region_at_event wird aus
-- stock_instruments.currency abgeleitet (EUR->Europa, USD->USA, sonst
-- global) statt der dort skizzierten Konstante 'DE' (die es in
-- trading.market_regime.region gar nicht gibt - gueltige Werte sind
-- 'Europa'/'USA'/'global', siehe sql/032 + der Regime-Port in Workflow 17,
-- 2026-08-28). currency ist eine gepflegte Spalte direkt auf
-- stock_instruments und vermeidet damit auch die dortige NULL-exchange-Falle
-- (BAS.DE-Fund 2026-08-28) - kein Rueckgriff auf Tickersuffix noetig.
--
-- Point-in-Time-Tauglichkeit von market_regime fuer diesen Join verifiziert
-- (Audit Kap. 9 hatte das offen gelassen): UNIQUE(region, business_date) in
-- sql/032 garantiert genau einen Regime-Snapshot je Tag, kein
-- ueberschreibendes Re-Compute ueber Tage hinweg - der Join liefert also
-- tatsaechlich das Regime zum jeweiligen Ereignisdatum, nicht das aktuelle.

BEGIN;

CREATE OR REPLACE VIEW trading.v_news_evidence_cases AS
SELECT
  vt.id, vt.data_source, vt.ticker, vt.news_date, vt.news_category,
  vt.predicted_direction, vt.observed_direction,
  vt.direction_correct_d1, vt.direction_correct_d3, vt.direction_correct_d5,
  vt.direction_correct_d10, vt.direction_correct_d20,
  vt.return_d1, vt.return_d3, vt.return_d5, vt.return_d10, vt.return_d20,
  vt.abnormal_return_d1, vt.abnormal_return_d3, vt.abnormal_return_d5,
  vt.abnormal_return_d10, vt.abnormal_return_d20,
  vt.confounded, vt.confounding_reason, vt.quality_score, vt.status,
  si.sektor,
  CASE si.currency WHEN 'EUR' THEN 'Europa' WHEN 'USD' THEN 'USA' ELSE 'global' END AS region_at_event,
  mr.combined_regime AS regime_at_event
FROM trading.v_news_impact_tracking_combined vt
LEFT JOIN trading.stock_instruments si ON si.ticker = vt.ticker
LEFT JOIN trading.market_regime mr
  ON mr.business_date = vt.news_date
  AND mr.region = CASE si.currency WHEN 'EUR' THEN 'Europa' WHEN 'USD' THEN 'USA' ELSE 'global' END
WHERE vt.status = 'completed';

COMMENT ON VIEW trading.v_news_evidence_cases IS
  'Historical Evidence Engine (Audit-Konzept 2026-08-24, Kap. 9): Lesesicht auf abgeschlossene News-Wirkungsfaelle (v_news_impact_tracking_combined) angereichert um Sektor + Marktregime zum Ereigniszeitpunkt, fuer das kuenftige deterministische Ticker/Kategorie/Sektor-Matching. Noch ohne Consumer - Historical-Evidence-Lookup-Subworkflow ist der naechste Umsetzungsschritt (Kap. 18).';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('075', 'View v_news_evidence_cases - News-Evidenz-Lesesicht fuer die Historical Evidence Engine (Audit-Konzept 2026-08-24, Kap. 9/18)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
