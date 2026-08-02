# Offene Aufgaben

Stand: 2026-08-02 (zusätzlich zum Original-Auftrag jetzt Welle 1, Welle 2, Welle 3 UND der Härtungsauftrag/Priorität-1+2-Fixes umgesetzt, siehe Abschnitte unten)

## Härtungsauftrag "Vollständige Fehlerbereinigung" - Priorität 1 (kritisch), 2026-08-01

Vollständiges Audit (7 parallele Code-Reviews) gegen SQL-Sicherheit, Orchestrator, Kursdaten/
Marktumfeld, News-Pipeline, Portfolio-Risiko/Paper-Trading, Lernagenten, Migrationen/Doku-
Konsistenz. Ergebnis: 21 eindeutige kritische Funde, 19 hoch, 21 mittel, 6 niedrig -
vollständige Liste mit Ursache/Auswirkung/Korrektur in `FEHLERANALYSE.md`.

- ✅ **Alle 23 kritischen Funde behoben** (A1/A5/A6/A9/A11, B1/B4, C4/C9, D3/D5/D13,
  E1/E2/E4/E5/E7/E8/E9/E12, F1/F2/F4), live gepusht, lokal mit gezielten Testfällen
  verifiziert (SQL-Injection-Payloads live gegen echte Webhooks getestet). Details je Fix:
  `AENDERUNGSPROTOKOLL.md`, Testfälle: `TESTPLAN.md`, Ampel-Bewertung: `PRODUKTIONSFREIGABE.md`.
- Als Nebeneffekt weitere ~9 hoch/mittel eingestufte Funde direkt mitbehoben (A3/A4/A7-teilw./
  B5/C5/D4/F5), da im selben Node/derselben Datei ohnehin bearbeitet.
- ✅ **`sql/038`+`sql/039` sind live ausgefuehrt**, per Diagnose-Query 2026-08-02 bestaetigt
  (`chk_learning_rule_proposals_status` enthaelt `activation_failed`, `paper_trades.sektor`,
  `portfolio_risk_checks.sequence_index` und `ux_paper_trade_costs_trade_costtype` existieren
  alle live) - Ausfuehrungszeitpunkt selbst nicht mehr rekonstruierbar, aber der Ist-Zustand
  ist zweifelsfrei geklaert.
- ✅ **14 von 15 eindeutigen "hoch"-Funden behoben** (2026-08-01/02): C1 (period=3mo→1y in
  `02`), C6 (Datenqualitaetsstatus-Kollaps in `02`, macht C9 in `14` scharf), C7/C8
  (vollstaendige Sitzungsstatus-Erkennung in `02b`, beeinflusst jetzt `combined_regime`),
  D1/D2/D6 (dynamische Watchlist im KI-Prompt + Ticker-Validierung + Konfidenzfelder in `03`),
  D9 (URL-Kanonisierung + `content_hash` als dritte Dedup-Schicht in `03`), D11/D12
  (Datum- statt Index-Abgleich + echte Handelszeiten je Boerse in `08`), B2 (Teilausfall
  trotz Gesamterfolg im Orchestrator sichtbar gemacht), A8 (zentrale Wertebereichs-Regeltabelle
  in `12`, loest gleichzeitig A7 vollstaendig ab und F11). Details je Fix: `AENDERUNGSPROTOKOLL.md`,
  Testfaelle: `TESTPLAN.md`.
- 🟡 **A2 (hoch) bewusst zurueckgestellt** (Nutzerentscheidung 2026-08-02): "Feste Stored
  Procedures pro Aktion mit typisierten Parametern statt String-Interpolation" fuer
  `Watchlist verwalten`/`RSS-Quellen verwalten`/`12` - ein voller Architekturumbau, kein
  punktueller Fix. Die akute Injection-/Validierungsluecke selbst ist bereits geschlossen
  (A1/A3/A4/A9/A11 kritisch, A8 hoch); A2 ist eine strukturelle Verteidigungstiefe-Verbesserung
  fuer kuenftige Aenderungen. **Eigenstaendiges Vorhaben fuer eine kuenftige Sitzung**, wenn
  gewuenscht: SQL-Funktionen je Schreibaktion entwerfen (Watchlist anlegen/aendern/loeschen,
  RSS-Quelle testen/anlegen, alle 5 Lernvorschlags-Aktivierungspfade aus `12`), dann
  Postgres-Nodes auf `n8n`s native Query-Parameter statt `executeQuery`+String-Interpolation
  umstellen, vollstaendiger Retest aller 3 Workflows inkl. der Live-Webhook-Tests aus
  `TESTPLAN.md` (SEC-1 bis SEC-16).
- ✅ **`sql/040`+`sql/041` (COMMENT-Korrektur C6 + Point-in-Time-Umstellung B8) sind live
  ausgefuehrt** (bestaetigt 2026-08-02, Nutzer-Retry zeigte "already exists" auf den
  Constraint-Schritt).
- ✅ **6 weitere "mittel"-Funde behoben (2026-08-01/02):** A10 (Optimistic Locking, `12`),
  B8 (Point-in-Time `technical_signals_history`, `sql/041`), C2, D7, D8, D10 - siehe
  `FEHLERANALYSE.md` je Fund. Dazu **G4** (Live-IDs/Backup-Nachweis fuer `09b`/`12`/`13`/`14`
  verifiziert+nachgezogen, 2026-08-02) und **E10** (`AMBIGUOUS_BAR_POLICY` war seit 08-01
  im Code auf `pipeline_config` umgestellt, aber der Key fehlte in Query+Seed - beim
  G4-Abgleich gefunden, live nachgezogen, `sql/042` bereitgestellt).
