# HUMAN_IN_THE_LOOP_ARCHITECTURE.md

Stand: 2026-08-20. Phase 2 (Architektur) des Human-in-the-Loop-Auftrags, aufbauend auf
`HUMAN_IN_THE_LOOP_REVIEW.md` (Phase 1) und den dort mit dem Nutzer geklärten vier Entscheidungen.
Noch keine Implementierung — dieses Dokument beschreibt Seitenstruktur, Datenfluss, Tabellen,
Endpunkte, Statusmodelle, Feedback-/Audit-Modell und Lernkreislauf, bevor in Phase 3 gebaut wird.

**Leitprinzip, aus Phase 1 übernommen:** additive Erweiterung, kein Parallelsystem. Jede neue
Tabelle referenziert eine bestehende (meist per Foreign Key auf `recommendations`/`paper_trades`);
jeder neue Workflow ist ein eigenständiges Webhook-Paar nach dem Muster von Workflow 12, nicht
Teil der bestehenden Pipeline-Workflows (06/14 bleiben unangetastet, Phase-1-Entscheidung 1).

---

## 1. Gesamtarchitektur

```
                         ┌────────────────────────┐
                         │   Finanz_Web_NavBar     │  (neuer Sub-Workflow, Execute-Workflow-only)
                         │   {currentPage} → {navHtml,navCss}
                         └───────────▲─────────────┘
                                     │ Execute Workflow (parallel zum Trigger, siehe Abschnitt 3.1)
     ┌──────────────┬────────────────┼─────────────────┬──────────────────┬─────────────┐
     │              │                │                 │                  │             │
┌────▼─────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌────────▼────────┐  ┌──────▼─────┐  ┌────▼────┐
│Startseite│  │Trading-     │  │Paper-Trading│  │News-Pruefen      │  │Lernen-und- │  │Regeln-  │
│ (Modul 7)│  │Entscheidungs│  │-Review      │  │(Modul 4)         │  │Feedback    │  │uebersicht│
│          │  │-zentrale    │  │(Modul 3)    │  │                  │  │(Modul 5)   │  │(Modul 6)│
└────┬─────┘  │(Modul 1+2)  │  └──────┬──────┘  └────────┬─────────┘  └──────┬─────┘  └────┬────┘
     │        └──────┬──────┘         │                  │                   │             │
     │               │                │                  │                   │             │
     └───────────────┴────────────────┴──────────────────┴───────────────────┴─────────────┘
                                       │
                        liest/schreibt bestehende + neue Tabellen
                                       │
     ┌─────────────────────────────────────────────────────────────────────────────────┐
     │  BESTEHEND (unverändert genutzt)          │  NEU (Phase 3)                        │
     │  trading.recommendations                   │  trading.recommendation_decisions     │
     │  trading.paper_trades(+events/valuations/   │  trading.trade_reviews                │
     │    costs)                                    │  trading.news_false_negative_flags    │
     │  trading.portfolio_risk_checks               │  news_items.status ∪ 'filtered'       │
     │  trading.news_assessments (confirmation_     │  probability_estimates.data_source    │
     │    status/reprocess_requested aktivieren)     │    ('paper_trades'|'simulation_trades')│
     │  trading.learning_rule_proposals              │                                        │
     │  trading.scoring_weights/strategy_regime_     │                                        │
     │    matrix/strategy_parameters/strategy_status │                                        │
     │  trading.probability_estimates/calibration_   │                                        │
     │    checks                                      │                                        │
     └─────────────────────────────────────────────────────────────────────────────────┘
```

Kein neuer Dienst, kein neues Framework. Alle sechs neuen Seiten sind n8n-Webhook-Workflows nach
dem in Phase 1 identifizierten Muster (Workflow 12): GET-Ansicht + POST-Aktion auf demselben oder
gepaarten Pfaden, serverseitig gerenderte Formulare, Postgres-Node baut/führt SQL.

---

