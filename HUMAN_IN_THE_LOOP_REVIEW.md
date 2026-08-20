# HUMAN_IN_THE_LOOP_REVIEW.md

Stand: 2026-08-20. Phase 1 (Bestandsaufnahme) des Human-in-the-Loop-Auftrags. Basiert auf
systematischer Durchsuchung aller root-level Workflow-JSONs, aller `sql/*.sql`-Migrationen, aller
`docs/*.md`-Dateien und Live-Code-Analyse (Node-Ebene, nicht nur Doku). **Noch nichts wurde
verändert oder implementiert** — reine Analyse, wie im Auftrag verlangt.

---

## Zusammenfassung

Das System ist für diesen Auftrag ungewöhnlich gut vorbereitet. Die Kernaussage vorweg: **die
fehlende Ebene ist fast ausschließlich die Entscheidungsschicht selbst — nicht das Datenmodell,
nicht die Risikologik, nicht die Berechnungen.** Entry/Stop/Target/CRV/Positionsgröße/
Portfolio-Auswirkung/Audit-Snapshot liegen bereits vollständig oder fast vollständig im Schema.
Was fehlt, ist eine Web-Oberfläche mit Annehmen/Ablehnen/Beobachten, eine Trennung
Systemvorschlag/Nutzerentscheidung, ein Trade-Review-Freitext, eine Gegenargumente-Anzeige und
ein False-Negative-Mechanismus für News.

**Die zehn wichtigsten Einzelfunde:**

1. **Ein fertiges, produktiv laufendes Bau-Muster existiert bereits**: Workflow 12
   ("Lernvorschlag-Freigabe", heute in dieser Sitzung selbst auf einen zweistufigen
   `proposed→approved→activated`-Flow umgebaut) implementiert exakt das gesuchte Muster —
   GET-Ansicht + POST-Aktion auf demselben Webhook-Pfad, serverseitig gerenderte Formulare (kein
   JS-Framework), `status`/`reviewed_at`/`reviewed_by`/`version`-Spalten, optimistisches Locking
   gegen Race Conditions. Dieses Muster lässt sich strukturell direkt auf Empfehlungen/Paper-Trades
   übertragen.
2. **Das "historische Vergleichsfälle"-Modul ist bereits vollständig spezifiziert, aber nie
   ausgeführt**: `trading.probability_estimates`/`calibration_checks` (sql/037,
   `docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md`) — merkmalsbasierte Segmentierung (Strategie ×
   Richtung × Marktregime × Risiko-/Evidenz-Bucket × Zeithorizont), Wilson-Score-Konfidenzintervall,
   explizit **kein** KI-Ersatzwert bei Datenmangel (`probability_status='insufficient_data'`
   statt Scheingenauigkeit) — genau das, was der Auftrag fordert. Bisher dormant, weil zu wenige
   abgeschlossene Paper-Trades vorlagen (0 Stand 2026-08-01). Mit den seither entstandenen
   `simulation_trades`-Daten (72+ Trades in einzelnen Testläufen) könnte die Datengrundlage jetzt
   ausreichen — die Formeln beziehen sich aktuell aber nur auf `paper_trades`, nicht auf
   `simulation_trades`.
3. **Zwei fertige, aber ungenutzte Korrektur-Haken für News existieren bereits im Schema**:
   `trading.news_assessments.confirmation_status` (`unconfirmed`/`manually_confirmed`/
   `manually_rejected`, sql/012) — die Consumer-View `v_news_latest_assessment` priorisiert
   manuelle Bestätigungen bereits korrekt, aber **kein Workflow beschreibt die Spalte**. Und
   `trading.news_items.reprocess_requested` (sql/010, "erzwingt erneute Recherche") — ebenfalls von
   keinem Workflow gelesen oder geschrieben.
4. **Ein False-Negative-Mechanismus für News existiert nirgends im System** — bestätigt durch
   repo-weite Suche. Der Regex-Vorfilter in Workflow 03 verwirft Artikel sogar komplett, ohne sie
   überhaupt zu persistieren (kein `discarded`-Status, keine Zeile, keine Wiederauffindbarkeit).
   Das ist die größte strukturelle Lücke im gesamten Auftrag.