- ✅ **`sql/042`** (E10, `AMBIGUOUS_BAR_POLICY_CODE`-Seed) **ausgefuehrt, bestaetigt 2026-08-02.**
- ✅ **9 weitere "mittel"-Funde behoben (2026-08-02):** B3 (Repo-Credential-Platzhalter war
  nur ein Repo/Live-Sync-Fehlalarm, echtes Credential live immer korrekt), B6 (eigene
  DRY_RUN-Pruefung in `14` als Verteidigung in der Tiefe), E6 (Drawdown-Nenner `peak_t`
  statt Konstante), E11 (separate Kennzahlen fuer eindeutige/mehrdeutige Trades in `10`),
  F6 (Regime-Konzentrationspruefung in `09b`), F7 (`ambiguous_pct`-Gate, `sql/043`), F12
  (restliche `proposed_value:null`-Faelle aus F5 nachgezogen), G1 (`trading.schema_migrations`-
  Tabelle, `sql/044`, `99` bewusst nicht erweitert - seit Migration 002 nicht mehr benutzt),
  G7 (Fehlalarm, Abhaengigkeit war in `docs/LERNAGENT_HANDELSSTRATEGIEN.md`/
  `docs/BACKTESTING_UND_WALK_FORWARD.md` bereits gegenseitig dokumentiert). Details je Fund
  in `FEHLERANALYSE.md`.
- ✅ **`sql/043`+`sql/044`** ausgefuehrt, bestaetigt 2026-08-02.
- ✅ **Alle 7 "niedrig"-Funde behoben (2026-08-02):** B7 (DRY_RUN-Quelle war seit B4 nur
  berechnet, nie tatsaechlich protokolliert - jetzt in `pipeline_runs.metadata_json` fuer
  `00`+`06`), B9 (deterministische `run_id` + drei neue UNIQUE-Indizes gegen Wiederholungs-
  laeufe in `14`, `sql/045`), C3 (Volumen-Kennzahlen aus `gueltigeKerzen` statt eigenem
  Filter in `02`), F3 (`LEARNING_MIN_NEWS_SAMPLE_SIZE` aus `pipeline_config`, `sql/046`,
  analog zu `09b`), G2 (`sql/045`+`046` explizit in `BEGIN`/`COMMIT` gefasst, Konvention
  fuer kuenftige Migrationen - `001`-`044` bewusst nicht rueckwirkend geaendert), G5
  (drei alte Repo-Dateien ohne "Agent V1"-Suffix nach `n8n_live_backup/` verschoben - reine
  lokale Altlast, live existierten sie laengst nicht mehr), G6 (Widerspruechliche
  Zusammenfassungszeile in diesem Dokument korrigiert). Details je Fund in `FEHLERANALYSE.md`.
- ✅ **`sql/045`+`sql/046`** ausgefuehrt, bestaetigt 2026-08-02 (Diagnose-Query gegen
  `activation_failed`-Constraint/Spalten/Index live verifiziert - siehe oben).
- 🟡 **F9** (Stabilitaet ueber Zeit/Drawdown je Strategie/Anteil blockierter Signale)
  bewusst zurueckgestellt 2026-08-02 - braucht neue Aggregationslogik (Zeitraum-Teilung,
  Verknuepfung mit `recommendation_veto_log`) statt eines einfachen Schwellenwerts wie
  F6/F7. Eigenstaendiges Vorhaben fuer eine kuenftige Sitzung, siehe `FEHLERANALYSE.md`.
- 🟡 **~80 unversionierte `n8n_live_backup/*.json`-Dateien (2026-07-21 bis 2026-07-27)**
  im Arbeitsverzeichnis entdeckt (2026-08-02, im Zuge von G4) - lokal vorhanden, nie
  committet. Gleiche Nachweisdisziplin-Luecke wie G4, nur historisch und groesser im
  Umfang. Noch nicht aufgeraeumt/committet - eigenstaendiger Punkt fuer eine kuenftige
  Sitzung (pruefen ob alle noch relevant sind, dann committen oder bewusst geordnet
  loeschen).
- **Noch offen (naechste Prioritaet laut Auftrag-Reihenfolge):** Von allen Funden aus
  `FEHLERANALYSE.md` (21 kritisch, 19 hoch, 22 mittel, 7 niedrig/niedrig-mittel) sind nur
  noch **A2** und **F9** offen - beide bewusst zurueckgestellt, siehe oben. Alle uebrigen
  sind behoben. Danach: automatisierte
  Pruefabfragen/Tests fuer die verbleibenden Bereiche, `PRODUKTIONSFREIGABE.md` mit dem neuen
  Stand neu bewerten.

## Welle 3 – Paper-Trading-Ledger, Portfoliorisiko, Backtesting und kalibriertes Lernen (2026-08-01)

Zwölf Arbeitspakete, größtenteils vollständig implementiert; zwei bewusst nur als Schema+Mechanismus-Spezifikation (Backtesting, Kalibrierung — beide mangels Historie dormant, siehe Begründung in den jeweiligen Docs). Live gepusht und verifiziert, siehe unten (Korrektur 2026-08-02, Fehleranalyse G6: diese Zusammenfassungszeile war nach dem eigentlichen Live-Push nicht mehr nachgezogen worden).

