# Migrationsplan: Aktienanalyse-System → kontrollierte Agentenarchitektur

Basis: `ARCHITEKTUR_BESTAND.md`. Dieser Plan setzt die dort dokumentierten Befunde in konkrete, sequenzierte Umbauschritte um. Reihenfolge folgt der im Auftrag vorgegebenen Vorgehensweise (Punkte 1-12), mit einer Vorziehung: das SQL-Schema (ursprünglich Phase 3) wird vor dem Orchestrator (Phase 2) erstellt, da der Orchestrator bereits `trading.pipeline_runs` benötigt.

## Leitprinzipien für jeden Schritt

1. **Additiv vor destruktiv**: bestehende Workflows werden als `– Agent V1`-Kopien angepasst, nicht in-place überschrieben. Die Originaldateien (`main`-Branch) bleiben unverändert als Rollback-Basis.
2. **Deterministik bleibt deterministisch**: 01, 02, 02b behalten ihre reine Berechnungslogik — kein KI-Einsatz dort, wie im Bestand vorgefunden und im Auftrag gefordert.
3. **Jede neue Data-Table-Abhängigkeit ist ein Zwischenschritt, kein Big-Bang**: die zentrale `stock_instruments`-Tabelle wird eingeführt, aber 01/02/02b/03/06 lesen ihre bisherige hartkodierte Watchlist so lange weiter, bis der jeweilige `– Agent V1`-Workflow einzeln getestet und übernommen ist (Phase 3, „schrittweise Migration“ wie im Auftrag verlangt).
4. **DRY_RUN als Standardparameter** in jedem neuen Workflow von Anfang an, nicht nachträglich ergänzt.

## Offener Klärungspunkt vor Phase 6

`stock_price_history` wird laut Bestandsanalyse von keinem der 8 Workflows beschrieben, aber von `07 – Status-Uebersicht` gelesen. Phase 6 (News-Wirkungsanalyse) braucht historische Tages-Schlusskurse für D+1/D+3/D+5/D+10/D+20 je Ticker und Benchmark. Zwei Optionen, beide werden vorbereitet:
- **Falls `stock_price_history` bereits produktiv von einem hier nicht vorliegenden Prozess befüllt wird**: 08 liest direkt daraus.
- **Falls nicht**: 08 muss selbst Kursdaten über den bereits vorhandenen lokalen FastAPI-Endpunkt (`172.16.1.14:8099/chart/{ticker}`, wie in 01/02/02b) nachladen und in `stock_price_history` (oder einer neuen `trading`-Tabelle) ablegen.

Der neue Workflow 08 ist so gebaut, dass er zuerst `stock_price_history` prüft und nur bei fehlenden Daten selbst nachlädt — funktioniert in beiden Fällen ohne Änderung.

## Offener Klärungspunkt: PostgreSQL-Zugang

Der Auftrag sieht ein eigenes `trading`-Schema in PostgreSQL vor (nicht n8n Data Tables) für Orchestrator-Protokoll, Agentenprotokoll, Instrumententabelle, News-Wirkungsanalyse und Lernregeln. Zum Zeitpunkt dieser Migration liegt kein bestätigter DB-Zugang vor. `sql/001_agenten_architektur.sql` ist vollständig geschrieben und idempotent (`CREATE ... IF NOT EXISTS`), aber **nur statisch geprüft** (kein Testlauf gegen eine echte Datenbank), bis Zugangsdaten vorliegen. Alle neuen n8n-Workflows referenzieren die Postgres-Verbindung über eine n8n-Credential mit Platzhaltername `Postgres – Trading (TODO Credential zuweisen)`, niemals mit eingebetteten Zugangsdaten.

---

## Phase 2: Orchestrator + Laufprotokoll

**Neue Datei**: `00 – Tagesabschluss-Orchestrator.json`

