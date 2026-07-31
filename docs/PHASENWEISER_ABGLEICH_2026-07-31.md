# Phasenweiser Abgleich: Original-Auftrag vs. tatsächlicher Stand

Stand: 2026-07-31. Dieser Abgleich prüft den vollständigen Original-Auftrag "Fachliche Überarbeitung der Aktienanalyse- und Lernpipeline" (12 Phasen) Punkt für Punkt gegen den live verifizierten Datenbank- und Workflow-Stand — nicht gegen die bisherige Paket-1-12-Zusammenfassung in `OFFENE_AUFGABEN.md`, die eine vereinfachte Paraphrase war.

**Methode**: `information_schema.columns` für das komplette `trading`-Schema live abgefragt (452 Spalten über 20 Tabellen + 1 View), die View-Definition von `v_news_latest_assessment` per `pg_get_viewdef` gelesen, `06 – Empfehlungswatchlist`s Entscheidungscode gegrept, Existenz der im Auftrag geforderten `docs/*.md`-Dateien geprüft. Workflow-Code wurde nicht Zeile für Zeile für jede Phase gelesen (siehe "Nicht geprüft" je Phase) — das wäre ein deutlich größerer Aufwand und sollte gezielt nachgeholt werden, wo eine Phase als Umsetzungskandidat ausgewählt wird.

