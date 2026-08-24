# Aktivierungsplan Paper-Trading — Härtung Welle 1-3

Stand: 2026-08-02. Gilt für die kontrollierte Aktivierung von `13` (Markt-Screener) und `14`
(Portfolio-Risiko und Paper-Trading) über den Orchestrator (`00`), sowie den zurückgehaltenen
Live-Push von `06`s `portfolio_pending`-Fix und `00`s Phase-14-Erweiterung selbst.

**Diese Reihenfolge ist zwingend, nicht optional** — jede Stufe setzt voraus, dass die
vorherige mindestens die angegebene Beobachtungsdauer ohne ungeklärte Abweichung durchlaufen
hat. Ein Überspringen einer Stufe widerspricht den Sicherheitsregeln des Härtungsauftrags
("keine Aktivierung von `13`/`14`, bevor deren DRY_RUN-Abnahmetests erfolgreich sind").

## Stufe 0 — Aktueller Zustand (jetzt)

- `00` läuft aktiv, unverändert (Phase-14-Version lokal fertig, **nicht live gepusht** — siehe
  `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md`, Phase 14.3).
- `13`, `14` inaktiv, mit deaktivierten Eigen-Schedules, aber vollständig ausgebaut (Execute
  Workflow Trigger, konsolidierte Envelopes).
- Feature-Flags `ENABLE_MARKET_SCANNER=FALSE`, `ENABLE_PAPER_TRADING=FALSE`,
  `ENABLE_TRADE_LEARNING=FALSE` in der DB (`sql/056`, live bestätigt).
- `06`s `portfolio_pending`-Fix liegt fertig im Repo, nicht live.
- 35/35 Tests aus `tests/welle_1_3_testsuite.js` bestehen (Node-Nachbildungen, keine echten
  n8n-Läufe — siehe `TESTPLAN_HAERTUNG_WELLE_1_3.md`).

**Kein reales Risiko in diesem Zustand**: keine reale Order-/Brokeranbindung existiert an
keiner Stelle dieses Systems (Sicherheitsregel, projektweit unverändert).

## Stufe 1 — `13` (Markt-Screener) isoliert aktivieren

**Voraussetzung**: keine (Scanner hat kein Order-/Bestandsrisiko, schreibt nicht in
`trading.recommendations`).

**Schritte**:
1. `00`s Phase-14-Version live pushen (jetzt technisch möglich, sobald mindestens ein
   referenzierter Sub-Workflow aktiv ist — siehe Schritt 2).
2. `13` aktivieren (`active:true`).
3. `ENABLE_MARKET_SCANNER=TRUE` setzen.

**Beobachtung**: mindestens 3 Handelstage. Prüfen: `trading.scan_runs`/`scan_candidates`
füllen sich plausibel (Universumsgröße konstant, `stage_a_survivors`/`stage_b_analyzed` in
erwarteter Größenordnung), `00`s Gesamtlauf bleibt `success`/`partial_failure` (nicht
`failed` durch die neue Stufe), Dashboard (`07`) zeigt den Scanner-`run_id` korrekt an
(Phase-12-Banner).

**Abbruchkriterium**: `Ausfuehren: Markt-Screener (13)`-Status wird wiederholt `failed`, oder
`00`s Gesamtlauf schlägt dadurch fehl → `ENABLE_MARKET_SCANNER=FALSE` zurücksetzen, Ursache
klären, Stufe 1 wiederholen.

## Stufe 2 — `06`s `portfolio_pending`-Fix + `14` isoliert (nur Job A/B, DRY_RUN erzwungen)

**Voraussetzung**: Stufe 1 stabil.

**Schritte**:
1. `06`s zurückgehaltenen Fix live pushen (Status-Zwischenschritt `portfolio_pending`).
2. `14` aktivieren.
3. `ENABLE_PAPER_TRADING=TRUE` setzen — **`DRY_RUN` in `trading.pipeline_config` bleibt in
   dieser Stufe explizit `TRUE`** (unabhängig vom sonstigen Systemzustand testweise
   erzwingen), damit `14` ausschließlich simuliert schreibt (B6-Tiefenverteidigung in den
   Dispatchern blockt reale Trade-Anlage bei `DRY_RUN=true` zusätzlich zur Gate-Logik selbst).

**Beobachtung**: mindestens 5 Handelstage. Prüfen: keine Empfehlung bleibt dauerhaft in
`portfolio_pending` hängen (das war exakt der Fehler, den Phase 6 behoben hat), Job B
überwacht auch bei 0 neuen Kandidaten weiter (Phase 14.2, bereits bestätigt), keine
doppelten `paper_trades`-Zeilen (Phase 16, `ON CONFLICT (trade_id)`), Dashboard/Report
zeigen konsistente Zahlen (Phase 12).

**Abbruchkriterium**: jede stillschweigend hängenbleibende `portfolio_pending`-Zeile älter
als 1 Tag, jeder unerwartete `data_error_final`/`portfolio_check_failed` ohne nachvollziehbare
Ursache.

## Stufe 3 — Echtes Paper-Trading (DRY_RUN=FALSE für `14`)

**Voraussetzung**: Stufe 2 mindestens 5 Handelstage ohne Abbruchkriterium.

**Schritte**: `DRY_RUN=FALSE` — `14` legt jetzt echte (weiterhin rein theoretische, keine
reale Order!) Paper-Trades an, die tatsächlich Positionen im Ledger eröffnen/schließen.

