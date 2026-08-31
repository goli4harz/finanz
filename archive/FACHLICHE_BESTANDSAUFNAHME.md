# Fachliche Bestandsaufnahme (Phase 0)

Stand: 2026-07-26. Grundlage: direkte Live-Abfrage des n8n-Servers (`http://172.16.1.14:5678`, REST-API) und der produktiven PostgreSQL-Instanz (Schema `trading`), plus Abgleich mit den bestehenden Repo-Dokumenten `ARCHITEKTUR_BESTAND.md` (2026-07-19, Ist-Zustand **vor** dem Agenten-Umbau) und `MIGRATIONSPLAN_AGENTEN.md` (2026-07-20, abgeschlossen). Diese Datei ersetzt beide nicht, sondern baut auf ihnen auf und aktualisiert den Stand auf **heute**, inklusive aller seit dem 20.07. dazugekommenen Workflows (03a, 08, 09, 10, 11, 12, RSS-Quellen verwalten, Watchlist verwalten) und der tatsächlichen aktuellen Postgres-Struktur (Migrationen 001–008).

Alle Aussagen unten sind gegen den **tatsächlich laufenden** Server geprüft (Workflow-Liste per `GET /api/v1/workflows`, Node-Inhalte per `GET /api/v1/workflows/{id}`, Schema per `information_schema`-Abfrage über den Hilfsworkflow `97 – Einmalig – Beliebige Query ausfuehren`), nicht nur gegen die Git-Dateien im Repo.

---

## 1. Aktive Workflows (live bestätigt, Stand heute)

Alle 17 unten genannten Workflows sind **aktiv** (`active: true`) und stimmen 1:1 mit den lokalen Repo-Dateien überein (jeweils frisch von der Live-Instanz gezogen).

| # | Workflow | Live-ID | Trigger | Node-Zahl (Kern-Typen) |
|---|---|---|---|---|
| 00 | Tagesabschluss-Orchestrator | `ncMZzkqDHpSiDGPm` | Cron `17:50` Mo–Fr | 20 Code, 9 Postgres, 5 ExecuteWorkflow, 6 Merge, 6 IF, 1 DataTable |
| 01 | Fundamentaldaten täglich | `TgHlJ6ckDhiOU1hq` | Cron `06:00` Mo–Fr (eigenständig, **nicht** vom Orchestrator aufgerufen) | 1 Postgres, 1 HTTP, 3 Code, 5 DataTable |
| 02 | Technische Signale täglich | `vgT6IrPp3ATaJg8s` | Cron `18:00` Mo–Fr (**Node deaktiviert**, siehe Abschnitt 4) + ExecuteWorkflowTrigger | 2 Postgres, 2 HTTP, 7 Code, 4 DataTable |
| 02b | Marktumfeld täglich | `9zO3uZeZeakTnLnX` | Cron `17:55` Mo–Fr (**Node deaktiviert**) + ExecuteWorkflowTrigger | 5 Code, 1 HTTP, 3 DataTable, 1 Postgres |
| 03 | News Ingestion stündlich – Agent V1 | `kXfFAy97N6xgRgQ5` | Cron stündlich Mo–Fr | 14 Code, 7 Postgres, 2 HTTP, 1 OpenAI |
| 03a | News-Recherche-Agent | `SUNb1rfSUTQGUTPN` | Cron alle 2h Mo–Fr | 6 Postgres, 7 Code, 1 HTTP, 1 OpenAI |
| 04 | Cleanup News-Tabellen – Agent V1 | `3aeFh4tfDrCi4dUm` | Cron `23:45` Mo–Fr / `Sa 00:15` | 5 Postgres, 5 Code |
| 05 | Tagesreport – Agent V1 | `VRr5jIHj7G7dsMwi` | Cron `18:30` Mo–Fr (**Node deaktiviert**) + ExecuteWorkflowTrigger | 1 ExecuteWorkflow (→10), 8 Code, 2 HTTP, 1 EmailSend |
| 06 | Empfehlungswatchlist – Agent V1 | `aguWZUolRizBnsj4` | Cron `18:10` Mo–Fr (**Node deaktiviert**) + ExecuteWorkflowTrigger | 5 Postgres, 13 Code, 1 DataTable |
| 07 | Status-Uebersicht – Agent V1 | `7hQ3t6KrSo9uDNML` | Webhook GET `/aktien-status` (**ohne Authentifizierung**, bewusst, siehe README) | 11 Postgres, 3 DataTable, 13 Merge |
| 08 | News-Wirkungsanalyse | `EvJKlqkuSIu9CHmR` | Cron `19:00` Mo–Fr | 7 Postgres, 8 Code |
| 09 | Lernagent Newswirkung | `LjZHC5g7thqcCElo` | Cron Samstag `08:00` | 7 Postgres, 7 Code, 1 OpenAI |
| 10 | Report- und Prüfagent | `BFlxfLyarzR2xbBT` | nur ExecuteWorkflowTrigger (kein eigener Cron) | 6 Postgres, 3 DataTable, 2 OpenAI |
| 11 | Zentraler Error-Handler | `VTBfUuzQfMZNGYDM` | n8n ErrorTrigger (global) | 1 Postgres, 1 HTTP |
| 12 | Lernvorschlag-Freigabe | `Ymto9WVvowvaLvrW` | Webhook GET/POST `/lernvorschlaege` | 2 Postgres |
| — | RSS-Quellen verwalten | `PHGNkEr8EZA2j5aV` | Webhook GET/POST `/rss-quellen` | 4 Postgres, 1 HTTP (neu, 2026-07-26) |
| — | Watchlist verwalten | `spOdAPmBfBGiel6u` | Webhook GET/POST `/aktien-watchlist` | 2 Postgres |