- Nutzt `n8n-nodes-base.executeWorkflow` (v1.2, bestätigt verfügbar — 02b/02/06/05 laufen bereits als eigenständige, per Execute-Workflow-fähige n8n-Workflows, keine Node-Versionsprüfung nötig, da der Node-Typ Kernbestandteil von n8n ist) mit `waitForSubWorkflow: true`.
- Erzeugt `run_id` im Format `daily-YYYY-MM-DD-HHMMSS-<6-hex>` als erster Schritt (Code-Node, nutzt `getBusinessDate()` für den Datumsteil — Europe/Berlin, nicht UTC).
- Schreibt vor/nach jeder Stufe eine Zeile in `trading.pipeline_runs` (Postgres-Node, `status` läuft pending → running → success/warning/failed).
- Ablauf exakt wie im Auftrag vorgegeben: Marktumfeld (02b) → Prüfung → Technische Signale (02) → Prüfung → Datenqualitätsprüfung (neuer, kleiner Code-Node: prüft Vollständigkeit/Alter der Ergebnisse) → Empfehlungswatchlist (06) → Report-Agent (Teil von 10) → Prüf-Agent (Teil von 10) → bei Freigabe versenden → Lauf abschließen.
- **Abbruchregeln** als IF-Kette vor dem Versand-Schritt, exakt die 5 im Auftrag genannten Bedingungen — bei Verstoß: `status='failed'` in `pipeline_runs`, technische Matrix-Warnung statt Normalversand.
- 02b/02/06 werden dabei NICHT verändert in ihrer Kernlogik — sie erhalten nur optional einen `run_id`-Input-Parameter (Execute-Workflow-Trigger-Feld), den sie in ihre `metadata_json`/Log-Felder durchreichen, falls vorhanden (Abwärtskompatibilität: eigenständiger Cron-Start bleibt weiterhin möglich, `run_id` ist dann leer/eigenständig generiert).
- Trigger: eigener `scheduleTrigger`, so gelegt, dass er die bestehenden Einzel-Trigger von 02b/02/06/05 ablösen kann (Umstellung von deren eigenen Cron-Triggern auf ausschließlich Execute-Workflow-Aufruf ist ein bewusster, separat zu bestätigender letzter Schritt — bis dahin laufen die alten Cron-Trigger UND der Orchestrator parallel, was zu doppelten Läufen führen würde; siehe TESTPLAN_AGENTEN.md „Idempotenz“ und Abschlussbericht „offene manuelle Schritte“).

---

## Phase 3: `stock_instruments` (vorgezogenes SQL bereits erstellt)

`sql/001_agenten_architektur.sql` enthält bereits `trading.stock_instruments` mit allen geforderten Feldern. Befüllung: einmaliger Seed-Insert mit den aus dem Bestand extrahierten 15 Tickern (siehe ARCHITEKTUR_BESTAND.md Prüfpunkt 5) — wird als `sql/002_seed_stock_instruments.sql` nachgereicht, sobald DB-Zugang bestätigt ist (Werte sind bereits bekannt, nur die Ausführung fehlt).

Migrationsreihenfolge je Workflow (schrittweise, wie im Auftrag verlangt — alte Logik bleibt bis zum erfolgreichen Test parallel lauffähig):
1. `– Agent V1`-Kopie liest weiterhin die hartkodierte Liste ODER `stock_instruments`, gesteuert über eine einzige Code-Zeile/Flag am Workflow-Anfang (`USE_CENTRAL_INSTRUMENTS`, Default `false` bis Test bestanden).
2. Erst nach bestandenem Parallel-Test (beide Quellen liefern identische Ticker-Menge) wird der Flag-Default auf `true` gesetzt und die hartkodierte Liste als Kommentar/Fallback stehen gelassen (nicht gelöscht — Rollback-Fähigkeit).
3. Reihenfolge der Umstellung: 02b (Markt-Referenzsymbole bleiben separat, nur Aktien-Ticker betroffen) → 01 → 02 → 03 → 06. 05/07 lesen Ticker nie selbst, sondern nur über die anderen Tabellen — keine eigene Umstellung nötig.

---

## Phase 4: News-Zustandsmodell

Betrifft `03 – News Ingestion stündlich – Agent V1.json` und `04 – Cleanup News-Tabellen – Agent V1.json`.

