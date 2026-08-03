# Reparaturplan — Technische Bereinigung und Härtung

Stand: 2026-08-03. Dieser Plan wurde nach der vollständigen Analyse aller 15 im Auftrag
genannten Punkte gegen den tatsächlichen, aktuellen Code (nicht gegen Annahmen) erstellt.
Jeder Fund wurde vor der Behebung live/strukturell verifiziert — der Auftrag erlaubt keine
Vermutungen. Umsetzung erfolgte direkt im Anschluss an die Analyse, wie vom Auftrag
vorgegeben ("Beginne danach direkt mit der Umsetzung"). Fortschritt und Ergebnis je Punkt:
`docs/REPARATURBERICHT.md`.

## Methode

Für jeden Punkt: (1) Live-Code der betroffenen Datei(en) lesen, (2) den behaupteten Fehler
tatsächlich nachweisen (nicht nur den Auftragstext übernehmen), (3) bei Bestätigung die
kleinstmögliche, fachlich unveränderte Korrektur umsetzen, (4) Backup vor jeder JSON-Änderung
in `backup-vor-reparatur/`, (5) Graph-Integrität (keine gebrochenen Connections) und
JavaScript-Syntax nach jeder Änderung geprüft, (6) bei aktiven Workflows Live-Push +
Webhook-/Ausführungs-Verifikation wo ohne reale Seiteneffekte möglich.

## P0 — zwingend zu beheben

### P0.1 — Ungültiges SQL im Empfehlungsworkflow
**Fund bestätigt, kritisch, live-relevant.** `06`s "Oeffnen: SQL bauen" enthielt einen
`//`-JS-Kommentar (aus der letzten Härtungssitzung) direkt im SQL-Template-String, zwischen
Spaltenliste und `VALUES` — hätte bei jeder produktiven Ausführung einen Postgres-Syntaxfehler
verursacht. Projektweiter Scan über alle 20 Workflows fand genau diesen einen Fall.
**Lösung:** Kommentar vor den SQL-String verschoben (nicht gelöscht). **Risiko der Änderung:**
minimal (reine Verschiebung eines Kommentars). **DB-Änderung:** keine. **Test:** Node-Skript
scannt alle `INSERT`/`UPDATE`/`SELECT`-Template-Literale auf `//` außerhalb von URLs — 0
Treffer nach Fix.

### P0.2 — Unsynchronisierte Parallelzweige
**Fund bestätigt, kritisch, projektweit.** Ancestor-Graph-Analyse aller `$('Node').all()`-
Rückbezüge in allen 20 Workflows fand 10 Fälle in 6 Dateien (02, 02b, 03, 06 je 1-7 Fälle, 08,
09 je 1 Fall), in denen der referenzierte Node auf einem strukturell unverbundenen
Parallelzweig lief — keine Ausführungsgarantie, nur zufällige Timing-Abhängigkeit (z. B.
einfache DB-Query vs. externer API-Call). **Lösung:** je nach Eingabeabhängigkeit des
nachgelagerten Node entweder direkte Verkettung (bei eingabeunabhängiger Query) oder
Wrap-Node + Merge-Kette (etabliertes Projektmuster) — Quelle wird echter Vorgänger, ohne
Item-Zahl-Semantik zu verändern. **Risiko:** niedrig (nur Ausführungsreihenfolge betroffen,
keine fachliche Logik). **DB-Änderung:** keine. **Test:** Ancestor-Check-Skript, 0 Risiken
nach Fix; Graph-Integrität + JS-Syntax für alle 6 Dateien bestätigt.

### P0.3 — Kartesische Merge-Kette in der Statusübersicht
**Fund bestätigt, kritisch, aktuell live-aktiv.** `07`s "Merge Status 17" bis "27" (11
Merge-Nodes) standen entgegen einer früheren Annahme weiterhin im `combineAll`-Modus,
gespeist direkt von unwrapped Postgres-Nodes mit potenziell vielen Zeilen (z. B.
"Geschlossene Paper Trades", "Lernstatus" `LIMIT 20`) — echtes, sich durch die ganze Kette
fortpflanzendes Kreuzprodukt-Risiko im aktiven Dashboard. **Lösung:** auf denselben bereits
etablierten sicheren Default/Append-Modus umgestellt wie "Merge Status 1"-"16" (reine
Synchronisationsbarriere — "Baue Uebersicht" liest ohnehin nur über Node-Rückbezüge, nie den
direkten Merge-Inhalt). **Risiko:** niedrig. **Test:** live gepusht, Webhook-Test (27 KB
valides HTML, korrekte Inhalte).

