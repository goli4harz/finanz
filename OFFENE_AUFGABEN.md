# Offene Aufgaben

Stand: 2026-07-27

## Fachliche Überarbeitung (Paket 1-8, erledigt 2026-07-26/27)

Umsetzung des 12-Phasen-Auftrags "Fachliche Überarbeitung der Aktienanalyse- und Lernpipeline" (Bestandsaufnahme: `docs/FACHLICHE_BESTANDSAUFNAHME.md`), package-weise additiv umgesetzt und live verifiziert:

- ✅ **Paket 1** (Phase 1+3+4, `sql/009-011`): `news_items` um vollständige Datenbasis (article_text/content_hash/...) + Recherche-Tracking (research_status/...) erweitert; `news_assessments` um getrennte Konfidenz-/Wahrscheinlichkeitsfelder.
- ✅ **Paket 2+3** (Phase 2, `sql/012-013`): View `trading.v_news_latest_assessment` für "genau eine gültige Bewertung je Nachricht" — behebt einen live bestätigten Bug (06/07/10 jointen `news_assessments` bisher ohne Deduplizierung, Risiko doppelter Empfehlungs-Trigger).
- ✅ **Paket 4** (Phase 10a, `sql/014`): `pipeline_runs.business_date` wird jetzt persistiert (Feld existierte zur Laufzeit schon, nur nicht gespeichert). Bewusst kein harter UNIQUE-Constraint (würde manuelle Test-Reruns als Duplikat-Fehler zählen).
- ✅ **Paket 5** (Phase 10b, `sql/015`): `trading.market_reference` (XETRA/NASDAQ/NYSE-Sessionzeiten), `stock_instruments.exchange` befüllt. Schema-only, aktuell kein Consumer.
- ✅ **Paket 6** (Phase 12, `sql/016`): `agent_runs.rule_version`/`configuration_version` (JSONB-Snapshot). Schema-only.
- ✅ **Paket 7** (Phase 8, `sql/017`): `recommendations` um Risikofelder erweitert (stop_price/target_price/decision_score/is_theoretical/...). Schema-only, **keine** Verdrahtung in `06`s Entscheidungslogik (bewusst separat gehalten wegen dessen dokumentierter Historie fragiler Merge-/DRY_RUN-Stellen).
- ✅ **Paket 8** (Phase 5/6/7, erster Schritt, `sql/018`): additive Point-in-Time-Historie für `stock_fundamentals`/`stock_market_context`/`stock_technical_signals` (3 neue Tabellen, parallel zu den bestehenden Data Tables beschrieben, kein Consumer geändert). **Dabei gefunden und mitgefixt**: ein vorbestehender, ~2 Wochen alter Bug in den originalen `02`/`02b`-„Kurshistorie"-Nodes (fehlendes `mode: runOnceForEachItem` ließ nur 1 Ticker/Tag statt aller erfassen) — betraf auch `stock_price_history` selbst, jetzt live auf volle Ticker-Abdeckung bestätigt.

**Offen, explizit zurückgestellt**: ob/wann `06`/`07`/`10` ihre Leseseite (teilweise) auf die neue Historie aus Paket 8 umstellen (z.B. Mehrtages-Trend statt nur Tages-Snapshot) — eigene, noch nicht getroffene Folgeentscheidung.

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
