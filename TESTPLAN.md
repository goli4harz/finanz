# Testplan

Stand: 2026-08-01. Alle Tests wurden lokal gegen den tatsächlichen Node-Code ausgeführt (Node.js `new Function(...)`-Harness, siehe `scratch/`-Skripte dieser Session), nicht gegen die echte n8n-Instanz simuliert - jeder Test lädt den *tatsächlichen* `jsCode`/`query`-String aus der live gepushten Workflow-Datei. Live-Webhook-Tests (Watchlist, RSS-Quellen, Lernvorschlag-Freigabe) liefen zusätzlich gegen die echte n8n-Instanz.

**Legende Status:** `bestanden` / `fehlgeschlagen` / `nicht ausgefuehrt`

---

## SQL-Sicherheit

| ID | Voraussetzung | Testdaten | Erwartetes Ergebnis | Tatsächliches Ergebnis | Status |
|---|---|---|---|---|---|
| SEC-1 | A1-Fix live | Watchlist-Ticker `ZZTEST1` mit Keyword `a'); DROP TABLE trading.watchlist;--` per echtem POST an `/webhook/aktien-watchlist` | Payload wird als Text gespeichert, kein SQL-Bruch | Bestätigt: Keyword erscheint verbatim im Wert-Attribut, Tabelle unverändert, Ticker anschließend gelöscht | bestanden |
| SEC-2 | A3/A4-Fix live | `ticker=X'; DROP TABLE watchlist;--` per echtem POST | Sichtbares Fehlerbanner statt Erfolgsseite | Bestätigt: `banner-error` mit "Ungueltiges Tickerformat" | bestanden |
| SEC-3 | A11-Fix live | `url=http://127.0.0.1:5678/rest/login` per echtem POST + Test-Aktion | SSRF-Block vor dem eigentlichen Abruf | Bestätigt: "Private/lokale IPv4-Adresse nicht erlaubt: 127.0.0.1" | bestanden |
| SEC-4 | A11-Fix live | Test einer echten Quelle (tagesschau.de, hat legitimen 301-Redirect) | Abruf funktioniert weiterhin | Bestätigt: "RSS/Atom-Feed gueltig (40 Eintraege)" nach Revert der Redirect-Deaktivierung | bestanden |
| SEC-5 | A5-Fix (lokal simuliert) | Proposal-DB-Zeile ist `weight_adjustment`, Body behauptet `strategy_deactivation` | Server verwendet ausschließlich die DB-Wahrheit | Bestätigt: generierte SQL nutzt `weight_adjustment`-Zweig unabhängig vom Body | bestanden |
| SEC-6 | A6-Fix (lokal simuliert) | Ziel-Update trifft 0 Zeilen (nicht existenter `target_value`) | Status wird nicht `activated` | Bestätigt: CASE-Ausdruck liefert `activation_failed` | bestanden |
| SEC-7 | A9-Fix (lokal simuliert) | `proposed_value` leer/NaN bei `threshold_adjustment` | Kein NULL-Write, sofortiger `activation_failed` | Bestätigt | bestanden |

## Orchestrator

| ID | Voraussetzung | Testdaten | Erwartetes Ergebnis | Tatsächliches Ergebnis | Status |
|---|---|---|---|---|---|
| ORCH-1 | B1-Fix (lokal) | `status` fehlt (undefined) | Gate blockiert | Bestätigt: `['success','partial_failure','skipped'].includes(undefined)` = false | bestanden |
| ORCH-2 | B1-Fix (lokal) | `status='partial_failure'` | Gate lässt durch | Bestätigt | bestanden |
| ORCH-3 | B4-Fix (lokal) | Config-Query liefert 0 Zeilen | `DRY_RUN=true` | Bestätigt (beide Stellen, 00 und 06) | bestanden |
| ORCH-4 | — | Echter Orchestrator-Lauf (00) end-to-end | — | **nicht ausgeführt** - würde reale Sub-Workflows anstoßen, außerhalb des Rahmens dieser Session | nicht ausgeführt |

## Candles/Datenqualität