## 2. Seitenstruktur

| Seite (Nav-Label) | Workflow (neu) | Webhook-Pfad(e) | Modul | Kernfunktion |
|---|---|---|---|---|
| HEUTE | `Startseite.json` | `/heute` (GET) | 7 | Aggregierte Kennzahlen-Kacheln, verlinkt in alle anderen Seiten |
| HANDELN | `Trading-Entscheidungszentrale.json` | `/heute-handeln` (GET Liste + GET Detail via `?id=`), `/trade-entscheidung` (POST) | 1+2 | Entscheidungssheets, Annehmen/Ablehnen/Beobachten/Später, Wertänderung |
| POSITIONEN | `Paper-Trading-Review.json` | `/trade-review` (GET Liste + POST) | 3 | Offene Trades verfolgen (verlinkt bestehende `aktien-status`-Tabelle), Review nach Abschluss |
| NEWS | `News-Pruefen.json` | `/news-pruefen` (GET + POST) | 4 | Relevanz-Korrektur, False-Negative-Meldung |
| FEEDBACK/LERNEN | `Lernen-und-Feedback.json` | `/lernen-feedback` (GET) | 5 | Aggregations-Hub offener Entscheidungen, rein lesend + Verlinkung |
| REGELN | `Regelnuebersicht.json` | `/regeln` (GET) | 6 | Regelübersicht über alle drei Versionierungsstile, rein lesend |
| — (Sub-Workflow) | `Finanz_Web_NavBar.json` | keiner (Execute-Workflow-only) | — | Zentrale Nav-Leiste für alle Seiten (Phase-1-Entscheidung 2) |

**Bestehende Seiten unverändert genutzt/verlinkt**: `aktien-status` (07, bleibt technische
Detailseite), `simulation-uebersicht`/`-vergleich` (SIMULATIONEN-Nav-Punkt, unverändert),
`lernvorschlaege` (12, wird von FEEDBACK/LERNEN aus verlinkt statt dupliziert), `historische-*`
(unverändert).

Bewusst **kein** zusätzliches "SYSTEM"-Nav-Item als neue Seite — `aktien-status` (07) übernimmt
diese Rolle weiterhin, nur ergänzt um die neue Systemstatus-Kachel (Abschnitt 9).

### 2.1 Nav-Leiste (Finanz_Web_NavBar)

Analog zum bestehenden ALLRIS-Muster (`ALLRIS_Web_NavBar`, Execute-Workflow-callable, `{currentPage,
theme} → {navHtml, navCss}`), hier ohne Theme-Parameter (finanz hat nur ein Farbschema, siehe
Phase-1-Fund zum Design-System). `PAGES`-Array im Sub-Workflow zentral gepflegt:

```js
const PAGES = [
  ['heute', 'Heute'],
  ['heute-handeln', 'Handeln'],
  ['trade-review', 'Positionen'],
  ['news-pruefen', 'News'],
  ['lernen-feedback', 'Feedback'],
  ['regeln', 'Regeln'],
  ['simulation-uebersicht', 'Simulationen'],
  ['aktien-status', 'System'],
  // bestehende Admin-Seiten bleiben als weitere Eintraege oder wandern in eine "Mehr"-Gruppe -
  // Detailentscheidung Phase 3, kein Blocker fuer die Architektur
];
```

**Wichtige Wiring-Regel (aus dem ALLRIS-Vorbild übernommen, dort mehrfach bestätigt)**: der
Execute-Workflow-Aufruf darf **nicht** inline in einer POST-Verarbeitungskette hängen, da er
`$json` überschreibt und dadurch die eigentlichen Formulardaten verloren gingen. Immer parallel
zum Trigger-Node verzweigen und per benanntem Node-Lookup (`$('Nav laden').first().json`) später
referenzieren — jede der sechs neuen Seiten muss diese Regel bei ihrem POST-Zweig beachten.

---

## 3. Datenmodell (neu, Phase 3)

