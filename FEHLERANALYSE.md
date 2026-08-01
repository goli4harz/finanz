# Fehleranalyse

Stand: 2026-08-01. Vollständige Fehlerbereinigung und fachliche Härtung des Aktienanalyse-, Lern- und Paper-Trading-Systems.

Diese Analyse entstand aus sieben parallelen, rein lesenden Code-Audits (nicht nur Dokumentationsprüfung) gegen den tatsächlichen Stand der n8n-Workflow-Exporte, SQL-Migrationen und Dokumentation in `C:\Users\olietz\Documents\finanz`. Jeder Fund wurde gegen den Code verifiziert, nicht aus `OFFENE_AUFGABEN.md` übernommen — das Projekt hat eine dokumentierte Geschichte von "Doku sagt fertig, Code war es nicht ganz" (siehe `docs/PHASENWEISER_ABGLEICH_2026-07-31.md`).

**Legende Status:** `offen` / `in Bearbeitung` / `behoben` / `verifiziert`

---

## Teil A — SQL- und Eingabesicherheit

### A1 — SQL-Injection über `pgArr()` in der Watchlist-Verwaltung
- **Schweregrad:** kritisch
- **Datei/Node:** `Watchlist verwalten.json`, Node „POST: Formular normalisieren + SQL bauen"
- **Ursache:** `pgArr()` escaped nur `"`, nicht `'`. Das PostgreSQL-Array-Literal wird selbst mit `'…'` umschlossen, ohne durch `pgStr` (das korrekt escaped) zu laufen.
- **Auswirkung:** Ein `keywords`-Feld mit Apostroph bricht die SQL-Zeichenkette auf (`a'); DROP TABLE trading.watchlist;--`). Da der Postgres-Node Mehrfach-Statements als einen String ausführt, wird injizierter SQL-Text als eigenes Statement ausgeführt. Jeder LAN-Client (kein Auth) kann beliebiges SQL einschleusen.
- **Korrektur:** `pgArr` durch korrektes Escaping ersetzen oder auf feste Stored Function `trading.watchlist_upsert(...)` mit typisierten Array-Parametern umstellen.
- **Test:** Ticker/Keywords mit `'`, `\`, `--`, `;` in Add/Edit senden, erwartet: Fehler oder korrektes Escaping, keine zweite Anweisung ausgeführt.
- **Status:** behoben, live verifiziert 2026-08-01 (Injection-Payload wird als Text gespeichert, kein SQL-Bruch; Testticker ZZTEST1 angelegt+geloescht)

### A2 — Kein echter Query-Parameter, ausschließlich String-Interpolation
- **Schweregrad:** hoch
- **Datei:** `Watchlist verwalten.json`, `RSS-Quellen verwalten.json`, `12 – Lernvorschlag-Freigabe.json`
- **Ursache:** Alle drei Workflows bauen SQL ausschließlich per String-Interpolation (`pgStr`/`pgArr`/`pgJson`), kein Einsatz echter Postgres-Node-Query-Parameter (`$1,$2,…`).
- **Auswirkung:** Architektur bleibt fragil — ein einziger vergessener Escape-Schritt (siehe A1) führt sofort zu Injection.
- **Korrektur:** Feste Stored Functions/Procedures pro Aktion mit typisierten Parametern.
- **Test:** Codereview — kein `pgStr`/`pgArr` mehr im finalen SQL-Text für nutzergenerierte Werte.
- **Status:** offen

### A3 — Keine serverseitige Feldvalidierung in der Watchlist
- **Schweregrad:** hoch
- **Datei/Node:** `Watchlist verwalten.json`
- **Ursache:** Ticker nur `.trim().toUpperCase()`, kein Format-Regex, keine DB-`CHECK`-Constraint. `edit` prüft `name` nicht auf Nicht-Leerheit. Keine Prüfung für Sektor/Keywords/Ausschlussbegriffe.
- **Auswirkung:** Leeres `name` überschreibt stillschweigend vorhandenen Namen; beliebige Zeichen in Ticker/Sektor möglich.
- **Korrektur:** Server-seitige Regex-/Längenprüfung je Feld, `CHECK`-Constraints in der DB ergänzen.
- **Test:** Leeres `name` bei `edit` senden → erwartet Fehlerstatus, kein stiller Overwrite.
- **Status:** behoben, live verifiziert 2026-08-01 (Ticker-Regex, Name-Pflicht bei add+edit, Laengenlimits)

### A4 — Ungültige Eingaben erzeugen keinen Fehlerstatus (`SELECT 1`-Fallback)
- **Schweregrad:** mittel
- **Datei/Node:** `Watchlist verwalten.json`, Postgres-Node mit `onError:"continueRegularOutput"`
- **Ursache:** Bei fehlendem `ticker`/`name` wird `sql='SELECT 1;'` gesetzt, Workflow zeigt normale Erfolgsseite. Echte SQL-Fehler werden ebenfalls verschluckt.
- **Auswirkung:** Nutzer bekommt keine Rückmeldung über fehlgeschlagene Aktionen, auch nicht über einen ausgenutzten Injection-Versuch.
- **Korrektur:** Bei Validierungsfehlern eigenes Fehler-Item mit sichtbarer Meldung; Postgres-Fehler im HTML als Banner anzeigen.
- **Test:** Ungültige Eingabe senden → erwartet sichtbare Fehlermeldung statt Erfolgsseite.
- **Status:** behoben, live verifiziert 2026-08-01 (sichtbares Fehlerbanner statt stiller SELECT-1-Erfolgsseite)

### A5 — Lernvorschlag-Freigabe: Client-Felder statt Server-Neuladen
- **Schweregrad:** kritisch
- **Datei/Node:** `12 – Lernvorschlag-Freigabe.json`, Node „POST: Formular normalisieren + SQL bauen"
- **Ursache:** `proposal_type`/`target_type`/`target_value`/`proposed_value`/`time_horizon` werden direkt aus dem POST-Body übernommen. Einziger Server-Check: `EXISTS(... WHERE id=... AND status='proposed')` — unabhängig vom übermittelten Zielwert.
- **Auswirkung:** Eine beliebige `id` mit Status `proposed` kann als Autorisierungs-Token missbraucht werden, um einen völlig anderen `proposal_type`/`target_type`/`proposed_value` einzuschleusen als ursprünglich vorgeschlagen (z. B. `MAX_RISK_PER_TRADE_PCT` auf einen beliebigen Wert setzen).
- **Korrektur:** Proposal-Zeile per `id` serverseitig neu laden (`SELECT ... WHERE id=$1 AND status='proposed' FOR UPDATE`), Browser-Felder komplett verwerfen.
- **Test:** POST mit `id` eines echten `weight_adjustment`-Vorschlags, aber `proposal_type=strategy_deactivation` im Body → erwartet: Server ignoriert Body-Wert, verwendet nur den DB-Wert.
- **Status:** behoben, live gepusht 2026-08-01 (neue Nodes "POST: Baue Load-Query" + "DB: Proposal laden (fuer Freigabe)" laden proposal_type/target_type/target_value/proposed_value/time_horizon frisch aus der DB; lokal per Simulation verifiziert, End-to-End-Wiring live bestaetigt (id=999999-Test, HTTP 200, kein Fehler); Test mit echter proposed-Zeile steht noch aus, da aktuell 0 Vorschlaege in der DB)

### A6 — Aktivierung ohne Zeilenzahl-Prüfung
- **Schweregrad:** kritisch
- **Datei/Node:** `12 – Lernvorschlag-Freigabe.json`, alle 5 Aktivierungszweige
- **Ursache:** Das `UPDATE ... SET status='activated'` läuft unbedingt nach dem eigentlichen Ziel-Update, unabhängig davon ob dieses 0 oder 1 Zeilen betraf.
- **Auswirkung:** Trifft das Ziel-Update keine Zeile (Tippfehler, veralteter Snapshot, A5 ausgenutzt), wird der Vorschlag trotzdem als `activated` markiert, obwohl inhaltlich nichts passiert ist.
- **Korrektur:** Rowcount des Ziel-Updates prüfen (`WITH upd AS (UPDATE ... RETURNING 1) UPDATE proposals SET status='activated' WHERE EXISTS(SELECT 1 FROM upd)`), sonst expliziten Fehlerstatus setzen.
- **Test:** Proposal mit nicht existierendem `target_value` freigeben → erwartet: Status bleibt nicht `activated`, sondern Fehler.
- **Status:** behoben, live gepusht 2026-08-01 (RETURNING/CTE-Rowcount-Check je Zielupdate, neuer Status activation_failed via sql/038 - Migration erstellt+in Workflow 97 eingetragen+gepusht, **manuelle Ausfuehrung durch Nutzer noch ausstehend**)

### A7 — Keine Allowlist für Zielobjekte in der Freigabe
- **Schweregrad:** hoch
- **Datei/Node:** `12 – Lernvorschlag-Freigabe.json`
- **Ursache:** `config_key`/`strategy`/`parameter_key`/`combined_regime` sind Freitext-Spalten ohne `CHECK`-Constraint und werden nicht gegen eine feste Liste erlaubter Schlüssel geprüft.
- **Korrektur:** Feste Allowlist-Tabelle oder `CHECK`-Constraint je Zielobjekttyp.
- **Test:** Freigabe mit unbekanntem `config_key` → erwartet Ablehnung.
- **Status:** teilweise behoben 2026-08-01 (Allowlist fuer threshold_adjustment-Config-Schluessel ergaenzt und live verifiziert; strategy/parameter_key/combined_regime weiterhin ungeprueft - volle Regeltabelle ist A8)

### A8 — Keine Wertebereichs-/Schrittweiten-/NULL-Prüfung in der Freigabe
- **Schweregrad:** hoch
- **Datei/Node:** `12 – Lernvorschlag-Freigabe.json`, `pgNum()`
- **Ursache:** `pgNum()` prüft nur numerische Parsebarkeit, sonst literal `'NULL'`. Keine Min/Max, keine maximale Schrittweite gegenüber `current_value`.
- **Auswirkung:** `MAX_RISK_PER_TRADE_PCT` könnte theoretisch von 1% auf 99% gesetzt werden. Siehe auch F10/A9 (NULL-Schreibfähigkeit bei `pipeline_config`).
- **Korrektur:** Zentrale Regeltabelle (Datentyp/Min/Max/Default/max. Schrittweite/NULL erlaubt) serverseitig durchsetzen (siehe auch Abschnitt F26).
- **Test:** Siehe F-Serie (Lernagenten), Testfall „Wert außerhalb des zulässigen Bereichs".
- **Status:** offen

### A9 — `pipeline_config.value_numeric` kann durch Freigabe auf NULL gesetzt werden
- **Schweregrad:** kritisch
- **Datei/Node:** `12 – Lernvorschlag-Freigabe.json`, Zweig `threshold_adjustment`
- **Ursache:** `trading.pipeline_config.value_numeric` hat weder `NOT NULL` noch `CHECK` (anders als die drei übrigen Zieltabellen, die durch `NOT NULL` geschützt sind).
- **Auswirkung:** Ein leerer/ungültiger `proposed_value` wird klaglos als NULL in einen produktiven Risikoparameter geschrieben.
- **Korrektur:** Vor UPDATE `IF proposedValue IS NULL THEN ABORT`; zusätzlich `NOT NULL`/`CHECK` auf `value_numeric` je Config-Key.
- **Test:** `threshold_adjustment` mit leerem `proposed_value` freigeben → erwartet Ablehnung, kein NULL-Write.
- **Status:** behoben, live gepusht 2026-08-01 (JS-seitiger NULL/NaN-Guard vor jedem Ziel-Update, lokal verifiziert - fuehrt bei ungueltigem Wert zu activation_failed statt NULL-Write; DB-seitige CHECK/NOT-NULL-Absicherung auf pipeline_config.value_numeric selbst noch nicht ergaenzt, siehe A8)

### A10 — Kein Versionskonflikt-Schutz in der Freigabe
- **Schweregrad:** mittel
- **Datei/Node:** `12 – Lernvorschlag-Freigabe.json`
- **Ursache:** `trading.learning_rule_proposals.version` existiert, wird aber nie gelesen/inkrementiert.
- **Korrektur:** Optimistic-Locking über `version`-Feld beim Freigeben.
- **Status:** offen

### A11 — RSS-Quellen: kein SSRF-Schutz vor dem Feed-Abruf
- **Schweregrad:** kritisch
- **Datei/Node:** `RSS-Quellen verwalten.json`, Node „HTTP: RSS-Feed abrufen"
- **Ursache:** Nutzer-URL wird direkt abgerufen, keine Protokoll-Allowlist, kein Hostname-/IP-Check gegen Loopback/Link-Local/private Bereiche/Metadaten-Endpunkte, keine erneute Prüfung nach Redirects.
- **Auswirkung:** Jeder LAN-Client kann eine RSS-Quelle auf eine interne Ziel-URL umbiegen und über „Testen" den n8n-Host als SSRF-Sonde gegen andere LAN-Hosts missbrauchen. „Alle Quellen testen" verstärkt das (ein manipulierter Eintrag läuft automatisch mit).
- **Korrektur:** Prüf-Node vor dem HTTP-Request: nur `http`/`https`, IP-Auflösung + Blockliste (Loopback/Link-Local/RFC1918/ULA/`169.254.169.254`), Redirect-Re-Validierung pro Hop oder Redirects deaktivieren, Antwortgrößen-Limit, Content-Type-Prüfung.
- **Test:** URL `http://127.0.0.1:5678/` bzw. `http://169.254.169.254/` als Quelle testen → erwartet Ablehnung vor dem eigentlichen Abruf.
- **Status:** behoben, live verifiziert 2026-08-01 (Protokoll-/Hostname-/IP-Allowlist vor jedem Abruf; Testquelle mit http://127.0.0.1:5678 angelegt+blockiert+geloescht, echter Feed tagesschau.de weiterhin funktionsfaehig verifiziert. WICHTIGER HINWEIS: der globale URL-Konstruktor ist im n8n-Code-Node-Sandbox nicht verfuegbar - musste durch manuelles Regex-Parsing ersetzt werden, sonst wurde jede URL faelschlich blockiert. Redirects bleiben aktiv (Deaktivierung brach echte Feeds mit legitimem 301, z.B. tagesschau.de) - kein Re-Check der Zieladresse nach Redirect, dokumentierte Restluecke gegen redirect-basiertes SSRF.)

---

## Teil B — Orchestrator und Workflowsteuerung

### B1 — Permissives Gate-Muster in allen 4 Execute-Workflow-Gates
- **Schweregrad:** kritisch
- **Datei/Node:** `00 – Tagesabschluss-Orchestrator.json`, Nodes „IF: Marktumfeld ok?", „IF: Technische Signale ok?", „IF: Empfehlungswatchlist ok?", „IF: Versand ok?"
- **Ursache:** Prüfung ist `status !== 'failed'` statt Allowlist. Fehlendes `status`-Feld (`undefined !== 'failed'`) gilt als OK.
- **Auswirkung:** Stürzt ein Sub-Workflow intern ab, bevor er sein eigenes Ergebnis-Objekt baut, liefert `onError: continueErrorOutput` ein Item ohne `status` — das Gate lässt es trotzdem passieren, der Lauf arbeitet mit unvollständigen/veralteten Daten weiter.
- **Korrektur:** Explizite Erfolgs-Allowlist (`status === 'success' || status === 'partial_failure'`), alles andere inkl. fehlend = Fehler.
- **Test:** Sub-Workflow-Aufruf mit Item ohne `status`-Feld simulieren → erwartet: Gate blockiert.
- **Status:** behoben, live gepusht 2026-08-01 (explizite Allowlist [success,partial_failure,skipped] statt notEquals-failed, lokal fuer alle Statuswerte durchsimuliert; echter Orchestrator-Lauf zur Verhaltensbestaetigung steht noch aus, da ein manueller Testlauf von 00 mehrere reale Sub-Workflows anstossen wuerde)

### B2 — Keine Differenzierung success/partial_failure/skipped in den Gates
- **Schweregrad:** hoch
- **Datei/Node:** `00`, gleiche 4 Gates wie B1
- **Ursache:** Sub-Workflows bauen sauberes Status-Enum (`success`/`partial_failure`/`skipped`/`failed`), das Gate prüft aber nur `!== 'failed'` — `partial_failure` und `skipped` werden wie voller Erfolg behandelt.
- **Korrektur:** Gate-Bedingung differenzieren, `partial_failure` mindestens in Report/Warnung aufnehmen statt stillschweigend zu ignorieren.
- **Status:** offen

### B3 — Zentraler Error-Handler mit Platzhalter-Credential
- **Schweregrad:** mittel (Live-Stand zu prüfen)
- **Datei/Node:** `11 – Zentraler Error-Handler.json`, Node „Fehler protokollieren (ausfuehren)"
- **Ursache:** `"id": "PLACEHOLDER_POSTGRES_CRED"` im Export.
- **Auswirkung:** Falls das der Live-Stand ist, schlägt DB-Logging von Node-Abstürzen fehl (Matrix-Alert-Zweig läuft vermutlich trotzdem).
- **Korrektur:** Live-Credential-Zuweisung in n8n verifizieren.
- **Status:** offen (Live-Check nötig)

### B4 — Unsicherer DRY_RUN-Fallback auf `false`
- **Schweregrad:** kritisch
- **Datei/Node:** `00`, Node „Kontext zusammenfuehren"; `06 – Empfehlungswatchlist – Agent V1.json`, Node „Kontext ergaenzen"
- **Ursache:** Beide Stellen fallen bei fehlender Config-Zeile/NULL/DB-Fehler auf `dryRun=false` zurück statt `true`.
- **Auswirkung:** Eine reine Konfigurationsstörung (DB kurzzeitig nicht erreichbar) aktiviert lautlos den echten Schreibpfad, ohne Warnung. Asymmetrie im selben Codeblock: `REQUIRE_CONFIRMATION` fällt korrekt auf `true` zurück, `DRY_RUN` im selben Block auf `false`.
- **Korrektur:** Fallback auf `true` drehen; Fallback-Nutzung loggen/alarmieren.
- **Test:** Config-Query liefert 0 Zeilen simulieren → erwartet `DRY_RUN=true`.
- **Status:** behoben, live gepusht 2026-08-01 in beiden Stellen (00 und 06), Fallback auf true gedreht + Quelle protokolliert (00), lokal fuer alle Config-Zustaende durchsimuliert

### B5 — Fehlendes `alwaysOutputData` auf `00`s Config-Node
- **Schweregrad:** hoch
- **Datei/Node:** `00`, Node „Config: DRY_RUN laden"
- **Ursache:** Kein `alwaysOutputData: true`. Liefert die Query 0 Zeilen, wird laut bereits im Projekt dokumentiertem n8n-Zero-Rows-Verhalten der gesamte nachgelagerte Pfad übersprungen.
- **Auswirkung:** Kompletter Tagesabschluss würde lautlos gar nicht laufen, ohne Fehlereintrag.
- **Korrektur:** `alwaysOutputData: true` ergänzen (analog zu `06`, wo bereits gesetzt).
- **Status:** behoben, live gepusht 2026-08-01 (alwaysOutputData:true ergaenzt)

### B6 — `14` hat keine eigene DRY_RUN-Prüfung
- **Schweregrad:** mittel
- **Datei/Node:** `14 – Portfolio-Risiko und Paper-Trading.json`
- **Ursache:** Verlässt sich vollständig darauf, dass `06` im DRY_RUN-Fall nichts schreibt — kein zweiter unabhängiger Schutz.
- **Auswirkung:** B4-Fehler kaskadiert bis in echte Paper-Trade-Anlage und Portfoliorisiko-Checks.
- **Korrektur:** Nach Fix von B4 optional eigene DRY_RUN-Prüfung als Verteidigung in der Tiefe ergänzen.
- **Status:** offen

### B7 — Keine Protokollierung der DRY_RUN-Konfigurationsquelle
- **Schweregrad:** niedrig
- **Datei/Node:** `00`, `06`
- **Status:** offen

### B8 — `technical_signals_history` überschreibt still statt zu revisionieren
- **Schweregrad:** mittel
- **Datei/Node:** `02 – Technische Signale täglich.json`, Node „Signal-Historie: SQL bauen"; `sql/018`
- **Ursache:** `UNIQUE(ticker, snapshot_date)` + `ON CONFLICT DO UPDATE` — dasselbe Muster, das bei `fundamentals_history` bewusst durch echte Point-in-Time-Revisionierung ersetzt wurde (Paket 14, `sql/022`), wurde hier nicht mitgezogen.
- **Auswirkung:** Ein zweiter `02`-Lauf am selben Tag überschreibt die technischen Signale des ersten Laufs rückstandslos — Verlust der Revisionshistorie.
- **Korrektur:** Gleiches Revisionsmuster wie `fundamentals_history`/`strategy_signals` übernehmen oder Abweichung bewusst dokumentieren.
- **Status:** offen

### B9 — Ungeschützte Audit-/Log-Tabellen in `14`
- **Schweregrad:** niedrig-mittel
- **Datei/Node:** `trading.paper_trade_events`, `trading.portfolio_risk_checks`, `trading.stress_scenarios` (`sql/035`/`036`)
- **Ursache:** Kein UNIQUE-Constraint, `run_id` in `14` nicht deterministisch pro Tag (`Date.now()`).
- **Auswirkung:** Wiederholter Lauf von `14` Job A am selben Tag dupliziert Event-/Check-Zeilen (widerspricht „lückenlose Ereignis-Historie").
- **Korrektur:** Deterministischen Schlüssel + UNIQUE-Constraint ergänzen.
- **Status:** offen

---

## Teil C — Technische Signale und Marktumfeld

### C1 — `02` ruft weiterhin `period=3mo` ab, Doku behauptet `period=1y`
- **Schweregrad:** hoch
- **Datei/Node:** `02 – Technische Signale täglich.json`, Node „Kurs abrufen (lokaler FastAPI)"
- **Ursache:** Die in `docs/DATENQUALITAET_UND_SESSIONS.md`/`OFFENE_AUFGABEN.md` dokumentierte Umstellung auf `period=1y` wurde nur in `02b` umgesetzt, nicht in `02` selbst.
- **Auswirkung:** `period=3mo` liefert nur ~63 Handelstage (laut eigenem früherem Live-Test dokumentiert). Das 252-Tage-Kriterium für Breakout-Signale ist damit praktisch nie erfüllbar (außer über das `fiftyTwoWeekHigh`-Metafeld), die 60-Tage-Volatilitätsberechnung läuft ohne Sicherheitsmarge.
- **Korrektur:** `period=3mo` → `period=1y` in `02` ändern, analog zu `02b`. Live-Test mit AAPL/SAP.DE wiederholen.
- **Test:** Nach Umstellung: Response-Länge für AAPL/SAP.DE prüfen, ≥252 gültige Handelstage nach Bereinigung.
- **Status:** offen — **höchste Priorität innerhalb Teil C, da funktionaler Bug mit Doku-Widerspruch**

### C2 — 52-Wochen-Hoch/-Tief-Fallback unflagged bei unzureichender Historie
- **Schweregrad:** mittel
- **Datei/Node:** `02`, Node „Technische Analyse (RSI/MACD/BB)"
- **Ursache:** Fallback-Berechnung aus vorhandenen `highs`/`lows` ignoriert `breakoutHistoryAusreichend`.
- **Auswirkung:** Dashboard/Report können ein "52-Wochen-Hoch" zeigen, das in Wahrheit nur ein 3-Monats-Hoch ist, ohne Kennzeichnung.
- **Korrektur:** `hoch52w`/`tief52w` bei `!breakoutHistoryAusreichend` auf `null` setzen oder als `unreliable` markieren.
- **Status:** offen

### C3 — Volumen-Kennzahlen nutzen unabhängig gefiltertes Rohvolumen
- **Schweregrad:** niedrig
- **Datei/Node:** `02`, Node „Technische Analyse (RSI/MACD/BB)"
- **Korrektur:** `vols` aus `gueltigeKerzen` ableiten statt eigenem Filter.
- **Status:** offen

### C4 — `02b` baut Kerzen nicht timestamp-indiziert, keine Zeilenvalidierung
- **Schweregrad:** kritisch
- **Datei/Node:** `02b – Marktumfeld täglich.json`, Node „Marktanalyse berechnen"
- **Ursache:** Jeder OHLCV-Array wird unabhängig an seiner eigenen letzten Array-Position gelesen (expliziter Code-Kommentar: „bewusst nur die letzten Rohwerte, keine vollständige Kerzenausrichtung wie in 02"). Keine High≥Low/Close-Innerhalb-Range/Volumen-Prüfung.
- **Auswirkung:** Bei `null`-Close am aktuellen Tag (unvollständige Session) bezieht sich `close` auf den Vortag, `open`/`high`/`low`/`volume` aber auf den aktuellen (ausgefallenen) Tag — eine gespeicherte Zeile in `stock_price_history` kann aus zwei verschiedenen Handelstagen gemischt sein.
- **Korrektur:** Dieselbe timestamp-indizierte Kerzenbildung wie `02` übernehmen (idealerweise als gemeinsame Funktion für beide Workflows).
- **Status:** behoben, live gepusht 2026-08-01 (identische timestamp-indizierte Kerzenbildung + Zeilenvalidierung wie in 02 uebernommen). Lokal mit synthetischem Datensatz verifiziert: korrupte letzte Kerze (close=null, aber O/H/L/V vorhanden mit abweichendem Preisniveau) wird jetzt komplett verworfen statt vermischt zu werden; sauberer 260-Tage-Datensatz unveraendert korrekt (EMA200/Regime plausibel). Echter Lauf gegen die reale FastAPI-Quelle noch nicht beobachtet.

### C5 — `02b`s `data_quality_status` ist hartkodierter Literal `'limited'`
- **Schweregrad:** mittel
- **Datei/Node:** `02b`, Node „Kurshistorie: SQL bauen"
- **Korrektur:** Mindestens vorhandene Prüfung (`closes.length < 26`) in echten Status übersetzen.
- **Status:** behoben, live gepusht 2026-08-01 (echter Status aus der Kerzenvalidierung, lokal verifiziert: valid bei sauberen Daten, limited bei verworfenen Zeilen)

### C6 — `02`s Datenqualitätsstatus wird beim Schreiben nach `stock_price_history` auf 2 Werte kollabiert
- **Schweregrad:** hoch
- **Datei/Node:** `02`, Node „Kurshistorie: SQL bauen"
- **Ursache:** `qualityStatus = (status==='invalid') ? 'invalid' : 'valid'` — `stale`, `limited`, `session_incomplete` werden strukturell zu `valid`.
- **Auswirkung:** Konsumenten von `stock_price_history` (u. a. `14`) können nicht erkennen, dass eine Kerze aus einer laufenden Sitzung stammt oder veraltet ist — Information geht verloren, bevor sie einen Gate-Punkt erreichen kann.
- **Korrektur:** Alle fünf Klassen unverändert durchreichen.
- **Status:** offen

### C7 — Sitzungsstatus-View wird nur von `02` genutzt, nicht von `02b`/`08`/`13`/`14`
- **Schweregrad:** hoch
- **Datei/Node:** alle fünf Workflows
- **Korrektur:** Abfrage mindestens in `14` (Ausführungs-/Exit-Logik) ergänzen.
- **Status:** offen

### C8 — `02b` implementiert eigene, unvollständige Sitzungsstatus-Logik und respektiert sie selbst nicht
- **Schweregrad:** hoch
- **Datei/Node:** `02b`, Node „Marktregime berechnen", Funktion `sessionStatusFor`
- **Ursache:** Eigene 3-Zustands-Logik statt `trading.v_market_session_status` (5 Zustände, DB-Abgleich). Zeitzonenbehandlung selbst korrekt (USA nutzt `America/New_York`, keine pauschale Uhrzeit), aber `session_status` beeinflusst `combined_regime` an keiner Stelle.
- **Auswirkung:** Läuft der Orchestrator während laufender US-Sitzung, wird `combined_regime` für Region USA aus unvollständiger Tageskerze berechnet — ohne Kennzeichnung. **Dieser Teil ist bereits aktiv wirksam** (nicht nur Vorwärtsrisiko), da ^IXIC/^GSPC bei jedem Lauf betroffen sein können.
- **Korrektur:** `sessionStatusFor` entfernen, `v_market_session_status` abfragen (Referenzsymbole brauchen dafür `stock_instruments`/`market_reference`-Einträge); bei `open_intraday` `combined_regime` auf „vorläufig" setzen.
- **Status:** offen

### C9 — `14` prüft Sitzungsstatus an keiner Stelle
- **Schweregrad:** kritisch
- **Datei/Node:** `14 – Portfolio-Risiko und Paper-Trading.json`, Nodes „DB: Marktregime laden (Portfolio)", „Job B: Ausfuehrung/Exit simulieren"
- **Ursache:** Weder `v_market_session_status` noch `market_regime.session_status` werden gelesen; einzige verfügbare Qualitätsinfo (`stock_price_history.data_quality_status`) ist durch C6 bereits kollabiert.
- **Auswirkung:** Für künftige nicht-europäische Ticker (im Projekt bereits als kommender Fall benannt) würde `14` eine Einstiegszonen-Berührung oder einen Stop/Ziel-Treffer auf Basis einer unvollständigen Tageskerze feststellen und den Trade füllen/schließen.
- **Korrektur:** `session_status` in Marktregime-Query aufnehmen und/oder `v_market_session_status` je Ticker laden; bei `open_intraday` Fill/Exit überspringen.
- **Status:** behoben, live gepusht 2026-08-01 (Job B prueft bar.data_quality_status==='session_incomplete' vor Fill/Exit-Entscheidungen). Greift aktuell noch nicht scharf, da 02 diesen Wert erst nach Fix C6 (noch offen, siehe dort) tatsaechlich liefert - Code-Pfad ist aber vollstaendig vorbereitet und wird automatisch wirksam, sobald C6 behoben ist. — **aktuell durch XETRA-only-Watchlist + späten Lauf entschärft, aber strukturell offen**

---

## Teil D — News-Pipeline und Wirkungsanalyse

### D1 — Hartkodierte Tickerliste im KI-System-Prompt (`03`)
- **Schweregrad:** hoch
- **Datei/Node:** `03 – News Ingestion stündlich – Agent V1.json`, Node „KI: Nachricht bewerten"
- **Ursache:** Statischer Prompt-Text mit 15 Tickern statt Laufzeit-Aufbau aus DB (wie in `03a` bereits korrekt gemacht).
- **Auswirkung:** Ein neu angelegter/deaktivierter Ticker wird von der KI-Zuordnung erst nach manuellem Workflow-Edit erkannt.
- **Korrektur:** String analog zu `03a` per Code-Node aus der Watchlist-DB-Abfrage zur Laufzeit aufbauen.
- **Status:** offen

### D2 — Von der KI zurückgegebene Ticker werden nicht gegen die Watchlist validiert
- **Schweregrad:** hoch
- **Datei/Node:** `03`, `03a`
- **Korrektur:** Nach Parsing gegen geladene Ticker-Menge filtern, verworfene Ticker loggen.
- **Status:** offen

### D3 — Beschreibung wird vor dem KI-Aufruf hart auf leer gesetzt
- **Schweregrad:** kritisch
- **Datei/Node:** `03`, Node „Baue Batch-Payload"
- **Ursache:** `beschreibung: ''` unbedingt gesetzt, obwohl der Vorfilter-Node den RSS-Kurztext bereits sauber extrahiert.
- **Auswirkung:** Die KI bewertet jede News ausschließlich anhand der (oft mehrdeutigen) Überschrift.
- **Korrektur:** `beschreibung: j.beschreibung` — abhängig von D5 (Persistierung).
- **Status:** behoben, live gepusht 2026-08-01 (beschreibung kommt jetzt aus der DB statt hartcodiert '', mit Fallback fuer Altzeilen vor D5). Lokal verifiziert.

### D4 — `type` wird konstant auf `stock_news` gesetzt
- **Schweregrad:** hoch
- **Datei/Node:** `03`, Node „Baue Batch-Payload" (gleicher Node wie D3)
- **Auswirkung:** Markt-/Kandidaten-News erhalten systematisch die falsche Bewertungsanweisung, da der System-Prompt je nach `type` unterschiedlich instruiert.
- **Status:** behoben, live gepusht 2026-08-01 (type kommt jetzt aus der DB statt konstant 'stock_news'). Lokal verifiziert.

### D5 — Persistierung verwirft Beschreibung/Typ/Vorfiltergrund/Ticker vollständig
- **Schweregrad:** kritisch
- **Datei/Node:** `03`, Node „Neue News speichern (SQL bauen)"
- **Ursache:** INSERT-Spaltenliste beschränkt sich auf `news_key, title, url, source, published_at, status` — `description`/`type`/`match_reason`/`ticker` (Migration `sql/009` legt die Spalten bereits an) werden nicht geschrieben.
- **Auswirkung:** Ein Artikel mit zwei Ticker-Treffern erzeugt zwei Items mit identischem `news_key` — das zweite INSERT läuft wegen `ON CONFLICT DO NOTHING` leer, der zweite Tickerbezug ist unwiederbringlich verloren, bevor die KI beteiligt ist. Ursache für D3/D4.
- **Korrektur:** `description`/`preclassified_type`/`match_reason`/`preclassified_tickers` in INSERT-Spaltenliste aufnehmen.
- **Status:** behoben, live gepusht 2026-08-01 (description/preclassified_type/match_reason/preclassified_tickers in INSERT-Spaltenliste aufgenommen - Spalten existierten bereits seit sql/009, waren aber nie befuellt; zusaetzlich ON CONFLICT DO UPDATE statt DO NOTHING, das preclassified_tickers bei mehreren Tickertreffern derselben News dedupliziert zusammenfuehrt statt den zweiten Tickerbezug zu verwerfen. 'DB: Faellige News laden' liest die neuen Spalten mit passenden Aliasen zurueck. Lokal SQL-Generierung verifiziert (korrektes Escaping bei Apostroph im Text).

### D6 — KI-Score/Konfidenz werden in `03` nie gespeichert
- **Schweregrad:** hoch
- **Datei/Node:** `03`, Node „Ergebnis persistieren (SQL bauen)"
- **Ursache:** Weder `score` noch `konfidenz` in der INSERT-Spaltenliste. Das komplette Konfidenz-Trennungs-Schema aus `sql/011` bleibt für Erstbewertungen ungenutzt.
- **Auswirkung:** `konfidenz` bleibt für praktisch alle Erstbewertungen dauerhaft NULL.
- **Korrektur:** Felder in INSERT-Spaltenliste aufnehmen, KI-Prompt um separierte Konfidenzfelder erweitern.
- **Status:** offen

### D7 — Fallback verschluckt Unterschied zwischen „fehlend" und „echt 0"
- **Schweregrad:** mittel
- **Datei/Node:** `03a`, Node „Antwort validieren (Schema)"
- **Ursache:** `Number(parsed.konfidenz) || 0`.
- **Korrektur:** `Number.isFinite(...) ? ... : null`.
- **Status:** offen

### D8 — Recherche-Tracking-Felder unbenutzt, kein Retry-Limit in `03a`
- **Schweregrad:** mittel
- **Datei/Node:** `03a`, Node „Recherche-Ergebnis persistieren (SQL bauen)"
- **Ursache:** `research_status`/`research_attempts`/`next_research_at` (`sql/010`) werden nicht beschrieben.
- **Auswirkung:** Ein Kandidat mit dauerhaft nicht parsebarer KI-Antwort wird alle zwei Stunden erneut (erfolglos) prozessiert, ohne Backoff/Cap.
- **Korrektur:** Fehlerzweig auf `research_status`/`research_attempts`/`next_research_at` umstellen.
- **Status:** offen

### D9 — Keine URL-Kanonisierung, `content_hash` ungenutzt
- **Schweregrad:** hoch
- **Datei/Node:** `03`, Node „News: news_key erzeugen" / „News: Duplikat-Check"
- **Auswirkung:** Derselbe Artikel mit zwei Tracking-URLs kann sowohl Exact-Match als auch Jaccard-Schwelle unterlaufen → doppelte Bewertung, doppelter Alert.
- **Korrektur:** URL vor Key-Bau normalisieren, `content_hash` als zusätzlichen Dedup-Schlüssel nutzen.
- **Status:** offen

### D10 — Agenturmeldungen/aktualisierte Fassungen nicht erkannt
- **Schweregrad:** mittel
- **Datei/Node:** `03`
- **Korrektur:** `content_hash`-Vergleich als dritte Dedup-Stufe, `last_seen_at` bei erkanntem Duplikat aktualisieren.
- **Status:** offen

### D11 — Aktie/Benchmark werden über Array-Position statt echtes Datum verglichen
- **Schweregrad:** hoch
- **Datei/Node:** `08 – News-Wirkungsanalyse.json`, Node „D+1..D+20 berechnen + Stoerfaktoren"
- **Ursache:** `targetIdx = baselineIdx + h` ohne Prüfung, dass Aktie und Benchmark am selben `datum` liegen.
- **Auswirkung:** Fehlt für Aktie oder Benchmark eine einzelne Kurszeile im Fenster, verschiebt sich der Index dauerhaft gegen den Benchmark — `abnormal_return_d5` wird gegen den falschen Kalendertag berechnet.
- **Korrektur:** Nach `datum` statt Index abgleichen, bei fehlendem Match `null` statt falscher Zuordnung.
- **Status:** offen

### D12 — Pauschale deutsche Handelszeiten für alle Börsen in `08`
- **Schweregrad:** hoch (aktuell latent)
- **Datei/Node:** `08`, Node „Baseline-Fall je (News,Ticker) bestimmen"
- **Auswirkung:** Aktuell folgenlos (alle 15 Watchlist-Ticker XETRA). Sobald ein US-Ticker aufgenommen wird: falsche Baseline-Tag-Zuordnung für abends veröffentlichte News.
- **Korrektur:** `v_market_session_status`/`market_reference` je Ticker/Exchange abfragen statt fixer Konstanten.
- **Status:** offen

### D13 — Grobes „News bereits bearbeitet"-Flag statt Pro-Ticker-Tracking
- **Schweregrad:** kritisch
- **Datei/Node:** `08`, Node „DB: Neue News-Ticker-Paare laden"
- **Ursache:** `NOT EXISTS (news_impact_tracking WHERE news_id=ni.id)` filtert pro `news_id`, nicht pro `(news_id, ticker)`.
- **Auswirkung:** Bei einer News mit zwei Tickern, von denen einer übersprungen wird (z. B. neuer Ticker ohne Kurshistorie), entsteht nur eine Tracking-Zeile — im nächsten Lauf gilt die News als komplett bearbeitet, das fehlende Ticker-Paar wird nie nachgezogen.
- **Korrektur:** Guard auf Ticker-Ebene umstellen.
- **Status:** offen

---

## Teil E — Portfoliorisiko und Paper-Trading

### E1 — Keine deterministische Sortierung neuer Empfehlungen
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Query „DB: Heutige neue Empfehlungen laden"
- **Ursache:** Kein `ORDER BY` — Verarbeitungsreihenfolge ist undefinierte physische Postgres-Zeilenreihenfolge.
- **Korrektur:** `ORDER BY` nach Freigabestatus/Qualität/Chance-Risiko/Konfidenz/Ticker.
- **Status:** behoben, live gepusht 2026-08-01 (deterministische Sortierung vor der Schleife). Lokal verifiziert: 3 Kandidaten mit MAX_OPEN_POSITIONS=10/9 bereits offen -> nur der beste (hoechster opportunity_score) wird genehmigt, die anderen 2 korrekt geblockt.

### E2 — Portfoliostand wird nicht zwischen mehreren neuen Positionen im selben Lauf fortgeschrieben
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Code „Job A: Portfoliopruefung + Trade-Anlage"
- **Ursache:** `offenePaperTrades`-Array wird nach jeder Genehmigung nicht um den neuen Trade ergänzt — jeder Kandidat wird gegen denselben (veralteten) Ausgangszustand geprüft.
- **Auswirkung (konkret nachvollzogen):** `MAX_OPEN_POSITIONS=10`, aktuell 9 offen, drei neue Kandidaten am selben Tag → jeder prüft `9+1>10=false` einzeln → alle drei genehmigt, Endstand 12 statt max. 10. Identisch für `TOTAL_RISK`, `SECTOR`, `DIRECTIONAL`, `CORRELATION`.
- **Korrektur:** Nach jeder Genehmigung `offenePaperTrades.push(neuerTrade)` vor der nächsten Iteration (abhängig von E4-Fix für korrekten Sektor).
- **Test:** 3 Empfehlungen simulieren, die einzeln unter, gemeinsam aber über einem Limit liegen → erwartet: ab dem Limit-überschreitenden Kandidaten wird blockiert.
- **Status:** behoben, live gepusht 2026-08-01 (genehmigter Kandidat wird sofort in den lokalen Portfoliozustand uebernommen). Lokal verifiziert am selben Testfall wie E1 - vorher haetten alle 3 Kandidaten das Limit gemeinsam ueberschritten.

### E3 — Vorher/Nachher-Portfoliozustand nur unvollständig gespeichert
- **Schweregrad:** mittel
- **Datei/Node:** `14`, `trading.portfolio_risk_checks`
- **Korrektur:** Nach E2-Fix zusätzlich laufende Sequenznummer + Zustands-Snapshot je Prüfung.
- **Status:** behoben, live gepusht 2026-08-01 (sequence_index + portfolio_state_snapshot_json, sql/039)

### E4 — `sektor` wird auf `paper_trades` nie persistiert — Sektorlimit faktisch wirkungslos
- **Schweregrad:** kritisch
- **Datei/Node:** `sql/035_paper_trading_ledger.sql` (keine `sektor`-Spalte auf `paper_trades`), `14` Code „SQL bauen (Dispatcher A)" (INSERT-Spaltenliste ohne `sektor`)
- **Ursache:** `06` schreibt `sektor` korrekt als Snapshot auf `recommendations.sektor`, `14` liest es korrekt in `empf.sektor` — verwirft es aber beim INSERT nach `paper_trades`.
- **Auswirkung:** `offeneSumme(..., t => t.sektor === empf.sektor)` vergleicht `undefined === 'Technologie'` → immer `false`. Da `MAX_SINGLE_POSITION_PCT` (8%) < `MAX_SECTOR_EXPOSURE_PCT` (15%), kann `SECTOR_LIMIT` **praktisch nie auslösen**.
- **Korrektur:** `sektor`-Spalte per Migration ergänzen, in Dispatcher-A-INSERT aufnehmen.
- **Status:** behoben, live gepusht 2026-08-01 (sektor-Spalte ergaenzt, sql/039, in INSERT-Spaltenliste aufgenommen). Lokal Dispatcher-SQL verifiziert.

### E5 — Equity-Kurve startet bei 0 statt `MODEL_PORTFOLIO_VALUE`
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Code „Job A"
- **Ursache:** `let equity = 0, peak = 0;` — Startkapital wird nie addiert.
- **Auswirkung:** Bei einer anfänglichen Verlustserie (plausibel, System ~2 Wochen alt) bleibt `equity` negativ, `peak` bleibt 0, `drawdown_pct` wird bei **jedem** Lauf als 0 berechnet — der Drawdown-Blocker kann in dieser Phase nicht auslösen, egal wie hoch der reale Verlust ist.
- **Korrektur:** `let equity = MODEL_PORTFOLIO_VALUE, peak = MODEL_PORTFOLIO_VALUE;`
- **Test:** Sofortiger erster Verlust simulieren → erwartet: `drawdown_pct > 0`, nicht 0.
- **Status:** behoben, live gepusht 2026-08-01 (equity/peak starten bei MODEL_PORTFOLIO_VALUE). Lokal verifiziert: 3 aufeinanderfolgende Verluste (-8000/-5000/-3000 auf 100000 Startkapital) ergeben jetzt korrekt 16% Drawdown und loesen DRAWDOWN_LIMIT aus - vorher waere 0% berechnet worden.

### E6 — Drawdown-Nenner ist Konstante statt `peak_t`
- **Schweregrad:** mittel
- **Datei/Node:** `14`, Code „Job A"
- **Korrektur:** Formel wörtlich auf `(peak_t-equity_t)/peak_t*100` umstellen oder Abweichung dokumentieren.
- **Status:** offen

### E7 — Einstiegskosten werden nie von `net_pnl` abgezogen
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Code „Job B: Ausfuehrung/Exit simulieren"
- **Ursache:** `entryFee`/`entrySlippage` werden beim Fill berechnet und in `paper_trade_costs` gespeichert, aber `netPnl = grossPnl - exitFee - exitSlippage` berücksichtigt nur die Ausstiegskosten.
- **Auswirkung:** Jeder Trade weist `net_pnl` um `entryFee+entrySlippage` zu hoch aus — pflanzt sich fort in `return_pct`, `realized_r_multiple`, Profit Factor, Trefferquote, Erwartungswert, Drawdown (E5) und Lernagenten-Gates (F8/E-Serie).
- **Korrektur:** `netPnl = grossPnl - entryFee - entrySlippage - exitFee - exitSlippage`, Entry-Kosten beim Fill auf dem Trade-Objekt mitführen statt nur in `paper_trade_costs` zu versenken.
- **Test:** Trade mit bekannten Fill-/Exit-Preisen und Kosten durchrechnen → `net_pnl` muss alle 4 Kostenkomponenten enthalten.
- **Status:** behoben, live gepusht 2026-08-01 (entry_fee_amount/entry_slippage_amount auf paper_trades, sql/039, beim Fill gespeichert und beim Close zusaetzlich zu den Austrittskosten von net_pnl abgezogen). Lokal verifiziert: net_pnl 196.70 bei grossPnl 200 (Differenz 3.30 = Entry 1.5 + Exit 1.8 Kosten) statt vorher 198.20 (nur Exit-Kosten).

### E8 — `data_error` ist eine dauerhafte Sackgasse, kein Retry-Zustand
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Code „Job B", Query „DB: Ausstehende/offene Paper-Trades laden"
- **Ursache:** Ladequery selektiert nur `status IN ('open','proposed')` — ein auf `data_error` gesetzter Trade matcht danach nie wieder. Kein `retry_count`/`next_retry_at`/Eskalationsmechanismus, `data_error` wird von keinem anderen Workflow gelesen.
- **Auswirkung:** Fehlt an einem Tag die Tageskerze für einen offenen Trade, wird er unwiderruflich eingefroren — nur manuelle SQL-Intervention hilft.
- **Korrektur:** `retry_count`/`first_error_at`/`last_attempt_at`/`next_retry_at`-Felder ergänzen, Ladequery um `OR (status='data_error' AND retry_count<MAX)` erweitern, nach Überschreiten echte Eskalation (Matrix-Alert/`workflow_errors`).
- **Status:** behoben, live gepusht 2026-08-01 (data_error_count/first_at/last_at, sql/039, neuer Endzustand data_error_final nach MAX_DATA_ERROR_RETRIES mit Eskalation nach trading.workflow_errors). Lokal verifiziert: Zaehler 2->3 bei MAX=3 loest korrekt Eskalation aus.

### E9 — Fill-Tag prüft nicht auf Stop-/Ziel-Berührung derselben Kerze
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Code „Job B", Zeilen 53–90
- **Ursache:** Der `proposed`-Zweig endet nach dem Fill mit `continue;`, geht nicht in den Exit-Engine-Block (`open`-Zweig) über.
- **Auswirkung:** Ein heute erstmals gefüllter Trade wird in diesem Lauf nicht auf Stop/Ziel derselben Kerze geprüft — erst am nächsten Tag, mit der Kerze von morgen und potenziell völlig anderem Exit-Preis. Unterläuft die AMBIGUOUS_BAR_POLICY strukturell für den Fill-Tag selbst.
- **Korrektur:** Nach erfolgreichem Fill im selben Durchlauf sofort Stop/Ziel gegen dieselbe Tageskerze prüfen.
- **Status:** behoben, live gepusht 2026-08-01 (kein `continue` mehr nach einem Fill - derselbe Trade faellt lokal als offen durch in die Exit-Pruefung derselben Kerze, Mehrdeutigkeit `same_bar_fill_and_exit` dokumentiert). Lokal verifiziert: Fill bei 101 + Stop-Beruehrung bei 98 auf derselben Kerze wird jetzt im selben Lauf als geschlossen erkannt statt erst am naechsten Tag.

### E10 — `AMBIGUOUS_BAR_POLICY` ist hartkodierte JS-Konstante, nicht konfigurierbar
- **Schweregrad:** mittel
- **Datei/Node:** `14`, Code „Job B"
- **Korrektur:** Als `pipeline_config`-Eintrag führen, falls die Doku-Behauptung „konfigurierbar" stimmen soll.
- **Status:** offen

### E11 — Mehrdeutige Trades werden in Kennzahlen mit eindeutigen vermischt
- **Schweregrad:** mittel
- **Datei/Node:** `10 – Report- und Prüfagent.json`, Node „DB: Strategieauswertung (Report)"
- **Ursache:** `win_rate_pct`/`profit_factor`/`expectancy_r` laufen über alle `closed`-Trades, `ambiguous_pct` ist nur zusätzliche Info-Kennzahl.
- **Korrektur:** Zusätzliche Kennzahlen mit `WHERE ambiguous_execution=FALSE` parallel ausweisen.
- **Status:** offen

### E12 — Keine DB-Transaktion für Paper-Trade-Schreibvorgänge, keine Constraints gegen Teilfehler
- **Schweregrad:** kritisch
- **Datei/Node:** `14`, Nodes „SQL ausfuehren (A/B/C)" (je `onError:"continueRegularOutput"`, kein `BEGIN`/`COMMIT`)
- **Ursache:** Trade-Zustandsänderung, Event, Kosten werden als mehrere unabhängige n8n-Postgres-Aufrufe ausgeführt, nicht atomar. `paper_trade_costs`/`paper_trade_events` haben keinen UNIQUE-Constraint.
- **Auswirkung:** Schlägt z. B. die Kosten-INSERT nach erfolgreichem Close-UPDATE fehl, gilt der Trade als geschlossen, die fehlende Kostenzeile wird nie nachgeholt (Trade wird von der Ladequery nicht mehr erfasst).
- **Korrektur:** Mindestens `UNIQUE(trade_id, cost_type)` + `ON CONFLICT DO NOTHING` auf Kosten; mittelfristig eine Postgres-Funktion (`trading.fn_close_trade(...)`), die Statuswechsel+Event+Kosten in einer Transaktion kapselt.
- **Status:** behoben, live gepusht 2026-08-01 (fill_cluster/close_cluster buendeln UPDATE+Kosten+Event in je einem BEGIN/COMMIT statt 3-4 unabhaengigen Dispatches; UNIQUE(trade_id,cost_type) + ON CONFLICT DO NOTHING gegen Doppel-Kosten bei Retries, sql/039). Lokal generierte SQL fuer beide Cluster-Typen verifiziert.

---

## Teil F — Lernagenten

### F1 — `current_value` in `09` ist hartkodiert `1.0`, kein DB-Read
- **Schweregrad:** kritisch
- **Datei/Node:** `09 – Lernagent Newswirkung.json`, Node „Baue Lernagent-Prompt"
- **Ursache:** `trading.scoring_weights` wird zwar referenziert, aber nur für Fallgewichtung nach `baseline_quality_*` — der eigentliche per-Dimension aktive Gewichtswert wird nie gelesen. Die KI darf `current_value` selbst behaupten (`p.current_value ?? 1.0`).
- **Auswirkung:** Liegt ein Gewicht bereits bei 0.6, suggeriert der Prompt „current_value=1.0" — ein KI-Vorschlag „0.8" sieht nach Absenkung aus, ist real eine Anhebung um +33%.
- **Korrektur:** Vor Prompt-Bau `SELECT weight_value FROM scoring_weights WHERE weight_key=... AND active=TRUE` je Kandidat joinen, `current_value` fest aus DB setzen.
- **Status:** offen

### F2 — `proposed_value` wird von der KI erfunden, kein Bounds-/Schrittweiten-Check im Code
- **Schweregrad:** kritisch
- **Datei/Node:** `09`, Node „Vorschlaege gegen Fallzahlen validieren"
- **Ursache:** „Änderungen typischerweise 0.1–0.3, nie mehr als 0.5" ist nur Prompt-Text; Code-Sicherheitsnetz prüft nur `dimension|value|horizon`-Matching, nicht den Wert selbst. `scoring_weights.weight_value` hat kein CHECK.
- **Korrektur:** Nach KI-Call `proposed_value` gegen `current_value ± max_step` und festen Wertebereich clampen/verwerfen.
- **Status:** offen

### F3 — Mindestfallzahl in `09` hartkodiert statt aus `pipeline_config`
- **Schweregrad:** niedrig
- **Datei/Node:** `09`, Node „Mindestfallzahlen klassifizieren"
- **Status:** offen

### F4 — OOS-Gate in `09b` ist global, nicht strategie-/versionsgebunden
- **Schweregrad:** kritisch
- **Datei/Node:** `09b – Lernagent Handelsstrategien.json`, Node „DB: OOS-Backtests laden"
- **Ursache:** `oosConfirmed = oosRuns.length > 0` ist ein einziges Boolean für alle Strategien/Regime — `strategy_filter`/`configuration_version`/`rule_version` aus `sql/037` werden nicht abgefragt.
- **Auswirkung:** Sobald irgendwann EIN abgeschlossener OOS-Backtest existiert (z. B. für `breakout`), gilt `oos_confirmed=true` für **alle** anderen Strategien/Regime-Kombinationen gleichzeitig — aktuell durch die leere Tabelle maskiert, wird beim ersten echten Backtest sofort scharf.
- **Korrektur:** OOS-Bestätigung je `(strategy, rule_version, configuration_version[, combined_regime])` prüfen.
- **Status:** offen — **muss vor dem ersten Backtest-Lauf behoben sein**

### F5 — `regime_restriction`-Kandidat auch bei positivem Ergebnis erzeugt
- **Schweregrad:** mittel
- **Datei/Node:** `09b`, Node „Mindestfallzahlen klassifizieren (Trades)"
- **Ursache:** `eligible` erlaubt sowohl `expR<=-0.15` als auch `expR>=0.3`, aber für den positiven Fall entsteht trotzdem ein `regime_restriction`-Kandidat mit `proposed_value:null`.
- **Auswirkung:** Führt zu F11 (NOT-NULL-Verletzung).
- **Korrektur:** Kandidatenerzeugung explizit an `expR<=-0.15` binden.
- **Status:** offen

### F6 — Regime-Konzentration wird nicht geprüft (nur Ticker-Konzentration)
- **Schweregrad:** mittel
- **Datei/Node:** `09b`
- **Status:** offen

### F7 — `ambiguous_pct` (E9/E10-Fälle) ist nur informativ, kein Gate in `09b`
- **Schweregrad:** mittel
- **Datei/Node:** `09b`
- **Status:** offen

### F8 — Effektstärke-Gate basiert auf `net_pnl` ohne Einstiegskosten
- **Schweregrad:** hoch (Folgefehler von E7)
- **Datei/Node:** `09b`, Effektstärke-Gate (`expectancy_r`)
- **Korrektur:** Nach Fix von E7 automatisch behoben, da `realized_r_multiple` dann korrekt ist.
- **Status:** offen (abhängig von E7)

### F9 — Stabilität über Zeit, Drawdown, Anteil blockierter Signale nicht geprüft
- **Schweregrad:** mittel
- **Datei/Node:** `09b`
- **Status:** offen

### F10 — `pipeline_config.value_numeric` kann durch `12` auf NULL gesetzt werden
- **Schweregrad:** kritisch (identisch mit A9, hier aus Lernagenten-Perspektive bestätigt)
- **Status:** offen (siehe A9)

### F11 — Kein zentrales Regelwerk (Typ/Min/Max/Default/Schrittweite/NULL-Policy) in `12`
- **Schweregrad:** hoch (identisch mit A8)
- **Status:** offen (siehe A8)

### F12 — NOT-NULL-Verletzung bei `learning_rule_proposals.proposed_value` durch F5, stiller Datenverlust
- **Schweregrad:** mittel
- **Datei/Node:** `09b`, Node „Vorschlag speichern (SQL bauen, Trades)"
- **Ursache:** F5 erzeugt `proposed_value:null` für `TEXT NOT NULL`-Spalte, INSERT schlägt fehl, `onError:"continueRegularOutput"` lässt den Workflow ohne sichtbaren Hinweis weiterlaufen.
- **Korrektur:** F5 beheben; zusätzlich Fehlerpfad der Postgres-Node in den Lernbericht aufnehmen.
- **Status:** offen

---

## Teil G — Migrationen und Dokumentation

### G1 — Keine Migrationsprotokoll-Tabelle, keine automatische Doppellauf-Sperre
- **Schweregrad:** mittel
- **Datei/Node:** `99 – Einmalig – SQL-Migration ausfuehren.json`
- **Ursache:** Kein `schema_migrations`-artiges Tracking. Einziger Nachweis über bereits gelaufene Migrationen ist Prosa in `OFFENE_AUFGABEN.md`.
- **Korrektur:** `trading.schema_migrations(version, applied_at, checksum)` ergänzen, `99` um Prüf-/Protokoll-Node erweitern.
- **Status:** offen

### G2 — Transaktionsverhalten pro Migration nicht explizit
- **Schweregrad:** niedrig
- **Datei/Node:** alle `sql/*.sql`
- **Korrektur:** Jede Migrationsdatei explizit mit `BEGIN;`/`COMMIT;` umschließen (unabhängig vom impliziten Postgres-Node-Verhalten).
- **Status:** offen

### G3 — (Positiv-Befund, kein Fehler) Vollständiger Objektabgleich: 0 von 35 referenzierten DB-Objekten fehlen
- **Status:** verifiziert, kein Fund

### G4 — Live-IDs/Aktivstatus für `09b`/`12`/`13`/`14` im Repo nicht verifizierbar
- **Schweregrad:** mittel
- **Datei/Node:** `09b`, `12`, `13`, `14` — kein `active`/`id`-Feld im Export, keine passenden `n8n_live_backup/`-Dateien vom 2026-08-01
- **Auswirkung:** Die in `OFFENE_AUFGABEN.md` genannten IDs und „bewusst inaktiv"-Aussagen sind aus dem Repo-Inhalt nicht nachprüfbar — Bruch der bisher eingehaltenen Nachweisdisziplin (GET-Backup vor jedem Push).
- **Korrektur:** `GET /workflows` ausführen, Ist-Stand nach `n8n_live_backup/` sichern, Root-JSON mit Live-Stand resynchronisieren.
- **Status:** offen

### G5 — Alt-Duplikate ohne „Agent V1"-Suffix
- **Schweregrad:** niedrig
- **Datei:** `04 – Cleanup News-Tabellen.json`, `06 – Empfehlungswatchlist.json`, `07 – Status-Uebersicht.json`
- **Befund:** `active`-Feld korrekt (Altversionen live deaktiviert) — kein funktionaler Fehler, reines Aufräumrisiko.
- **Korrektur:** Nach `n8n_live_backup/` oder `archiv/` verschieben.
- **Status:** offen

### G6 — Redaktionsfehler in `OFFENE_AUFGABEN.md` (Zeile 7 vs. 21)
- **Schweregrad:** niedrig
- **Befund:** „Live-Push steht noch aus" (Zeile 7) vs. „Live gepusht und verifiziert" (Zeile 21) — kein Sachwiderspruch, nur nicht nachgezogene Zusammenfassungszeile.
- **Korrektur:** Zeile 7 aktualisieren/streichen.
- **Status:** offen

### G7 — `09b`s OOS-Gate hängt von nie gebautem Backtesting-Workflow ab (nicht in Doku als Abhängigkeit sichtbar)
- **Schweregrad:** mittel
- **Befund:** `trading.backtest_runs` wird von keinem Workflow beschrieben (Backtesting bewusst nicht gebaut) — `09b`s OOS-Gate liest daraus, ist also strukturell dauerhaft "kein Ergebnis", bis Welle 3 AP7 nachgezogen wird. Verstärkt die Dringlichkeit von F4 (muss vor erstem echten Backtest behoben sein).
- **Status:** offen (Dokumentationslücke, kein Code-Fehler)

---

## Statusübersicht nach Schweregrad

| Schweregrad | Anzahl | IDs |
|---|---|---|
| kritisch | 22 | A1, A5, A6, A9, A11, B1, B4, C4, C9, D3, D5, D13, E1, E2, E4, E5, E7, E8, E9, E12, F1, F2, F4, F10 |
| hoch | 19 | A2, A3, A7, A8, B2, B5, C1, C6, C7, C8, D1, D2, D4, D6, D9, D11, D12, F8, F11 |
| mittel | 21 | A4, A10, B3, B6, B8, B9, C2, C5, D7, D8, D10, E3, E6, E10, E11, F3, F5, F6, F7, F9, F12, G1, G4, G7 |
| niedrig | 6 | B7, C3, G2, G5, G6 |

(Hinweis: A9/F10 und A8/F11 sind jeweils derselbe Fund aus zwei Blickwinkeln — 22 kritische Funde bei 21 eindeutigen Ursachen.)

Nächster Schritt: Priorisierung mit dem Nutzer abstimmen, danach Git-Commit-Basis, dann Fixes in der im Auftrag vorgegebenen Reihenfolge (Datenintegrität/Risikolimits/Paper-Trading/Lernregeln/SQL-Sicherheit/Workflowsteuerung zuerst).
