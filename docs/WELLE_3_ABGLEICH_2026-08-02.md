# Welle 3 – Abgleich gegen den vollständigen Original-Auftragstext (2026-08-02)

Der Nutzer hat am 2026-08-02 den vollständigen Original-Auftragstext für Welle 3 eingefügt (vorher lag nur die Paraphrase in `OFFENE_AUFGABEN.md` vor — gleiche Situation wie beim 12-Phasen-Auftrag am 2026-07-31, siehe `docs/PHASENWEISER_ABGLEICH_2026-07-31.md`). Live-Audit gegen echten DB-Schema-Stand (`information_schema`/`pg_constraint`/`pg_indexes` via Workflow `97`, Ergebnis per `GET /executions/:id?includeData=true` statt manueller Übertragung) und echten Code-Stand (`14`, `09b`, `07`, `10`).

**Anders als beim 12-Phasen-Auftrag: die Dokumentation war hier bereits ehrlich.** AP7 (Backtesting) und AP8 (Kalibrierung) waren schon vorher transparent als "Schema fertig, Ausführungs-Workflow bewusst nicht gebaut, mangels Historie" markiert — kein Fall von "Doku sagt fertig, Code war es nicht". Trotzdem ergab der Abgleich **5 echte, bisher nicht dokumentierte Lücken**.

## Ergebnis nach Arbeitspaket

