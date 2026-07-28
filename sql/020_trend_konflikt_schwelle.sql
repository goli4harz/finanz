-- ============================================================================
-- Folge-Entscheidung zu Paket 10 (Empfehlungswatchlist-Nutzerfrage 2026-07-28):
-- 5-Tage-RSI-Trend darf eine Kauf-/Verkauf-Entscheidung in "06 -
-- Empfehlungswatchlist" tatsaechlich blockieren (statt nur informativ zu
-- begleiten) - aber ausdruecklich nur bei STARKEM Gegen-Trend, nicht bei
-- jedem kleinen Ausschlag.
-- ============================================================================
-- TREND_KONFLIKT_SCHWELLE: Mindest-Betrag der RSI-Veraenderung ueber die
-- letzten 5 Handelstage (|RSI_heute - RSI_vor_5_Tagen|), ab dem ein
-- gegenlaeufiger Trend als "stark" gilt und die Aktion automatisch zum
-- Vorschlag (kein sofortiger Schreibvorgang) statt zur echten Empfehlung wird.
-- Default 10 RSI-Punkte - ein bewusster Startwert, kein empirisch belegter;
-- ueber diese Tabelle jederzeit ohne Workflow-Redeploy anpassbar.

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES
    ('TREND_KONFLIKT_SCHWELLE', 10,
     'Mindest-RSI-Aenderung ueber 5 Handelstage, ab der ein gegenlaeufiger Trend als stark gilt und die Kauf-/Verkauf-Entscheidung in 06 automatisch zum Vorschlag (kein Write) herabstuft.')
ON CONFLICT (config_key) DO NOTHING;
