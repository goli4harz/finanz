# HUMAN_IN_THE_LOOP_CHANGELOG.md

Chronologischer Bau-Verlauf der Human-in-the-Loop-Initiative (Entscheidungs-/Feedback-Schicht
über dem bestehenden Empfehlungs-/Paper-Trading-System). Phase 4 (dieses Dokument + Test-Report +
Final-Review) nachgetragen am 2026-09-01, elf Tage nach Phase-3-Abschluss — der eigentliche
Auftragstext mit den ursprünglichen 17 nummerierten Tests/18 Abschlussfragen ist nicht mehr im
Repo auffindbar; dieses Dokument und die beiden Geschwisterdokumente wurden daher mit einem
selbst entworfenen, inhaltlich gleichwertigen Testplan nachgezogen (siehe
HUMAN_IN_THE_LOOP_TEST_REPORT.md, Abschnitt "Hinweis zur Testplan-Herkunft").

## Phase 1 — Bestandsaufnahme (2026-08-20)

- `eff7b27` — `HUMAN_IN_THE_LOOP_REVIEW.md`: Analyse bestehender UI/Workflows/Tabellen (3
  parallele Recherche-Agenten + eigene Prüfung). Kernbefund: das Datenmodell
  (Entry/Stop/Target/CRV/Positionsgröße/Portfolio-Auswirkung/Audit-Snapshot) existierte bereits
  fast vollständig in `trading.recommendations`/`trading.paper_trades` — es fehlte fast nur die
  Entscheidungsschicht selbst.

## Phase 2 — Architektur (2026-08-20)

- `dee3f16` — vier offene Entscheidungsfragen mit dem Nutzer geklärt (separate neue Workflows
  statt Erweiterung bestehender, zentrale Nav-Bar jetzt bauen, `probability_estimates` auch aus
  `simulation_trades` speisen, Vorfilter-verworfene News vollständig statt nur stichprobenhaft
  persistieren).
- `3526927` — `HUMAN_IN_THE_LOOP_ARCHITECTURE.md`: sechs neue Webhook-Seiten + `Finanz_Web_NavBar`
  geplant, drei neue Tabellen entworfen (`recommendation_decisions`, `trade_reviews`,
  `news_false_negative_flags`).

## Phase 3 — Umsetzung (2026-08-20 bis 2026-08-21)

- `62f3356` — `sql/071`: die drei Kern-Tabellen + additive Erweiterungen (`news_items.status`
  bekommt `'filtered'`, `probability_estimates` bekommt `data_source`).
- `ec56cdf` — `Finanz_Web_NavBar` (zentraler Nav-Sub-Workflow, Vorbild `ALLRIS_Web_NavBar`).
- `952964e` — **Modul 1+2 Trading-Entscheidungszentrale** (`/heute-handeln`,
  `/trade-entscheidung`): tägliche Trade-Ideen-Liste + Detailansicht mit vollem manuellem
  Handelsplan, Entscheidung (PAPER TRADE / BEOBACHTEN / SPÄTER ENTSCHEIDEN / ABLEHNEN) mit
  Ablehnungsgründen und optionaler Werteanpassung, System-Original bleibt immer erhalten.
- `d0dbd03` — **Modul 3 Paper-Trading-Review** (`/trade-review`, `/trade-review-abgeben`):
  System- vs. Nutzer-Performance-Vergleich, Review geschlossener Trades.
- `0a59c1a` — **Modul 4 News-Pruefen** (`/news-pruefen`, `/news-review-abgeben`): fünf Sektionen
  (Zu bestätigen/Unsicher/KI verworfen/Vorfilter verworfen/gemeldete False Negatives), erstmals ein
  Schreibpfad für `news_assessments.confirmation_status` (seit `sql/012` ungenutzt) und für die
  vorher komplett fehlende False-Negative-Meldung.
- `7c0463b` — **Modul 5 Lernen-und-Feedback** (`/lernen-feedback`, nur GET): Aggregations-Hub über
  fünf Kategorien.
- `56e81d0` — **Modul 6 Regelnuebersicht** (`/regeln`, nur GET): alle drei
  Regel-Versionierungsstile lesbar (`scoring_weights`, `strategy_regime_matrix`,
  `strategy_parameters`, `strategy_status`) plus `news_match_exclusions`.
- `7d8fb09` — **Modul 7 Startseite** (`/heute`, nur GET): sechs KPI-Kacheln, darunter der erste
  Lesezugriff überhaupt auf `trading.workflow_errors` (seit Workflow 11 nur beschrieben, nie
  gelesen).

## Nav-Vereinheitlichung (2026-08-21, gleicher Tag, Folgesession)

- `b4c2ee2` — `aktien-status` (Workflow 07) hatte noch die alte, isolierte Nav-Zeile.
- `ed29f95` — acht weitere alte Admin-Seiten (Watchlist, RSS-Quellen, Lernvorschläge, Historische
  Marktdaten, GDELT-Import, False-Positive-Lernvorschläge, Ausschlüsse-Audit, alle drei
  Simulation-Steuerzentrale-Unterseiten) hatten dasselbe Problem — alle auf `Finanz_Web_NavBar`
  vereinheitlicht.

## Vorfilter-Wirksamkeit (2026-08-21, gleicher Tag)

- `d357f34` — `trading.news_prefilter_runs` (eine Zusammenfassungszeile je stündlichem
  Workflow-03-Lauf, keine Einzelartikel) + KPI-Block auf News-Pruefen. Noch am selben Tag später
  gegen einen echten stündlichen Lauf bestätigt (7 Läufe, 949 geprüft/420 durchgelassen).
- `8444706`, `fe1efab`, `692064c` — Folgeausbau: Live-Vorfilter respektiert jetzt bestätigte
  Ausschlussregeln, historische Ticker-Filter-Durchlassquote ergänzt.

## Phase 4 — Tests + Abschlussdokumente (2026-09-01, dieses Dokument)

- Live-Testrunde gegen die produktive Instanz (`172.16.1.6:5678`) durchgeführt, siehe
  `HUMAN_IN_THE_LOOP_TEST_REPORT.md` für Details und Befunde.
- Kein Code an den sieben Modulen geändert — reine Verifikation + Dokumentation. Eine
  Beobachtung (Entscheidungsformular auch bei `portfolio_blocked`-Empfehlungen sichtbar, Schreiben
  aber korrekt vom Backend verweigert) wird dort als Empfehlung für eine mögliche spätere
  UI-Politur festgehalten, nicht als Defekt gewertet und nicht in dieser Session behoben.

## Bewusst nicht umgesetzt (unverändert seit Phase 3)

- Vollständige Artikel-Persistenz für Vorfilter-verworfene News (nur Aggregat-Zähler, laut
  Nutzerentscheidung in Phase 2 die bewusst gewählte leichtgewichtige Variante).