| AP | Thema | Status |
|---|---|---|
| 1 | Paper-Trading-Ledger | 🟢 vollständig — alle 26 geforderten Felder live bestätigt, Statusmodell korrekt (+1 legitime Ergänzung `data_error_final`), Ereignis-Historie, deterministische `trade_id` |
| 2+3 | Ausführung + Exit-Engine | 🟢 vollständig — konservative Modelle, alle Annahmen dokumentiert |
| 4 | Trade-Kennzahlen | 🟡 **Lücke: `financing_cost` fehlt komplett** (siehe unten) |
| 5 | Portfoliorisikomotor | 🟡 **Lücke: 3 der im Auftragstext genannten Prüfungen fehlen** (siehe unten) |
| 6 | Stressszenarien | 🟡 **Lücke: Sektor-Szenario nicht sektorspezifisch, obwohl jetzt möglich** (siehe unten) |
| 7 | Backtesting | 🟡 bewusst dormant (Auftragsvorgabe: keine Scheingenauigkeit aus zu kurzen Fenstern) — **korrekt begründet, kein Fund** |
| 8 | Kalibrierung | 🟡 bewusst dormant (0 abgeschlossene Trades) — **korrekt begründet, kein Fund** |
| 9 | Lernagent Handelsstrategien | 🟢 vollständig, diese Sitzung zusätzlich gehärtet (F6/F7/F12) |
| 10 | Versionierung | 🟡 **Lücke: nur `paper_trades` hat alle 5 Versionsfelder** (siehe unten) |
| 11 | Dashboard | 🟢 alle 5 Sektionen in `07` bestätigt |
| 12 | Report-/Prüfagent | 🟡 **Lücke: 3 der 8 Ablehnungsregeln fehlen im Prompt** (siehe unten) |
| Tests | 22 Testfälle | 🟢 18 getestet, 1 bewusst nicht umgesetzt (Trailing-Stop, laut Auftrag selbst optional), 3 schema-only mangels Daten, 1 unverändert aus Welle 1/2 übernommen |
| Migrationen | nummeriert, idempotent | 🟢 |
| Dokumentation | 7 docs/*.md | 🟢 alle vorhanden, inhaltlich akkurat |

## Die 5 gefundenen Lücken im Detail

### 1. AP4 — `financing_cost` fehlt komplett
Der Auftrag listet `financing_cost` explizit als eine der deterministisch zu berechnenden Kennzahlen. Weder `paper_trades` noch `paper_trade_costs.cost_type` kennen diesen Wert. Da das System ohne Hebelprodukt-Broker-Anbindung simuliert wird, könnte `financing_cost=0` fachlich korrekt sein (keine echte Fremdkapitalkosten-Position) — aber das ist aktuell nirgendwo als bewusste Entscheidung dokumentiert, das Feld fehlt einfach.

### 2. AP5 — drei Prüfungen aus der Auftrags-Prosaliste fehlen
Der Auftrag nennt in der Prüfliste vor den 9 explizit benannten Konfigurationswerten zusätzlich: "Exposition je Region", "Exposition je Währung", "mehrere Positionen mit gleichem Markttreiber". Live-Code-Check (`Job A`, Workflow `14`): `region` wird nur für das Regime-Lookup verwendet (Stress-Multiplikator), nicht als Expositionslimit. `waehrung`/`currency` und `markttreiber`/`driver` kommen im Code überhaupt nicht vor — keine dieser drei Prüfungen existiert als echtes Gate. (Die explizite Konfigurationsliste des Auftrags selbst enthält diese drei nicht — nur die vorangestellte Prosa-Prüfliste tut es. Da alle Bestandsticker aktuell EUR-denominiert sind, ist die Währungslücke praktisch derzeit folgenlos, aber nicht als bewusste Entscheidung festgehalten.)

### 3. AP6 — Sektor-Stressszenario trifft alle Positionen, nicht nur den Sektor
`Job C`s `sektor_minus_7pct`-Szenario wendet den Schock unabhängig vom tatsächlichen Sektor auf **alle** offenen Positionen an (Code-Kommentar bestätigt das explizit). Zum Zeitpunkt der ursprünglichen Umsetzung (2026-08-01) war das nachvollziehbar, da kein `sektor`-Feld auf `paper_trades` existierte — das wurde aber inzwischen durch Fehleranalyse E4 (2026-08-01, noch am selben Tag) nachgezogen. Das Szenario wurde seither nicht aktualisiert und ist funktional identisch zu einem weiteren Index-Schock, liefert also keinen zusätzlichen diagnostischen Wert gegenüber den bereits vorhandenen −3/−5/−10%-Szenarien.

### 4. AP10 — Versionierung nur auf `paper_trades` vollständig
Der Auftrag verlangt `rule_version`/`configuration_version`/`data_schema_version`/`execution_model_version`/`risk_model_version`/`learning_model_version` auf **jedem** Trade, Signal, Backtest und Lernvorschlag. Live-Schema-Check:
- `paper_trades`: alle 5 relevanten Felder vorhanden. ✅
- `trading.strategy_signals` (Welle 2, Signale): nur `rule_version`. `configuration_version`/`data_schema_version`/`execution_model_version`/`risk_model_version` fehlen.
- `trading.learning_rule_proposals` (Lernvorschläge, `09`+`09b`): **keines** der 5 Versionsfelder vorhanden — nur ein generischer `version`-Integer (das ist der heute eingeführte Optimistic-Locking-Zähler aus A10, kein Modell-/Regel-Versionsfeld) und ein unstrukturiertes `metadata_json`.

### 5. AP12 — 3 von 8 Ablehnungsregeln fehlen im Prüfagent-Prompt
Live-Check von `10`s "Pruef-Prompt aufbauen": vorhanden sind Fallzahl-zu-klein, Brutto-vs-Netto, OOS-fehlt, mehrdeutige Ausführungen. **Fehlen**: "Drawdown unverhältnismäßig hoch", "Kalibrierung schlecht", "wenige Einzelfälle dominieren das Gesamtergebnis". Bei den letzten beiden ist die praktische Dringlichkeit aktuell gering (Kalibrierung ist dormant, es gibt 0 Trades), aber die Regel selbst sollte trotzdem existieren — genau wie die OOS-Regel schon existiert, obwohl OOS aktuell auch immer `false` ist.

## Nicht-Funde (bewusst geprüft, kein Fund)

- Trailing-Stop: Auftragstext selbst nennt ihn "optional" innerhalb der Trend-Following-Exitregeln — bewusstes Zurückstellen ist auftragskonform, nicht nur eine Priorisierungsentscheidung des vorherigen Baus.
- AP7/AP8 dormant: Auftrags-Grundregel 8 ("Kleine Fallzahlen dürfen keine produktive Regeländerung auslösen") und die explizite `BACKTEST_MIN_WINDOW_DAYS=180`-Vorgabe rechtfertigen das Zurückstellen bei einem ~2 Wochen alten System.

## Empfehlung

Die 5 Lücken sind unterschiedlich groß: (2) und (5) sind kleine, gut abgegrenzte Ergänzungen (neue Gates/Prompt-Regeln nach etabliertem Muster). (3) ist eine kleine Code-Änderung (Sektor-Filter statt Alle-Positionen). (4) ist mittelgroß (Migrationen + Code-Änderungen an 3 Tabellen/mehreren Schreibpfaden). (1) ist eine Design-Entscheidung (Feld hinzufügen + Wert bewusst auf 0/N/A dokumentieren oder eine echte Finanzierungskosten-Formel entwerfen) und sollte zuerst geklärt werden, bevor Code entsteht.