| ID | Voraussetzung | Testdaten | Erwartetes Ergebnis | Tatsächliches Ergebnis | Status |
|---|---|---|---|---|---|
| CANDLE-1 | C4-Fix (lokal) | 40-Tage-Datensatz, letzter Tag: `close=null`, aber `open/high/low/volume` mit abweichendem Preisniveau vorhanden | Korrupte Kerze komplett verworfen, letzte gültige Kerze konsistent | Bestätigt: `kerze_close=100`, `kerze_open=99.8` (Vortag), nicht die korrupten 999/1005 | bestanden |
| CANDLE-2 | C4-Fix (lokal) | Sauberer 260-Tage-Datensatz | `data_quality_status='valid'`, plausible EMA200/Regime | Bestätigt | bestanden |
| CANDLE-3 | C1-Fix live | Echter Abruf `GET /chart/AAPL?period=1y&interval=1d` und `GET /chart/SAP.DE?period=1y&interval=1d` gegen die reale lokale FastAPI | ≥251 Handelstage statt ~63, `breakoutHistoryAusreichend` erreichbar (direkt oder über `fiftyTwoWeekHigh`-Meta) | Bestätigt: AAPL 251 Tage (zusätzlich `fiftyTwoWeekHigh=344.57` als Fallback), SAP.DE 253 Tage (direkt ≥252) | bestanden |
| CANDLE-4 | C6-Fix (lokal) | 6 Testfälle: `data_quality_status` = `session_incomplete`/`stale`/`limited`/`valid`/`invalid` sowie kein Match in `Signal: flach aufbereiten` | Alle fünf Werte landen unverändert in der generierten SQL, kein Match → `SELECT 1;` (kein Schreibversuch) | Bestätigt für alle 6 Fälle | bestanden |

## Portfolio-Risiko/Paper-Trading (Workflow 14)

| ID | Voraussetzung | Testdaten | Erwartetes Ergebnis | Tatsächliches Ergebnis | Status |
|---|---|---|---|---|---|
| PORT-1 | E1/E2-Fix (lokal) | 9 offene Positionen (`MAX_OPEN_POSITIONS=10`), 3 neue Kandidaten (verschiedene `opportunity_score`) | Nur bester Kandidat genehmigt, Rest korrekt geblockt | Bestätigt: AAA genehmigt (9→10), BBB/CCC beide `MAX_OPEN_POSITIONS`-geblockt | bestanden |
| PORT-2 | E5-Fix (lokal) | 3 Verluste (-8000/-5000/-3000) auf 100000 Startkapital | 16% Drawdown erkannt, `DRAWDOWN_LIMIT` löst aus | Bestätigt | bestanden |
| PORT-3 | E7-Fix (lokal) | Trade mit bekannten Entry-/Exit-Kosten (1.5+1.8) | `net_pnl` enthält beide Kostenkomponenten | Bestätigt: 196.70 statt 200 (Bruttogewinn) | bestanden |
| PORT-4 | E8-Fix (lokal) | `data_error_count=2`, `MAX_DATA_ERROR_RETRIES=3`, keine Kerze | Eskalation nach `data_error_final` + `workflow_errors`-Eintrag | Bestätigt | bestanden |
| PORT-5 | E9-Fix (lokal) | Fill bei 101 (in Zone), Stop bei 98, Kerze mit `low=97` | Same-Bar-Exit erkannt, nicht erst am Folgetag | Bestätigt: `close_cluster` mit `exit_reason='stop_loss'`, `same_bar_fill_and_exit` markiert | bestanden |
| PORT-6 | E4/E12-Fix (lokal) | Generierte SQL für `fill_cluster`/`close_cluster` | Gültiges, atomares `BEGIN...COMMIT`, `sektor` in INSERT enthalten | Bestätigt (manuell auf SQL-Korrektheit geprüft) | bestanden |
| PORT-7 | sql/039 ausgeführt | Echter Lauf von Job A/B gegen reale DB | — | **nicht ausgeführt** - Migration steht noch aus, Workflow bewusst inaktiv | nicht ausgeführt |

## News-Pipeline