Alle neuen Tabellen folgen dem bereits etablierten Audit-Muster: `config_snapshot_json`/
`rule_version` wo fachlich sinnvoll, niemals löschende Updates auf Entscheidungsdaten (neue Zeile
statt Überschreiben, wie seit heute bei `strategy_regime_matrix`), optimistisches Locking über
`version` bei jeder POST-Aktion.

### 3.1 `trading.recommendation_decisions` (Modul 2)

```sql
CREATE TABLE trading.recommendation_decisions (
  id                     BIGSERIAL PRIMARY KEY,
  recommendation_id      BIGINT NOT NULL REFERENCES trading.recommendations(id),
  entscheidung           TEXT NOT NULL CHECK (entscheidung IN ('angenommen','abgelehnt','beobachten','spaeter')),
  ablehnungsgruende_json  JSONB,   -- Array von Codes, siehe Abschnitt 4.1
  freitext                 TEXT,
  system_werte_json         JSONB NOT NULL,  -- Snapshot des Original-Vorschlags zum Entscheidungszeitpunkt (entry/stop/target/hebel/quantity/CRV) - wird NIE nachtraeglich geaendert
  meine_werte_json           JSONB,           -- NULL = unveraendert uebernommen; sonst die vom Nutzer geaenderten Felder
  paper_trade_id               TEXT REFERENCES trading.paper_trades(trade_id),  -- gesetzt, sobald "angenommen" zu einem echten Paper Trade gefuehrt hat
  status                        TEXT NOT NULL DEFAULT 'aktuell' CHECK (status IN ('aktuell','ueberholt')),
  version                        INTEGER NOT NULL DEFAULT 1,
  config_snapshot_json             JSONB,   -- rule_version/pipeline_config zum Entscheidungszeitpunkt
  entschieden_am                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  entschieden_von                    TEXT NOT NULL DEFAULT 'nutzer',
  created_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Genau eine "aktuelle" Entscheidung je Empfehlung - eine erneute Entscheidung (z.B. von
-- "spaeter" zu "angenommen") legt eine NEUE Zeile an und setzt die alte auf 'ueberholt',
-- exakt das heute bereits etablierte Muster (sql/067, strategy_regime_matrix).
CREATE UNIQUE INDEX uq_recommendation_decisions_aktuell
  ON trading.recommendation_decisions (recommendation_id) WHERE status = 'aktuell';
```

`system_werte_json` dupliziert bewusst Werte, die bereits auf `recommendations` stehen — nötig,
weil sich die `recommendations`-Zeile selbst über die Zeit ändern kann (Status, `performance_pct`
u. a.), während die Frage "was hat das System zum Entscheidungszeitpunkt vorgeschlagen" dauerhaft
unverändert beantwortbar bleiben muss (Auftragsvorgabe "niemals überschreiben").

### 3.2 `trading.trade_reviews` (Modul 3)

```sql
CREATE TABLE trading.trade_reviews (
  id                    BIGSERIAL PRIMARY KEY,
  trade_id              TEXT NOT NULL UNIQUE REFERENCES trading.paper_trades(trade_id),
  vorschlag_sinnvoll    TEXT CHECK (vorschlag_sinnvoll IN ('ja','teilweise','nein')),
  entry_sinnvoll        TEXT CHECK (entry_sinnvoll IN ('ja','teilweise','nein')),
  stop_sinnvoll         TEXT CHECK (stop_sinnvoll IN ('ja','teilweise','nein')),
  target_sinnvoll       TEXT CHECK (target_sinnvoll IN ('ja','teilweise','nein')),
  hebel_sinnvoll        TEXT CHECK (hebel_sinnvoll IN ('ja','teilweise','nein')),
  richtung_richtig      TEXT CHECK (richtung_richtig IN ('ja','teilweise','nein')),
  begruendung_korrekt   TEXT CHECK (begruendung_korrekt IN ('ja','teilweise','nein')),
  kommentar             TEXT,
  reviewed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_von          TEXT NOT NULL DEFAULT 'nutzer'
);
```