**Ehrliches Gesamtbild vorab**: Die in `OFFENE_AUFGABEN.md` als "Paket 1-11" dokumentierte Arbeit ist real und live verifiziert, deckt aber nur einen Teil der hier im Original-Auftrag geforderten Detailtiefe ab. Mehrere Phasen (5, 6, 7, 8's Veto-Logik, 11, 12) sind schema-seitig **nicht** oder nur ansatzweise umgesetzt.

---

## Phase 0: Bestandsaufnahme

**Status: teilweise.** `docs/FACHLICHE_BESTANDSAUFNAHME.md` existiert, wurde aber gegen eine Paraphrase des Auftrags geschrieben, nicht gegen diesen exakten Text. Inhaltlich weitgehend zutreffend (live gegengeprüft), aber nicht 1:1 gegen die hier gestellten Anforderungen entstanden.

## Phase 1: Vollständige News-Datenbasis

**Status: größtenteils erfüllt, ein klarer Fund.**

`news_items` enthält: `title`, `url`, `source`, `published_at`, `article_text`, `content_hash`, `language`, `last_seen_at`, `preclassified_type`, `preclassified_tickers`, `match_reason`, `publication_time_quality` — praktisch die komplette geforderte Feldliste, nur teils anders benannt (`title` statt `raw_title`, `created_at`/`fetched_at` statt `first_seen_at`/`ingested_at` — funktional plausibel äquivalent, nicht geprüft ob Semantik exakt übereinstimmt).

**Fund: `raw_description` fehlt komplett** — keine Spalte `description`/`raw_description` in `news_items`, auch nicht ersichtlich in `metadata_json` (nicht inhaltlich geprüft, nur Spaltenschema). Der Auftrag verlangt explizit: "Setze beschreibung nicht mehr pauschal auf einen leeren String." Muss im `03`-Ingestion-Code geprüft werden, ob eine Beschreibung überhaupt irgendwo ankommt, bevor eine Spalte ergänzt wird.

**Nicht geprüft**: ob `03`s KI-Payload tatsächlich alle vorhandenen Felder ans Modell weiterreicht (nur Schema, nicht Code gelesen); Content-Hash-Dedup-Verhalten in der Praxis; Volltext-Ladelogik/Begrenzung.

## Phase 2: Genau eine gültige Bewertung je Nachricht

**Status: erfüllt, live verifiziert.**

`trading.v_news_latest_assessment` existiert. View-Definition geprüft:

```sql
ORDER BY ni.id, (CASE
    WHEN na.confirmation_status = 'manually_confirmed' THEN 0
    WHEN na.prompt_version = 'news-recherche-agent-v1' THEN 1
    WHEN na.prompt_version = 'news-ingestion-v1' THEN 2
    ELSE 3
  END), na.created_at DESC
```

Prioritätslogik entspricht exakt der Vorgabe (manuell > Recherche > Erstbewertung, bei Gleichstand neueste zuerst), `WHERE confirmation_status IS DISTINCT FROM 'manually_rejected'` schließt abgelehnte Bewertungen korrekt aus, `DISTINCT ON (ni.id)` garantiert genau eine Zeile je Nachricht. Fast alle geforderten Ausgabefelder vorhanden (`effect_level` deckt vermutlich das im Auftrag zusätzlich genannte `strength` mit ab — beide könnten dasselbe meinen, nicht abschließend geklärt).

**Nicht geprüft**: ob `06`/`07`/`08`/`09`/`10` diese View tatsächlich durchgängig nutzen statt direkt `news_assessments` zu joinen (laut `OFFENE_AUFGABEN.md` "Paket 2+3" wurde das für mindestens einen Konsumenten gemacht, nicht alle einzeln bestätigt).

## Phase 3: Wiederholte Recherche verhindern

**Status: Schema erfüllt, Logik nicht verifiziert.**

Alle geforderten Felder vorhanden: `research_status`, `research_attempts`, `last_research_at`, `next_research_at`, `research_error`, `reprocess_requested`.

**Nicht geprüft**: ob `03a`s tatsächliche Kandidatenauswahl (a) eine Obergrenze für `research_attempts` respektiert, (b) das explizite `reprocess_requested`-Flag berücksichtigt, (c) nicht mehr allein wegen `wirkungsrichtung = 'unklar'` erneut auswählt (der im Auftrag explizit verbotene Fall). Erfordert Lesen von `03a`s Kandidaten-Query/Code.

## Phase 4: Konfidenzen und Prognosen trennen

**Status: größtenteils erfüllt.**

`news_assessments` hat: `relevance_confidence`, `probability_positive/negative/neutral`, `strength_confidence`, `data_quality_score`, `prediction_horizon_days`, `prediction_created_at`, `modell_version` (~model_name), `prompt_version`. Die verlangte Wahrscheinlichkeitsverteilung ist als drei separate Spalten abgebildet, nicht als JSON-Objekt — funktional gleichwertig.

**Fund**: keine explizit benannten `predicted_direction`/`predicted_strength`-Spalten in `news_assessments` selbst — die Legacy-Felder `wirkungsrichtung`/`wirkung_staerke` übernehmen diese Rolle vermutlich weiter, ohne als "neue, bevorzugte" Felder gekennzeichnet zu sein, wie der Auftrag es vorsieht ("Passe ... an, dass sie die neuen Felder bevorzugen"). Diese Felder existieren separat bereits in `news_impact_tracking` (für die spätere Ist-Messung), aber nicht am Zeitpunkt der Vorhersage in `news_assessments`.

**Nicht geprüft**: ob eine DB- oder Code-seitige Validierung existiert, die sicherstellt `probability_positive + neutral + negative = 1` und ungültige Werte ablehnt ("dürfen nicht stillschweigend gespeichert werden") — kein CHECK-Constraint im Spaltenschema sichtbar (aber CHECK-Constraints tauchen in `information_schema.columns` ohnehin nicht auf, müsste separat per `pg_constraint` geprüft werden).

## Phase 5: Fundamentaldaten numerisch und historisch

**Status: ERFÜLLT (2026-07-31, Pakete 13+14, zwei Schritte).**

Ursprünglicher Befund (bis 2026-07-31 vormittags): `fundamentals_history` (aus Paket 8) existierte, aber **alle** fachlichen Werte waren als `text` typisiert, kein `_numeric`, kein `known_at`/`valid_from`/`valid_to`/`revision_number` — reine Spiegelung des alten Data-Table-Formats, genau das vom Auftrag ausgeschlossene Anti-Pattern.

**Schritt 1** (`sql/021`, Paket 13): additive `_numeric`-Spalten + `currency`, Rohwerte exakt wie von der lokalen FastAPI geliefert (kein Anzeige-Rundenformat). `01`s Aufbereitungs- und Historie-Nodes angepasst. Zwei Bugs live gefunden+gefixt (Data-Table-Roundtrip verlor die neuen Felder; `.item`-Fragilität lieferte anfangs für jeden Ticker denselben Wert).

**Schritt 2** (`sql/022`, Paket 14): `known_at`/`valid_from`/`valid_to`/`revision_number` ergänzt, `UNIQUE(ticker, snapshot_date)` durch `UNIQUE(ticker, snapshot_date, revision_number)` + partiellen Unique-Index (genau eine aktuelle Revision je Tag) ersetzt. Das bisherige `ON CONFLICT DO UPDATE` (überschrieb frühere Werte am selben Tag ersatzlos, live bestätigt) durch Schließen+Neuanlegen ersetzt. Die beiden einzigen Konsumenten (`07`, `10`, per grep gefunden) auf `valid_to IS NULL` angepasst, damit sie weiterhin eine Zeile je Tag sehen. Alles live über mehrere Testläufe verifiziert.

## Phase 6: Technische Strategien trennen

**Status: NICHT erfüllt.**

`technical_signals_history` hat `signal_punkte`, `signal_gruende`, `signal_staerke` als einzelne Text-Felder — ein einziges kombiniertes Punktesystem, keine Trennung in `mean_reversion_signal`/`trend_following_signal`/`breakout_signal` mit je eigenem `raw_score`/`regime_fit`/`data_quality`/`evidence`-JSON. Keine entsprechenden Spalten oder JSON-Strukturen vorhanden.

## Phase 7: ATR und Volatilität

**Status: NICHT erfüllt.**

Keine `atr_14`, keine realisierte Volatilität (20/60 Tage), keine durchschnittliche Tagesrange in `technical_signals_history`. `ziel_kurs`/`stop_kurs` existieren als einzelne Text-Felder mit `ziel_logik`/`stop_logik`-Begründungstext, aber keine Trennung `legacy_stop`/`legacy_target` vs. `atr_stop`/`atr_target`, keine zentrale Multiplikator-Konfiguration erkennbar.

## Phase 8: Empfehlungslogik erweitern

**Status: Schema teilweise erfüllt, Kern-Anforderung (harte Vetos) NICHT erfüllt.**

`recommendations` hat: `stop_price`, `target_price`, `thesis_expires_at`, `expected_holding_days`, `data_quality_score`, `market_regime`, `decision_score`, `decision_blockers` (jsonb), `invalidation_reason`, `is_theoretical`.

Fehlend: `decision` (expliziter Entscheidungswert), `decision_reasons` (nur `decision_blockers` vorhanden, keine getrennten Gründe), `strategy` (kein Bezug zu Phase 6, die ohnehin fehlt), `regime_fit`, `fundamental_risk`, `invalidation_price`, `expected_return`/`expected_loss`/`expected_value`.

**Wichtigster Fund**: `decision_score`/`decision_blockers` werden in `06`s Code (`Empfehlungen: Abgleich berechnen`) berechnet und geschrieben, aber **nicht zum Blockieren verwendet** — bestätigt durch `OFFENE_AUFGABEN.md`s eigene Formulierung zu Paket 10 ("rein informativ, die eigentliche Kauf-/Verkauf-Entscheidung bleibt unverändert") und Paket 7 ("keine Verdrahtung in 06s Entscheidungslogik"). Einzige tatsächliche Gating-Wirkung: Paket 11s RSI-Gegentrend stuft bei starkem Gegentrend zum Vorschlag herab (über den bereits vorhandenen `REQUIRE_CONFIRMATION`-Pfad) — das ist eine weiche Abstufung, kein hartes Veto im Sinne des Auftrags. Keiner der im Auftrag aufgelisteten harten Veto-Gründe (unzureichende Datenqualität, veraltete Nachricht, widersprüchliche gültige Bewertung, fehlender Referenzkurs, unplausibler Stop/Ziel, abgelaufene These, offene DB-Fehler) ist als tatsächliche Blockade im Code gefunden worden.

## Phase 9: Hebelproduktberechnung entschärfen

**Status: größtenteils erfüllt.**

`is_theoretical`-Flag existiert in `recommendations` (Bonus über den Auftrag hinaus, der nur Textkennzeichnung verlangt). Laut Bestandsaufnahme bereits vor dieser Überarbeitung textuell korrekt gekennzeichnet ("Kein konkretes Produkt"). **Nicht geprüft**: ob `is_theoretical` vom Code tatsächlich gesetzt wird (Spalte könnte schema-only/immer NULL sein, wie bei anderen Paket-7-Feldern der Fall).

## Phase 10: Trigger und Orchestrator

**Status: größtenteils erfüllt, eine bewusste Abweichung.**

`pipeline_runs` hat `run_id`, `stage_name`, `status`, `started_at`, `finished_at`, `business_date`, `market_session_snapshot` (jsonb — deckt Session-Status vermutlich als Blob statt Einzelspalten ab, Inhalt nicht geprüft). `market_reference` liefert Handelszeiten/Zeitzonen je Markt.

**Bewusste Abweichung** (bereits in `OFFENE_AUFGABEN.md` dokumentiert, keine neue Erkenntnis): kein harter `UNIQUE`-Constraint/`idempotency_key` auf `pipeline_runs` — Entscheidung, um manuelle Test-Reruns nicht als Duplikatfehler zu werten. Weicht vom Auftragstext ab ("darf... nicht unkontrolliert doppelt schreiben"), war aber eine explizite, dokumentierte Abwägung, keine übersehene Lücke.

**Nicht geprüft**: Inhalt von `market_session_snapshot` (ob `session_status`/`data_is_partial`-Äquivalente tatsächlich befüllt werden); ob alle Einzeltrigger von `02`/`02b`/`05`/`06` wie dokumentiert deaktiviert sind (letzter Stand aus `OFFENE_AUFGABEN.md`, nicht heute erneut live geprüft).

## Phase 11: Cleanup auf Archivierung umstellen

**Status: NICHT erfüllt.**

Heute (2026-07-31) wurde ein konkreter, akuter Fremdschlüssel-Bug in `04`s drei bestehenden DELETE-Regeln gefunden und gefixt (`news_assessments`-Schutz ergänzt, siehe Commit `b4b78e0`) — das war eine reine Bugfix-Maßnahme, **keine** Umsetzung dieser Phase. Der Auftrag verlangt eine strukturelle Umstellung (Status `archived`, Archivtabellen, Partitionierung, Aufbewahrungsregeln je Datenklasse) plus `docs/DATENAUFBEWAHRUNG.md` — nichts davon existiert. `news_items` hat kein `archived`-Status (nur `discarded`/`failed`/`evaluated`/vermutlich weitere), keine Archivtabelle gefunden.

## Phase 12: Vorbereitung Point-in-Time-Simulation

**Status: teilweise (Einzelfelder vorhanden), Kern-Deliverable fehlt.**

Vorhanden: `published_at`, `assessed_at`, `prompt_version` (mehrfach), `rule_version`/`configuration_version` (`agent_runs`, aus Paket 6). Fehlend als explizite, durchgängige Felder: `event_time`, `first_seen_at`, `ingested_at`, `known_at`, `valid_from`/`valid_to`, `model_version` (nur `model_name` vorhanden, andere Semantik — Auftrag will Versionierung, nicht nur Namen).

`docs/POINT_IN_TIME_SIMULATION.md` **existiert nicht**.

---

## Fehlende Pflicht-Dokumente (alle Phasen)

Live geprüft, keines existiert:

- `docs/DATENAUFBEWAHRUNG.md` (Phase 11)
- `docs/POINT_IN_TIME_SIMULATION.md` (Phase 12)
- `docs/FACHLICHE_AENDERUNGEN.md`
- `docs/DATENMODELL_NEU.md`
- `docs/MIGRATIONSREIHENFOLGE.md`
- `docs/TESTPLAN.md`
- `docs/ROLLBACK_PLAN.md`

## Zusammenfassung — Ampel je Phase

| Phase | Thema | Status |
|---|---|---|
| 0 | Bestandsaufnahme | 🟡 vorhanden, nicht gegen diesen exakten Text geschrieben |
| 1 | Vollständige News-Basis | 🟡 fast vollständig, `raw_description` fehlt |
| 2 | Eine gültige Bewertung | 🟢 erfüllt, live verifiziert |
| 3 | Recherche-Wiederholung verhindern | 🟡 Schema da, Logik nicht geprüft |
| 4 | Konfidenzen/Prognosen trennen | 🟡 größtenteils da, Validierung ungeprüft |
| 5 | Fundamentaldaten numerisch/historisch | 🟢 erfüllt (Pakete 13+14, 07-31) |
| 6 | Technische Strategien trennen | 🔴 nicht erfüllt |
| 7 | ATR/Volatilität | 🔴 nicht erfüllt |
| 8 | Empfehlungslogik/harte Vetos | 🔴 Schema teilweise, Vetos fehlen |
| 9 | Hebelprodukt entschärfen | 🟢 größtenteils erfüllt |
| 10 | Orchestrator/Idempotenz | 🟡 größtenteils, bewusste Abweichung |
| 11 | Cleanup → Archivierung | 🔴 nicht erfüllt |
| 12 | Point-in-Time-Vorbereitung | 🟡 Felder teilweise, Dokument fehlt |

**Fazit (Stand ursprünglich 2026-07-31 vormittags)**: von 13 geprüften Punkten waren 2 grün, 6 gelb (teilweise/ungeprüfte Details), 5 rot (nicht umgesetzt). Der bisherige "Pakete 1-11 erledigt"-Stand war real, aber deutlich unterhalb der im Original-Auftrag geforderten Tiefe. **Update, selber Tag nachmittags**: Phase 5 (der größte Einzelbefund) über Pakete 13+14 vollständig nachgezogen — Stand jetzt 3 grün, 6 gelb, 4 rot. Nächster naheliegender Kandidat für denselben Rot→Grün-Umbau: Phase 8s harte Veto-Logik (Schema existiert bereits, siehe oben) oder Phase 11 (Archivierung, siehe [[finanz-paket12-phase11-cleanup-fk-bug-2026-07-31]] für den bisherigen Teil-Fix).
