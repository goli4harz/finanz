# Datenaufbewahrung

Stand: 2026-07-31 (Paket 19, Phase 11 der fachlichen Überarbeitung). Dieses Dokument beschreibt, welche Daten wie lange und in welcher Form aufbewahrt werden, und warum.

**Grundprinzip**: historisch benötigte Bewertungen, Wirkungsdaten und Prognosen werden **niemals gelöscht**, wenn sie später für Lernen, Audit oder Simulation gebraucht werden könnten. Nur technisch unbrauchbare Rohdaten und reine Betriebs-Logs ohne fachlichen Lernwert unterliegen einer Löschfrist.

## Datenklassen und Regeln

### 1. Technisch unbrauchbare Rohdaten

**Tabelle**: `trading.news_items` mit `status = 'failed'`
**Regel**: Löschung nach 30 Tagen (`04 – Cleanup News-Tabellen`, "Loesche fehlgeschlagene News").
**Begründung**: Ein technisch fehlgeschlagener Abruf/Parse-Vorgang hat keinen Inhalt und keinen Lernwert. 30 Tage Puffer für Debugging, danach kein Nutzen mehr.
**Schutz**: seit Paket 12 zusätzlich `NOT EXISTS (news_assessments)` — sollte eine `failed`-Zeile wider Erwarten doch bewertet worden sein, bleibt sie erhalten.

### 2. Irrelevante News ohne Lernwert

**Tabelle**: `trading.news_items` mit `status = 'discarded'`
**Regel**: Löschung nach 21 Tagen (`04`, "Loesche irrelevante Rohnews").
**Begründung**: Der Erstbewertungs-Agent hat die News bewusst als irrelevant verworfen (kein Ticker-Bezug, kein fachlicher Inhalt). Kurze Frist, da diese Masse den größten Anteil der Rohdaten ausmacht (452 von ~1.100 Zeilen bei Systemstand 07-31).
**Wichtige Einschränkung** (live gefunden, Paket 12): 452 von 452 geprüften `discarded`-Zeilen hatten trotzdem eine Bewertung (`news_assessments`) — der `NOT EXISTS`-Schutz greift dadurch fast immer, die Regel läuft de facto als Sicherheitsnetz für den seltenen unbewerteten Fall, nicht als aktive Massenlöschung. Bewusste Entscheidung, keine übersehene Ineffizienz.

### 3. Historisch benötigte Bewertungen

**Tabellen**: `trading.news_items` mit `status IN ('evaluated', 'archived')`, `trading.news_assessments`, `trading.v_news_latest_assessment`
**Regel**: **Keine Löschung.** Ab 180 Tagen und abgeschlossener Wirkungsmessung wird der `news_items`-Status auf `archived` umgestellt (Paket 19, "Archiviere abgeschlossene News") — die Zeile bleibt vollständig erhalten, zählt aber nicht mehr als "aktiv" in Tagesansichten/Dashboards.
**Begründung**: Bewertungen sind die Grundlage für Lernen (Workflow `09`), Audit und jede spätere Point-in-Time-Simulation (Phase 12). Löschung würde genau die in Phase 2/3 des Auftrags geforderte Nachvollziehbarkeit zerstören.
**Archivierungs-Bedingung bewusst strenger als nur "alt genug"**: nur News, deren `news_impact_tracking.status = 'completed'` ist (nicht nur "irgendein Tracking existiert"), gelten als abgeschlossen — eine News mit noch laufender D+1..D+20-Messung bleibt `evaluated`, auch wenn sie älter als 180 Tage ist.
**Aktuell dormant**: die Wirkungsmessung braucht bis zu 20 Handelstage bis `completed`; das System ist Stand 07-31 erst ~12 Tage alt. Noch keine Zeile erfüllt beide Bedingungen (weder das 180-Tage-Alter noch ein abgeschlossenes Tracking). Die Regel ist korrekt implementiert und wird über die kommenden Monate organisch aktiv, kein Fehler.

### 4. Wirkungsdaten

**Tabelle**: `trading.news_impact_tracking`
**Regel**: **Keine Löschung, kein Archivierungsstatus.** Bleibt für die volle Systemlaufzeit erhalten.
**Begründung**: Ist selbst die Messgrundlage für Kalibrierung/Lernen (Phase 5/7 des ursprünglichen 12-Phasen-Auftrags: "saubere Wirkungsmessung"). Hat außerdem einen `FOREIGN KEY` (`NO ACTION`) auf `news_items.id` — eine Löschung wäre ohnehin blockiert, solange die zugehörige News existiert (was sie laut Regel 3 dauerhaft tut).

### 5. Fehlerprotokolle

