-- ============================================================================
-- 081 - trading.simulation_run_validation: additive Audit-Kennzeichnung fuer
-- historische Simulationslaeufe, OHNE die Laeufe selbst zu veraendern.
-- ============================================================================
-- Kontext (WF17-v2-Reparatur, Sitzungsdiagnose 2026-09-06): Runs 17/21/22/25
-- haben nachgewiesene, sich ueberlappende offene Positionen desselben Tickers.
-- Fuer Run 25 (ALV.DE) und stichprobenartig Run 25/DBK.DE ist der GENAUE
-- Mechanismus bewiesen: ein Same-Day-Close-and-Reopen fuehrt dazu, dass der
-- INSERT der neuen Recommendation VOR dem UPDATE (Schliessen der alten
-- Recommendation) ausgefuehrt wird - der partielle Unique-Index
-- ux_simulation_recommendations_one_open_per_ticker (WHERE status='offen')
-- blockt den neuen INSERT per ON CONFLICT DO NOTHING, die Order/der Trade
-- entstehen aber unabhaengig trotzdem. Fuer Runs 17/21/22 ist nur die
-- UEBERLAPPUNG selbst nachgewiesen (identischer Datumsabgleich wie bei Run 25),
-- nicht einzeln der exakte Mechanismus - aber alle Laeufe nutzen denselben
-- v1-Legacy-Codepfad, daher hohe Plausibilitaet derselben Ursache.
--
-- Getrennt davon: alle 6 v1-Laeufe (17/21/22/23/24/25) simulieren ungehebelten
-- Handel trotz MINI_FUTURE_LEVERAGE=4 in der Config-Snapshot - bewiesen, dass
-- dieser Wert im Legacy-Pfad nie in einer Rechenoperation verwendet wird (nur
-- geladen + einmal in einem Kommentar referenziert). Das ist KEIN Fehler im
-- Sinne von "falsch gerechnet" - der Kapitalpfad ist intern mathematisch
-- konsistent - sondern eine Modelluecke gegenueber dem konfigurierten Anspruch.
-- Deshalb WARNING, nicht INVALID.
--
-- Diese Migration aendert NIEMALS eine Zeile in backtest_runs/simulation_trades/
-- simulation_orders/simulation_recommendations/simulation_daily_portfolio -
-- rein additive Protokollierung in einer neuen, separaten Tabelle.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS trading.simulation_run_validation (
  id                  BIGSERIAL PRIMARY KEY,
  simulation_run_id   BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  validation_status   TEXT NOT NULL CHECK (validation_status IN ('VALID','WARNING','INVALID','UNCHECKED')),
  validation_code     TEXT NOT NULL,
  validation_note     TEXT,
  detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (simulation_run_id, validation_code)
);
COMMENT ON TABLE trading.simulation_run_validation IS
  'Additive Audit-Kennzeichnung je Simulationslauf - AENDERT NIEMALS den referenzierten Lauf '
  'selbst. Ein Lauf kann mehrere Codes gleichzeitig tragen (z.B. INVALID/... und WARNING/...).';
COMMENT ON COLUMN trading.simulation_run_validation.validation_status IS
  'VALID = Pruefung fuer diesen Code bestanden. WARNING = bekannte Modell-/Datenluecke, '
  'Ergebnis bleibt grundsaetzlich nutzbar. INVALID = nachgewiesener struktureller Fehler, '
  'Vorsicht bei Interpretation der betroffenen Kennzahlen. UNCHECKED = noch nicht geprueft.';
COMMENT ON COLUMN trading.simulation_run_validation.validation_code IS
  'Bekannte Codes (Liste waechst additiv, kein CHECK-Constraint): '
  'INVALID_ENGINE_V1_RECOMMENDATION_STATE, LEGACY_CAPITAL_MODEL, '
  'NO_DUPLICATE_OPEN_TICKER_CHECK_PASSED.';