- Neues Feld `status` (`pending`/`processing`/`evaluated`/`retry`/`failed`/`discarded`) — wird zunächst als **zusätzliche** Spalte in den bestehenden n8n Data Tables `stock_news`/`stock_news_evaluated` ergänzt (nicht in Postgres, da diese beiden Tabellen bewusst n8n-Data-Table-basiert bleiben — der Auftrag verlangt Postgres nur für die neuen Tabellen, nicht für eine Zwangsmigration der bestehenden). Alternative, sauberere Variante (empfohlen, aber größerer Eingriff): vollständiger Umzug von `stock_news`/`stock_news_evaluated` nach `trading.news_items`/`trading.news_assessments` (bereits im SQL-Schema vorbereitet) — Entscheidung wird dem Nutzer zur Freigabe vorgelegt, da sie die Duplikatprüfung strukturell verändert (Umzug wird als bevorzugte Zielarchitektur gebaut, alte n8n-Data-Table-Version bleibt als Fallback dokumentiert).
- `News: Duplikat-Check` wird umgebaut: Duplikatabgleich bleibt (verhindert echte Doppel-Einträge), aber **Status-Filterung** kommt davor — eine News mit `status IN ('retry')` und `next_retry_at <= now()` wird bewusst NICHT als Duplikat verworfen, sondern erneut zur Bewertung geschickt.
- `retry_count`/`last_error`/`last_attempt_at`/`next_retry_at` werden bei jedem KI-/Parse-/DB-Fehler geschrieben (Backoff: `next_retry_at = now() + retry_count * 15 Minuten`, Obergrenze 5 Versuche → `status='failed'`, Datensatz bleibt erhalten).
- Batch-Größe der KI-Bewertung wird von „alle neuen News in einem Call“ auf 10-20 News/Call reduziert (`splitInBatches` vor dem KI-Node), mit Einzel-Retry-Fähigkeit pro fehlgeschlagenem Batch-Element.
- `04 – Cleanup`: siehe Phase 12 (eigener Abschnitt, da die Aufbewahrungsregeln sich grundlegend ändern).

---

## Phase 5: `03a – News-Recherche-Agent.json`

- AI-Node-Typ: `@n8n/n8n-nodes-langchain.openAi` (bereits bestätigt verfügbar und produktiv im Einsatz in 03/05, typeVersion 2.3) bzw. `@n8n/n8n-nodes-langchain.agent` falls Tool-Calling-Fähigkeit (Werkzeuge: Artikel laden, Instrumententabelle lesen, ähnliche News suchen) benötigt wird — **wird vor dem Bau anhand der tatsächlich im n8n-Node-Katalog dieser Instanz verfügbaren Node-Typen geprüft** (siehe Auftrag: keine erfundenen Node-Funktionen). Sub-Workflow-Aufruf über `executeWorkflow`, analog zum bereits produktiven Muster (05 ruft ebenfalls einen `@n8n/n8n-nodes-langchain.openAi`-Node auf, kein neues Muster).
- Eingabe: eine News aus `trading.news_items`/`stock_news` mit `status='pending'` oder `status='retry'` mit fälligem `next_retry_at`.
- Werkzeuge exakt wie im Auftrag benannt, keine darüber hinausgehenden. Kein Werkzeug zum Anlegen neuer Instrumente, Löschen, oder Eröffnen von Positionen — technisch durchgesetzt durch schlichtes Nicht-Vorhandensein solcher Tool-Definitionen (kein Agent kann ein Werkzeug nutzen, das nicht existiert).
- Strukturierte Ausgabe: exaktes Schema aus dem Auftrag, validiert per Code-Node (nicht blind vertraut — ungültige `wirkungsrichtung`/`wirkung_staerke`-Werte außerhalb der zulässigen Enums werden auf `unklar` korrigiert statt den Datensatz zu verwerfen).
- Schreibt `trading.news_assessments` (eine Zeile) + setzt `trading.news_items.status='evaluated'`.
- Jeder Aufruf wird in `trading.agent_runs` protokolliert (`agent_name='news-recherche-agent'`, `prompt_version` aus `trading.prompt_versions`).

---

## Phase 6+7: `08 – News-Wirkungsanalyse.json` (inkl. Störfaktoren)