**Tabellen**: `trading.workflow_errors`, `trading.pipeline_runs` (Status `failed`/`warning`/`skipped`/`success`)
**Regel**: Löschung nach 180 Tagen (Paket 19, "Loesche alte Betriebs-Logs").
**Begründung**: Reine Betriebs-Logs ohne fachlichen Lernwert — anders als Bewertungen oder Wirkungsdaten sagen sie nichts über die Marktrealität aus, sondern nur über den technischen Zustand der Pipeline zu einem Zeitpunkt. 180 Tage sind großzügig genug für nachträgliches Debugging von Vorfällen, ohne unbegrenzt zu wachsen. Live per `information_schema` geprüft (2026-07-31): keine Fremdschlüssel von anderen Tabellen auf diese beiden Tabellen — Löschung ist unbedenklich.
**Umfang bei Einführung** (07-31): 219 `pipeline_runs`-Zeilen, 36 `workflow_errors`-Zeilen, beide noch weit unter der 180-Tage-Grenze — Regel ist aktiv, betrifft aber aktuell 0 Zeilen.

### 6. Temporäre Payloads

**Beobachtung**: `trading.news_items.metadata_json`, `trading.pipeline_runs.metadata_json`/`market_session_snapshot`, `trading.agent_runs.metadata_json` u.ä. sind JSONB-Spalten, die potenziell große KI-Rohantworten/Zwischenergebnisse enthalten können.
**Regel**: folgt der Aufbewahrungsregel der jeweiligen Zeile (siehe oben) — es gibt keine separate Payload-Kompression oder -Kürzung.
**Nicht umgesetzt, bewusst zurückgestellt**: Payload-Kompression und Partitionierung (siehe "Nicht umgesetzt" unten) wären hier der nächste Schritt, falls Speicherplatz je zum echten Problem wird. Bei aktueller Datenmenge (niedrige drei- bis vierstellige Zeilenzahl pro Tabelle) nicht gerechtfertigt.

## Nicht umgesetzt (bewusste Zurückstellung, nicht übersehen)

- **Separate Archivtabellen**: der Auftrag nennt sie als bevorzugte Struktur ("Archivtabellen"). Umgesetzt wurde stattdessen ein Status-Flag (`archived`) auf der bestehenden Tabelle — einfacher, weniger Migrationsrisiko, bei aktuellem Datenvolumen (741 `evaluated`-Zeilen nach 12 Tagen) keine Performance-Notwendigkeit für eine physische Trennung. Sollte das Datenvolumen um Größenordnungen wachsen, ist eine spätere Migration auf eine echte `news_items_archive`-Tabelle mit identischem Schema ein reiner Kopiervorgang, kein Neubau.
- **Partitionierung**: bei aktueller Tabellengröße (niedrige drei- bis vierstellige Zeilenzahl) kein Performance-Problem, das Partitionierung rechtfertigen würde.
- **Komprimierte Payloads**: keine JSONB-Kompression oder -Kürzung eingeführt, siehe Punkt 6 oben.
- **`trading.agent_runs`, `trading.learning_rule_proposals`, `trading.scoring_weights`, `trading.recommendations`**: keine explizite Aufbewahrungsregel definiert. `agent_runs` protokolliert jeden KI-Aufruf (Kosten-/Prompt-Audit) und `learning_rule_proposals`/`scoring_weights` sind die Grundlage kontrollierten Lernens (Phase 9 des Auftrags) — beide vermutlich eher in Kategorie 3 (dauerhaft aufbewahren) einzuordnen, aber nicht explizit entschieden. `recommendations` (Empfehlungs-Historie) hat ebenfalls keine Löschregel — bei Simulationscharakter (kein echtes Order-System) vermutlich unproblematisch, aber ebenfalls nicht explizit adressiert. Sollte in einer Folge-Iteration entschieden werden, falls das Datenvolumen relevant wird.

## Zusammenfassung der Fristen

| Datenklasse | Tabelle(n) | Regel | Frist |
|---|---|---|---|
| Technisch unbrauchbar | `news_items` (failed) | Löschen | 30 Tage |
| Irrelevant, kein Lernwert | `news_items` (discarded) | Löschen | 21 Tage |
| Bewertet, historisch benötigt | `news_items` (evaluated→archived), `news_assessments` | Nie löschen, ab 180d+abgeschlossen archivieren | — |
| Wirkungsdaten | `news_impact_tracking` | Nie löschen | — |
| Fehlerprotokolle | `workflow_errors`, `pipeline_runs` | Löschen | 180 Tage |
| Temporäre Payloads | diverse `*_json`-Spalten | folgt Zeilenregel | — |