- ✅ **AP1** (Paper-Trading-Ledger): `trading.paper_trades`/`paper_trade_events`/`paper_trade_valuations`/`paper_trade_costs` (`sql/035`), vollständiges Statusmodell, lückenlose Ereignis-Historie, deterministische `trade_id` (kein Duplikat bei Wiederholung).
- ✅ **AP2+AP3** (Ausführung/Exit): Workflow `14`, Job B — konservative Einstiegszonen-Fill-Logik (kein Fill am Signaltag, dokumentierte Gap-Behandlung), Exit-Engine mit 10 Gründen, `AMBIGUOUS_BAR_POLICY` für Stop+Ziel in derselben Kerze. Trailing-Stop bewusst **nicht** umgesetzt (optional laut Auftrag, siehe `docs/AUSFUEHRUNGSMODELL.md`).
- ✅ **AP4** (Trade-Kennzahlen): `gross_pnl`/`net_pnl`/`return_pct`/`realized_r_multiple`/`holding_period`/MFE/MAE direkt auf `paper_trades`, Kennzahlen je Strategie/Regime im Dashboard.
- ✅ **AP5** (Portfoliorisikomotor): Workflow `14`, Job A — 9 konfigurierbare Limits inkl. Korrelation und Stress-Reduktionsfaktor, strukturierte Blocker (`trading.portfolio_risk_checks`).
- ✅ **AP6** (Stressszenarien): 7 transparente Szenarien (`trading.stress_scenarios`), bewusst einfache 1:1-Marktbewegungs-Annahme statt vorgetäuschtem Beta-Modell.
- 🟡 **AP7** (Backtesting): Schema vollständig (`sql/037`), Ausführungs-Workflow bewusst **nicht gebaut** — mangels ausreichender Historie (System ~2 Wochen alt, `BACKTEST_MIN_WINDOW_DAYS=180`) wäre ein heute laufender Backtest ohne Aussagekraft. Siehe `docs/BACKTESTING_UND_WALK_FORWARD.md`.
- 🟡 **AP8** (Kalibrierung): Schema+Formeln vollständig spezifiziert (`sql/037`), Berechnungs-Workflow bewusst **nicht gebaut** — 0 abgeschlossene Paper Trades. Siehe `docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md`.
- ✅ **AP9** (Lernagent erweitert): neuer Workflow `09b – Lernagent Handelsstrategien`, vier harte Gates (Fallzahl/OOS/Konzentration/Effektstärke), KI berechnet keine Zahlen mehr (nur include/exclude-Entscheidung). `12` um vier neue, echte Aktivierungspfade erweitert (eine dokumentierte Ausnahme: `strategy_parameter_change` wird von `02` noch nicht gelesen). `06` prüft `trading.strategy_status` vor jeder Kandidatenauswahl.
- ✅ **AP10** (Versionsfelder): `rule_version`/`configuration_version`/`data_schema_version`/`execution_model_version`/`risk_model_version` durchgängig auf `paper_trades`/`backtest_runs`/`probability_estimates`.
- ✅ **AP11+AP12**: Dashboard (`07`) um 6 neue Sektionen erweitert, Report/Prüfagent (`10`) um 4 neue Ablehnungsregeln.
- ✅ 18 von 22 geforderten Testfällen lokal automatisiert getestet (`tests/test_welle3_reine_funktionen.js`, 18/18 Assertions bestanden), 1 bewusst als "nicht implementiert" dokumentiert (Trailing-Stop), 3 Schema-only mangels Daten. Details: `docs/TESTPLAN_WELLE_3.md`.
- ✅ Dokumentation: `docs/PAPER_TRADING_LEDGER.md`, `docs/AUSFUEHRUNGSMODELL.md`, `docs/PORTFOLIORISIKO.md`, `docs/BACKTESTING_UND_WALK_FORWARD.md`, `docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md`, `docs/LERNAGENT_HANDELSSTRATEGIEN.md`, `docs/TESTPLAN_WELLE_3.md`.
- ✅ **Live gepusht und verifiziert** (2026-08-01): alle 3 Migrationen (`sql/035-037`) live ausgeführt und per Verifikationsquery bestätigt (alle 20 erwarteten Tabellen/Spalten/Config-Keys/Seed-Zeilen exakt vorhanden). 4 geänderte Workflows (`06`, `07`, `10`, `12`) gepusht, 2 neue Workflows angelegt (`09b – Lernagent Handelsstrategien` id `N91C38VeoNXUBWmB`, `14 – Portfolio-Risiko und Paper-Trading` id `H0iZrWQy1HQi6iro`), beide bewusst **inaktiv**. **Noch offen**: kein echter Lauf beobachtet — beide neuen Workflows brauchen einen ersten manuellen Test, bevor an eine Aktivierung der Zeitpläne zu denken ist.

## Welle 2 – Strategiemotor, Marktregime und systematische Kandidatensuche (2026-08-01)

Acht Arbeitspakete (AP1-AP8), vollständig implementiert und lokal getestet, **live-Push und Test gegen die echte n8n-Instanz noch ausstehend** (siehe unten).

- ✅ **AP1** (normalisiertes Strategiesignal): neue Tabelle `trading.strategy_signals` (Point-in-Time revisioniert wie `fundamentals_history`, `sql/031`). `02` schreibt die drei bestehenden technischen Strategiesignale (mean_reversion/trend_following/breakout, seit Paket 18) jetzt zusätzlich normalisiert dorthin, inkl. neu ergänztem strategie-spezifischem Stop/Ziel/Entry-Zone/Zeitstop (statt nur einem einzigen ATR-Stop für alle drei).
- ✅ **AP2** (4 Strategien getrennt): `news_event` als vierte Strategie neu in `06` berechnet (dort liegen News+technische Bestätigung erst gemeinsam vor), ebenfalls nach `strategy_signals` geschrieben. Bestehendes Gesamtpunktesystem unverändert erhalten (Rückwärtskompatibilität).
- ✅ **AP3** (Marktregime): `02b` berechnet jetzt Trend-/Volatilitäts-/Stress-Regime je Region (Europa/USA) aus den 8 bereits vorhandenen Referenzsymbolen (`trading.market_regime`, `sql/032`), plus eine versionierte Strategie-Regime-Matrix (4 Strategien × 7 Regime-Zustände). Marktbreite/Liquiditätsregime bewusst NICHT erfunden (keine Datenquelle) — bleiben `not_available`. FastAPI-Periode in `02b` ebenfalls auf `1y` umgestellt (für EMA200).
- ✅ **AP4** (Opportunity/Risk/Evidence): drei neue, fachlich getrennte Scores auf `recommendations` (`sql/033`) ersetzen die fachliche Bedeutung von `decision_score` (bleibt nur noch als abgeleiteter, klar veralteter Wert). Dokumentierte Evidenzgruppen-Logik verhindert Doppelzählung korrelierter Indikatoren (RSI+Bollinger, MACD-Varianten).
- ✅ **AP5** (Fundamentaltrend): ROE-/Margen-/Verschuldungs-/Kurszieltrend real aus der Point-in-Time-Historie berechnet. Umsatz-/Gewinntrend (absolut) bleiben explizit `not_available` — die FastAPI-Quelle liefert keine absoluten Werte, nur Kennzahlen/Ratios.
- ✅ **AP6** (Markt-Screener): neuer Workflow `13 – Markt-Screener täglich`, zweistufig (günstiges Screening → vertiefte Auswahl unter konfigurierbaren Obergrenzen), historisiert in `trading.scan_runs`/`trading.scan_candidates` (`sql/034`), jeder ausgeschlossene Kandidat mit Grund. Schreibt NICHT in `recommendations`, aktiviert/löscht keine Watchlist-Titel — rein beobachtend. Bekannte Einschränkung: Datenuniversum == Watchlist aktuell (siehe `docs/MARKTSCANNER.md`).
- ✅ **AP7** (`06` umgestellt): komplette Ablösung der alten "News+Technik-Kombo" durch strategiesignal-getriebene Auswahl der dominanten, regime-bereinigten Strategie je Ticker, andere passende Strategien als Alternativszenarien gespeichert. Hebelprodukt-Logik bleibt schema-kompatibel, aber nicht mehr Teil der allgemeinen Entscheidung. Welle 1s 12 harte Vetos, Risikomodell, Schließungs-Fallback vollständig erhalten und angepasst.
- ✅ **AP8**: Dashboard (`07`) und Report/Prüfagent (`10`) um Top-Strategiesignale, Marktregime je Region, Scanner-Ergebnisse (inkl. Ausschlussgründe), Opportunity/Risk/Evidence, Einstiegskorridor erweitert. Prüf-Agent bekommt zwei weitere Ablehnungsregeln (Opportunity fälschlich als Erfolgswahrscheinlichkeit dargestellt, regime-blockierte Strategie als aussichtsreich dargestellt).
- ✅ 14 von 16 geforderten Testfällen lokal automatisiert getestet (`tests/test_welle2_reine_funktionen.js`, 14/14 Assertions bestanden), 2 (DRY_RUN/REQUIRE_CONFIRMATION) unverändert aus Welle 1 übernommen. Details: `docs/TESTPLAN_WELLE_2.md`.
- ✅ Dokumentation: `docs/STRATEGIEMODELL.md`, `docs/MARKTREGIME.md`, `docs/OPPORTUNITY_RISK_EVIDENCE.md`, `docs/MARKTSCANNER.md`, `docs/TESTPLAN_WELLE_2.md`.
- ✅ **Live gepusht und verifiziert** (2026-08-01): alle 4 Migrationen (`sql/031-034`) über `97` ausgeführt, per Verifikationsquery bestätigt (alle erwarteten Tabellen/Spalten/28 Matrix-Zeilen/7 Scanner-Config-Keys vorhanden). Fünf geänderte Workflows (`02`, `02b`, `06`, `07`, `10`) per n8n-API gepusht, neuer Workflow `13 – Markt-Screener täglich` per API angelegt (id `43lG9aZVHwzIp0jq`, bewusst **inaktiv** — noch kein Testlauf beobachtet). **Noch offen**: kein echter Tageslauf beobachtet (nächster planmäßiger `00`-Lauf Montag 2026-08-03), `13` noch nie manuell ausgeführt. Details im Abschlussbericht.

