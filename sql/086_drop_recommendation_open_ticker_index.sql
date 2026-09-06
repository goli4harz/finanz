-- ============================================================================
-- 086 - Entfernt den alten partiellen Unique-Index auf simulation_recommendations,
-- der urspruenglich Ursache des Recommendation-State-Bugs war. WF17-v2-Reparatur,
-- Nacharbeit zu 081-085 (beim Bau der CTE-Loesung fuer Migration 081-085 entdeckt).
-- ============================================================================
-- ux_simulation_recommendations_one_open_per_ticker (WHERE status='offen') war der
-- konkrete Mechanismus, der beim Same-Day-Close-and-Reopen per ON CONFLICT DO NOTHING
-- die neue Recommendation stillschweigend verworfen hat (siehe Migration 081 und die
-- Sitzungsdiagnose 2026-09-06).
--
-- v2s neuer CTE-basierter Insert (siehe "Baue SQL fuer Paket-Ergebnisse") hat KEIN
-- ON CONFLICT mehr - er wuerde bei einer Verletzung dieses Index NICHT mehr still
-- verwerfen, sondern die gesamte Tages-Transaktion mit einem Fehler abbrechen. Die
-- aktuelle Code-Reihenfolge (Recommendation-Close IMMER vor Neu-Insert desselben
-- Tages) verhindert das zwar durch Konstruktion, aber genau das waere "eine Loesung,
-- die nur zufaellig wegen der Reihenfolge funktioniert" - ausdruecklich nicht gewollt.
--
-- Fachlich ist der Index seit v2 ohnehin nicht mehr sinnvoll: Recommendations sind
-- reine Dokumentation/Audit (Grundsatz der Reparatur) und steuern nicht mehr den
-- Portfoliozustand - mehrere gleichzeitig "offene" Recommendation-Zeilen fuer denselben
-- Ticker sind daher harmlos (sie dokumentieren nur Entscheidungen, blockieren nichts).
-- Die tatsaechliche Ein-Position-pro-Ticker-Invariante wird jetzt ausschliesslich ueber
-- isOccupied() (Anwendung) + ux_simulation_trades_one_open_per_ticker_v2 (Migration 082,
-- DB-Notbremse) auf simulation_trades durchgesetzt - nicht mehr auf Recommendation-Ebene.
--
-- Reines DROP INDEX (Metadaten-Operation) - KEINE Zeile in simulation_recommendations
-- wird veraendert oder geloescht, v1-Daten (inkl. Run 25) bleiben vollstaendig unangetastet.
-- ============================================================================

BEGIN;

DROP INDEX IF EXISTS trading.ux_simulation_recommendations_one_open_per_ticker;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('086', 'DROP des alten partiellen Unique-Index auf simulation_recommendations (Ursache des v1-Recommendation-State-Bugs) - Recommendations sind seit v2 reine Dokumentation ohne Eindeutigkeitszwang - WF17-v2-Reparatur')
ON CONFLICT (version) DO NOTHING;

COMMIT;