| ID | Voraussetzung | Testdaten | Erwartetes Ergebnis | Tatsächliches Ergebnis | Status |
|---|---|---|---|---|---|
| NEWS-1 | D3/D4-Fix (lokal) | DB-Zeile mit echter `beschreibung`/`type` | Batch-Payload nutzt echte Werte statt Hardcoding | Bestätigt | bestanden |
| NEWS-2 | D5-Fix (lokal) | Artikel mit Apostroph im Titel/Beschreibung, Ticker-Match | Korrekt escapte INSERT-SQL mit allen Spalten | Bestätigt | bestanden |
| NEWS-3 | D13-Fix | SQL-Syntax der geänderten Query | Gültige PostgreSQL-Syntax (korrelierte EXISTS/NOT EXISTS mit `jsonb_array_elements_text`) | Manuell verifiziert, kein Postgres-Zugriff für EXPLAIN in dieser Session verfügbar | bestanden (Syntax), nicht ausgeführt (Laufzeit) |
| NEWS-4 | D2-Fix (lokal) | KI meldet `betroffene_ticker: ['BMW.DE','FAKE.XX']`, Watchlist enthält nur `BMW.DE`/`SAP.DE`/`MBG.DE` | `betroffene_ticker=['BMW.DE']`, `betroffene_ticker_verworfen=['FAKE.XX']` | Bestätigt | bestanden |
| NEWS-5 | D2-Fix (lokal) | Watchlist-Node in `$(...)` nicht auffindbar (simuliert) | Alle gemeldeten Ticker gelten als nicht bestätigt, kein Crash | Bestätigt: `betroffene_ticker=[]` | bestanden |
| NEWS-6 | D6-Fix (lokal) | KI meldet `wahrscheinlichkeit_positiv/negativ/neutral = 0.6/0.2/0.2` | Werte unverändert in `probability_positive/negative/neutral` und in der generierten SQL | Bestätigt | bestanden |
| NEWS-7 | D6-Fix (lokal) | KI meldet `wahrscheinlichkeit_positiv/negativ/neutral = 0.9/0.9/0.9` (Summe 2.7) | Alle drei Wahrscheinlichkeitsfelder `NULL` statt einer inkonsistenten Verteilung | Bestätigt | bestanden |
| NEWS-8 | D6-Fix (lokal) | KI liefert kein `relevanz_konfidenz`-Feld | `relevance_confidence=NULL` (nicht `0`, D7-Muster) | Bestätigt | bestanden |

## Lernagenten

| ID | Voraussetzung | Testdaten | Erwartetes Ergebnis | Tatsächliches Ergebnis | Status |
|---|---|---|---|---|---|
| LERN-1 | F1-Fix (lokal) | Aktives Gewicht `source:Reuters:D+1=0.6` in DB | Finding bekommt `current_value=0.6`, nicht 1.0 | Bestätigt | bestanden |
| LERN-2 | F1-Fix (lokal) | Unbekannte Kombination ohne DB-Eintrag | `current_value=1.0` (echter Default) | Bestätigt | bestanden |
| LERN-3 | F2-Fix (lokal) | KI behauptet `current_value=1.0` (Lüge), `proposed_value=0.8` (echte Basis 0.6, innerhalb Schrittweite) | `current_value` wird auf echten Wert korrigiert, Vorschlag akzeptiert | Bestätigt | bestanden |
| LERN-4 | F2-Fix (lokal) | `proposed_value=5.0` (weit außerhalb Schrittweite von 0.6) | Vorschlag verworfen | Bestätigt: `proposals_final=[]` | bestanden |
| LERN-5 | F2-Fix (lokal) | `proposed_value=0.05` (unter `MIN_WEIGHT`) | Vorschlag verworfen | Bestätigt | bestanden |
| LERN-6 | F2-Fix (lokal) | `proposed_value='ungueltig'` (nicht numerisch) | Vorschlag verworfen | Bestätigt | bestanden |
| LERN-7 | F4-Fix (lokal) | OOS-Backtest nur für `breakout`, Findings für `breakout` UND `mean_reversion` | Nur `breakout` OOS-bestätigt, `mean_reversion` bleibt unbestätigt | Bestätigt | bestanden |
| LERN-8 | F5-Fix (lokal) | `strategy_regime`-Finding mit positivem Erwartungswert (0.5) | Kein `regime_restriction`-Kandidat | Bestätigt: `candidate_proposal=null` | bestanden |

## Nicht abgedeckt in dieser Session (offen)

- Vollständiger End-to-End-Lauf von Workflow `00` (Orchestrator) mit allen Sub-Workflows.
- Workflow `14` gegen die echte Datenbank nach Ausführung von `sql/039`.
- Workflow `12` (Lernvorschlag-Freigabe) mit einer echten `proposed`-Zeile (aktuell 0 Vorschläge in der DB) nach Ausführung von `sql/038`.
- Alle Testfälle aus Auftrag Abschnitt 29-30, die nicht direkt den in dieser Session behobenen kritischen Punkten entsprechen (z.B. vollständige SQL-Injection-Testsuite für `12`s andere Proposal-Typen, vollständige Portfolio-Mehrfachszenarien mit Korrelation+Sektor gemeinsam).
- Die 19 "hoch" und 21 "mittel" eingestuften Funde aus `FEHLERANALYSE.md` sind noch unbehandelt (nächste Priorität laut Auftrag-Reihenfolge).