- Läuft täglich nach Handelsschluss, verarbeitet `trading.news_assessments` mit noch offenen `trading.news_impact_tracking`-Beobachtungen.
- Erzeugt bei neuer bewerteter+relevanter News (`relevant=true`) für jeden Ticker in `betroffene_ticker_json` eine eigene Zeile in `trading.news_impact_tracking` (`UNIQUE(news_id, ticker)` verhindert Duplikate bei erneutem Lauf — Idempotenz wie gefordert).
- Baseline-Kurs-Logik exakt wie im Auftrag spezifiziert (vor Handelsbeginn/während/nach Handelsende → jeweils passender Schlusskurs), berechnet über `getBusinessDate()` (Europe/Berlin) für die Tagesgrenze.
- D+1/D+3/D+5/D+10/D+20 werden anhand tatsächlich vorhandener Kursdatensätze ermittelt (Handelstage, nicht Kalendertage) — siehe „Offener Klärungspunkt“ oben zu `stock_price_history`.
- Abnormale Rendite (Aktie minus Benchmark) wird als numerischer `NUMERIC`-Wert gespeichert, nicht als String — bereits so im SQL-Schema angelegt.
- **Störfaktor-Erkennung (Phase 7)** als eigener Code-Node zwischen Kursabruf und Abschluss: prüft im jeweiligen D+N-Fenster auf weitere hoch relevante News zum selben Ticker (`trading.news_assessments` erneut abfragen), starke Markt-/Sektorbewegungen (`trading.news_impact_tracking.benchmark_return_dN` bereits berechnet, Schwellenwert konfigurierbar) — bei Treffer `confounded=true` + `confounding_reason` (Klartext, welcher Störfaktor). Kategorien wie Quartalszahlen/Dividendenabschläge/Übernahmeberichte werden zunächst über Schlagwort-Matching auf `news_kategorie`/Titel erkannt (kein separates Fundamentaldaten-Kalender-Feed vorhanden — Einschränkung wird dokumentiert, keine erfundene Datenquelle vorausgesetzt).
- Status-Übergänge `pending → waiting_d1 → ... → completed` (oder `confounded`/`failed`) werden bei jedem Lauf für alle offenen Zeilen aktualisiert, je nachdem welche D+N-Fenster inzwischen Kursdaten haben.

---

## Phase 8+9: `09 – Lernagent Newswirkung.json` + `trading.learning_rule_proposals`

- Wöchentlicher Trigger (Samstag, wie im Auftrag empfohlen).
- Liest ausschließlich `trading.news_impact_tracking` mit `status='completed'` (nicht `confounded` als Lerndatenbasis, aber in Statistiken/Bericht sichtbar als „ausgeschlossen wegen Störfaktor“, exakt wie gefordert).
- Mindestfallzahlen-Logik exakt wie im Auftrag als deterministische Code-Funktion (kein KI-Ermessen bei der Einordnung „belastbar/nicht belastbar“ — nur die Interpretation/Formulierung der Befunde ist KI-Aufgabe, die Fallzahl-Schwellen selbst sind Code).
- Ausgabeschema exakt wie im Auftrag (`analysis_period`, `total_events`, `clean_events`, `confounded_events`, `overall_direction_accuracy`, `findings[]`, `proposals[]`).
- Schreibt **ausschließlich** `trading.learning_rule_proposals` mit `status='proposed'` — kein Schreibzugriff auf `trading.scoring_weights` oder `trading.prompt_versions`, technisch durchgesetzt durch fehlende Postgres-Node-Berechtigung/fehlende Schreib-Nodes für diese Tabellen in diesem Workflow (kein Agent-Ermessen, strukturelle Trennung).
- Kein Lösch-, Prompt-Überschreib- oder Order-Node im gesamten Workflow — verifizierbar durch Node-Liste (wird in TESTPLAN_AGENTEN.md als statischer Check aufgenommen).

---

## Phase 10: `10 – Report- und Prüfagent.json`