5. **Der Lernagent (09b) erzeugt aktuell strukturell keine Vorschläge**: Das
   Out-of-Sample-Bestätigungs-Gate (eines von vier Pflicht-Gates) ist immer leer, weil bislang kein
   passender `run_type='out_of_sample'`-Lauf je Strategie existiert. Operativ relevant: eine
   "Lernvorschläge prüfen"-Kachel wäre heute leer — nicht wegen einer UI-Lücke, sondern weil die
   Vorstufe nichts liefert.
6. **Drei unterschiedliche Versionierungsstile für Regeln existieren bereits parallel** im System:
   voll versioniert mit History (`scoring_weights`, `strategy_regime_matrix` seit heute),
   einfacher In-Place-Zähler (`strategy_parameters`), reines Flag ohne Historie
   (`strategy_status`). Alle referenzieren einheitlich `source_proposal_id →
   learning_rule_proposals(id)` als Audit-Rückverweis — das eigentlich wiederverwendbare Element.
7. **Die Navigationsleiste ist in jeder Webhook-Seite hart einkopiert**, nicht zentral gepflegt
   (kein gemeinsamer Sub-Workflow wie im Schwesterprojekt ALLRIS). Eine neue Seite erfordert
   Änderungen an mehreren Stellen gleichzeitig — Wartungsrisiko für die geplante neue
   Startseiten-Navigation.
8. **Es gibt kein "Systemstatus: OK"-Konzept.** `trading.workflow_errors` (Workflow 11) wird
   ausschließlich beschrieben, nie gelesen — für die geforderte Startseiten-Kachel
   "Systemstatus: OK" müsste diese Tabelle erstmals abgefragt werden.
9. **Schema-Drift bei den News-Ausschlussregeln**: `trading.news_match_exclusions`/
   `_candidates`/`_hits` (Basis des einzigen bestehenden False-Positive-Freigabe-Workflows, 16c/16d)
   existieren live in der DB, aber **nicht** als `sql/*.sql`-Migration im Repo — am 2026-08-16
   nachträglich nur als JSON-Export synchronisiert. Sollte bei Gelegenheit nachgezogen werden.
10. **Hebelprodukt-Felder existieren bereits im Schema, sind aber inhaltlich deaktiviert**:
    `hebelprodukt_typ`, `hebel_spanne`, `basispreis_hebel_3/4`, `onvista_link`,
    `hebelprodukt_hinweis` (seit sql/007) — die texterzeugende Funktion wurde in einer früheren
    Härtungsrunde neutralisiert (liefert laut Code-Kommentar nur noch `''`).

---

## 1. Welche benötigten Bausteine existieren bereits? (je Modul aus dem Auftrag)

### Modul 1 — Heutige Handelsvorschläge / Entscheidungssheet