Ein Review pro Trade (`UNIQUE (trade_id)`) — reicht für "nach Abschluss bewerten"; ein erneutes
Absenden überschreibt bewusst (Review ist eine nachträgliche Einschätzung, kein Audit-kritischer
Systemwert, anders als `recommendation_decisions`).

### 3.3 `trading.news_false_negative_flags` (Modul 4)

```sql
CREATE TABLE trading.news_false_negative_flags (
  id                   BIGSERIAL PRIMARY KEY,
  news_id              BIGINT NOT NULL REFERENCES trading.news_items(id),
  markiert_von         TEXT NOT NULL DEFAULT 'nutzer',
  grund                TEXT,
  status               TEXT NOT NULL DEFAULT 'possible_false_negative'
                        CHECK (status IN ('possible_false_negative','filter_revision_required','bestaetigt_kein_fehler','bestaetigt_false_negative')),
  ausloesende_regel_id BIGINT REFERENCES trading.news_match_exclusions(id),  -- falls ermittelbar
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at          TIMESTAMPTZ,
  reviewed_von         TEXT
);
```

Analog zu `news_match_exclusion_candidates` (Freigabe-Richtung), nur umgekehrt: hier wird eine
bereits getroffene Verwerfung nachträglich angezweifelt, nicht ein neuer Ausschluss vorgeschlagen.
`status='filter_revision_required'` löst **keine** automatische Regeländerung aus (Feedback-Prinzip,
Abschnitt 6) — markiert nur, dass ein Mensch die auslösende Regel ansehen sollte.

### 3.4 Erweiterung `trading.news_items` — vollständige Vorfilter-Persistenz (Modul 4, Phase-1-Entscheidung 4)

```sql
ALTER TABLE trading.news_items
  DROP CONSTRAINT IF EXISTS <bestehender_status_check_name>;
ALTER TABLE trading.news_items
  ADD CONSTRAINT chk_news_items_status
  CHECK (status IN ('pending','processing','evaluated','retry','failed','discarded','filtered'));
```

Neuer Status `'filtered'`: Workflow 03s Regex-Vorfilter (`classifyArticle`) schreibt ab jetzt für
**jeden** verworfenen Artikel eine Zeile mit `status='filtered'`, `discarded_reason` = die
zutreffende Filterkategorie/das Muster (z. B. `globalExcludePatterns:<Muster>`). Kein neues
KI-Bewertungs-Objekt nötig — diese Zeilen durchlaufen `08`/`09` weiterhin nicht (deren Queries
filtern bereits auf `relevant=TRUE` bzw. evaluierte Zeilen), sie existieren nur, damit
`News-Pruefen` sie überhaupt anzeigen und der Nutzer sie als möglichen False Negative markieren
kann (per `news_false_negative_flags`, Abschnitt 3.3, das per `news_id` genau auf diese neuen
Zeilen verweisen kann).

### 3.5 Erweiterung `trading.probability_estimates` — Simulationsdaten (Phase-1-Entscheidung 3)

```sql
ALTER TABLE trading.probability_estimates
  ADD COLUMN IF NOT EXISTS data_source TEXT NOT NULL DEFAULT 'paper_trades'
    CHECK (data_source IN ('paper_trades','simulation_trades'));

ALTER TABLE trading.probability_estimates
  DROP CONSTRAINT IF EXISTS <bisheriger_unique_constraint_name>;
ALTER TABLE trading.probability_estimates
  ADD CONSTRAINT uq_probability_estimates_segment
  UNIQUE (segment_strategy, segment_direction, segment_market_regime, segment_risk_bucket,
          segment_evidence_bucket, segment_time_horizon, rule_version, data_source);
```