- Zwei AI-Nodes in Reihe: Report-Agent (interpretiert, rechnet nichts neu — bekommt bereits fertige Zahlen aus 01/02/02b/06/08/09 als strukturierten Input, exakt wie im Auftrag „berechnet aber keine technischen Indikatoren neu"), dann Prüf-Agent (bekommt NUR den fertigen Berichtstext + dieselben Rohdaten zur Gegenprüfung, kein Zugriff auf den Report-Agent-Prompt selbst — echte zweite, unabhängige Instanz).
- Ersetzt/ergänzt `05`s KI-Node `KI: Tagesreport erstellen` — `05 – Tagesreport – Agent V1.json` ruft `10` per `executeWorkflow` auf, statt selbst zu generieren; die Formatierungs-/Versandlogik (Matrix, E-Mail) bleibt in `05`.
- Prüf-Agent-Ausgabeschema exakt wie im Auftrag. Bei `approved=false`: `05`s bestehender `Matrix: Fehler-Alert`-Pfad (siehe Bestand, bereits vorhanden für Datenqualitätswarnungen) wird wiederverwendet und um die Ablehnungsgründe erweitert, statt einen neuen Alert-Mechanismus zu bauen.
- Beide Agentenläufe werden in `trading.agent_runs` protokolliert.

---

## Phase 11: `06 – Empfehlungswatchlist – Agent V1.json`

Konkrete Fixes je Bestandsbefund:
1. **Matrix erst nach Speicherung**: `Matrix: Zusammenfassung bauen` wird umverdrahtet, sodass sie NACH `DB: Empfehlung schließen`/`DB: Empfehlung öffnen` hängt (Merge-Node wartet auf beide Zweige), statt parallel/unabhängig zu laufen (behebt Prüfpunkt 4 aus dem Bestand).
2. Nach dem Schreiben wird das Schreibergebnis geprüft (n8n Data-Table-Node liefert die geschriebene Zeile zurück — IF-Node prüft auf vorhandene `id`), erst dann Matrix.
3. Direkt aus Punkt 1+2 folgend: keine Nachricht ohne bestätigten Schreiberfolg.
4. Hebel-/KO-Berechnung (`hebelHinweis()`) bleibt unverändert — bereits korrekt als Näherung gekennzeichnet (Bestand Prüfpunkt 10 „vorhanden, aber sauber“), keine Änderung nötig, nur re-verifiziert.
5. `entry_grund`/Report-Texte werden um einen festen Zusatz „SIMULATION — keine reale Order“ ergänzt, an allen Ausgabepunkten (Matrix + Data Table + späterer Report).
6. Neue optionale Matrix-Rückfrage vor `DB: Empfehlung öffnen` (analog zum bereits produktiven ALLRIS-Muster für Matrix-Poll-und-Antwort, hier neu für dieses Projekt aufgebaut) — DRY_RUN-Modus überspringt dies und protokolliert nur.
7. Getrennte Lernkreise: `trading.news_impact_tracking` (Newsprognose) bleibt strikt getrennt von einer neuen `trading.trade_simulation_outcomes`-artigen Auswertung (Entry/Exit/Performance aus `stock_empfehlungen`) — wird als eigene, kleine Zusatztabelle in `sql/002_...` nachgereicht, sobald DB-Zugang steht; bis dahin bleibt diese Auswertung weiterhin in der bestehenden `stock_empfehlungen`-Tabelle, nur mit klarer Namens-/Feldtrennung von den News-Feldern (keine Vermischung der beiden Bewertungsarten in einem gemeinsamen Score).

---

## Phase 12: `04 – Cleanup News-Tabellen – Agent V1.json`

Neue Aufbewahrungsregeln exakt wie im Auftrag:
- Irrelevante Rohnews (`status='discarded'` oder `relevanz='niedrig'` ohne Weiterverwendung): 14-30 Tage (konfigurierbar, Default 21).
- Bewertete News (`status='evaluated'`): mindestens 365 Tage.
- `trading.news_impact_tracking`: dauerhaft, nie automatisch gelöscht.
- Lernstatistiken (`trading.learning_rule_proposals`, zukünftige Lernberichte): dauerhaft.
- Agenten-Rohantworten (`trading.agent_runs.output_reference`, falls Volltext dort abgelegt wird statt nur Referenz): 90 Tage.
- Fehlgeschlagene News (`status='failed'`): mindestens 30 Tage.
- **Archivieren statt Löschen**: statt `deleteRows` wird (wo die Zieltabelle in Postgres liegt) ein `archived=true`-Flag bevorzugt bzw. ein Umzug in eine separate Archiv-Tabelle; für die weiterhin in n8n Data Tables verbleibenden Alt-Tabellen (`stock_news`/`stock_news_evaluated`, falls der Umzug aus Phase 4 nicht sofort vollzogen wird) bleibt `deleteRows` technisch die einzige Option (n8n Data Tables kennen kein natives Archiv-Flag-Pattern besser als eine Extra-Spalte) — dann zumindest mit den oben genannten längeren Fristen statt der bisherigen pauschalen 3 Tage.
- Datensätze ohne Datum: werden NICHT mehr automatisch gelöscht, sondern mit `discarded_reason='fehlendes_datum_datenqualitaet'` markiert und einer manuellen Prüfliste zugeführt (neuer, kleiner Zweig im Workflow).

---

## Phase 13: `07 – Status-Uebersicht – Agent V1.json`

- Zusätzliche Sektion im HTML: Orchestrator-Läufe (`trading.pipeline_runs`, letzter Lauf je `workflow_name`/`stage_name`, Status, Dauer, Retry-Anzahl, Input/Output-Counts), Agentenläufe (`trading.agent_runs`, letzter Lauf je `agent_name`, Modell, Prompt-Version), News-Zustand (offene `retry`/`failed`-Zählung aus `trading.news_items`), Wirkungsanalyse-Fortschritt (Zählung je `status` in `trading.news_impact_tracking`, Trefferquote `direction_correct`-Anteil unter `completed`, Anzahl `confounded`), letzter Lernagentenlauf + Anzahl offener `learning_rule_proposals` mit `status='proposed'`.
- **Webhook-Schutz**: `httpHeaderAuth` (n8n-natives Auth-Feature am Webhook-Node, seit n8n-Webhook-Node-Version 2 verfügbar — bestätigt dieselbe Node-Version wie der bestehende Webhook) mit einer neuen n8n-Credential (Platzhaltername `Status-Webhook Token (TODO Credential zuweisen)`, kein Wert im Workflow-JSON). Alternative Basic-Auth wird dokumentiert, Header-Token favorisiert, da geringster Eingriff in bestehende Aufrufer.
- Bestehende Kennzahlen (Datenquellen-Tabelle, Handelskandidaten, offene Positionen) bleiben unverändert erhalten — reine additive Erweiterung, kein Umbau der bestehenden HTML-Ausgabe.
- UTC/Berlin-Inkonsistenz aus dem Bestand (Prüfpunkt 8) wird im selben Zug behoben: `heute`-Vergleichswert wird auf `getBusinessDate()` (Europe/Berlin) umgestellt, damit „aktuell/veraltet“-Badges konsistent mit dem angezeigten Berlin-Zeitstempel sind.

---

## Reihenfolge der tatsächlichen Umsetzung (Baureihenfolge in dieser Session)

1. ✅ ARCHITEKTUR_BESTAND.md, MIGRATIONSPLAN_AGENTEN.md (dieses Dokument)
2. ✅ `sql/001_agenten_architektur.sql`
3. `00 – Tagesabschluss-Orchestrator.json`
4. `03 – News Ingestion stündlich – Agent V1.json` + `04 – Cleanup News-Tabellen – Agent V1.json` (Zustandsmodell zusammen mit Cleanup, da beide dieselben Statuswerte teilen)
5. `03a – News-Recherche-Agent.json`
6. `08 – News-Wirkungsanalyse.json`
7. `09 – Lernagent Newswirkung.json`
8. `10 – Report- und Prüfagent.json`
9. `05 – Tagesreport – Agent V1.json` (ruft jetzt 10 statt eigener KI-Node)
10. `06 – Empfehlungswatchlist – Agent V1.json`
11. `07 – Status-Uebersicht – Agent V1.json`
12. `TESTPLAN_AGENTEN.md`, `README_AGENTEN_ARCHITEKTUR.md`, Abschlussbericht
