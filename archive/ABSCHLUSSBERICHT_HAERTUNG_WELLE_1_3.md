# Abschlussbericht — Vollständige Härtung und betriebsfähige Integration der Handelsanalyse-Pipeline

Stand: 2026-08-02. Bezieht sich auf den 18-Phasen-Auftrag "Vollständige Härtung und
betriebsfähige Integration der Handelsanalyse-Pipeline (Welle 1-3)". Detailliertes
Fehler-für-Fehler-Protokoll: `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md`. Änderungsprotokoll je
Workflow/Migration: `AENDERUNGSPROTOKOLL_HAERTUNG_WELLE_1_3.md`. Testumfang/-ergebnisse:
`TESTPLAN_HAERTUNG_WELLE_1_3.md`/`TESTERGEBNISSE_HAERTUNG_WELLE_1_3.md`.
Aktivierungsreihenfolge: `AKTIVIERUNGSPLAN_PAPER_TRADING.md`. Ampel-Übersicht:
`PRODUKTIONSFREIGABE_PAPER_TRADING.md`.

## 1. Auftragskontext und Vorgehen

Auftrag: audit, korrigieren, vollständig verdrahten und mit reproduzierbaren Tests absichern
der **bestehenden** Handelsanalyse-Pipeline — ausdrücklich **keine** parallele
Architektur. Vorgehen: 18 Phasen systematisch abgearbeitet (Bestandsaufnahme →
Merge-Sicherheit → Migrationsverifikation → fachliche Einzelfixes → Verdrahtung →
Absicherung → Tests → Aktivierungsplan), autonom entschieden außer bei den 4 explizit
benannten Rückfrage-Bedingungen (reale Datenlöschung, fehlende Zugangsdaten, reale
Orderanbindung, unvereinbare Zieldecisionen). Eine Rückfrage tatsächlich nötig: ein
zwischenzeitlich ungültig gewordener n8n-API-Schlüssel (Zugangsdaten fehlten kurzzeitig) —
vom Nutzer bereitgestellt, danach fortgesetzt.

## 2. Bestandsaufnahme (Phase 1)

11 Kern-Workflows (`00`-`14` plus `05`/`06`/`07`/`09b`/`10` etc.) plus mehrere
Hilfs-Workflows (`08`, `11`, `12`, RSS/Watchlist-Verwaltung) vollständig kartiert: aktiv/
inaktiv-Status, Trigger-Art, Ein-/Ausgaben, Schreibziele, bekannte Risiken. Ergebnis: `13`
und `14` vollständig fertig entwickelt, aber **nicht in den Orchestrator eingebunden** und
ohne Aufrufmechanismus (kein `executeWorkflowTrigger`) — der zentrale strukturelle Befund,
der Phase 14 motivierte.

## 3. Gefährliche Merge-Ketten identifiziert und entschärft (Phase 2)

Mehrere Workflows (`07`, `10`, `13`, `14`) hatten lange Ketten von `n8n-Merge`-Nodes im
Default-Append-Modus, aber mit dem Risiko, versehentlich auf `combine`/`combineAll`
umgestellt zu werden (Kreuzprodukt-Explosion). Etabliertes Gegenmuster: jede Datenquelle wird
vor dem Merge auf genau 1 Item gewrappt (`{dataset, rows}`), wodurch die Zeilenanzahl der
Quelle irrelevant für die Merge-Ergebnisgröße wird. Insgesamt 43 Wrap-Nodes über 4 Workflows
ergänzt, 0 Regressionen (bestehende `$('Node').all()`-Rückbezüge funktionieren unverändert).

## 4. Migrationsverifikation (Phase 3)

Kritischer Fund: `sql/045` (B9-Fix, `business_date`-Spalte + 3 Unique-Indizes für `14`) war
**nie tatsächlich ausgeführt** worden — in einer früheren Sitzung durch `sql/046` in der
Query-Node überschrieben, bevor der Nutzer ausführen konnte. Wäre `14` in diesem Zustand
aktiviert worden, hätte jeder Job-A/B/C-Schreibvorgang mit einem SQL-Fehler abgestürzt. Durch
systematische Diagnose gefunden (nicht angenommen), korrigiert nachgeholt, per zweiter
Diagnose-Query bestätigt (5/5 Prüfungen `true`).

## 5. Fachliche Einzelfixes (Phasen 4-11)

- **Phase 4**: `data_error`-Retry in `14` repariert — Status vor Fehlereintritt wird gesichert
  und nach Wiederherstellung restauriert (statt eines festen, potenziell falschen Rückfalls).