`data_source` wird **Teil des Unique-Constraints**, nicht nur eine Info-Spalte — Paper-Trade- und
Simulations-Statistiken für dasselbe Segment dürfen sich nicht stillschweigend vermischen
(Grundregel 9, keine Scheingenauigkeit). Die neue Berechnungslogik (Phase 3) liest wahlweise aus
`trading.paper_trades` oder `trading.simulation_trades` und schreibt jeweils eine eigene Zeile.
Ein Konsument (das Entscheidungssheet, Modul 1) zeigt bevorzugt `paper_trades`-Schätzungen, fällt
bei `insufficient_data` auf `simulation_trades` zurück und macht die Quelle **immer sichtbar**
("Basis: 47 Simulationsfälle" vs. "Basis: 12 echte Paper Trades") — kein stillschweigendes
Vermischen von simulierter und realer Historie.

---

## 4. Statusmodelle

### 4.1 `recommendation_decisions.entscheidung` (Modul 2)

```
[Empfehlung erzeugt, keine Entscheidung]
        │
        ├── angenommen ──────► paper_trade_id wird gesetzt, sobald 14 den Trade anlegt
        ├── abgelehnt ───────► terminal, ablehnungsgruende_json + freitext
        ├── beobachten ──────► keine Aktion, aber sichtbar auf "Beobachten"-Liste (Modul 1 nennt das explizit)
        └── spaeter ─────────► bleibt auf der Handeln-Seite sichtbar, keine Terminierung
```

`ablehnungsgruende_json`-Codes (aus dem Auftrag übernommen, als Enum-Array, Mehrfachauswahl
möglich): `risiko_zu_hoch, stop_unlogisch, einstieg_gefaellt_nicht, news_nicht_ueberzeugend,
technik_nicht_ueberzeugend, portfolio_exponiert, hebel_zu_hoch, ereignisrisiko,
andere_einschaetzung, sonstiges`.

Jede erneute Entscheidung zur selben Empfehlung: alte Zeile `status='ueberholt'`, neue Zeile
`status='aktuell'`, `version` fortlaufend — identisches Muster zu `strategy_regime_matrix` (heute
gebaut).

### 4.2 `news_false_negative_flags.status` (Modul 4)

```
possible_false_negative (Nutzer markiert)
        │
        ▼ (manuelle Prüfung, kein Automatismus)
        ├── bestaetigt_false_negative ──► kann als EIN Datenpunkt in einen Lernvorschlag einfließen (Abschnitt 6, erst nach mehreren Fällen)
        ├── bestaetigt_kein_fehler ─────► terminal, kein weiterer Effekt
        └── filter_revision_required ───► sichtbar auf Regeln-Seite, blockiert/ändert NICHTS automatisch
```

### 4.3 Aktivierung bestehender Status (kein neues Modell, nur neue Schreibpfade)

- `news_assessments.confirmation_status`: `News-Pruefen` (POST) schreibt `manually_confirmed`/
  `manually_rejected` — Statuswerte und Priorisierungs-View existieren bereits unverändert.
- `news_items.reprocess_requested`: `News-Pruefen` (POST-Aktion "erneut prüfen") setzt `TRUE`;
  Workflow 03a müsste diese Zeilen künftig zusätzlich zu seiner bestehenden `research_status`-Logik
  aufgreifen (kleine Erweiterung, Phase 3, kein neues Schema).

---

## 5. API-Endpunkte (Webhook-Pfade, Payload-Grundform)

Alle POST-Endpunkte folgen dem WF12-Muster: `id` + `action` + optionale Aktionsfelder + `version`
(optimistisches Locking) im Body; Server lädt die betroffene Zeile frisch aus der DB, vertraut dem
Body nur für `action`/`version`/Freitext, niemals für Inhalte, die aus der DB kommen sollten
(identische Sicherheitsregel wie WF12s "A5"-Fix).