### P0.4 — Einheitliche Subworkflow-Rückgabe
**Fund bestätigt, kritisch.** `02`, `02b`, `06` hatten je 2-3 unverbundene Endnodes
(Envelope-Builder UND separate rohe Postgres-Schreibknoten) — der Orchestrator erhielt ein
Gemisch aus echtem Ergebnis und rohen DB-Antworten, ausgewählt per "meiste Felder gewinnt"-
Heuristik. **Lösung:** (1) alle Workflows auf genau einen Endnode reduziert (rohe
Schreibergebnisse werden vorher gefiltert/markiert und in die bestehende Merge-Kette
eingehängt, ohne die Envelope-Logik fachlich zu ändern); (2) alle 6 vom Orchestrator
aufgerufenen Sub-Workflows (02, 02b, 05, 06, 10, 13, 14) liefern jetzt zusätzlich das
geforderte `workflow_result`-Schema additiv; (3) `00`s Heuristik in allen 7
Ergebnis-entduplizieren-Nodes durch eine harte Prüfung auf `type === 'workflow_result'`
ersetzt — fehlt ein gültiges Ergebnis, wird das jetzt explizit als Fehler markiert.
**Risiko:** mittel (Struktur-Änderung an mehreren aktiven Workflows) — durch defensive
Filter/Marker-Muster abgefedert, die die bestehende Envelope-Berechnung unangetastet lassen.
**Test:** Graph-Integrität + JS-Syntax für alle Dateien, Live-Push für 02/02b/05/10/13/14.

### P0.5 — SSRF-Schutz vollständig durchsetzen
**Fund bestätigt, kritisch.** Die SSRF-Prüfung griff ausschließlich beim manuellen Testen
einer RSS-Quelle — beim tatsächlichen Speichern (add/edit) lief sie nie, eine unsichere URL
konnte ungeprüft in die DB gelangen und wurde danach von `03` stündlich ungeprüft produktiv
abgerufen. **Lösung:** (1) dieselbe Prüfung läuft jetzt auch beim Speichern, unsichere URLs
werden nicht persistiert (Warnbanner im Admin-UI); (2) Verteidigung in der Tiefe: dieselbe
Prüfung läuft zusätzlich unmittelbar vor jedem produktiven Abruf in `03`; (3) Redirects am
produktiven Abruf deaktiviert. Zusätzlich gehärtet: Ablehnung von URLs mit eingebetteten
Zugangsdaten, Erkennung numerischer IP-Alternativdarstellungen (dezimal/hex) — beides fehlte
in der ursprünglichen Prüfung. **Risiko:** niedrig (rein additive Sicherheitsprüfung).
**Test:** beide Workflows live gepusht, `RSS-Quellen verwalten` per Webhook bestätigt (200,
13 KB valides HTML).

## P1 — wichtige funktionale Bereinigungen

### P1.6 — `portfolio_pending` sauber behandeln
**Fund bestätigt.** Grundmechanik war bereits aus der vorherigen Härtungssitzung (Phase 6+7)
korrekt vorhanden, aber `06`s Fix (self-gatend über `ENABLE_PAPER_TRADING`, sicherer Default
`FALSE`) war bisher manuell zurückgehalten und nicht live gepusht. **Lösung:** `06` jetzt
sicher live — bei deaktiviertem Flag direkt `status='offen'`, bei aktivem Flag
`portfolio_pending`. **Risiko:** niedrig (reines Feature-Flag-Gating, Default deaktiviert).
**Test:** live gepusht und verifiziert.

### P1.7 — Handelsstrategien-Lernagent korrekt integrieren
**Fund bestätigt.** `09b` bekam einen `Execute Workflow Trigger` + eigenen deaktivierten
Schedule (gleiches Muster wie `13`/`14`), bleibt `active:false` (Sicherheitsregel).
`LEARNING_MIN_TRADE_SAMPLE_SIZE` war bereits korrekt vorhanden — kein Fund dort. **Risiko:**
keines (Workflow bleibt inaktiv). **Test:** JS-Syntax + Graph-Integrität geprüft.