| Anforderung | Vorhanden? | Fundstelle |
|---|---|---|
| Ticker/Richtung/Strategie | ✅ | `trading.recommendations.ticker/richtung/strategy` |
| Entry-Zone + Entry-Begründung | ✅ | `entry_zone_low/high` (sql/033), `entry_grund` (sql/007), `trade_thesis` (sql/030) |
| Stop (deterministisch, ATR-basiert) | ✅ | `stop_price` (sql/017), Formel in `docs/RISIKOMODELL_EINZELTRADE.md` |
| Trailing Stop | ⚠️ nur in Simulation | `simulation_trades.extreme_price_since_entry` (WF17) — **im Live-Pfad (06/14) existiert kein Trailing-Stop** |
| Target + CRV | ✅ | `target_price`, `reward_risk_ratio` (bereits in `aktien-status` als Spalte "CRV" angezeigt) |
| Haltedauer | ✅ | `expected_holding_days` (sql/017), `time_stop_at`/`thesis_expires_at` |
| Positionsgröße aus max. Verlust | ✅ | vollständige Formel in `docs/RISIKOMODELL_EINZELTRADE.md`, Felder `theoretical_quantity/risk_amount/position_value/max_planned_loss` |
| Portfolio-Kontext (Sektor/Region/Exposure) | ✅ | `trading.portfolio_risk_checks` (alle 9 Limits, sql/036), zurückgeschrieben auf `recommendations.portfolio_risk_before/after` (sql/053) |
| Strukturierte Begründung (Technik/News/Fundamental/Regime/Risiko) | ✅ (Rohdaten) | `opportunity_score/risk_score/evidence_confidence` + Detail-JSONBs (sql/033) — **die zusammenfassende Textform existiert noch nicht**, nur die Rohkomponenten |
| Gegenargumente | ⚠️ teilweise | `decision_blockers` (sql/017, nicht-blockierende Hinweise) — kein strukturiertes Pro/Contra, kein "was spricht dagegen"-Textbaustein |
| Konfidenzklasse statt Scheingenauigkeit | ✅ (Konzept) | `docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md` unterscheidet bereits explizit Ranking-Score vs. echte Wahrscheinlichkeit — nur nicht ausgeführt (siehe Fund 2) |
| Historische Vergleichsfälle | ✅ (Konzept, dormant) | siehe Fund 2 |
| Hebelprodukt-Empfehlung (Zielhebel etc.) | ⚠️ Schema vorhanden, inhaltlich leer | siehe Fund 10 |

### Modul 2 — Meine Entscheidung (Annehmen/Ablehnen/Beobachten, manuelle Änderung)

**Fehlt vollständig.** Es gibt keinen Status auf `recommendations` oder `paper_trades`, der eine
Nutzerentscheidung abbildet (deren Status-Enums sind rein systemgetrieben:
`offen/geschlossen` bzw. `proposed/blocked/awaiting_confirmation/open/closed/expired_unfilled/
cancelled/data_error`). Keine Ablehnungsgründe, kein Freitext, keine "System-Vorschlag vs.
meine Entscheidung"-Trennung. Das Referenzmuster dafür (`learning_rule_proposals` mit
`status/reviewed_at/reviewed_by/version`) existiert aber bereits produktiv für einen anderen
Anwendungsfall (siehe Fund 1) und ist strukturell fast 1:1 übertragbar.

### Modul 3 — Paper-Trading / Trade-Review

| Anforderung | Vorhanden? | Fundstelle |
|---|---|---|
| Einstieg/Stop/Target/aktueller Kurs verfolgen | ✅ | `trading.paper_trades` (sql/035) |
| unrealized PnL, MFE/MAE | ✅ **live verdrahtet, täglich aktualisiert** | `trading.paper_trade_valuations` (eine Zeile je Trade+Tag), Peak-Werte auf `paper_trades` übertragen |
| Exit-Grund, finale Performance | ✅ | `exit_reason`, `net_pnl`, `realized_r_multiple`, `holding_period_days`, View `v_paper_trade_metrics` |
| Trade Review (War Entry/Stop/Target/Hebel/Richtung sinnvoll? Freitext) | ❌ fehlt vollständig | kein Feld, kein Workflow gefunden |
| System-vs.-User-Performance-Auswertung | ❌ fehlt (Voraussetzung: Modul 2 muss erst existieren) | — |

### Modul 4 — News-Review

| Anforderung | Vorhanden? | Fundstelle |
|---|---|---|
| Relevante/unsichere/verworfene News anzeigen | ✅ (Daten vorhanden) | `trading.news_assessments`, `v_news_latest_assessment` |
| Manuelle Korrektur (relevant/irrelevant/unsicher) | ⚠️ Schema-Hook vorhanden, nie beschrieben | `confirmation_status` (Fund 3) |
| False-Positive-Filter-Verwaltung | ✅ **aber nur für historische Pipeline** | Workflows 16c/16d, Tabellen `news_match_exclusions*` (Fund 9: Schema-Drift) |
| False-Negative-Erfassung | ❌ fehlt vollständig, in beiden Pipelines | Fund 4 |
| Filterregel-Qualitätskennzahlen (Anwendungen, Trefferquote, Status) | ⚠️ teilweise | `news_match_exclusions.hit_count/last_hit_at/aktiv` vorhanden, aber kein `ACTIVE/REVIEW_REQUIRED/DISABLED`-Statusmodell, keine False-Negative-Rate (weil Fund 4) |