| Pfad | Methode | Zweck |
|---|---|---|
| `/heute` | GET | Startseite (Modul 7) |
| `/heute-handeln` | GET | Liste (Modul 1) / Detail via `?id=` |
| `/trade-entscheidung` | POST | `action ∈ {annehmen,ablehnen,beobachten,spaeter,werte_anpassen}` |
| `/trade-review` | GET | Liste offener Reviews + Detail |
| `/trade-review` | POST | Review-Formular absenden |
| `/news-pruefen` | GET | Liste (relevant/unsicher/verworfen/`filtered`) |
| `/news-pruefen` | POST | `action ∈ {relevant,irrelevant,unsicher,falsch_bewertet,filter_falsch,als_false_negative_markieren,erneut_pruefen}` |
| `/lernen-feedback` | GET | Aggregations-Hub, rein lesend |
| `/regeln` | GET | Regelübersicht, rein lesend |

Keine neuen FastAPI-Endpunkte nötig — alle Berechnungen (Positionsgröße, CRV, Limits) laufen
bereits deterministisch in 06/14/`trading_engine`; die neuen Seiten lesen nur und schreiben
Entscheidungsdaten.

---

## 6. Feedbackmodell

Direkt aus der bestehenden Lernagent-Governance abgeleitet (09b/09c → 12), **nicht neu erfunden**:

```
Einzelnes Nutzer-Feedback (Ablehnung, Review, False-Negative-Flag)
        │
        ▼  NICHT automatisch Wahrheit — nur gespeichert
        │
Über mehrere Fälle aggregiert (neue, kleine Auswertungs-Query je Feedback-Art,
z.B. "Ablehnungsgrund X kam bei Strategie Y in den letzten N Fällen Z-mal vor")
        │
        ▼  Muster erkannt (Schwellenwert, analog 09b MIN_SAMPLE)
        │
Lernvorschlag in trading.learning_rule_proposals (neuer proposal_type, z.B.
'user_feedback_pattern', mit reason-Text der das Muster beschreibt)
        │
        ▼  IDENTISCHER Weg wie jeder andere Lernvorschlag
        │
Workflow 12 (Freigabe) → Simulation/OOS-Bestätigung (wo zutreffend) → aktiv
```

Kein neuer Governance-Mechanismus — Nutzer-Feedback wird nur eine **weitere Datenquelle** für den
bereits bestehenden `learning_rule_proposals`-Fluss, exakt wie es der Auftrag verlangt
("Feedback erzeugt Lernvorschlag, aber KEINE automatische produktive Regeländerung").

---

## 7. Auditmodell

Für alle neuen Tabellen gilt einheitlich, was im System bereits mehrfach etabliert ist (und heute
in dieser Sitzung selbst an `strategy_regime_matrix` nachvollzogen wurde, nachdem ein In-Place-
Update-Bug gefunden wurde):

- **Entscheidungsdaten werden nie überschrieben** — neue Zeile + `status='ueberholt'` auf die
  alte, wie `recommendation_decisions` (Abschnitt 3.1).
- **Jede Zeile trägt, wo fachlich relevant, einen Config-/Rule-Version-Snapshot** —
  `system_werte_json`/`config_snapshot_json` auf `recommendation_decisions`.
- **Optimistisches Locking** bei jeder POST-Aktion (`WHERE id=... AND version=...`,
  `version=version+1`) — verhindert stille Konflikte bei parallelen Browser-Tabs, exakt wie WF12s
  A10-Fix.
- **Rückverweise statt Duplikate** wo möglich: `recommendation_decisions.recommendation_id`,
  `trade_reviews.trade_id`, `news_false_negative_flags.news_id` — jede neue Tabelle hängt an einer
  bestehenden, keine Kopie der Ursprungsdaten außer dem bewusst eingefrorenen
  `system_werte_json`-Snapshot.

---

## 8. Lernkreislauf (Gesamtbild)