## Welle 1 – Verlässliche Datenbasis, harte Vetos, Einzeltrade-Risiko (2026-07-31)

Neuer, separater Auftrag nach Abschluss des ursprünglichen 12-Phasen-Auftrags. Sieben Arbeitspakete (AP1-AP7), vollständig implementiert und lokal getestet, **live-Push und Test gegen die echte n8n-Instanz noch ausstehend** (siehe unten).

- ✅ **AP1** (vollständige OHLCV-Historie): `trading.stock_price_history` speichert jetzt open/high/low/volume/adjusted_close/exchange/source_timestamp (vorher nur close+source), mit Point-in-Time-Revisionierung statt stillem Überschreiben (`sql/025`). `02`/`02b` schreiben vollständig, `07`/`08` als Leser auf `valid_to IS NULL` angepasst.
- ✅ **AP2+AP3** (Kerzenbildung/Datenqualität/Mindesthistorie): `02` baut Kerzen jetzt über den gemeinsamen Zeitstempel statt vier unabhängig gefilterter Arrays, klassifiziert in valid/limited/invalid/stale/session_incomplete (`sql/026`), erzwingt echte 252/60/20-Tage-Mindesthistorien. Live gegen den FastAPI-Kursdienst geprüft: `period=3mo` lieferte nur ~63 Handelstage, auf `period=1y` umgestellt (252+ Tage, verifiziert an AAPL/SAP.DE).
- ✅ **AP4** (Börsensitzungs-Status): neue zentrale View `trading.v_market_session_status` (`sql/027`), nutzt die seit Paket 5 vorhandenen, bis dahin ungenutzten `market_reference`/`exchange`-Daten.
- ✅ **AP5** (alle 12 harten Vetos): strukturiert in `06` umgesetzt (Code/severity/source/message/observed_value/required_value), geloggt in `trading.recommendation_veto_log` (`sql/028`) statt nur console.warn. Dabei zwei echte Bestandsfehler gefunden+gefixt: (1) `stop_price`/`target_price` wurden seit Paket 17 berechnet, aber nie in die INSERT-Spaltenliste aufgenommen; (2) der Kurs-Ungültig-Check blockierte bisher Öffnen UND Schließen gemeinsam — Schließungen haben jetzt einen sicheren Fallback-Pfad.
- ✅ **AP6** (Einzeltrade-Risikomodell): deterministische Formel (risk_amount/unit_risk/theoretical_quantity/position_value/reward_risk_ratio/estimated_fees/estimated_slippage/max_planned_loss), konservative Default-Konfiguration in `trading.pipeline_config` (`sql/029`).
- ✅ **AP7** (These/Zeitstop): deterministische, versionierte Regeln je Strategiefamilie (`sql/030`) — die KI legt keine Zeitpunkte frei fest.
- ✅ Dashboard (`07`) und Report/Prüfagent (`10`) um Datenqualität/harte Blocker/Risiko/These/Sitzungsstatus erweitert, Prüf-Agent bekommt vier neue explizite Ablehnungsregeln.
- ✅ 12 von 14 geforderten Testfällen lokal automatisiert getestet (`tests/test_welle1_reine_funktionen.js`, 13/13 Assertions bestanden), 2 (DRY_RUN/REQUIRE_CONFIRMATION) unverändert aus früheren Paketen übernommen. Details: `docs/TESTPLAN_WELLE_1.md`.
- ✅ Dokumentation: `docs/DATENQUALITAET_UND_SESSIONS.md`, `docs/RISIKOMODELL_EINZELTRADE.md`, `docs/HARTE_VETOS.md`, `docs/TESTPLAN_WELLE_1.md`.
- ✅ **Live gepusht und verifiziert** (2026-07-31 abends): alle 6 Migrationen (`sql/025-030`) über `97` gegen die echte DB ausgeführt und per Verifikationsquery bestätigt (alle erwarteten Spalten/Tabellen/View/Config-Keys vorhanden, `v_market_session_status` liefert für alle 15 Ticker plausible Zeilen). Alle 6 geänderten Workflows (`02`, `02b`, `06`, `07`, `08`, `10`) per n8n-API gepusht, Knotenzahlen live bestätigt. Bewusste Architekturentscheidung: `06` liest die neuen Datenqualitätsfelder NICHT aus der `stock_technical_signals`-Data-Table, sondern aus der bereits bestehenden Postgres-Historie `technical_signals_history` — keine neuen Data-Table-Spalten nötig. **Noch offen**: ein echter Tageslauf (nächster planmäßiger `00`-Lauf ist Montag 2026-08-03) wurde noch nicht beobachtet — die Live-Verifikation deckt Schema + View-Abfrage ab, nicht den vollständigen Workflow-Durchlauf. Details und Restpunkte im Abschlussbericht.

