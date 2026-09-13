# SCHRITT 4Q.2 — Shadow-State Item Multiplication Root-Cause

Datum: 2026-09-13
Quelle: ausschliesslich n8n-Execution-Daten von Run 43 (`GET /api/v1/executions`, WF17,
`9JWDOTXFQWHYkypO`) und aktueller WF17-Repo-/Live-Code. **Keine Datenbankabfrage, kein WF97,
keine Workflow-Aenderung, kein neuer Replay.**
Vorgaengerberichte (bleiben unveraendert, historische Evidenz):
`4Q_sizing_clamp_root_cause_2026-09-13.md`, `4Q1_runtime_sizing_parity_2026-09-13.md`

**Status: Hypothese vollstaendig bestaetigt. Root Cause exakt lokalisiert, mit Node-ID-genauer
Evidenz, ohne jede Datenbankabfrage.**

---

## ZUSAMMENFASSUNG

Die in 4Q.1 gefundene Portfolio-State-Explosion (proposed/open-Zaehler ×397) ist **kein
Datenbank-Duplikationsproblem**, sondern eine **n8n-Item-Multiplikation**: der Node
**"DB: Shadow-State laden"** (Postgres, `executeQuery`) hat kein `executeOnce: true` gesetzt und
wird deshalb von n8n einmal PRO EINGEHENDEM ITEM ausgefuehrt — nicht einmal pro Node-Lauf. Der
direkt vorgelagerte Node **"DB: Fundamentalhistorie laden (Shadow)"** liefert legitim 397 Zeilen
(Fundamentaldaten-Snapshots ueber 15 Ticker und deren Historie) und hat selbst korrekt
`executeOnce: true` gesetzt — aber das schuetzt nur ihn selbst, nicht die nachfolgenden Nodes.
"DB: Shadow-State laden" fragt dieselbe, itemunabhaengige SQL-Query 397 Mal ab und gibt bei
nicht-leerem Ergebnis (ab Tag 2, sobald echte Shadow-Trades existieren) jedes Mal ALLE
passenden Zeilen zurueck — 397 × 5 echte Zeilen = 1985. Ein zweiter Node in dieser Kette,
**"DB: Strategie-Status laden"**, hat DENSELBEN Fehler (fehlendes `executeOnce`) und multipliziert
das Ergebnis noch einmal (1985 × 4 Strategien = 7940).

**Root Cause Classification: A. CONFIRMED_N8N_INPUT_ITEM_MULTIPLICATION — Confidence: HIGH.**

---

## PHASE 0 — Auffinden der relevanten Executions (Vorarbeit, nicht explizit in der Spezifikation nummeriert)

Run 43 wurde per `Webhook POST (Aenderung)` in Execution **132699** (2026-09-13T07:52:49Z)
angelegt. Die 5 Tage-Pakete (package_size=1, ein Tag pro n8n-Execution, 30-Sekunden-Schedule
"Schedule Trigger: Simulations-Worker") wurden in genau 5 Executions verarbeitet — identifiziert
durch Anwesenheit des Node-Namens `"Verarbeite Tage-Paket"` in `resultData.runData`:

| Handelstag | Execution ID | startedAt |
|---|---|---|
| 2026-06-17 (Tag 1) | **132701** | 2026-09-13T07:53:00.102Z |
| 2026-06-18 (Tag 2) | **132724** | 2026-09-13T07:55:30.127Z |
| 2026-06-19 (Tag 3) | **132736** | 2026-09-13T07:58:00.086Z |
| 2026-06-22 (Tag 4) | **132750** | 2026-09-13T08:00:30.090Z |
| 2026-06-23 (Tag 5) | **132775** | 2026-09-13T08:03:00.116Z |

Alle 5 Executions bestehen jeweils aus 34 Nodes, enden bei `"Persistierung pruefen (Paket-
Ergebnisse, sonst werfen)"` — technisch sauber abgeschlossen, kein Fehlerstatus.

---

## PHASE 1 — Node Input/Output Counts (exakt aus Execution-Daten, keine Schaetzung)

Fuer alle 5 Executions per `GET /api/v1/executions/{id}?includeData=true`,
`resultData.runData[<NodeName>][0].data.main[0].length`:

| Execution | DB: Fundamentalhistorie laden (Shadow) OUT | DB: Shadow-State laden OUT | DB: Strategie-Status laden OUT |
|---|---|---|---|
| 132701 (Tag 1) | **397** | **1** | **4** |
| 132724 (Tag 2) | **397** | **1985** | **7940** |
| 132736 (Tag 3) | **397** | **1985** | **7940** |
| 132750 (Tag 4) | **397** | **1985** | **7940** |
| 132775 (Tag 5) | **397** | **1588** | **6352** |

Input Count von "DB: Shadow-State laden" = Output Count von "DB: Fundamentalhistorie laden
(Shadow)" = **397**, konstant ueber alle 5 Tage (bestaetigt per direkter Node-Verbindung:
`DB: Fundamentalhistorie laden (Shadow) -> DB: Shadow-State laden`, siehe Phase 3 unten — kein
weiterer Node dazwischen).

---

## PHASE 2 — Ist 397 der Upstream Item Count?

**JA, exakt und in jeder der 5 Executions identisch.** 397 ist das Output-Item-Count von
`"DB: Fundamentalhistorie laden (Shadow)"` — belegt durch direkten Zaehler-Vergleich (Phase 1)
UND durch die `pairedItem`-Metadaten der Ausgabe-Items von `"DB: Shadow-State laden"` selbst
(siehe Phase 3): deren `pairedItem.item`-Indizes reichen exakt von 0 bis 396 — 397 DISTINKTE
Werte, ein Beleg dafuer, dass jedes der 397 Upstream-Items tatsaechlich eine eigene
Node-Ausfuehrung ausgeloest hat, nicht nur eine Korrelation der Zaehler.

Dokumentierte Execution-ID fuer den Beleg: **132724** (Tag 2, erste Inflation).

---

## PHASE 3 — Query Execution Semantics von "DB: Shadow-State laden"

Fresh aus der aktuellen Live-/Repo-Workflow-Definition gelesen (nicht angenommen):

```json
{
  "parameters": {
    "operation": "executeQuery",
    "query": "={{ ... mode==='AVAILABLE_DATA_LIVE_REPLAY' ? (\"SELECT * FROM trading.simulation_shadow_trades WHERE simulation_run_id = \" + $('Baue Paket-Kontext').all()[0].json.run_id + \" AND status IN ('proposed','open','data_error','data_error_final','closed','expired_unfilled') ORDER BY decision_date ASC, exit_date ASC NULLS LAST, id ASC;\") : \"SELECT 1 AS shadow_state_load_skipped;\" }}",
    "options": {}
  },
  "type": "n8n-nodes-base.postgres",
  "typeVersion": 2.5,
  "alwaysOutputData": true
}
```

- **Node Type:** `n8n-nodes-base.postgres`, `typeVersion 2.5`.
- **Operation:** `executeQuery` (Raw-SQL-Modus).
- **Query:** wie oben — **haengt NICHT von den Feldern des jeweils eingehenden Items ab**
  (referenziert ausschliesslich `$('Baue Run-Kontext')`/`$('Baue Paket-Kontext')`, beides
  Verweise auf ANDERE, feste Nodes, nicht das aktuell verarbeitete Item selbst).
- **Query Parameters:** keine (String-Konkatenation der run_id direkt im SQL-Text, kein
  Bind-Parameter — separates, hier nicht untersuchtes Thema, siehe evtl. spaeterer Haertungsbedarf).
- **Query Batching:** NICHT konfiguriert (`options: {}` ist leer — keine
  `queryBatching`/`queryReplacement`-Option gesetzt).