```
Systemvorschlag (recommendations, bestehend)
        │
        ▼
Nutzerentscheidung (recommendation_decisions, NEU) ──► ggf. Paper Trade (paper_trades, bestehend)
        │                                                       │
        │                                                       ▼
        │                                              Trade-Review nach Abschluss (trade_reviews, NEU)
        │                                                       │
        ▼                                                       ▼
   [Ablehnungsgründe]                                   [War Entry/Stop/Target/Hebel/Richtung/
        │                                                Begründung sinnvoll?]
        └──────────────────────┬────────────────────────────────┘
                                ▼
                  Aggregierte Muster-Erkennung (neu, klein, Phase 3)
                                │
                                ▼
                  learning_rule_proposals (bestehend, neuer proposal_type)
                                │
                                ▼
                  Workflow 12 (Freigabe, heute umgebaut: proposed→approved→activated)
                                │
                                ▼
                  scoring_weights / strategy_regime_matrix / strategy_parameters /
                  strategy_status (bestehend, je nach proposal_type)
```

Parallel dazu, unabhängig vom Trade-Feedback-Kreislauf, der News-Kreislauf:

```
News verworfen (Vorfilter ODER KI, jetzt vollständig in news_items persistiert)
        │
        ▼
Nutzer markiert als möglichen False Negative (news_false_negative_flags, NEU)
        │
        ▼
Manuelle Prüfung, ggf. "filter_revision_required"
        │
        ▼
Bei Muster über mehrere Fälle: gleicher Weg wie oben (learning_rule_proposals → 12)
        │
        ▼
news_match_exclusions (Regel deaktivieren/anpassen) ODER Live-Vorfilter-Regex anpassen
```

---

## 9. Ergänzung: Systemstatus-Kachel (Phase-1-Fund 8)

Kein neues Modul, aber Voraussetzung für Modul 7 ("Systemstatus: OK"): neue Query auf
`trading.workflow_errors` (`COUNT(*) WHERE occurred_at > now() - interval '24h'`), eingebunden in
`Startseite.json`. Keine Schema-Änderung nötig, nur der erste lesende Zugriff auf eine bereits
bestehende, bisher nie gelesene Tabelle.

---

## 10. Nicht in dieser Phase

- Reaktivierung der `hebelprodukt_hinweis`-Textgenerierung (Phase-1-Fund 10) — separate,
  fachliche Entscheidung, ob und wie Hebelprodukt-Empfehlungen textlich wieder ausgegeben werden
  sollen. Das Schema (`hebelprodukt_typ`/`hebel_spanne`/etc.) bleibt unverändert nutzbar.
- Nachziehen von `news_match_exclusions`/`_candidates`/`_hits` als reguläre SQL-Migration
  (Phase-1-Fund 9) — technische Schuld, kein HITL-Feature, wird vor oder parallel zu Modul 4
  erledigt, aber separat committet.
- Aggregierte Muster-Erkennung (Abschnitt 8) wird in Phase 3 bewusst klein/einfach gehalten
  (SQL-Zählung mit Schwellenwert, kein ML) — Feinschliff der Schwellenwerte ist Phase-4-Aufgabe
  nach ersten echten Feedback-Daten.
- Detailausgestaltung der Startseiten-Kacheltexte/-Schwellenwerte (wie viele offene Entscheidungen
  gelten als "auffällig") — Phase 3, kein Architektur-Blocker.

---

## Verifikation gegen die Abschlussfragen des Auftrags (Vorschau, wird in Phase 4 vollständig beantwortet)

Dieses Dokument legt die Grundlage, mit der die 18 Abschlussfragen des Auftrags am Ende
beantwortbar werden. An dieser Stelle nur der Architektur-Bezug, keine Vorwegnahme von Phase 4:
jede Frage lässt sich auf eine konkrete Tabelle/einen konkreten Endpunkt aus den Abschnitten 2–5
zurückführen (z. B. Frage 5 "Bleibt der ursprüngliche Systemvorschlag immer erhalten?" →
`recommendation_decisions.system_werte_json`, nie überschrieben, Abschnitt 3.1/7).