## Fachliche Überarbeitung (Paket 1-8, erledigt 2026-07-26/27)

Umsetzung des 12-Phasen-Auftrags "Fachliche Überarbeitung der Aktienanalyse- und Lernpipeline" (Bestandsaufnahme: `docs/FACHLICHE_BESTANDSAUFNAHME.md`), package-weise additiv umgesetzt und live verifiziert:

- ✅ **Paket 1** (Phase 1+3+4, `sql/009-011`): `news_items` um vollständige Datenbasis (article_text/content_hash/...) + Recherche-Tracking (research_status/...) erweitert; `news_assessments` um getrennte Konfidenz-/Wahrscheinlichkeitsfelder.
- ✅ **Paket 2+3** (Phase 2, `sql/012-013`): View `trading.v_news_latest_assessment` für "genau eine gültige Bewertung je Nachricht" — behebt einen live bestätigten Bug (06/07/10 jointen `news_assessments` bisher ohne Deduplizierung, Risiko doppelter Empfehlungs-Trigger).
- ✅ **Paket 4** (Phase 10a, `sql/014`): `pipeline_runs.business_date` wird jetzt persistiert (Feld existierte zur Laufzeit schon, nur nicht gespeichert). Bewusst kein harter UNIQUE-Constraint (würde manuelle Test-Reruns als Duplikat-Fehler zählen).
- ✅ **Paket 5** (Phase 10b, `sql/015`): `trading.market_reference` (XETRA/NASDAQ/NYSE-Sessionzeiten), `stock_instruments.exchange` befüllt. Schema-only, aktuell kein Consumer.
- ✅ **Paket 6** (Phase 12, `sql/016`): `agent_runs.rule_version`/`configuration_version` (JSONB-Snapshot). Schema-only.
- ✅ **Paket 7** (Phase 8, `sql/017`): `recommendations` um Risikofelder erweitert (stop_price/target_price/decision_score/is_theoretical/...). Schema-only, **keine** Verdrahtung in `06`s Entscheidungslogik (bewusst separat gehalten wegen dessen dokumentierter Historie fragiler Merge-/DRY_RUN-Stellen).
- ✅ **Paket 8** (Phase 5/6/7, erster Schritt, `sql/018`): additive Point-in-Time-Historie für `stock_fundamentals`/`stock_market_context`/`stock_technical_signals` (3 neue Tabellen, parallel zu den bestehenden Data Tables beschrieben, kein Consumer geändert). **Dabei gefunden und mitgefixt**: ein vorbestehender, ~2 Wochen alter Bug in den originalen `02`/`02b`-„Kurshistorie"-Nodes (fehlendes `mode: runOnceForEachItem` ließ nur 1 Ticker/Tag statt aller erfassen) — betraf auch `stock_price_history` selbst, jetzt live auf volle Ticker-Abdeckung bestätigt.

- ✅ **Paket 9** (Consumer-Migration Teil 1): `07`/`10` nutzen jetzt die Paket-8-Historie für einen 5-Handelstage-Trend-Kontext (Dashboard-Spalte bzw. eigene Report-Sektion). Live über den öffentlichen Webhook (07) und einen echten Execute-Workflow-Lauf inkl. KI-Aufruf (10) verifiziert. Dabei nebenbei einen zweiten Nebenbefund behoben: `07`s `DB: Kursverlauf laden` (stock_price_history, 35 Tage) wurde bisher nur für eine Frische-Prüfung geladen, nie angezeigt — jetzt als Balkendiagramm sichtbar.

- ✅ **Paket 10** (Consumer-Migration Teil 2): `06` schreibt jetzt bei jeder neuen Position `decision_score`/`decision_blockers`/`market_regime` aus dem 5-Tage-Trend — **rein informativ**, die eigentliche Kauf-/Verkauf-Entscheidung bleibt unverändert (dieselbe Ticker-Menge, dieselbe Empfehlung). Neuer Trend-Node seriell in 06s bestehende (nicht Merge-basierte) Datenkette eingefügt, DRY_RUN/REQUIRE_CONFIRMATION unberührt. Funktional simuliert + live per DRY_RUN=true-Test bestätigt.