- **Phase 5**: Gap-through-Stop konservativ simuliert (`stopRawExitPrice()`), 5 neue
  Audit-Felder, `net_pnl`-Formel selbst unangetastet (kein Regressionsrisiko).
- **Phase 6+7**: neuer Statuszwischenschritt `portfolio_pending` löst den Widerspruch
  "Empfehlung bleibt dauerhaft `offen`, obwohl der zugehörige Paper-Trade `blocked` ist" —
  gleichzeitig löst dieselbe Änderung die Rückstandsverarbeitung (rein statusbasierte
  Ladequery statt Datumsfilter).
- **Phase 8**: `13`s "relative Stärke" berechnete tatsächlich nur eine Absolutrendite — echte
  `relativeStrengthVsIndex()` gegen den jeweiligen Referenzindex ergänzt.
- **Phase 9**: Mean-Reversion/Breakout erlaubten bisher einen Einstieg allein auf Basis eines
  moderaten RSI-Werts bzw. reiner Nähe zum 52-Wochen-Hoch — beides jetzt echte
  UND-Bedingungen (Überdehnung UND Preisbestätigung bzw. echter Ausbruch UND
  Volumenbestätigung).
- **Phase 10**: `MAX_POSITION_VALUE_PCT` war nur ein Informationsfeld, kein tatsächliches
  Limit auf die Stückzahl — `theoretical_quantity = min(quantity_by_risk, quantity_by_value)`
  jetzt echt durchgesetzt, inkl. neuem `QUANTITY_ZERO`-Veto.
- **Phase 11**: Hebelprodukt-/Onvista-Logik reichte bis in `06`s Kernschreibpfad
  (`trading.recommendations`), nicht nur in `05`s Reporttext — an allen 3 gefundenen Stellen
  entfernt/neutralisiert.

## 6. Datenbankänderungen (`sql/051`-`sql/056`)

6 neue, additive und idempotente Migrationen (alle mit `BEGIN`/`COMMIT` und
Selbstregistrierung in `trading.schema_migrations`), live ausgeführt und jeweils per
Diagnose-Query bestätigt — siehe `AENDERUNGSPROTOKOLL_HAERTUNG_WELLE_1_3.md` für die
vollständige Spaltenliste je Migration. Keine historischen Daten gelöscht oder überschrieben.

## 7. Dashboard/Report-Konsistenz (Phase 12)

Neuer Datenfrische-Banner in `07` (business_date, Alter des letzten Orchestrator-Laufs,
Scanner-/Portfolio-`run_id`) — live end-to-end getestet, dabei ein selbst verursachter
Laufzeitfehler (Variablen-Referenz vor Deklaration in einer großen zusammenhängenden
HTML-Bau-Anweisung) gefunden und behoben. `10`s Merge-Sicherheit strukturell/statisch
bestätigt, aber mangels sicherem isoliertem Live-Trigger (reale OpenAI-Kosten) nicht
end-to-end getestet.

## 8. Zweigsicherheit Tagesreport (Phase 13)

`05`s vollständige Zweig-/Merge-Struktur geprüft: genau eine Abschluss-Hülle pro Lauf,
DRY_RUN und Ablehnung strukturell vom tatsächlichen Versand getrennt, partielle
Fehlschläge korrekt als `partial_failure` erkannt. Kein Fund, keine Änderung nötig — bereits
korrekt gebaut.

## 9. Orchestrator vollständig verdrahtet (Phase 14)

`13` und `14` bekamen je einen `Execute Workflow Trigger`, ein konsolidiertes
Endergebnis-Envelope (vorher nicht vorhanden) und deaktivierte Eigen-Schedules. `00` bekam
zwei neue, per Feature-Flag gesteuerte Pipeline-Stufen (`ENABLE_MARKET_SCANNER`,
`ENABLE_PAPER_TRADING`, beide `FALSE`) zwischen den bestehenden Stufen, mit vollständigem
Bypass bei deaktiviertem Flag. **Technischer Befund**: n8n verweigert das Speichern eines
Workflows, der einen inaktiven Sub-Workflow referenziert — `00`s neue Version ist fertig,
geprüft und committet, aber bewusst noch nicht live gepusht (Teil von Aktivierungsstufe 1).

## 10. `09b` abgesichert (Phase 15)

Bestätigt: bleibt inaktiv, alle Sicherheitsfixes aus der vorherigen Härtungssitzung (F6/F7/
F8/F12) weiterhin live und von den Welle-1-3-Änderungen unberührt (keine Überschneidung mit
`trading.recommendations` oder den neuen Phase-5-Audit-Feldern).

## 11. Idempotenz/Transaktionen (Phase 16)

