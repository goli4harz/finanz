# Testergebnisse — Härtung Welle 1-3 (Phase 17)

Letzter Lauf: 2026-08-02, `node tests/welle_1_3_testsuite.js`.

## Ergebnis

| Suite | Bestanden | Fehlgeschlagen | Gesamt |
|---|---|---|---|
| A — Merge/Load-Sicherheit | 4 | 0 | 4 |
| B — Paper-Trading | 8 | 0 | 8 |
| C — Portfolio-Risiko | 5 | 0 | 5 |
| D — Markt-Screener | 5 | 0 | 5 |
| E — Zustands-Konsistenz | 4 | 0 | 4 |
| F — Report/Dispatch | 9 | 0 | 9 |
| **Gesamt** | **35** | **0** | **35** |

Rohausgabe des Laufs:

```
=== Suite A - Merge/Load-Sicherheit (kein Kreuzprodukt, kein Warten auf nie feuernden Zweig) ===
  4 bestanden, 0 fehlgeschlagen

=== Suite B - Paper-Trading (data_error-Retry, Gap-through-Stop) ===
  8 bestanden, 0 fehlgeschlagen

=== Suite C - Portfolio-Risiko (Empfehlung/Portfolioveto-Statusmodell) ===
  5 bestanden, 0 fehlgeschlagen

=== Suite D - Markt-Screener (relative Staerke vs. Referenzindex) ===
  5 bestanden, 0 fehlgeschlagen

=== Suite E - Zustands-Konsistenz (Idempotenz bei Retry) ===
  4 bestanden, 0 fehlgeschlagen

=== Suite F - Report/Dispatch (Zweigsicherheit 05, konsolidierte Envelopes 13/14) ===
  9 bestanden, 0 fehlgeschlagen

=== Gesamtergebnis: 35 bestanden, 0 fehlgeschlagen (von 35) ===
```

## Einordnung

Alle 35 Tests bestanden. Das ist eine **notwendige, aber keine hinreichende** Bedingung für
eine Freigabe — die Suiten prüfen Node-Nachbildungen der Kernfunktionen, keine echten
End-to-End-Ausführungen der n8n-Workflows selbst (siehe `TESTPLAN_HAERTUNG_WELLE_1_3.md`,
Abschnitt "Bekannte Grenzen"). Ergänzend dazu wurden während der Phasen 4/5/8/9/10 bereits
gezielte inline-lokale Tests durchgeführt und einzeln in `FEHLERANALYSE_HAERTUNG_WELLE_1_3.md`
protokolliert; diese Datei bündelt die wichtigsten Fälle in einer wiederholbaren Form, ersetzt
das Detailprotokoll dort aber nicht.

Live-Verifikationen, die tatsächlich stattgefunden haben (nicht nur simuliert):
- Alle SQL-Migrationen `sql/051`-`sql/056` live ausgeführt und per Diagnose-Query bestätigt.
- `07`s Dashboard-Fix (Phase 12) live über den echten Webhook getestet (inkl. eines dabei
  gefundenen und behobenen Laufzeitfehlers).
- `02`s Signal-Härtung und `05`s Hebelprodukt-Entfernung live gepusht (aktive Workflows,
  reine Verschärfung/Textentfernung, kein struktureller Regressionsvektor).

Für eine Produktionsfreigabe von Paper-Trading (`14`) fehlen weiterhin — wie in den
Sicherheitsregeln des Auftrags explizit gefordert — ausreichend abgeschlossene Paper Trades
und ein belastbares Out-of-Sample-Verfahren; das ist keine Frage des Testsuiten-Ergebnisses,
sondern der in `AKTIVIERUNGSPLAN_PAPER_TRADING.md` beschriebenen Beobachtungsphase.