- ✅ **Paket 11** (Folge-Entscheidung zu Paket 10, `sql/020`, 2026-07-28): starker 5-Tage-RSI-Gegentrend (Schwelle konfigurierbar über `TREND_KONFLIKT_SCHWELLE`, Default 10) stuft eine sonst ausgelöste Kauf-/Verkauf-Entscheidung automatisch zum Vorschlag herab (kein sofortiger Write), über den bereits bestehenden `REQUIRE_CONFIRMATION`/"Als Vorschlag markieren"-Pfad. Schwacher Gegentrend bleibt weiterhin nur informativ (`decision_score`/`decision_blockers` unverändert). Positions-Schließungen werden bewusst nicht gegatet. Migration `sql/020` noch über `97` einzuspielen (Fallback-Default greift bis dahin identisch).
- ✅ `recommendations.run_id` war bei jeder Zeile NULL (Node `Empfehlungen: Abgleich berechnen` reichte den Trigger-Kontext nie durch) — behoben, `sql`-unabhängig, reiner Code-Fix.
- ✅ `trading.scoring_weights` wurde von der eigentlichen Gewichtungslogik (hartkodierte Formel in `09 - Lernagent Newswirkung`, 20 Stellen) nicht gelesen — jetzt per `CROSS JOIN` verdrahtet, `sql/019` seedet die bisherigen Werte als aktive Zeilen (verhaltensneutral bis zur ersten echten Aktivierung).
- ✅ **Paket 12** (Phase 11, 2026-07-31): `04`s Cleanup-Regeln waren laut Bestandsaufnahme (Abschnitt 8/9) nie Zeile für Zeile geprüft. Live per `information_schema`-Abfrage gefunden: `news_assessments.news_id` ist ein `FOREIGN KEY (NO ACTION)` auf `news_items.id` — alle drei DELETE-Regeln (discarded/21d, failed/30d, evaluated/365d) hätten mit einem Fremdschlüssel-Fehler abgebrochen, sobald die erste betroffene Zeile ins jeweilige Zeitfenster fällt (bisher latent, da das System erst ~12 Tage alt ist, noch unter der kürzesten 21-Tage-Frist). Live bestätigt: 817/817 evaluated- und 452/452 discarded-Zeilen haben bereits eine Bewertung. Nutzerentscheidung: eine bewertete News wird nie gelöscht, unabhängig vom Alter — allen drei Regeln denselben `NOT EXISTS (news_assessments)`-Schutz hinzugefügt (analog zum bereits vorhandenen Schutz gegen `news_impact_tracking`). Praktische Folge: die 21- und 365-Tage-Regeln greifen dadurch faktisch fast nie mehr (Assessments sind nahezu universell), bleiben aber als Sicherheitsnetz für unbewertete Zeilen bestehen. **Wichtig**: dies war nur ein FK-Bugfix, keine Umsetzung von Phase 11 selbst (Archivierungsumstellung) — siehe `docs/PHASENWEISER_ABGLEICH_2026-07-31.md`.

### Vollständiger Abgleich gegen den Original-Auftrag (2026-07-31)

Nutzer hat den kompletten Original-Auftragstext eingefügt (vorher lag nur eine Paraphrase vor). Live-Audit gegen den echten DB-/Workflow-Stand ergab: nur 2 von 13 Punkten sind wirklich erfüllt, 5 sind gar nicht umgesetzt (Phase 5/6/7/8-Vetos/11), alle 7 geforderten `docs/*.md` fehlten. Vollständiger Befund mit Ampel-Tabelle: `docs/PHASENWEISER_ABGLEICH_2026-07-31.md`.