Systematischer Scan aller `INSERT`-Statements über 20 Workflows. Alle handelsrelevanten
Schreibpfade (`paper_trades`, `portfolio_risk_checks`, `recommendations`, `scoring_weights`)
bereits korrekt abgesichert — deterministische Schlüssel + `ON CONFLICT`, das etablierte
Point-in-Time-Revisionierungsmuster (mit impliziter Postgres-Transaktion bei
Mehrfach-Statement-Strings), oder vorgelagerte Anwendungslogik + Constraint-Backstop. 2
niedrigpriore Restfunde dokumentiert (keine Handelsrelevanz).

## 12. Testabdeckung (Phase 17)

6 Suiten, 35 Einzeltests, alle bestanden (`tests/welle_1_3_testsuite.js`). Node-Nachbildungen
der produktiven Kernfunktionen, keine echten n8n-End-to-End-Läufe (reale Seiteneffekte bei
`10`/`05`/`13`/`14` verhindern das ohne dedizierte Testumgebung — dieselbe Einschränkung, die
bereits in Phase 12 zum Abbruch eines Live-Testversuchs durch den Auto-Mode-Klassifikator
führte).

## 13. Sicherheitsregel-Konformität (Checkliste)

| Regel | Status |
|---|---|
| Keine reale Broker-/Orderanbindung | ✅ nirgends vorhanden |
| Keine realen Käufe/Verkäufe/Produktorders | ✅ nirgends vorhanden |
| Keine Löschung historischer Daten | ✅ alle Migrationen additiv |
| Keine stillen Änderungen fachlicher Regeln | ✅ jede Änderung dokumentiert+begründet |
| Keine Aktivierung von `13`/`14` vor Tests | ✅ beide bleiben inaktiv |
| Keine Aktivierung von `09b` vor OOS-Verfahren | ✅ bleibt inaktiv |
| Zugangsdaten nicht offengelegt/verändert | ✅ API-Key nur zur Laufzeit verwendet |
| DRY_RUN/REQUIRE_CONFIRMATION erhalten | ✅ unverändert, `DRY_RUN`-Fail-Safe sogar geprüft |
| Migrationen additiv/idempotent | ✅ alle mit `ON CONFLICT`/`IF NOT EXISTS` |
| Keine erfundenen Preise/Wahrscheinlichkeiten/Kennzahlen | ✅ `financing_cost=0` explizit als "nicht simuliert" markiert statt geschätzt |
| Doku und Code auf demselben Stand | ✅ `docs/*.md` in Phase 18 aktualisiert |

## 14. Bekannte Grenzen und offene Punkte

- Kein echtes Out-of-Sample-Verfahren (Voraussetzung für `09b`, Aktivierungsplan Stufe 4).
- Kein echter Tiefenanalyse-Workflow für Scanner-Stufe B außerhalb der Watchlist.
- `10`/`05` nicht live end-to-end getestet (reale Seiteneffekte).
- 2 niedrigpriore Idempotenz-Restfunde (`scan_candidates`, `learning_rule_proposals`).
- `00`s Phase-14-Version, `06`s Phase-6/10/11-Fixes: fertig, aber noch nicht live (Teil des
  Aktivierungsplans, nicht vergessen).

## 15. Empfehlung

**Scanner (`13`) freigeben für Aktivierungsstufe 1** (siehe
`AKTIVIERUNGSPLAN_PAPER_TRADING.md`) — kein Order-/Bestandsrisiko, alle fachlichen Befunde
behoben, live-Code bereits gepusht, nur die Aktivierung selbst steht aus.

**Paper-Trading (`14`) NICHT sofort voll freigeben** — stattdessen gestufter Einstieg über
Stufe 2 (DRY_RUN erzwungen, mindestens 5 Handelstage) und Stufe 3 (`DRY_RUN=FALSE`,
mindestens 20 Handelstage bzw. 30 abgeschlossene Trades) gemäß Aktivierungsplan. Das ist
weder "nicht freigeben" (das System ist fachlich fertig und getestet) noch "sofort
freigeben" (die Sicherheitsregel verlangt explizit ausreichend abgeschlossene Paper Trades
und ein belastbares Out-of-Sample-Verfahren, beides aktuell nicht gegeben).

**`09b` (Lernagent) bleibt inaktiv**, bis Stufe 4 (echtes Out-of-Sample-Verfahren) abgeschlossen ist.

**Kurzformel**: Scanner freigeben (Stufe 1) · Paper-Trading gestuft freigeben, beginnend mit
erzwungenem DRY_RUN (Stufe 2-3) · Lernagent weiterhin nicht freigeben (bis Stufe 4).