### Modul 5 — Feedback- und Lernzentrale

Keine zentrale "offene Entscheidungen"-Übersicht vorhanden. Die Bausteine, die dort aggregiert
werden müssten, existieren aber bereits einzeln und wären per SQL-Zählung zusammenführbar: offene
Lernvorschläge (`learning_rule_proposals WHERE status='proposed'`), Status-Übersicht zeigt bereits
einen "Lernstatus"-Abschnitt (WF07). Das Feedback-Prinzip ("Nutzer-Feedback ≠ automatische
Wahrheit, erst über mehrere Fälle prüfen, dann Lernvorschlag, dann Simulation/OOS/Freigabe") ist
architektonisch **bereits exakt der bestehende Lernagent-Governance-Fluss** (09b/09c → 12) — es
fehlt nur die Feedback-Erfassung selbst als neue Datenquelle für diesen Fluss.

### Modul 6 — Regelverwaltung

Die Governance-Logik (Vorschlag → Prüfen → Simulieren → OOS → Freigeben → Aktiv) ist bereits
produktiv über Workflow 12 umgesetzt (heute erweitert). Eine **verständliche, tabellenübergreifende
Ansicht** aller Regeln (Scoring-Gewichte, Strategie-Parameter, Regime-Matrix, Strategie-Status,
News-Ausschlussregeln) existiert nicht — jede Regelart hat eigene Tabellen mit unterschiedlicher
Versionierungstiefe (Fund 6), aber keine gemeinsame Übersichtsseite.

### Modul 7 — Tägliche Startseite

Workflow 07 ("Status-Uebersicht") ist mit 24 Abschnitten bereits eine sehr umfangreiche,
technisch-orientierte Statusseite — aber nach Pipeline-Stufen organisiert, nicht nach
Nutzer-Entscheidungen (genau der im Auftrag kritisierte Zustand). Design-System und
Kachel-Bausteine (`.stat`/`.summary`, `.badge`) sind direkt wiederverwendbar für eine neue,
entscheidungsorientierte Startseite. Ein "Systemstatus: OK"-Baustein fehlt (Fund 8).

---

## 2. Was fehlt — zusammengefasst

1. **Die gesamte Entscheidungsschicht**: Annehmen/Ablehnen/Beobachten/Später für Empfehlungen,
   getrennte Speicherung System-Vorschlag vs. Nutzer-Änderung, Ablehnungsgründe.
2. **Trade-Review nach Abschluss** (strukturierte Fragen + Freitext).
3. **System-vs.-User-Performance-Auswertung** (Voraussetzung: 1).
4. **News-False-Negative-Erfassung** (in beiden Pipelines, komplett neu).
5. **Aktivierung der bereits vorhandenen News-Korrektur-Hooks** (`confirmation_status`,
   `reprocess_requested`) — kein neues Schema nötig, nur ein Schreibpfad.
6. **Gegenargumente-Textbaustein** (Rohdaten vorhanden, keine strukturierte Pro/Contra-Aufbereitung).
7. **Ausführung des vorhandenen Wahrscheinlichkeits-/Kalibrierungs-Mechanismus**
   (`probability_estimates`), ggf. erweitert um `simulation_trades` als zusätzliche Datenquelle.
8. **Zentrale Feedback-/Regel-Übersichtsseiten** (Aggregation existierender Einzelquellen).
9. **Zentrale Navigationskomponente** (aktuell N-fach dupliziert, Fund 7).
10. **"Systemstatus"-Auswertung** über `trading.workflow_errors` (Fund 8).
11. **Hebelprodukt-Hinweistext reaktivieren** (Fund 10) — falls weiterhin gewünscht.
12. **News-Ausschlussregeln als reguläre SQL-Migration nachziehen** (Fund 9, technische Schuld,
    kein HITL-Feature, aber Voraussetzung für sichere Weiterentwicklung dieses Bereichs).

---

## 3. Wiederverwendbare Tabellen (nach Domäne)

**Empfehlungen/Risiko** (alle in `trading` Schema): `recommendations` (Basis sql/007, erweitert
sql/017/029/030/033/053/055 — vollständige Spaltenliste s. Agentenbericht, u. a. bereits
`configuration_snapshot_json`, `risk_model_version`, `thesis_rule_version` als Audit-Trail),
`recommendation_veto_log` (sql/028, harte Vetos), `portfolio_risk_checks` (sql/036, alle 9
Limits), `stress_scenarios` (sql/036).

**Paper-Trading**: `paper_trades` (sql/035, mit `recommendation_id`-FK zurück zur Empfehlung —
strukturell bereits die Brücke System-Vorschlag→Ausführung), `paper_trade_events`
(Ereignis-Historie), `paper_trade_valuations` (tägliches MFE/MAE), `paper_trade_costs`, View
`v_paper_trade_metrics`.

**News**: `news_items`, `news_assessments` (inkl. `confirmation_status`, `reprocess_requested`),
`news_impact_tracking`, View `v_news_latest_assessment`; historisch: `historical_news`,
`historical_news_assessments`, `historical_news_impact_tracking`, View
`v_news_impact_tracking_combined`; Filter: `news_match_exclusions`/`_candidates`/`_hits`
(Schema-Drift, Fund 9), `watchlist.exclude_keywords`, `stock_instruments.exclude_patterns_json`.

**Lernen/Regeln**: `learning_rule_proposals` (das Referenzmuster, sql/001), `scoring_weights`,
`strategy_regime_matrix` (beide heute versioniert), `strategy_parameters`, `strategy_status`,
`v_experiment_register` (heute gebaut, sql/069).

**Kalibrierung**: `probability_estimates`, `calibration_checks` (sql/037, dormant, Fund 2).

**Simulation/Backtest** (bereits aus heutiger Session bekannt): `backtest_runs`,
`simulation_trades`, `simulation_daily_portfolio`, `v_experiment_register`.

**System**: `workflow_errors` (sql/005, nie gelesen, Fund 8), `pipeline_config`.

---

## 4. Wiederverwendbare Workflows

- **Workflow 12 ("Lernvorschlag-Freigabe")** — das zentrale Bau-Muster für jede neue
  Annehmen/Ablehnen-Oberfläche (Fund 1). Nicht wiederverwenden im Sinne von "denselben Workflow
  erweitern" (fachlich anderer Gegenstand), sondern als **Vorlage kopieren**.
- **Workflow 16c/16d** — Vorlage für eine künftige False-Negative-Oberfläche (gleiches
  Kandidaten→Freigabe-Muster, bereits mit Sicherheitsprüfungen vor Aktivierung).
- **Workflow 07 ("Status-Uebersicht")** — Kachel-/Design-Bausteine wiederverwendbar für eine neue
  Startseite; die Seite selbst bleibt vermutlich als technische Detailseite bestehen, wird aber
  nicht die neue "GUTEN MORGEN"-Startseite.
- **Workflow 09b/09c** — unverändert weiterverwenden als automatische Lernvorschlags-Quelle;
  müsste um eine zweite Quelle "aus Nutzer-Feedback" ergänzt werden (Modul 5), nicht ersetzt
  werden.
- **RSS-Quellen verwalten / Watchlist verwalten** — liefern das CRUD-Formular-Muster
  (Formular-pro-Zeile mit `form="id"`-Referenz statt Verschachtelung) für einfache
  Verwaltungsseiten (z. B. Regelverwaltung, Modul 6).

---

## 5. Bestehende APIs

- **n8n REST-API** (Workflow-Verwaltung, aus dieser Session bekannt) — nicht Teil der
  Nutzeroberfläche, nur für Deploys relevant.
- **`http://172.16.1.14:8099`** (FastAPI/yfinance-Marktdatendienst, separates Repo) — liefert
  Kursdaten, keine HITL-relevanten Endpunkte.
- **`http://172.16.1.14:8099/engine/simulation/step`** (heute gebaut, `trading_engine`-Router) —
  deterministische Berechnungen (Signal/Sizing/Fill/Exit/Equity), aktuell nur von Workflow 17
  genutzt. Fachlich relevant für Modul 1 (Stop-/Sizing-Formeln), aber bisher nicht für den
  Live-Empfehlungspfad (06/14) angebunden — die dort verwendeten Formeln sind eigener,
  unabhängiger JS-Code (siehe `TRADING_ENGINE_ARCHITECTURE.md`, "Drei-Wege-Problem").
- **Alle übrigen "APIs" sind n8n-Webhook-Seiten** (GET/POST auf `/webhook/<pfad>`) — das ist
  bereits das etablierte Muster für jede Nutzer-Interaktion in diesem System, kein separates
  Backend-Framework.

---

## 6. Welche neuen Endpunkte sind notwendig?

Nur grob benannt (Detailarchitektur ist Phase 2). Grundmuster durchgehend: GET-Ansicht + POST-Aktion
auf demselben Webhook-Pfad, wie Workflow 12.

- `/webhook/heute-handeln` — Modul 1 (Entscheidungssheet-Liste)
- `/webhook/trade-entscheidung` (POST-Aktionen: annehmen/ablehnen/beobachten/später, plus Wertänderung) — Modul 2
- `/webhook/paper-trades` bzw. Erweiterung von `aktien-status` — Modul 3 (falls nicht in bestehende Seite integriert)
- `/webhook/trade-review` (POST nach Trade-Abschluss) — Modul 3
- `/webhook/news-pruefen` (GET + POST für `confirmation_status`/`reprocess_requested`/False-Negative) — Modul 4
- `/webhook/lernen-feedback` — Modul 5 (Aggregations-Startseite für offene Entscheidungen)
- `/webhook/regeln` — Modul 6 (regelübergreifende Übersicht)
- Erweiterung oder Ablösung von `aktien-status` als neue Startseite — Modul 7

Ob diese als eigenständige neue Workflows oder als neue Webhook-Paare in bestehenden Workflows
entstehen, ist eine Architekturfrage für Phase 2 — beide Muster existieren im Repo bereits parallel.

---

## 7. Welche DB-Erweiterungen sind wirklich notwendig?

Bewusst minimal gehalten, im Sinne von "Bestehendes wiederverwenden":

1. **Neue Tabelle für Nutzer-Entscheidungen** (Modul 2) — kein bestehendes Feld ist dafür
   geeignet, ohne die Semantik von `recommendations.status`/`paper_trades.status` zu verwässern.
   Analog zum `learning_rule_proposals`-Muster: eigene Tabelle mit `recommendation_id`-FK,
   `entscheidung` (annehmen/ablehnen/beobachten/später), `ablehnungsgrund`, `freitext`,
   `system_werte_json` (Snapshot des Original-Vorschlags — **niemals überschreiben**),
   `meine_werte_json` (falls geändert), `entschieden_am`, `entschieden_von`.
2. **Neue Tabelle für Trade-Reviews** (Modul 3) — `paper_trades.trade_id`-FK,
   strukturierte Ja/Teilweise/Nein-Antworten je Frage (Entry/Stop/Target/Hebel/Richtung/Begründung
   sinnvoll?), Freitext.
3. **Kein neues Schema für News-Korrektur nötig** — `confirmation_status`/`reprocess_requested`
   existieren bereits, nur beschreibbar machen (Fund 3).
4. **Neue, kleine Tabelle für False-Negative-Kennzeichnung** (Modul 4) — analog
   `news_match_exclusion_candidates`, aber umgekehrte Richtung: `news_id`, `ticker`,
   `markiert_von`, `grund`, `status` (`possible_false_negative`/`filter_revision_required`/
   `bestaetigt`/`verworfen`), Rückverweis auf die auslösende Filterregel falls ermittelbar.
5. **Persistenz für vorfilter-verworfene Artikel in Workflow 03** — aktuell keine Zeile,
   keine Wiederauffindbarkeit (größte Einzellücke, Fund 4). Kleinste Lösung: verworfene Artikel
   ebenfalls in `news_items` mit `status='filtered'` (oder ähnlich) plus `discarded_reason`
   schreiben, statt sie nie zu persistieren.
6. **`news_match_exclusions`/`_candidates`/`_hits` als reguläre Migration nachziehen** (Fund 9) —
   keine neue Struktur, nur bestehende Live-Struktur ins Repo nachziehen.
7. Optional, falls Modul 1 die historischen Vergleichsfälle nutzen soll: `probability_estimates`
   um eine Datenquellen-Erweiterung auf `simulation_trades` prüfen (kein neues Schema, ggf. neue
   Berechnungslogik).

**Bewusst nicht vorgeschlagen**: keine zweite Parallel-Tabelle für Empfehlungen, kein neues
Risiko-/Positionsgrößen-Schema, keine neue Audit-Trail-Struktur (das bestehende
`config_snapshot_json`/`rule_version`-Muster wird für alle neuen Tabellen übernommen).

---

## 8. Welche bestehenden Oberflächen können erweitert werden?

- **`aktien-status` (Workflow 07)** — stärkster Kandidat für Erweiterung um Annehmen/Ablehnen-
  Buttons direkt in der "Offene Empfehlungs-Positionen"/"Offene Paper Trades"-Tabelle, ODER als
  Vorbild für eine komplett neue, schlankere Startseite (Modul 7 verlangt explizit "0 bis 5
  qualitativ gute Kandidaten", nicht die aktuelle vollständige Technik-Tabelle — eher ein Fall für
  eine NEUE Seite mit Verweis auf 07 als Detail-Ansicht).
- **`lernvorschlaege` (Workflow 12)** — bereits fertig für Modul 6 (Regel-Teilbereich
  Lernvorschläge), keine Änderung nötig außer ggf. Einbindung in eine gemeinsame Feedback-Startseite
  als Kachel-Link.
- **`Watchlist verwalten` / `RSS-Quellen verwalten`** — Formularmuster wiederverwenden, Seiten
  selbst bleiben unverändert.

---

## 9. Sicherheits-/Integritätsrisiken

1. **Audit-Trail-Prinzip konsequent durchhalten**: das System hat bereits an mehreren Stellen
   gelernt, dass In-Place-Updates ohne Versionierung zu stillen Fehlern führen (sql/067,
   heute in dieser Sitzung selbst behoben: `strategy_regime_matrix`). Jede neue
   Entscheidungs-/Review-Tabelle muss von Anfang an "niemals überschreiben" umsetzen, nicht
   nachträglich nachgezogen werden.
2. **Optimistisches Locking** (`WHERE id=... AND status=...`, `version=version+1`) ist im
   bestehenden System der Standard gegen Race Conditions bei gleichzeitigen Aktionen (Workflow 12)
   — muss für neue POST-Aktionen übernommen werden, sonst Gefahr doppelter/inkonsistenter
   Entscheidungen bei parallelen Browser-Tabs.
3. **Keine automatische Orderausführung** — bereits durchgängige Architektur-Eigenschaft des
   gesamten Systems (kein Broker-API-Zugriff irgendwo im Repo gefunden), passt zur
   Auftragsvorgabe ohne Änderung.
4. **Schema-Drift-Risiko** (Fund 9) — zeigt, dass live editierte Workflows/Tabellen ohne
   SQL-Migration entstehen können. Für neue HITL-Tabellen von Anfang an als `sql/0xx`-Migration
   anlegen, nicht nur live in n8n bauen.
5. **Navigationsleiste dupliziert** (Fund 7) — bei einer wachsenden Anzahl neuer Seiten wächst das
   Risiko, dass die Nav-Leiste inkonsistent gepflegt wird. Sollte in Phase 2 als zentrale Frage
   behandelt werden (gemeinsamer Sub-Workflow analog ALLRIS, oder bewusst weiter duplizieren).
6. **LLM-Kosten/Grenzen**: die bestehende Architektur trennt bereits sauber zwischen
   deterministischer Berechnung (PnL, Positionsgrößen, Limits — alles vorhanden) und KI-Interpretation
   (News-Bewertung, Lernbericht-Text). Diese Trennung muss für die Begründungstexte in Modul 1
   fortgeführt werden: LLM formuliert, System liefert Fakten (bereits im Auftrag so verlangt und
   bereits im bestehenden Muster — z. B. Lernagent 09b — exakt so umgesetzt, inkl.
   Validierungs-Sicherheitsnetz gegen KI-Erfindungen).
7. **`REQUIRE_CONFIRMATION`-Sackgasse in Workflow 06**: aktuell wird bei aktivem
   `REQUIRE_CONFIRMATION`-Flag eine Empfehlung als `vorschlag_ungespeichert` markiert, aber es gibt
   keinen Mechanismus, sie nachträglich zu bestätigen — der Vorschlag verschwindet faktisch. Das
   ist funktional bereits kaputt und sollte im Zuge von Modul 2 mitgelöst werden (die neue
   Entscheidungsschicht ersetzt diesen Mechanismus ohnehin sinnvoll).

---

## 10. Empfohlene UX-Struktur (grob, Detailausarbeitung folgt in Phase 2)

Navigation orientiert an den Nutzer-Fragen aus dem Auftrag, nicht an Workflow-Nummern — deckt sich
mit der im Auftrag vorgeschlagenen Struktur, hier nur gegen das Bestehende gespiegelt:

- **HEUTE** (neue Startseite, Modul 7) — aggregiert Kennzahlen aus mehreren bestehenden Quellen
  (offene Entscheidungen, Lernstatus, News-Auffälligkeiten, Systemstatus-Kachel neu aus
  `workflow_errors`), verlinkt in die Detailseiten.
- **HANDELN** (Modul 1+2) — neue Seite, nutzt bestehende `recommendations`-Daten + neue
  Entscheidungstabelle.
- **POSITIONEN** (Modul 3) — Erweiterung von/Verweis auf `aktien-status`s Paper-Trade-Tabelle plus
  neue Review-Aktion nach Abschluss.
- **NEWS** (Modul 4) — neue Seite, aktiviert bestehende dormante Hooks + neue
  False-Negative-Erfassung.
- **FEEDBACK/LERNEN** (Modul 5) — neue Aggregationsseite über bestehende Einzelquellen.
- **REGELN** (Modul 6) — neue Übersichtsseite über die drei bestehenden Regel-Versionierungsstile.
- **SIMULATIONEN** — bereits vollständig vorhanden (Simulation-Steuerzentrale), unverändert
  einbinden.
- **SYSTEM** — `aktien-status` (07) bleibt als technische Detailseite bestehen, aus HEUTE heraus
  verlinkt, nicht ersetzt.

Design-System (Farben/Klassen/CSS) durchgängig aus den bestehenden Seiten übernehmen — keine neue
Optik nötig, wie vom Auftrag gefordert ("Bestehendes wiederverwenden").

---

## Offene Fragen für Phase 2 (Architektur)

1. Sollen neue Seiten als Webhook-Paare in **neuen** Workflows entstehen (sauberer, aber mehr
   Workflows) oder in **bestehenden** Workflows ergänzt werden (weniger neue Dateien, aber größere
   Workflows, z. B. Erweiterung von 06/14 direkt)?
2. Soll die Nav-Leisten-Duplikation (Fund 7) in Phase 2 mitgelöst werden (gemeinsamer Sub-Workflow),
   oder bewusst im bestehenden Duplikationsmuster bleiben?
3. Soll `probability_estimates` (Fund 2) um `simulation_trades` als Datenquelle erweitert werden,
   um die historischen Vergleichsfälle schon mit den vorhandenen Simulationsdaten befüllen zu
   können, statt auf echte Paper-Trades zu warten?
4. Umfang der News-Vorfilter-Persistenz (Punkt 5 in Abschnitt 7) — vollständige Persistenz aller
   verworfenen Artikel (teurer, aber lückenlos) oder eine Stichprobe (günstiger, analog zum
   bestehenden historischen KI-Stichproben-Modell)?

Diese vier Punkte würde ich vor Phase 2 kurz mit dir klären, statt sie hier vorwegzunehmen.