INSERT INTO trading.simulation_run_validation (simulation_run_id, validation_status, validation_code, validation_note) VALUES
  (17, 'INVALID', 'INVALID_ENGINE_V1_RECOMMENDATION_STATE',
   'Systemweiter Datums-Ueberlappungs-Scan (2026-09-06) fand ueberlappende offene Positionen '
   'desselben Tickers: HEN3.DE (3x), BAYN.DE, ALV.DE, SIE.DE, ^GSPC (3x), SAP.DE (2x). '
   'Exakter Mechanismus nicht einzeln fuer diesen Lauf verifiziert (siehe Run 25 fuer den '
   'bewiesenen Ablauf), aber identischer v1-Legacy-Codepfad.'),
  (21, 'INVALID', 'INVALID_ENGINE_V1_RECOMMENDATION_STATE',
   'Ueberlappungen bei ^GSPC (2x), BAYN.DE, SAP.DE (2x) nachgewiesen (Datums-Ueberlappungs-Scan '
   '2026-09-06). Exakter Mechanismus nicht einzeln verifiziert, identischer Codepfad wie Run 25.'),
  (22, 'INVALID', 'INVALID_ENGINE_V1_RECOMMENDATION_STATE',
   'Ueberlappungen bei HEN3.DE, ALV.DE (2x), BAYN.DE (2x), EOAN.DE, BMW.DE, BAS.DE nachgewiesen '
   '(Datums-Ueberlappungs-Scan 2026-09-06). Exakter Mechanismus nicht einzeln verifiziert, '
   'identischer Codepfad wie Run 25.'),
  (25, 'INVALID', 'INVALID_ENGINE_V1_RECOMMENDATION_STATE',
   'Vollstaendig bewiesener Ablauf (Sitzungsdiagnose 2026-09-06): Trade trd-25-974 (ALV.DE) '
   'schliesst 2026-07-06, noch am selben Tag entsteht Order 977 fuer ALV.DE. Der INSERT der '
   'neuen Recommendation wird durch ON CONFLICT DO NOTHING verworfen (alte Recommendation 974 '
   'war zum INSERT-Zeitpunkt noch status=offen), danach schliesst das breite UPDATE die alte '
   'Recommendation. Order 977 und Trade trd-25-977 existieren anschliessend ohne offene '
   'Recommendation. openRecTickers weiss beim naechsten Worker-Tick nichts von der offenen '
   'Position -> am 2026-07-23 entsteht Order 979 (trd-25-979) fuer denselben Ticker, obwohl '
   'trd-25-977 weiterhin offen ist. Ergebnis: 2 gleichzeitig offene ALV.DE-Positionen bis '
   'Laufende. DBK.DE zeigt denselben Recommendation-Verlust latent (fehlende Recommendation-Zeile '
   'fuer Order 982), ohne dass eine dritte DBK.DE-Order vor Laufende die Luecke ausnutzte.'),
  (23, 'VALID', 'NO_DUPLICATE_OPEN_TICKER_CHECK_PASSED',
   'Systemweiter Datums-Ueberlappungs-Scan (2026-09-06) fand keine gleichzeitig offenen '
   'Positionen desselben Tickers in diesem Lauf.'),
  (24, 'VALID', 'NO_DUPLICATE_OPEN_TICKER_CHECK_PASSED',
   'Systemweiter Datums-Ueberlappungs-Scan (2026-09-06) fand keine gleichzeitig offenen '
   'Positionen desselben Tickers in diesem Lauf.'),
  (17, 'WARNING', 'LEGACY_CAPITAL_MODEL',
   'MINI_FUTURE_LEVERAGE=4 im Legacy-Pfad (Verarbeite Tage-Paket) nachweislich nie in einer '
   'Rechenoperation verwendet (nur in cfg geladen + einmal in einem Kommentar referenziert). '
   'Lauf simuliert intern konsistent ungehebelten Handel mit Mini-Future-Kostenmodell '
   '(Spread+Finanzierung), nicht echten 4x-Hebel. Kein Rechenfehler, nur Modelluecke.'),
  (21, 'WARNING', 'LEGACY_CAPITAL_MODEL', 'Siehe Run 17 - identischer Legacy-Code-Pfad.'),
  (22, 'WARNING', 'LEGACY_CAPITAL_MODEL', 'Siehe Run 17 - identischer Legacy-Code-Pfad.'),
  (23, 'WARNING', 'LEGACY_CAPITAL_MODEL', 'Siehe Run 17 - identischer Legacy-Code-Pfad.'),
  (24, 'WARNING', 'LEGACY_CAPITAL_MODEL', 'Siehe Run 17 - identischer Legacy-Code-Pfad.'),
  (25, 'WARNING', 'LEGACY_CAPITAL_MODEL',
   'Ausfuehrlich nachgewiesen in der Sitzungsdiagnose 2026-09-06 (Teil 7/8): '
   'MINI_FUTURE_LEVERAGE geladen, nie in Arithmetik verwendet. Lauf simuliert ungehebelten '
   'Aktien-/Underlying-Handel mit Mini-Future-Kostenmodell.')
ON CONFLICT (simulation_run_id, validation_code) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('081', 'trading.simulation_run_validation: additive Audit-Kennzeichnung fuer v1-Laeufe (Recommendation-State-Bug + Legacy-Capital-Model), keine Aenderung an den Laeufen selbst - WF17-v2-Reparatur')
ON CONFLICT (version) DO NOTHING;

COMMIT;