### P1.8 — Zentralen Error-Handler vereinheitlichen
**Fund bestätigt, zwei Teile.** (1) `settings.errorWorkflow` (`11 - Zentraler Error-Handler`)
fehlte bei `09b`, `12`, `13`, `14`, `RSS-Quellen verwalten`, `Watchlist verwalten` — auf allen
6 ergänzt, gleiches Muster wie bei allen anderen Workflows. (2) Die Lade-Nodes vor `Baue HTML`
in `RSS-Quellen verwalten`/`Watchlist verwalten` hatten kein `onError` (Default `stopWorkflow`)
— ein DB-Ausfall genau hier ließ den Webhook ohne jede Antwort hängen statt strukturiert zu
antworten. **Lösung:** `onError:continueRegularOutput` + `alwaysOutputData`, plus sichtbares
Fehlerbanner mit korrelierbarer Fehler-ID (keine Credentials/Stacktrace) statt stillschweigend
leerer Liste. **Risiko:** niedrig (additive Settings-/Fehlerbehandlung, keine
Geschäftslogik-Änderung). **Test:** alle 6 live gepusht + GET-Diff-verifiziert, beide Webhooks
per curl bestätigt (200, kein Fehlerbanner im Normalbetrieb).

### P1.9 — Zeitzone Europe/Berlin
**Fund bestätigt, zwei Bugklassen.** (1) 8 Stellen in 6 Workflows (`01`, `02`, `02b`, `09`,
`09b`, `13`) berechneten ein "heute"-Datum über `new Date().toISOString().substring(0,10)` —
das ist der UTC-Kalendertag, nicht Berlin; im Fenster 22:00–02:00 Berliner Zeit (je nach
Sommer-/Winterzeit) wäre das um einen Tag falsch gewesen und hätte nicht mehr zum
`business_date`/`snapshot_date` anderer Workflows gepasst. **Lösung:** ersetzt durch die
bereits etablierte, DST-sichere `getBusinessDate()`-Hilfsfunktion (`Intl.DateTimeFormat` mit
explizitem `timeZone:'Europe/Berlin'`), pro betroffenem Node inline ergänzt (n8n Code-Nodes
teilen keinen gemeinsamen Scope). (2) 28 SQL-Queries in 5 Workflows (`06`, `07`, `10`, `13`,
`14`) filterten "heute" über unqualifiziertes `CURRENT_DATE` — hängt vom Timezone-Setting der
Postgres-Session ab, nicht garantiert Europe/Berlin. **Lösung:** ersetzt durch
`(now() AT TIME ZONE 'Europe/Berlin')::date`; Sonderfall 2 Stellen (`07`/`10` "DB: Vetos
heute") vergleichen gegen eine TIMESTAMPTZ-Spalte (`created_at`) statt DATE — dort die
präzisere, richtungssichere Form `(created_at AT TIME ZONE 'Europe/Berlin')::date >= (now()
AT TIME ZONE 'Europe/Berlin')::date` verwendet (spiegelt `06`s bereits korrektes
News-Filter-Muster). **Risiko:** niedrig (macht bestehendes, vermutlich meist zufällig
korrektes Verhalten explizit und session-timezone-unabhängig). **Test:** alle 10 betroffenen
Workflows live gepusht + GET-Diff-verifiziert, `07`/`10`-Webhooks per curl bestätigt.

## P2 — Qualitätsverbesserungen

Punkte 10-15 (Lernvorschläge dauerhaft speichern, News-Retry unabhängig vom RSS-Ergebnis,
Cleanup-Workflow doppelte Node-IDs, veraltete TODOs, Markt-Screener-Abgrenzung, semantische
Variablennamen) — Analyse und Umsetzung im Anschluss an P1, gleiche Methode (Fund verifizieren
vor Fix, kleinstmögliche Änderung, kein Aktivierungszustand ändern).

## Nicht aktivierte Module — unverändert

`09b`, `13`, `14` bleiben `active:false`. Alle bisher deaktivierten Schedule-Trigger bleiben
deaktiviert. Keine Ausnahme in dieser Sitzung.