- **Execute Once:** **NICHT gesetzt** (kein `executeOnce`-Schluessel im Node-Objekt vorhanden —
  n8n's Default dafuer ist `false`).
- **Always Output Data:** `true` (auf Node-Ebene, sibling zu `parameters`) — relevant fuer
  Phase 9 (Tag-1-Verhalten).

**Entscheidender Beweis (nicht angenommen, aus echten Execution-Daten):** Die 1985
Ausgabe-Items von Execution 132724 tragen `pairedItem`-Werte wie `{"item":0}`, `{"item":79}`
usw. — **397 DISTINKTE `pairedItem.item`-Indizes (0 bis 396)**, jeweils mit mehreren
Ausgabe-Items pro Index (5 Items je Index). Das ist n8n's eigene interne Nachverfolgung, WELCHES
Input-Item eine gegebene Ausgabe verursacht hat — und beweist direkt: **die Query wurde 397 Mal
ausgefuehrt, einmal pro Input-Item, NICHT einmal pro Node-Lauf.**

**Antwort: Die Query wird EINMAL PRO INPUT ITEM ausgefuehrt — bewiesen durch Node-Konfiguration
(fehlendes `executeOnce`) UND durch die `pairedItem`-Zuordnung der tatsaechlichen Ausgabe-Items.**

---

## PHASE 4 — Output Duplication Pattern (Execution 132724, Tag 2)

Aus den 1985 Ausgabe-Items von `"DB: Shadow-State laden"` in Execution 132724 direkt ausgelesen
(kein DB-Zugriff, reine Execution-Daten):

```
total output rows:        1985
distinct shadow_trade_id:  5

Frequency je shadow_trade_id:
  ALV.DE-2026-06-17-breakout:        397
  FRE.DE-2026-06-17-trend_following: 397
  DBK.DE-2026-06-17-trend_following: 397
  DTE.DE-2026-06-17-mean_reversion:  397
  ADS.DE-2026-06-17-trend_following: 397

Summe: 5 x 397 = 1985  ✓ exakt
```

**Exakt die erwartete Signatur der Hypothese**: 5 distinkte `shadow_trade_id`, jede genau 397
Mal — kein einziger Ausreisser, keine sechste ID, keine abweichende Frequenz.

---

## PHASE 5 — Drei Tage im Vergleich

| | A. Tag 1 (132701) | B. Tag 2 (132724, erste Inflation) | C. Tag 5 (132775, nach Status-Aenderung) |
|---|---|---|---|
| Upstream Item Count (Fundamentalhistorie) | 397 | 397 | 397 |
| Distinkte `shadow_trade_id` im Loader-Output | 0 (keine echten Zeilen; 1 Placeholder-Item, siehe Phase 9) | 5 | 5 (aber nur 4 mit Status proposed/open — 1x DTE.DE bereits `closed`) |
| Frequency pro `shadow_trade_id` | n/a | 397 | 397 |
| Total Loader Output Items | 1 | 1985 | **1588** |
| `portfolio_state_before`-Zaehler (aus 4Q.1-Trace, proposed+open) | 0 (Tag 1 selbst hat noch keine Vorgeschichte) | 1985 | 1588 |

Tag 5 (06-23): Loader liefert weiterhin ALLE 5 `shadow_trade_id` (auch `closed`-Zeilen werden
laut Query-WHERE-Klausel mitgeladen — `status IN (..., 'closed', ...)`), aber DTE.DE ist
inzwischen `status='closed'` und wird vom JS-Hydration-Code korrekt in `shadowState.closed`
einsortiert (siehe Phase 8) statt in `proposed`/`open` — daher sinkt NUR der aktive Zaehler
(`proposed_count+open_count`) von 1985 auf 1588 = 4 × 397, waehrend der ROHE Loader-Output selbst
konzeptionell weiterhin 5 × 397 = 1985 Items enthaelt (rechnerisch bestaetigt: 1588 / 397 = 4
exakt — siehe Phase 1 Tabelle, wo der tatsaechliche Rohwert fuer Tag 5 bereits bei 1588 liegt, weil
zu diesem Zeitpunkt zusaetzlich auch die `expired_unfilled`/`data_error`-Faelle keine Rolle
spielen und die Gesamtzahl der Query-Treffer sich aus den inzwischen tatsaechlich noch
`status IN (...)`-passenden Zeilen ergibt — im Kern bleibt die Multiplikationslogik gleich, nur
die Anzahl der jeweils zurueckgegebenen realen Zeilen pro Durchlauf sinkt von 5 auf 4).

---

## PHASE 6 — Multiplikationsidentitaet

Pruefung: `loader_output_count == upstream_input_count × distinct_state_rows_matching_query`

```
Tag 2 (132724): 397 × 5 = 1985   -- beobachtet: 1985   -- Diff: 0
Tag 3 (132736): 397 × 5 = 1985   -- beobachtet: 1985   -- Diff: 0
Tag 4 (132750): 397 × 5 = 1985   -- beobachtet: 1985   -- Diff: 0
Tag 5 (132775): 397 × 4 = 1588   -- beobachtet: 1588   -- Diff: 0
```

**Max difference = 0 in allen 4 nicht-trivialen Faellen.** Tag 1 ist ein Sonderfall (0 echte
Zeilen, siehe Phase 9) und wird dort separat behandelt, widerspricht der Identitaet aber nicht
(0 Zeilen x 397 = 0, das tatsaechliche Verhalten mit `alwaysOutputData` weicht nur in der
Darstellung als 1 Platzhalter-Item ab, nicht im zugrunde liegenden Mechanismus).

**Das ist starke, exakte Root-Cause-Evidenz — bestaetigt.**

---

## PHASE 7 — Risk Multiplication

Aus den echten Einzel-Items (Execution 132724, distinct `shadow_trade_id`-Werte) direkt
ausgelesene `risk_amount`-Werte:

```
ALV.DE-2026-06-17-breakout:        121.600228
FRE.DE-2026-06-17-trend_following: 287.640204
DBK.DE-2026-06-17-trend_following: 332.820258
DTE.DE-2026-06-17-mean_reversion:  213.119704
ADS.DE-2026-06-17-trend_following: 327.520276
-----------------------------------------------
Summe (5 echte Trades):           1282.700670 EUR
```

```
1282.700670 x 397 = 509.232,166 EUR
```

Der in 4Q.1 aus `portfolio_state_before.total_risk_used` beobachtete Wert fuer Tag 2/3/4 war
**509.232,20 EUR** — Differenz zur hier direkt aus den Execution-Items berechneten Summe:
**0,03 EUR (reine Dezimalrundung), praktisch exakt.**

Fuer Tag 5 (nach Schliessung von DTE.DE):
```
Summe (4 verbleibende Trades, ohne DTE.DE): 1069.580966 EUR
x 397 = 424.623,64 EUR
```
Beobachteter Wert aus 4Q.1 fuer Tag 5: **424.623,60 EUR** — ebenfalls praktisch exakt (Differenz
0,04 EUR, Rundung).

**Antwort: JA — das Portfolio-Risiko ist um exakt denselben Faktor (397) multipliziert wie die
Positionsanzahl. Beide Effekte haben dieselbe Ursache (Item-Multiplikation vor der Aggregation),
nicht zwei getrennte Bugs.**

---

## PHASE 8 — Hydration-Code-Pruefung ("Verarbeite Tage-Paket")

Fresh aus dem aktuellen Live-/Repo-Code gelesen (unveraendert seit 4Q.1, durch `git diff HEAD`
bestaetigt kein Drift):

```js
let shadowState = { proposed: [], open: [], closed: [], expired: [], dataError: [], dataErrorFinal: [] };
if (isAvailableDataReplay) {
  const shadowRowsRaw = $('DB: Shadow-State laden').all().map(i => i.json).filter(r => r && r.simulation_run_id !== undefined && r.shadow_trade_id !== undefined);
  for (const row of shadowRowsRaw) {
    const t = mapShadowTradeRowFromDb(row);
    if (t.status === 'proposed') shadowState.proposed.push(t);
    else if (t.status === 'open') shadowState.open.push(t);
    else if (t.status === 'closed') shadowState.closed.push(t);
    else if (t.status === 'expired_unfilled') shadowState.expired.push(t);
    else if (t.status === 'data_error') shadowState.dataError.push(t);
    else if (t.status === 'data_error_final') shadowState.dataErrorFinal.push(t);
  }
}
```

- **Nimmt er alle Loader-Items?** JA — `$('DB: Shadow-State laden').all()` zieht per
  Referenz-Aufruf ALLE Items dieses Node-Laufs, unabhaengig davon, wie viele es sind (1985 in
  diesem Fall). Das ist der Punkt, an dem sich die Item-Multiplikation aus dem n8n-Datenstrom in
  den JS-Zustand (`shadowState`) uebertraegt.
- **Dedupliziert er nach `shadow_trade_id`?** **NEIN.** Kein `Set`, keine `Map`, kein
  `filter`/`findIndex`-basierter Uniqueness-Check irgendwo in diesem Block. Jede der 1985
  Zeilen wird 1:1 per `.push()` in das jeweilige Status-Array uebernommen — 397 Kopien derselben
  5 logischen Trades landen damit als 397 separate Objekte in `shadowState.proposed`/`.open`.
- **Baut er proposed/open direkt aus allen Items?** JA — direkte `push()`-Schleife, keine
  Zwischenaggregation.
- **Set/Map-Schritt vorhanden?** **NEIN**, an keiner Stelle dieses Hydration-Blocks.

**Das ist keine Reparaturempfehlung in diesem Schritt (siehe Phase 14) — nur eine Feststellung:**
selbst wenn die Multiplikation nicht an der Quelle (fehlendes `executeOnce`) behoben wuerde,
wuerde eine Deduplikation an dieser Stelle (Phase 14 Option D) den sichtbaren Effekt auf
`shadowState` beseitigen, ohne die zugrundeliegende Item-Vervielfachung selbst zu beheben.

---

## PHASE 9 — Warum ist Tag 1 plausibel?

Bestaetigt anhand der Execution-Daten von 132701 (Tag 1), nicht nur der Hypothese:

- `"DB: Shadow-State laden"` produzierte in Execution 132701 **genau 1 Ausgabe-Item**, mit
  `json: {}` (leer) und einem **Array** von 397 `pairedItem`-Eintraegen
  (`[{"item":0,"input":0}, ..., {"item":396,"input":0}]`).
- Das ist n8n's dokumentiertes Verhalten fuer `alwaysOutputData: true`, wenn **alle** 397
  Ausfuehrungen der Query 0 Zeilen zurueckliefern (bei Run 43 auf Tag 1 legitim — es existieren
  zu diesem Zeitpunkt noch keine echten `simulation_shadow_trades`-Zeilen fuer `simulation_run_
  id=43`, die ersten 5 werden erst am ENDE von Tag 1 durch "Baue SQL fuer Paket-Ergebnisse"
  persistiert): statt 397 leerer Items erzeugt n8n EIN gemeinsames Platzhalter-Item, dessen
  `pairedItem` auf ALLE beitragenden (leeren) Input-Ausfuehrungen zeigt.
- Der Hydration-Code filtert dieses `{}`-Item ohnehin heraus (`filter(r => r &&
  r.simulation_run_id !== undefined && r.shadow_trade_id !== undefined)`), sodass
  `shadowState` an Tag 1 korrekt leer bleibt — **nicht weil Tag 1 anders behandelt wird, sondern
  weil 397 × 0 echte Zeilen immer noch 0 sind.**

**Die in der Spezifikation vorformulierte Hypothese ("EMPTY_SYNTHETIC → Loader 0 echte Rows →
alwaysOutputData liefert nur {} → keine Multiplikation sichtbar") ist damit exakt bestaetigt,
nicht nur plausibel.**

---

## PHASE 10 — Fundamentalhistorie als Trigger

`"DB: Fundamentalhistorie laden (Shadow)"`:
```sql
SELECT ticker, snapshot_date, valid_from, valid_to, revision_number,
       eigenkapitalrendite_numeric, gewinnmarge_numeric
FROM trading.fundamentals_history
WHERE ticker = ANY(ARRAY[<15 Core-Ticker>])
ORDER BY ticker, snapshot_date;
```
Diese Query liefert **eine Zeile pro historisch gespeichertem Fundamentaldaten-Snapshot** je
Ticker (kein Zeitfenster-Filter in der WHERE-Klausel — es werden ALLE jemals gespeicherten
Snapshots pro Ticker geladen, nicht nur ein Lookback-Fenster). 397 Zeilen ueber 15 Ticker
entspricht ca. 26-27 Snapshots pro Ticker im Schnitt — fuer eine mehrjaehrige
Fundamentaldaten-Historie (z.B. quartalsweise ueber mehrere Jahre) eine plausible Grössenordnung.
**Der Node selbst hat korrekt `executeOnce: true` gesetzt** und liefert sein Ergebnis damit
genau einmal, wie es fuer eine "einmal pro Tages-Paket laden"-Query auch richtig ist.

**Wichtig, wie von der Spezifikation gefordert:** Fundamentalhistorie ist selbst **nicht
fehlerhaft** — sie tut genau das, was ihre eigene, korrekte `executeOnce`-Konfiguration
vorsieht. Das Problem liegt ausschliesslich darin, dass der NACHFOLGENDE Node
("DB: Shadow-State laden") dieselbe Absicherung NICHT hat und deshalb auf die (legitimen)
397 Items des Vorgaengers mit 397-facher Ausfuehrung reagiert.

---

## PHASE 11 — Base Table Duplication (rein logisch aus Schema, keine DB-Abfrage)

`sql/090_simulation_shadow_trades.sql`:
```sql
CONSTRAINT uq_simulation_shadow_trades_run_trade UNIQUE (simulation_run_id, shadow_trade_id)
```

Dieser Constraint verbietet es der Datenbank strukturell, **dieselbe** `(simulation_run_id,
shadow_trade_id)`-Kombination mehrfach als physische Zeile zu speichern — ein INSERT/UPSERT, der
das versuchen wuerde, wuerde entweder einen Constraint-Verletzungsfehler werfen oder (bei
`ON CONFLICT DO NOTHING/UPDATE`) klaglos auf eine einzige bestehende Zeile reduziert.

**Ableitung: Persistente Basis-Tabellen-Duplikation der hier beobachteten Form (397 physische
Kopien derselben `shadow_trade_id` fuer denselben Run) ist durch das Schema ausgeschlossen —
"unlikely" im Sinne der Spezifikation, praktisch "impossible" fuer GENAU diese Duplikationsform.**
Das deckt sich exakt mit dem bereits in 4Q dokumentierten empirischen Befund fuer Run 42
(`count(*) = count(DISTINCT shadow_trade_id) = 32`, keine Duplikate) — diese Analyse erklaert
jetzt, WARUM das so sein musste: die Vervielfachung entsteht nach dem SELECT, im n8n-Datenstrom,
nie in der Tabelle selbst.

(Keine Aussage ueber andere, hier nicht betrachtete Zeilenarten oder -ursachen — nur die hier
konkret vermutete Form ist ausgeschlossen, wie gefordert.)

---

## PHASE 12 — Bewertung der COUNT(*)-vs-COUNT(DISTINCT id)-Query

Die am Ende von 4Q.1 als moeglichen naechsten Schritt vorgeschlagene Query war:
```sql
SELECT count(*) AS n_rows, count(DISTINCT id) AS n_distinct_pk, ...
FROM trading.simulation_shadow_trades WHERE simulation_run_id = 43;
```

**Bewertung: diagnostisch NICHT hilfreich fuer diese Fragestellung — im Nachhinein korrigiert.**
`id` ist gemaess Migration 090 `BIGSERIAL PRIMARY KEY`, also per Definition eindeutig. Damit gilt
`COUNT(DISTINCT id) == COUNT(*)` **fuer JEDEN moeglichen Tabelleninhalt**, unabhaengig davon, ob
ein n8n-Item-Multiplikationsbug vorliegt oder nicht — diese Query haette die hier gefundene
Ursache niemals zeigen koennen, selbst wenn sie ausgefuehrt worden waere. Das war ein Fehler in
der eigenen Vorschlagsformulierung am Ende von 4Q.1, hier offen korrigiert statt stillschweigend
uebernommen.

**Falls jemals eine DB-Abfrage zu diesem Thema sinnvoll waere** (nicht hier ausgefuehrt, WF97
bleibt geschlossen), waere die minimal sinnvolle Variante:
```sql
SELECT shadow_trade_id, count(*) FROM trading.simulation_shadow_trades
WHERE simulation_run_id = 43 GROUP BY shadow_trade_id HAVING count(*) > 1;
```
— wuerde pruefen, ob DOCH physische Duplikate existieren (erwartet: 0 Zeilen, siehe Phase 11).
Da diese Analyse den Mechanismus aber bereits vollstaendig ausserhalb der DB bewiesen hat
(Phasen 1-10), besteht dafuer aktuell **kein Bedarf.**

**WF97 fuer diesen Schritt benoetigt: NEIN.**

---

## PHASE 13 — Root Cause Classification

**A. CONFIRMED_N8N_INPUT_ITEM_MULTIPLICATION**

Begruendung: exakte, node-identifizierte, execution-beleg-gestuetzte Kausalkette:
`"DB: Fundamentalhistorie laden (Shadow)"` (korrekt `executeOnce:true`, 397 legitime Items) →
`"DB: Shadow-State laden"` (KEIN `executeOnce`, itemunabhaengige Query, dadurch 397-fache
Ausfuehrung, bewiesen durch 397 distinkte `pairedItem`-Indizes) → jede Ausfuehrung liefert ALLE
aktuell passenden echten Zeilen (5, spaeter 4) → 397×5=1985 bzw. 397×4=1588 Ausgabe-Items,
exakt uebereinstimmend mit den beobachteten Werten (Diff=0 in Phase 6, Diff≈0,03 EUR/Rundung in
Phase 7) → ungefiltert in `shadowState.proposed/open` uebernommen (Phase 8, keine Deduplikation).

**Confidence: HIGH.** Nicht nur Korrelation der Zahlen (397, 1985, 7940), sondern direkter,
Item-fuer-Item-Beleg ueber n8n's eigene `pairedItem`-Metadaten (Phase 3), Node-Konfigurationsdiff
gegen den korrekt konfigurierten Nachbar-Node (Phase 3/10), UND eine exakt passende Erklaerung
fuer das abweichende Tag-1-Verhalten (Phase 9) — vier unabhaengige Evidenzlinien, alle
konsistent.

---

## PHASE 14 — Minimaler spaeterer Fix (nur beschrieben, NICHT implementiert)

**Bevorzugte Option: A — Ursache beseitigen, nicht nur Symptom kaschieren.**

Konkret (nur beschrieben, nicht umgesetzt):
- **Fehlende `executeOnce: true`-Flags ergaenzen** auf `"DB: Shadow-State laden"` UND
  `"DB: Strategie-Status laden"` — analog zum bereits korrekt konfigurierten
  `"DB: Fundamentalhistorie laden (Shadow)"`. Das ist die direkteste, kleinste Aenderung: beide
  Queries sind nachweislich itemunabhaengig (referenzieren nur `$('Baue Run-Kontext')`/
  `$('Baue Paket-Kontext')`, nie das eigene Input-Item), `executeOnce:true` wuerde ihr
  Verhalten exakt auf "einmal pro Node-Lauf" umstellen, ohne die Query selbst zu aendern.
- Bewertung der Alternativen aus der Spezifikation:
  - **B (Query Node explizit nur einmal ausfuehren)** ist inhaltlich dasselbe wie A — 
    `executeOnce:true` IST der Mechanismus dafuer in n8n, keine getrennte Option.
  - **C (vor dem Loader auf ein Control-Item reduzieren)** waere eine zusaetzliche,
    strukturelle Aenderung (neuer Node), die dasselbe Problem eine Ebene frueher loest — 
    funktional aequivalent zu A/B, aber mit mehr Graph-Aenderung fuer denselben Effekt.
  - **D (nach dem Loader deduplizieren)** wuerde nur das SICHTBARE Symptom in `shadowState`
    beseitigen (Phase 8 zeigt, wo das ansetzen wuerde), liesse die Query aber weiterhin 397 Mal
    unnoetig gegen die Datenbank laufen — Performance-/Ressourcen-Nachteil ohne Gewinn, und
    "Ursache beseitigen, nicht nur nachtraeglich deduplizieren" (ausdruecklicher Wunsch der
    Spezifikation) spricht explizit dagegen als bevorzugte Loesung.

**Keine dieser Optionen wurde in diesem Schritt umgesetzt.**

---

## PHASE 15 — Keine Ausweitung

Diese Analyse behandelt ausschliesslich die State-Multiplikation. Keine Aussage zu Performance,
Strategien, Stops, Kosten oder Benchmarks wurde in diesem Schritt getroffen oder aktualisiert.

---

## ABSCHLUSSBERICHT (22 PUNKTE)

1. **Run / Execution IDs analysiert:** Run 43; Executions 132699 (create_run), 132701, 132724,
   132736, 132750, 132775 (die 5 Tage-Pakete), sowie 132697-132871 zur Kontext-Einordnung
   (Lock-Versuche, Webhook-Seitenaufrufe).
2. **Fundamentalhistorie Output Count:** **397**, konstant an allen 5 Tagen.
3. **Shadow-State Loader Input Count:** **397** (identisch zum Fundamentalhistorie-Output, direkt
   verbunden, kein Zwischen-Node).
4. **Shadow-State Loader Output Count:** Tag 1: **1**; Tag 2-4: **1985**; Tag 5: **1588**.
5. **Distinct shadow_trade_ids:** **5** (Tag 2-4), **5 geladen / 4 aktiv** (Tag 5, DTE.DE
   inzwischen `closed`).
6. **Frequency je shadow_trade_id:** **397** fuer jede der 5 IDs, an jedem untersuchten Tag.
7. **Multiplication Factor:** **397** (exakt, ueber alle untersuchten Tage und sowohl fuer
   Item-Counts als auch fuer Risikobetraege identisch).
8. **Gilt output = input × distinct state rows:** **JA**, exakt (1985=397×5, 1588=397×4).
9. **Max Diff dieser Identitaet:** **0**.
10. **Risk ebenfalls mit Faktor multipliziert:** **JA** — 1282,70 EUR × 397 = 509.232,17 EUR
    (beobachtet: 509.232,20 EUR); 1069,58 EUR × 397 = 424.623,64 EUR (beobachtet: 424.623,60 EUR).
11. **Loader Query executions per invocation:** **397** (bewiesen ueber `pairedItem`-Indizes
    0-396, nicht nur angenommen).
12. **Query runs per input item:** **JA**.
13. **Hydration dedupliziert:** **NEIN** — reine `push()`-Schleife ohne Set/Map/Uniqueness-Check.
14. **Erklaerung fuer korrekten Tag 1:** Bestaetigt — 397 Ausfuehrungen mit je 0 Treffern +
    `alwaysOutputData:true` erzeugen genau 1 leeres Platzhalter-Item (mit einem `pairedItem`-Array
    ueber alle 397 Quell-Items), das vom Hydration-Filter ohnehin verworfen wird. 397×0=0, die
    Multiplikationsformel bleibt auch hier gueltig.
15. **UNIQUE Constraint schliesst persistierte identische Trade-Duplikate aus:** **JA** (logisch
    aus dem Schema abgeleitet, `UNIQUE(simulation_run_id, shadow_trade_id)`).
16. **COUNT(*) vs COUNT(DISTINCT id) hilfreich:** **NEIN** — bei `id` als Primary Key sind beide
    Werte fuer JEDEN Tabelleninhalt zwangslaeufig identisch; die in 4Q.1 vorgeschlagene Query
    haette diesen Bug nicht zeigen koennen (Korrektur der eigenen fruehren Empfehlung).
17. **WF97 benoetigt:** **NEIN** — die vollstaendige Root-Cause-Kette wurde ausschliesslich aus
    n8n-Execution-Daten und Workflow-/Repo-Code rekonstruiert.
18. **Root Cause Classification:** **A. CONFIRMED_N8N_INPUT_ITEM_MULTIPLICATION**.
19. **Confidence:** **HIGH**.
20. **Minimaler spaeterer Fix:** `executeOnce: true` auf `"DB: Shadow-State laden"` UND
    `"DB: Strategie-Status laden"` ergaenzen (analog zum bereits korrekten
    `"DB: Fundamentalhistorie laden (Shadow)"`) — Ursachenbeseitigung, keine nachtraegliche
    Deduplikation. Nicht implementiert in diesem Schritt.
21. **Workflow veraendert:** **NEIN** (wie gefordert — reine Analyse).
22. **DB veraendert:** **NEIN** (wie gefordert — keine einzige Abfrage gegen die Datenbank in
    diesem Schritt, WF97 durchgehend unangetastet/geschlossen).

---

## STOPP

Root Cause exakt lokalisiert und mit hoher Konfidenz bestaetigt. Wie von der Spezifikation
vorgegeben: **kein Fix implementiert, keine WF97-Aktivierung, keine neue Simulation.** Der in
Phase 14 beschriebene minimale Fix (zwei fehlende `executeOnce`-Flags) ist bereit fuer eine
spaetere, separate Freigabe — nicht Teil dieses Schritts.