**Beobachtung**: **mindestens 20 Handelstage bzw. bis mindestens 30 abgeschlossene
(`status='closed'`) Paper-Trades vorliegen** — je nachdem, was länger dauert. Das ist die
explizite Sicherheitsregel-Vorgabe ("ausreichend abgeschlossene Paper Trades") und keine
willkürliche Zahl: unter 30 abgeschlossenen Trades ist jede Kennzahl (`expectancy_r`,
`profit_factor`, `ambiguous_pct`) statistisch nicht belastbar genug für eine Entscheidung.

## Stufe 4 — Out-of-Sample-Verfahren etablieren

**Voraussetzung**: Stufe 3 abgeschlossen, ≥30 geschlossene Paper-Trades.

Ein belastbares Out-of-Sample-Verfahren fehlt aktuell vollständig (`trading.backtest_runs`
mit `run_type='out_of_sample'` existiert als Schema, aber ohne Producer-Workflow — bestätigt
in `09b`s Query "DB: OOS-Backtests laden", die aktuell 0 Zeilen findet). **Das Aufbauen dieses
Verfahrens ist ein eigenständiges, in dieser Sitzung nicht enthaltenes Vorhaben** (kein
Backtest-Workflow existiert; ihn zu bauen wäre ein Projekt in der Größenordnung eines Teils
von `06`/`14`). Ohne dieses Verfahren bleibt `09b` (Lernagent) inaktiv (Sicherheitsregel).

## Stufe 5 — `09b` (Lernagent Handelsstrategien)

**Voraussetzung**: Stufe 4 abgeschlossen (echtes OOS-Verfahren vorhanden UND mindestens einen
vollen OOS-Durchlauf gegen die bis dahin gesammelten Paper-Trades gezeigt).

Erst danach: `ENABLE_TRADE_LEARNING=TRUE`, `09b` aktivieren, mit weiterhin nur
`status='proposed'`-Lernvorschlägen (keine automatische Regelanwendung — Freigabe bleibt
manuell über `12`, unverändert).

## Was in keiner Stufe passiert

- Keine reale Broker-/Orderanbindung — an keiner Stelle dieses Plans vorgesehen, technisch
  nicht vorhanden.
- Keine automatische Aktivierung von `09b` vor einem echten OOS-Verfahren (Stufe 4).
- Kein Überspringen der Beobachtungsfristen, auch wenn Zwischenwerte gut aussehen.

## Rollback

Jede Stufe ist über das jeweilige Feature-Flag (`value_bool=FALSE` in
`trading.pipeline_config`) sofort und ohne Codeänderung rückgängig zu machen — der
Orchestrator bypassed die betroffene Stufe beim nächsten Lauf automatisch (Phase 14). Ein
Rollback löscht **keine** historischen Daten (Sicherheitsregel) — `paper_trades`/`recommendations`
bleiben unverändert stehen, nur künftige neue Läufe der Stufe finden nicht mehr statt.

## Nachtrag 2026-08-24 — Live-Zustand weicht vom geplanten Ablauf ab (bestätigt, nicht zurückgerollt)

Im Rahmen des Audits für den Konzeptbericht "Persönlicher KI-Trading-Analyst" per Live-Query
gegen `trading.pipeline_config` festgestellt:

| Flag | Live-Wert | zuletzt geändert |
|---|---|---|
| `DRY_RUN` | `false` | 2026-07-20 |
| `ENABLE_MARKET_SCANNER` | `false` | 2026-08-02 |
| `ENABLE_PAPER_TRADING` | `true` | 2026-08-02 |
| `ENABLE_TRADE_LEARNING` | `false` | 2026-08-02 |

Workflows `13` und `14` sind live beide `active:true`.

**Das bedeutet strukturell: Stufe 3 ist erreicht** (`DRY_RUN=false` — `14` kann echte, weiterhin
rein theoretische Paper-Trades im Ledger öffnen/schließen) — **ohne dass für Stufe 2 (DRY_RUN
erzwungen `TRUE`, mindestens 5 Handelstage Beobachtung) ein dokumentierter Beobachtungszeitraum
vorliegt.** Die Zeitstempel (`DRY_RUN` → `false` am 2026-07-20, `ENABLE_PAPER_TRADING` → `true`
erst am 2026-08-02) legen nahe, dass Stufe 2 faktisch übersprungen statt durchlaufen wurde,
entgegen der oben als zwingend beschriebenen Reihenfolge.

**Auf Rückfrage am 2026-08-24 bestätigt: dieser Zustand ist beabsichtigt und wird nicht
zurückgerollt.** Realer Effekt bislang gering — 4 Empfehlungen, alle `portfolio_blocked`/
`portfolio_pending`; 4 `paper_trades`, alle `blocked` (Quelle: Live-Audit 2026-08-24).

`ENABLE_MARKET_SCANNER=false` heißt: Stufe 1 ist trotz `13`s `active:true` weiterhin **nicht**
scharf — der Orchestrator überspringt `13` unverändert vollständig. Das `active:true` von
`13`/`14` selbst ist reine n8n-Infrastrukturvoraussetzung (Execute-Workflow-Aufrufbarkeit),
keine funktionale Aktivierung.

Zusätzlich gefunden und auf Rückfrage korrigiert: `REQUIRE_CONFIRMATION` (Migrations-Default
`TRUE`, "Erfordert eine Bestätigung vor dem Öffnen oder Schließen von Empfehlungen") stand seit
2026-07-20 undokumentiert auf `false`. Nicht beabsichtigt — am 2026-08-24 zurück auf `true`
gesetzt.

**Für alles, was noch nicht gesetzt ist** (`ENABLE_MARKET_SCANNER`, `ENABLE_TRADE_LEARNING`,
Stufe 4/5), bleibt die oben beschriebene Stufenfolge weiterhin verbindlich — nur der bereits
vollzogene Sprung zu Stufe 3 für `14` wird nicht nachträglich zurückgedreht.
