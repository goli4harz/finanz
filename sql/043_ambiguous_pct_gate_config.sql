-- ============================================================================
-- 043 (Fehleranalyse F7, mittel, Haertungsauftrag 2026-08-02): Schwellenwert
-- fuer das neue ambiguous_pct-Gate in 09b (Lernagent Handelsstrategien)
-- ============================================================================
-- F7: ambiguous_pct (Anteil mehrdeutiger Ausfuehrungen, E9/E10-Faelle) war
-- bisher nur informativ im Lernbericht sichtbar, floss aber nie in
-- "eligible" (die Gate-Pruefung, ob ein Lernvorschlag ueberhaupt entstehen
-- darf) ein. Additiv, konservativer Default (20% - deutlich ueber dem
-- Normalfall, blockiert nur wirklich auffaellige Segmente).

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES
  ('MAX_AMBIGUOUS_PCT_FOR_PROPOSAL', 20.0, 'Obergrenze fuer den Anteil mehrdeutiger Ausfuehrungen (ambiguous_execution, E9/E10-Faelle) je Segment, oberhalb derer 09b keinen Lernvorschlag erzeugt - die Datengrundlage gilt dann als zu unsicher (Fehleranalyse F7).')
ON CONFLICT (config_key) DO NOTHING;