- ✅ **Paket 13** (Phase 5, Schritt 1 von 2, 2026-07-31, `sql/021`): Rohwert/Anzeigeformat-Trennung für `fundamentals_history` — additive `_numeric`-Spalten + `currency`, Rohwerte exakt wie von FastAPI geliefert (z.B. `eigenkapitalrendite_numeric` als Dezimalbruch 0.163, `marktkapitalisierung_numeric` als volle Zahl statt `/1e9`). `01 – Fundamentaldaten täglich` schreibt jetzt beides. Dabei zwei echte Bugs live gefunden+gefixt: (1) die Data-Table-Write-Nodes gaben die neuen Felder gar nicht zurück, (2) der erste Fix-Versuch nutzte `.item` (singular), das ticker-übergreifend denselben (falschen) Wert lieferte — durch `.all()` + explizites Ticker-Matching ersetzt. Live über 3 Testläufe verifiziert. - ✅ **Paket 14** (Phase 5, Schritt 2 von 2, 2026-07-31, `sql/022`): echte Point-in-Time-Semantik — `known_at`/`valid_from`/`valid_to`/`revision_number`, `UNIQUE(ticker, snapshot_date)` ersetzt durch `UNIQUE(ticker, snapshot_date, revision_number)` + partiellem Unique-Index (genau eine "aktuelle" Revision je Tag). `01`s History-Schreibung macht kein `ON CONFLICT DO UPDATE` mehr (überschrieb live bestätigt frühere Werte am selben Tag), sondern schließt die aktuelle Revision und legt eine neue an. `07`/`10` (einzige bestehende Leser, per grep vor der Änderung gefunden) auf `AND valid_to IS NULL` angepasst, damit sie weiterhin genau eine Zeile je Ticker/Tag sehen. Live über 2 Testläufe verifiziert (Revision 1 geschlossen, Revision 2 aktuell, alle 17 Ticker konsistent). **Phase 5 damit vollständig umgesetzt.**
- 🟡 **Paket 15** (Phase 8, Teilschritt, 2026-07-31): 2 der 7 vom Auftrag geforderten harten Vetos in `06`s `Empfehlungen: Abgleich berechnen` echt umgesetzt — fehlender/ungültiger Referenzkurs blockiert Öffnen+Schließen komplett, widersprüchliche gleichtägige starke News (war schon vorher blockiert, jetzt sichtbar via `console.warn` statt still). Restliche 5 Vetos (Datenqualität, veraltete Nachricht, Stop/Ziel-Plausibilität, These-Ablauf, DB-Fehler) offen — 3 davon brauchten Phase 7 als Datengrundlage (jetzt vorhanden, siehe Paket 16 — Verdrahtung in `06` selbst aber noch nicht nachgezogen). Bewusst nur Execution-Log-Sichtbarkeit, keine neue Matrix-Sektion (Routing-Graph-Risiko fürs echte Order-Schreiben, mit Nutzer abgestimmt). **Noch nicht live gegen einen echten Trigger getestet** (nur JS-Syntaxprüfung) — `06` läuft nur über `00` oder einen nicht risikofrei fernauslösbaren UI-Trigger.
- ✅ **Paket 17** (Phase 8, Teil 2, 2026-07-31): `06`s Trend-Signal-Query um `atr_14_numeric`/`atr_stop_numeric`/`atr_target_numeric` erweitert (kein neuer Node noetig, bestehende `technical_signals_history`-Abfrage passte schon). Neue `atrInfo(ticker)`-Funktion + Veto an beiden `oeffnen`-Stellen: fehlender/unverwertbarer ATR-Stop/-Ziel blockiert die Eroeffnung komplett (deckt "unzureichende Datenqualitaet" + "unplausibler Stop/Ziel" zusammen ab). `recommendations.stop_price`/`target_price` (seit Paket 7 leere Schema-Spalten) werden dabei erstmals wirklich befuellt. Beim eigenen Patch einen echten Bug gefunden+gefixt (Funktionsdefinition wurde erst lokal berechnet, aber nie zurueckgeschrieben — waere beim naechsten Lauf mit "atrInfo is not defined" gecrasht), per Syntax-Check vor dem Push abgefangen. **Damit 3 von 7 Vetos aus dem Auftrag real umgesetzt.** Weiterhin nicht live gegen einen echten Trigger getestet (siehe Paket 15).
- ✅ **Paket 16** (Phase 7, 2026-07-31, `sql/023`): ATR-14 (Wilder-geglättet), annualisierte realisierte Volatilität (20d/60d), durchschnittliche Tagesrange (14d) sowie ATR-basierte Stop/Ziel-Werte (Einstieg -/+1.5x ATR bzw. +/-2.5x ATR, richtungsabhängig) in `02`s `Technische Analyse (RSI/MACD/BB)` ergänzt — berechnet direkt aus den bereits vorhandenen High/Low/Close-Arrays der FastAPI-Antwort (35+ Handelstage pro Abruf), nicht aus `trading.stock_price_history` (die hat nur `close`, kaum Tiefe — separater, hier nicht behobener Befund). Bestehende `ziel_kurs`/`stop_kurs` ("legacy") unangetastet, neue Werte zusätzlich in `technical_signals_history`. Unterwegs denselben Data-Table-Roundtrip-Verlust wie bei Paket 13 gefunden+gefixt (`.all()`+Ticker-Matching statt `.item`). Live per manuellem `02`-Lauf verifiziert (Long/Short-Mathematik korrekt, neutrale Signale liefern echte ATR/Vol-Werte aber korrekt NULL für Stop/Ziel, ein defekter Ticker blieb korrekt komplett NULL). **Phase 7 damit vollständig umgesetzt.**
- ✅ **Paket 18** (Phase 6, 2026-07-31, `sql/024`): drei getrennte technische Strategiesignale statt eines gemischten Gesamtscores — `mean_reversion` (RSI-Extremwert + Bollinger-Band-Berührung + Abstand EMA20), `trend_following` (MACD-Kreuzung/Nulllinie/Histogramm + EMA20-Trendbestätigung), `breakout` (Nähe 52-Wochen-Hoch/-Tief + Volumenfaktor + Tagesbewegung). Jedes Signal mit `direction`, `raw_score`, `regime_fit` (aus Bollinger-Band-Breite als Trend-/Seitwärts-Indikator abgeleitet), `data_quality` (=`min(1, closes.length/60)`), `expected_horizon_days` (strategie-typisch, statisch) und `evidence[]` — ausschließlich aus bereits real berechneten Werten, keine erfundene KI-Evidenz. `dominant_strategy` = höchster `raw_score`. Bekannte Korrelationen zwischen den zugrundeliegenden Indikatoren (MACD-Kreuzung/-Histogramm, RSI/Bollinger) statisch dokumentiert statt live berechnet, da dafür eine historische Zeitreihe je Indikatorpaar fehlt. Bestehendes Punktesystem (`signal_punkte`/`signal_gruende`) unangetastet erhalten. **Phase 6 damit vollständig umgesetzt.**
- ✅ **Paket 19** (Phase 11, 2026-07-31): `04 – Cleanup News-Tabellen` um Archivierung statt Löschung erweitert — vollständig ausgewertete News mit abgeschlossener Wirkungsmessung (`news_impact_tracking.status='completed'`, nicht nur "irgendeine Zeile") werden ab 180 Tagen auf `status='archived'` umgestellt statt gelöscht, die Zeile bleibt für Audit/Lernen/Simulation vollständig erhalten. Zusätzlich neue Löschregel für reine Betriebs-Logs ohne fachlichen Lernwert (`pipeline_runs`, `workflow_errors`, 180 Tage) — vorab per `information_schema` auf fehlende Fremdschlüssel geprüft. Neues Dokument `docs/DATENAUFBEWAHRUNG.md` beschreibt alle 6 Datenklassen mit Regel und Begründung, inkl. explizit offen gelassener Fälle (`agent_runs`, `learning_rule_proposals`, `scoring_weights`, `recommendations`). Live per manuellem `04`-Lauf verifiziert (neue Nodes fehlerfrei, aktuell 0 betroffene Zeilen da System erst ~12 Tage alt bzw. alle Logs noch unter 180 Tagen — Regeln korrekt implementiert, aber noch dormant). **Phase 11 damit vollständig umgesetzt.**

**Ergebnis des kompletten Original-Auftrags** ("Fachliche Überarbeitung der Aktienanalyse- und Lernpipeline", 12 Phasen, Stand 2026-07-31 abends): keine der 13 geprüften Phasen ist mehr rot (unbearbeitet). 7 grün (vollständig umgesetzt): Phase 1, 2, 3, 4, 5, 6, 7, 11. 6 gelb (real umgesetzt, aber mit bewusst benannten Restlücken): u.a. Phase 8 (3 von 7 geforderten Vetos), Phase 9, 10, 12 — Details je Phase in `docs/PHASENWEISER_ABGLEICH_2026-07-31.md`. Größte verbleibende Lücken: 4 der 7 Phase-8-Vetos (veraltete News, Thesen-Ablauf — dafür fehlt noch ein gesetztes `thesis_expires_at` — und offene DB-Fehler), sowie `Kurshistorie: SQL bauen` in `02`, die weiterhin nur `close` statt vollem OHLC in `stock_price_history` schreibt.

## Priorität 4 (erledigt, 2026-07-26)

- ✅ RSS-Quellenverwaltung: die bisher in `03`s Node "RSS-Feeds laden & filtern" hartkodierten 7 Feed-URLs liegen jetzt in `trading.rss_sources` (Migration `sql/008_rss_sources.sql`). Neuer Workflow `RSS-Quellen verwalten`, Web-Oberfläche unter `/webhook/rss-quellen` (gleiches Muster wie Watchlist verwalten): Quellen anlegen/bearbeiten/löschen/aktivieren-deaktivieren, plus ein echter Erreichbarkeits-/Gültigkeitstest je Quelle oder für alle auf einmal ("Alle Quellen testen") — ruft die URL live ab und prüft auf ein gültiges `<rss>`/`<feed>`/`<rdf:RDF>`-Tag samt Eintragsanzahl. `03` liest die aktiven Quellen jetzt über einen neuen Node "RSS-Quellen aus DB laden (News)" (mit `executeOnce:true`, da Postgres-Nodes sonst einmal pro Input-Item statt einmal pro Lauf ausführen — ohne diesen Fix liefen 7 Feeds fälschlich 17x, siehe unten). Live getestet: alle 7 echten Feeds erfolgreich abgerufen (15–54 Einträge je Quelle), Fehlerfall mit bewusst kaputter Test-URL korrekt erkannt, CRUD-Aktionen (add/edit/toggle/delete) alle live bestätigt, kompletter `03`-Lauf danach fehlerfrei mit exakt 7 (nicht mehr 7×17=119) geladenen Quellen.

