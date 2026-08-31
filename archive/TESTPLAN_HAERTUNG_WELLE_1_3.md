# Testplan — Härtung Welle 1-3 (Phase 17)

Stand: 2026-08-02. Zugehörig zu `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md` (Phasen 1-16) und
`AKTIVIERUNGSPLAN_PAPER_TRADING.md` (Phase 18).

## Methode

Alle Suiten (`tests/welle_1_3_testsuite.js`, `node tests/welle_1_3_testsuite.js`) sind
**Node-Nachbildungen der produktiven Kernfunktionen** zum Stand dieser Sitzung — kein
Zugriff auf eine echte n8n-Testumgebung oder eine isolierte Postgres-Instanz war verfügbar,
daher keine echten End-to-End-Ausführungen der Workflows selbst. Jede Nachbildung wurde
Zeile für Zeile gegen den tatsächlich in der jeweiligen `.json`-Datei live/lokal vorliegenden
Code abgeglichen (nicht aus dem Gedächtnis neu geschrieben). Live-End-to-End-Verifikation für
die inaktiven Workflows (`10`, `05`, `13`, `14` als Sub-Workflow) ist über die reguläre
n8n-API nicht ohne reale Seiteneffekte (echte OpenAI-Calls, echte Matrix-/E-Mail-Sends)
möglich und wurde vom Auto-Mode-Klassifikator in Phase 12 korrekt blockiert — das bleibt eine
bekannte, dokumentierte Lücke (siehe unten "Bekannte Grenzen"), keine verschwiegene Annahme.

Zusätzlich zu den 6 Suiten unten wurden während der Phasen 4/5/8/9/10 bereits **inline lokale
Tests** durchgeführt und in `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md` protokolliert (z. B. 6/6
Gap-through-Stop-Fälle, 6/6 Strategieregel-Fälle, 3/3 Positionsgrößen-Fälle) — die hier
gebündelten Suiten B/D fassen die wichtigsten davon in eine wiederholbare, versionierte Datei
zusammen, ersetzen aber nicht das dortige Detailprotokoll.

## Suite A — Merge/Load-Sicherheit

**Ziel**: das in Phase 2 etablierte Wrap-Node-Muster verhindert tatsächlich das
Kreuzprodukt-Risiko (`combineAll`) und lässt keinen Merge auf einen strukturell nie
feuernden Zweig warten (Phase-14-Feature-Flag-Bypass).

- A1: 2 Quellen mit 37/52 Zeilen, gewrappt auf je 1 Item → Merge liefert 2 Items, nicht 1924.
- A2: leere Quelle (0 Zeilen) → `rows()`-Filterfunktion liefert `[]`, kein Crash.
- A3/A3b: Feature-Flag-Gate (Phase 14) — `false` bypassed direkt zur nächsten Stufe, `true`
  ruft die Stufe auf.

## Suite B — Paper-Trading

**Ziel**: `data_error`-Retry-Eskalation (Phase 4) und Gap-through-Stop-Simulation (Phase 5)
verhalten sich wie in der ursprünglichen Detailprüfung nachgewiesen.

- B1-B4: `stopRawExitPrice()` — Long/Short, mit/ohne Gap.
- B5-B7: `data_error`-Zähler — erster Fehltag, Eskalationsschwelle, Wiederherstellung.
- B8: `trade_id`-Determinismus als Grundlage für `ON CONFLICT (trade_id) DO NOTHING`.

## Suite C — Portfolio-Risiko

**Ziel**: das in Phase 6+7 eingeführte `portfolio_pending`-Statusmodell löst korrekt auf und
verliert keine veralteten Zeilen (Rückstandsverarbeitung).

- C1/C2: Portfoliocheck-Ergebnis → `offen` bzw. `portfolio_blocked` (nicht mehr dauerhaft
  hängend in `offen`).
- C3/C4: Dead-Letter-Eskalation nach `MAX_PORTFOLIO_CHECK_ATTEMPTS`.
- C5: eine `portfolio_pending`-Zeile vom Vortag wird trotzdem geladen (rein statusbasiert,
  kein Datumsfilter).

## Suite D — Markt-Screener

**Ziel**: echte relative Stärke ggü. Referenzindex (Phase 8) statt reiner Absolutrendite,
plus das Positionsgrößen-Wertlimit (Phase 10), das direkt aus derselben Kandidaten-Pipeline
gespeist wird.

- D1: exakt Testfall D5 aus dem ursprünglichen Auftrag — positive Absolutrendite, aber
  negative relative Stärke ggü. einem stärkeren Index.
- D2: Aktie fällt weniger als der Markt in absoluten Zahlen, ist aber real schwächer relativ.
- D3-D5: `theoretical_quantity = min(quantity_by_risk, quantity_by_value)`, inkl. des Falls
  Stückzahl 0 (`QUANTITY_ZERO`-Veto).

## Suite E — Zustands-Konsistenz

**Ziel**: die in Phase 16 geprüften Idempotenz-Muster (`ON CONFLICT DO NOTHING`,
Point-in-Time-Revisionierung) verhalten sich bei einem simulierten Retry wie erwartet.

- E1: Retry mit identischem `trade_id` erzeugt keine zweite Zeile.
- E2-E4: Revisionierungsmuster — genau eine aktuelle Revision nach Retry, neue (nicht
  überschriebene) Revisionsnummer, alte Revision korrekt geschlossen.

## Suite F — Report/Dispatch

**Ziel**: `05`s Zweigzusammenführung (Phase 13) liefert immer genau eine Abschluss-Hülle mit
korrektem Status; die neuen konsolidierten Envelopes in `13`/`14` (Phase 14) fassen
Job-Ergebnisse korrekt zusammen.

- F1/F2: DRY_RUN bzw. Ablehnung → `skipped`/`failed`, kein Versand.
- F3-F5: Versand-Zweig — Erfolg, Teilausfall (`partial_failure`), vollständiger Fehlschlag.
- F6: unbekannter/fehlender Zweig → defensive Fehler-Hülle statt Absturz.
- F7-F9: `13`/`14`-Envelope — DRY_RUN-Leerlauf zählt nicht als `processed`, `skipped` bei 0
  Items, `partial_failure` bei gemischtem Ergebnis.

## Bekannte Grenzen (nicht Teil dieser Suiten)

- Keine echte n8n-Ausführung von `10`, `05`, `13`, `14` als Sub-Workflow — reale
  Seiteneffekte (OpenAI-Kosten, Matrix-/E-Mail-Sends) verhindern das ohne dedizierte
  Testumgebung; siehe Phase 12/13 für die Begründung.
- Keine Last-/Performance-Tests (Auftrag verlangt das nicht explizit).
- Keine Tests gegen eine echte Postgres-Instanz (die `ON CONFLICT`/Revisionierungs-Annahmen
  in Suite E sind Simulationen der SQL-Semantik, keine echten DB-Ausführungen) — die echten
  SQL-Migrationen selbst wurden aber bereits in den Phasen 3-14 live gegen die tatsächliche
  Datenbank ausgeführt und per Diagnose-Query verifiziert (siehe `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md`).