**Nicht in der Liste, weil auf dem Server nicht aktiv/nicht vorhanden**: `97`, `98`, `99` (Dev-Hilfswerkzeuge, absichtlich `active:false`, manuell ausgeführt).

### Veraltete/doppelte Dateien im Git-Repo (Achtung bei künftigen Änderungen)

Drei lokale Dateien im Repo-Root entsprechen **keinem** Workflow auf dem Server — weder aktiv noch inaktiv, sie existieren serverseitig schlicht nicht (mutmaßlich Reste aus der Zeit vor der `– Agent V1`-Umbenennung, nie aus dem Repo entfernt):

- `04 – Cleanup News-Tabellen.json` (ohne „– Agent V1"-Suffix)
- `06 – Empfehlungswatchlist.json` (ohne Suffix)
- `07 – Status-Uebersicht.json` (ohne Suffix)

**Handlungsempfehlung**: nicht versehentlich als „aktuelle Version" bearbeiten. Diese Bestandsaufnahme behandelt ausschließlich die `– Agent V1`-Varianten (bzw. bei 00/01/02/02b/03a/08/09/10/11/12 die einzige vorhandene Version) als verbindlich, da nur diese live sind.

---

## 2. Persistenzschichten — wichtigster Einzelbefund dieser Bestandsaufnahme

Das System nutzt **zwei getrennte, nicht synchronisierte Persistenzschichten**. Das ist keine unbeabsichtigte Inkonsistenz, sondern eine dokumentierte, bewusste Entscheidung aus `MIGRATIONSPLAN_AGENTEN.md` („Leitprinzip 2: Deterministik bleibt deterministisch — 01, 02, 02b behalten ihre reine Berechnungslogik"), die aber für die in diesem Auftrag geforderte Point-in-Time-Historie (Phase 5/6/7 unten) direkt relevant ist.

### 2a. PostgreSQL, Schema `trading` (Migrationen 001–008, live verifiziert)

15 Tabellen, vollständiger Spaltenbestand per `information_schema.columns` geprüft (nicht aus den `.sql`-Dateien geraten — Migration `007_runtime_schema_reconciliation.sql` existiert exakt deshalb, weil frühere Live-Abweichungen von den `.sql`-Dateien gefunden wurden, die Live-DB ist die verbindliche Quelle):

`agent_runs`, `learning_rule_proposals`, `news_assessments`, `news_impact_tracking`, `news_items`, `pipeline_config`, `pipeline_runs`, `prompt_versions`, `recommendations`, `rss_sources`, `scoring_weights`, `stock_instruments`, `stock_price_history`, `watchlist`, `workflow_errors`.

Vollständige Spaltenlisten: siehe `sql/001_agenten_architektur.sql` bis `008_rss_sources.sql` (Live-Schema stimmt mit diesen Dateien überein, Stand heute geprüft).

**Constraints (live geprüft, relevant für Phase 2/10 unten):**
- `news_assessments`: **keine** UNIQUE-Constraint außer der eigenen `id`. Nichts auf DB-Ebene verhindert mehrere Bewertungszeilen pro `news_id`.
- `news_impact_tracking`: `UNIQUE(news_id, ticker)` — verhindert Duplikate korrekt (wie in `MIGRATIONSPLAN_AGENTEN.md` Phase 6+7 zugesichert).
- `news_items`: `UNIQUE(news_key)`.
- `pipeline_runs`: **nur** PRIMARY KEY(`id`) — keine Unique-Constraint auf `(run_id, workflow_name, stage_name)` o.ä. Kein DB-seitiger Schutz vor doppeltem Schreiben derselben Stufe.
- `stock_price_history`: `UNIQUE(symbol, trading_date)` — korrekt.
- `stock_instruments`: `UNIQUE(ticker)`.
- `scoring_weights`, `prompt_versions`: jeweils `UNIQUE(key, version)`-Paar — korrekt für Versionierung.

### 2b. n8n Data Tables (Projekt `CrnegVcMvlcRU0OP`) — weiterhin produktiv, NICHT nach Postgres migriert

Drei Tabellen aus dem alten Bestand sind **unverändert** in Betrieb, mit reinem Get-then-Update/Insert-Muster (aktueller Snapshot pro Ticker/Symbol, **keine Historie**, jeder Lauf überschreibt die Vorzeile):

| Data Table | Geschrieben von | Gelesen von |
|---|---|---|
| `stock_fundamentals` (`Le3FJQ6pctb6qtGi`) | 01 | 07, 10 |
| `stock_market_context` (`dzUOoGnfASjaaVhn`) | 02b | 02, 07, 10 |
| `stock_technical_signals` (`GDMAKrvQovPcBItA`) | 02 | 00, 06, 07, 10 |

Das war bereits im alten `ARCHITEKTUR_BESTAND.md` so dokumentiert und wurde beim Umbau bewusst **nicht** verändert. Für **Phase 5/6/7 des vorliegenden neuen Auftrags ist das der zentrale Befund**: die geforderte Trennung Rohwert/Anzeigeformat, `known_at`-Semantik und Point-in-Time-Historie existiert für Fundamentaldaten und technische Signale aktuell **gar nicht** — es gibt nur einen einzigen, ständig überschriebenen Zeilenstand je Ticker. Nur `stock_price_history` (OHLCV-Kurshistorie) wurde bereits nach Postgres migriert und ist echt historisch (append-only, ein Datensatz pro Tag/Symbol).

**Offene Lücke (dokumentiert statt geraten):** die exakten Spaltennamen/-typen der drei Data Tables wurden nicht per API abgefragt (n8n Data-Table-Schema-Introspection wurde in dieser Bestandsaufnahme nicht ausgeführt, nur die Lese/Schreib-Operationen der Nodes). Vor einer Migration dieser Tabellen muss ihr Spaltenschema zusätzlich per `GET /api/v1/data-tables/{id}` (oder gleichwertig) abgefragt werden.

---

## 3. Datenfluss zwischen Workflows (Abhängigkeitsübersicht)

```
00 – Orchestrator (17:50 Mo–Fr, eigener Cron)
  → liest: pipeline_config, pipeline_runs, news_items; stock_technical_signals (DataTable, nur Zaehlung)
  → schreibt: pipeline_runs
  → ruft per ExecuteWorkflow auf (waitForSubWorkflow): 02b → 02 → 06 → 10 → 05
  → externe Dienste: Matrix (Technische Warnung)

01 – Fundamentaldaten (06:00, EIGENSTÄNDIG, nicht vom Orchestrator erfasst)
  → liest: trading.watchlist (Postgres); stock_fundamentals (DataTable, get)
  → schreibt: stock_fundamentals (DataTable, update/insert)
  → externe Dienste: lokale FastAPI :8099/fundamentals/{ticker}

02 – Technische Signale (eigener Cron DEAKTIVIERT, läuft nur via 00 oder Webhook-Trigger)
  → liest: trading.watchlist, trading.stock_price_history (Postgres); stock_market_context (DataTable)
  → schreibt: trading.stock_price_history (Postgres); stock_technical_signals (DataTable)
  → externe Dienste: lokale FastAPI :8099/chart/{ticker}, Matrix Alert

02b – Marktumfeld (eigener Cron DEAKTIVIERT, läuft nur via 00 oder Webhook-Trigger)
  → liest/schreibt: trading.stock_price_history (Postgres); stock_market_context (DataTable, get/update/insert)
  → externe Dienste: lokale FastAPI :8099/chart/{symbol} (DAX/MDAX/Stoxx50/Nasdaq/S&P/EURUSD/Öl/Gold)

03 – News Ingestion (stündlich, EIGENSTÄNDIG)
  → liest: trading.rss_sources, trading.watchlist, trading.agent_runs, trading.news_assessments, trading.news_items
  → schreibt: trading.news_items, trading.news_assessments, trading.agent_runs
  → externe Dienste: 7 RSS-Feeds (aus rss_sources, seit heute DB-getrieben statt hartkodiert), OpenAI (KI: Nachricht bewerten), Matrix (RSS-Fehler-Alert, Wichtige-Nachricht-Alert)

03a – News-Recherche-Agent (alle 2h, EIGENSTÄNDIG)
  → liest: trading.news_items, trading.news_assessments, trading.agent_runs, trading.stock_instruments
  → schreibt: trading.news_items, trading.news_assessments, trading.agent_runs
  → externe Dienste: Volltext-Artikelabruf (httpRequest), OpenAI (KI: Recherche-Bewertung)

04 – Cleanup News-Tabellen (23:45 Mo–Fr / Sa 00:15, EIGENSTÄNDIG)
  → liest/schreibt: trading.news_items, trading.pipeline_runs; liest trading.news_impact_tracking (zum Schutz vor Löschung offener Beobachtungen)

05 – Tagesreport (Cron DEAKTIVIERT, läuft nur via 00 oder ExecuteWorkflowTrigger)
  → ruft 10 (Report- und Prüfagent) per ExecuteWorkflow auf
  → externe Dienste: E-Mail (SMTP), Matrix (Tagesreport, Fehler-Alert)
  → HINWEIS: node-lokale Query-Extraktion zeigt keine direkten Postgres-Lesezugriffe in 05 selbst — die fachlichen Daten kommen über 10 (bzw. dessen Data-Table-/Postgres-Zugriffe)

06 – Empfehlungswatchlist (Cron DEAKTIVIERT, läuft nur via 00 oder ExecuteWorkflowTrigger)
  → liest: trading.news_assessments, trading.news_items, trading.pipeline_config, trading.recommendations; stock_technical_signals (DataTable)
  → schreibt: trading.recommendations
  → externe Dienste: Matrix (Empfehlungs-Update)

07 – Status-Uebersicht (Webhook, on-demand)
  → liest (nur lesend, kein Schreiben): trading.agent_runs, learning_rule_proposals, news_assessments, news_impact_tracking, news_items, pipeline_config, pipeline_runs, recommendations, stock_price_history; plus stock_fundamentals/stock_market_context/stock_technical_signals (DataTable)

08 – News-Wirkungsanalyse (19:00 Mo–Fr, EIGENSTÄNDIG)
  → liest: trading.news_assessments, news_impact_tracking, news_items, pipeline_config, stock_instruments, stock_price_history
  → schreibt: trading.news_impact_tracking

09 – Lernagent Newswirkung (Samstag 08:00, EIGENSTÄNDIG)
  → liest: trading.agent_runs, learning_rule_proposals, news_impact_tracking
  → schreibt: trading.agent_runs, learning_rule_proposals
  → externe Dienste: OpenAI (KI: Lernbericht interpretieren), Matrix (Lernbericht)

10 – Report- und Prüfagent (nur ExecuteWorkflowTrigger, aufgerufen von 00 und von 05)
  → liest: trading.agent_runs, learning_rule_proposals, news_assessments, news_items, pipeline_runs, recommendations; stock_fundamentals/stock_technical_signals/stock_market_context (DataTable)
  → schreibt: trading.agent_runs
  → externe Dienste: OpenAI (KI: Report-Agent, KI: Pruef-Agent)

11 – Zentraler Error-Handler (globaler ErrorTrigger, von jedem Workflow-Fehler ausgelöst)
  → schreibt: trading.workflow_errors
  → externe Dienste: Matrix (Fehler-Alert)

12 – Lernvorschlag-Freigabe (Webhook, on-demand)
  → liest/schreibt: trading.learning_rule_proposals, trading.scoring_weights; liest trading.watchlist

RSS-Quellen verwalten (Webhook, on-demand, NEU 2026-07-26)
  → liest/schreibt: trading.rss_sources

Watchlist verwalten (Webhook, on-demand)
  → liest/schreibt: trading.watchlist, trading.stock_instruments
```

---

## 4. Orchestrator/Trigger-Status (Phase 10 der neuen Aufgabe — bereits teilweise geprüft)

Live-Check (Node-Attribut `disabled` direkt aus der JSON, nicht nur Workflow-`active`-Flag):

- **02, 02b, 05, 06** haben jeweils **beide** einen eigenen `scheduleTrigger`-Node UND einen `executeWorkflowTrigger`-Node. Der jeweilige `scheduleTrigger` ist bei allen vieren **`disabled: true`** — bestätigt, kein Doppellauf-Risiko *aktuell*. Das deckt sich mit der Notiz in `OFFENE_AUFGABEN.md` (Priorität 3, 2026-07-24: „Aktivierungsstatus live geprüft und stimmt weiterhin").
- **01, 03, 03a, 04, 08, 09** laufen **ausschließlich** über ihren eigenen, aktiven Cron — sie sind laut Orchestrator-Node-Liste (`00`, `Ausfuehren:`-Nodes) **nicht** Teil der Execute-Workflow-Kette. Das ist beabsichtigt (unterschiedliche Kadenzen: 01 morgens vor Handelsbeginn, 03/03a durchgehend stündlich/2-stündlich, 04/08/09 nach Handelsschluss bzw. wöchentlich) — kein Fehler, aber auch keine formale Dokumentation dieser Entscheidung bisher.
- **Kein DB-seitiger Schutz**: `pipeline_runs` hat keine Unique-Constraint (siehe 2a). Würde jemand versehentlich einen der vier deaktivierten Trigger wieder aktivieren, gäbe es aktuell **keinen automatischen Schutz** vor doppelten Läufen — nur die manuell gepflegte `disabled`-Flag. Das entspricht genau der in der neuen Aufgabe (Phase 10) beschriebenen Lücke (`run_id`/`business_date`/`idempotency_key` fehlen als harte Schranke).
- **Kein `business_date`-Feld** in `pipeline_runs` — `run_id` enthält laut `MIGRATIONSPLAN_AGENTEN.md` einen Datumsanteil im Format `daily-YYYY-MM-DD-...`, aber es gibt keine eigene, abfragbare `business_date`-Spalte.
- **Keine Markt-/Handelszeit-Felder** (`market`, `exchange_timezone`, `session_status` etc.) irgendwo im Schema — die in Phase 10 beschriebene US-Handelszeit-Problematik (17:50 Uhr deutscher Zeit = US-Markt ggf. noch offen) ist aktuell nicht abgebildet.

---

## 5. Konkrete Befunde zu „genau eine gültige Bewertung je Nachricht" (Phase 2 der neuen Aufgabe)

Direkt aus den Live-Node-Queries extrahiert, nicht angenommen:

- **08 – News-Wirkungsanalyse** dedupliziert bereits selbst gebaut, mit einer eigenen, hartkodierten Prioritätslogik direkt in der SQL-Query (`DISTINCT ON (ni.id) ... ORDER BY ni.id, CASE WHEN prompt_version='news-recherche-agent-v1' THEN 1 WHEN prompt_version='news-ingestion-v1' THEN 2 ELSE 3 END, created_at DESC`).
- **06 – Empfehlungswatchlist**, **07 – Status-Uebersicht** und **10 – Report- und Prüfagent** joinen `news_assessments` dagegen **ohne jede Deduplizierung** — ein `JOIN trading.news_assessments na ON na.news_id = ni.id` ohne `DISTINCT ON`/Prioritätsfilter. Hat eine News sowohl eine Erstbewertung (`news-ingestion-v1`) als auch eine spätere Recherchebewertung (`news-recherche-agent-v1`), erscheinen in diesen drei Workflows **beide Zeilen** — mit dem Risiko doppelter Zählung (z.B. zwei „hoch"-Wirkungszeilen für dieselbe News in 06, die dann fälschlich zwei separate Empfehlungs-Trigger auslösen könnten, falls beide Zeilen `wirkung_staerke='hoch'` tragen).
- Das Feld `usage_type` existiert bereits in `news_assessments`, wird aber aktuell nur beim **Schreiben** in 03 gesetzt (`INSERT ... usage_type ...`) — keiner der lesenden Workflows filtert danach. Es ist ungenutztes Potential, kein vollwertiger Ersatz für die geforderte zentrale View.
- Es gibt **keine** Spalte, die eine Bewertung explizit als „ungültig/verworfen/durch neuere ersetzt" markiert (kein `superseded_by`, kein `is_valid`, kein `status`). Phase 2 der neuen Aufgabe trifft hier auf eine reale, schema-seitig unadressierte Lücke.

---

## 6. Konkrete Befunde zur Empfehlungslogik (Phase 8/9 der neuen Aufgabe)

Aus dem tatsächlichen Code von `06 – Empfehlungswatchlist`, Node „Empfehlungen: Abgleich berechnen" (vollständig gelesen, nicht zusammengefasst geraten):

- Aktuelle Entscheidungsregel ist exakt „starke News (`wirkung_staerke='hoch'`, `wirkungsrichtung` positiv/negativ, ohne Widerspruch am selben Tag) + gleichgerichtetes technisches Signal (`handels_status` handelskandidat/beobachten)". Schließen nur bei Gegensignal.
- **Fehlend, schema-seitig bestätigt** (Tabelle `trading.recommendations` hat diese Spalten nicht): `stop_price`, `target_price`, `thesis_expires_at`, `expected_holding_days`, `data_quality_score`, `market_regime`, `decision_score`, `decision_blockers`, `invalidation_reason`. Kein hartes Veto-System, keine automatische Schließregel außer Gegensignal.
- **`DRY_RUN`/`REQUIRE_CONFIRMATION`** existieren bereits (aus `trading.pipeline_config`, per Node „Kontext ergaenzen" durchgereicht) — Bestätigungspflicht-Infrastruktur ist also schon vorhanden und muss bei Phase 8 erhalten bleiben, nicht neu gebaut werden.
- **Hebelprodukt-Berechnung** (`hebelHinweis()`-Funktion): rein rechnerische Näherung (`Kurs × (1 ± 1/3)` bzw. `1/4`), **bereits heute eindeutig als „kein konkretes Produkt" im Ausgabetext gekennzeichnet** (`hebelprodukt_hinweis`-Feld enthält wörtlich „Kein konkretes Produkt -... Emittent/Spread/Finanzierungskosten selbst pruefen"). Phase 9 der neuen Aufgabe ist hier größtenteils bereits erfüllt; eine zusätzliche strukturelle Kennzeichnung auf Feldebene (z.B. ein `is_theoretical: true`-Flag statt nur Text) wäre eine Verschärfung, kein Neubau.
- Alle Empfehlungen tragen bereits `[SIMULATION - keine reale Order]` im `entry_grund`-Text — das System ist ein reines Papier-Tracking, keine echte Order-Anbindung. Wichtig für die Einordnung von Phase 8/9: es besteht kein Risiko einer versehentlichen realen Order, nur das Risiko irreführender Darstellung.

---

## 7. Prompt-Versionierung und Agentenprotokoll (bereits vorhanden)

`trading.prompt_versions` und `trading.agent_runs` existieren bereits produktiv und werden befüllt (03, 03a, 09, 10 schreiben in `agent_runs`). Das deckt einen Teil der in Phase 12 der neuen Aufgabe verlangten Versionsfelder (`model_name`, `prompt_version`) bereits ab — die dort zusätzlich verlangten `rule_version`/`configuration_version` existieren dagegen nicht.

---

## 8. Cleanup-/Aufbewahrungsregeln (Phase 11 der neuen Aufgabe)

`04 – Cleanup News-Tabellen – Agent V1` arbeitet ausschließlich auf `trading.news_items`/`trading.pipeline_runs` (Postgres) — die alte, im ARCHITEKTUR_BESTAND als Risiko dokumentierte pauschale 3-Tage-Löschung der n8n-Data-Table-Versionen (`stock_news`/`stock_news_evaluated`) betrifft **nicht mehr** den produktiven Pfad, da News vollständig nach Postgres migriert wurden. Die genauen aktuellen Aufbewahrungsfristen/-regeln in `04`s Code-Nodes wurden in dieser Bestandsaufnahme **nicht Zeile für Zeile geprüft** — das ist eine offene Lücke, die vor einer Umsetzung von Phase 11 der neuen Aufgabe noch verifiziert werden muss (aktuell nur per automatisierter Tabellen-Extraktion erfasst, nicht per vollständigem Node-Code-Read).

---

## 9. Explizit offene Lücken dieser Bestandsaufnahme (ehrlich benannt, nicht verschwiegen)

Diese Punkte wurden **nicht** vollständig verifiziert und dürfen nicht als geprüft gelten:

1. Exaktes Spaltenschema der drei verbleibenden n8n Data Tables (`stock_fundamentals`, `stock_market_context`, `stock_technical_signals`) — nur Lese/Schreib-Operationen der Nodes geprüft, nicht die Spaltenliste selbst.
2. Vollständiger Node-für-Node-Code von `04` (Cleanup-Fristen im Detail), `07` (alle 13 Merge-Node-Verknüpfungen), `10` (beide Agenten-Prompts im Volltext) — diese wurden nur über die automatisierte Tabellen-/Trigger-Extraktion erfasst, nicht Zeile für Zeile gelesen.
3. Genaue aktuelle Werte in `trading.pipeline_config` (z.B. ob `DRY_RUN` aktuell `true` oder `false` steht) wurden nicht abgefragt.
4. Ob `stock_price_history` tatsächlich lückenlos von 02/02b befüllt wird (Datenqualität/Vollständigkeit der Historie) wurde nicht geprüft, nur dass die Schreib-Nodes existieren.
5. n8n-Node-Versionsverfügbarkeit für eventuell neue, in späteren Phasen benötigte Node-Typen (z.B. für Wahrscheinlichkeitsverteilungs-Validierung) wurde nicht recherchiert.

---

## 10. Empfehlung für das weitere Vorgehen

Diese Bestandsaufnahme deckt Phase 0 der neuen Aufgabe ab. Vor Beginn von Phase 1 (vollständige News-Datenbasis) sollte laut der in der Aufgabe selbst vorgegebenen Reihenfolge zunächst ein konkreter Umsetzungsplan für die betroffenen Dateien/Tabellen erstellt und bestätigt werden — insbesondere, weil Phase 5 (Fundamentaldaten-Historie) laut Abschnitt 2b dieser Bestandsaufnahme einen **architektonischen Bruch mit einer bewussten früheren Entscheidung** (`MIGRATIONSPLAN_AGENTEN.md`, Leitprinzip 2) bedeuten würde und das nicht nebenbei, sondern explizit entschieden werden sollte.