## Priorität 1 (erledigt, 2026-07-24)

- ✅ `08 – News-Wirkungsanalyse` lief am 24.07. automatisch um 19:00 Uhr erfolgreich durch (kein Fehler-Eintrag, anders als an den drei Tagen zuvor mit `error, mode:trigger` um 17:00 UTC) — die 3-Tage-Fehlserie ist durchbrochen, der Abhängigkeitsfehler ist behoben.
- ✅ Automatischer Taglauf über `00` (17:50 Uhr) lief bis zum Prüfagenten durch; dieser lehnte den Report inhaltlich begründet ab (Konfidenz 41) — das ist die vorgesehene Governance-Funktion, kein Fehler.

## Priorität 2 (erledigt, 2026-07-26)

- ✅ Ablehnungs- und DRY_RUN-Pfad in Workflow `05` getestet (2026-07-24, per pinData auf `Execute Workflow Trigger`, danach zurückgesetzt): Ablehnung → `{ok:false, status:'failed'}` inkl. korrektem Matrix-Fehler-Alert; DRY_RUN → `{ok:true, status:'skipped'}`, kein echter Versand, sauber getaggt. Beide wie erwartet.
- ✅ Fehler-Pfade in `05` geprüft: `onError:continueRegularOutput` korrekt auf allen drei Sende-Nodes (Matrix-Report, E-Mail, Matrix-Fehler-Alert) gesetzt, wie in Priorität 6 spezifiziert. Echtes automatisches Node-Retry existiert bewusst nicht (API lehnt node-level `retryOnFail`/`maxTries` beim Push ab, siehe README) — bekannte, akzeptierte Grenze, kein offener Test.
- ✅ SMTP-E-Mail-Versand real bestätigt (2026-07-26, per pinData mit klar als „TESTLAUF" markierten Daten, danach zurückgesetzt): echte Mail an `oliver.lietz@golietz.de`, Server-Antwort `250 2.0.0 Ok: queued as BB6BE288967`, `accepted:['oliver.lietz@golietz.de']`, `rejected:[]`. Da der reale Sende-Zweig E-Mail und Matrix gemeinsam auslöst, lief die Matrix-Nachricht im selben Test mit durch (echte `event_id` erhalten) — auf Nutzerwunsch nicht isoliert, beides zusammen bestätigt.
- ✅ `sql/007_runtime_schema_reconciliation.sql` gegen ein leeres Schema geprüft (2026-07-26): alle 7 Migrationsdateien (001–007) in Reihenfolge gegen ein frisches `trading_test`-Schema ausgeführt (per `97 – Einmalig – Beliebige Query ausführen`, `trading.` global auf `trading_test.` umgeschrieben, Original-`trading`-Schema nicht angerührt). Ergebnis: alle 14 erwarteten Tabellen fehlerfrei erstellt (`agent_runs`, `learning_rule_proposals`, `news_assessments`, `news_impact_tracking`, `news_items`, `pipeline_config`, `pipeline_runs`, `prompt_versions`, `recommendations`, `scoring_weights`, `stock_instruments`, `stock_price_history`, `watchlist`, `workflow_errors`) — die Migrationskette ist von Grund auf reproduzierbar. Test-Schema danach vollständig entfernt (`DROP SCHEMA trading_test CASCADE`, verifiziert).

## Priorität 3

- ✅ Veraltete Aussagen in `README.md` und `MIGRATIONSPLAN_AGENTEN.md` bereinigt (2026-07-24): `07`s Status-Übersicht fälschlich noch als "mit Header-Token" geführt (tatsächlich seit 07-23 ohne Auth), `05`s DRY_RUN-/Ablehnungs-Zweig noch als "ungetestet" vermerkt (heute bestätigt getestet). Aktivierungsstatus (`02`/`02b`/`05`/`06` eigene Trigger deaktiviert) live geprüft und stimmt weiterhin.
- ✅ Kontrollierter Freigabe-/Aktivierungsworkflow für die von Workflow `09` erzeugten Lernvorschläge (2026-07-25): neuer Workflow `12 – Lernvorschlag-Freigabe`, Web-Oberfläche unter `/webhook/lernvorschlaege` (gleiches Muster wie Watchlist verwalten, auf Nutzerwunsch keine Matrix-Umfrage). „Freigeben & aktivieren" schreibt sofort nach `trading.scoring_weights` und markiert die Proposal-Zeile als `activated`, „Ablehnen" setzt nur den Status. Live getestet (aktuell 0 Vorschläge, da `09` noch keine erzeugt hat). Dabei einen echten n8n-Plattform-Bug gefunden und gefixt: Postgres-Abfragen mit 0 Ergebniszeilen ließen nachgelagerte Nodes gar nicht erst ausführen, wodurch der Webhook lautlos leer antwortete (kein Fehler, keine Execution). Fix: `alwaysOutputData:true` auf dem Postgres-Node + Filter des dadurch erzeugten Platzhalter-Items. Derselbe (bisher nicht ausgelöste) Bug wurde vorsorglich auch in `Watchlist verwalten` behoben.
- Hinweis: `trading.scoring_weights` wird von der eigentlichen Gewichtungslogik (z.B. in `03`/`09`) noch nicht gelesen — die dort hartkodierte Formel (`high=1.0/medium=0.7/limited=0.4/confounded=0.25`) wird durch eine Aktivierung also noch nicht automatisch wirksam. Separates, noch nicht beauftragtes Folge-Thema, falls gewünscht.

## Bereits erledigt

- Status- und Watchlist-Webseiten sind im LAN ohne Webhook-Authentifizierung erreichbar.
- Ticker können über die Watchlist-Webseite angelegt, bearbeitet, aktiviert, deaktiviert und nach Bestätigung gelöscht werden.
- Beim Ändern oder Löschen werden `trading.watchlist` und `trading.stock_instruments` synchron gehalten.
