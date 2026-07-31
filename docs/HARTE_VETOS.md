# Harte Vetos (Welle 1, AP5)

Stand: 2026-07-31. Alle 12 im Auftrag geforderten harten Vetos für das Öffnen einer theoretischen Position, umgesetzt in `06 – Empfehlungswatchlist – Agent V1`, Node `Empfehlungen: Abgleich berechnen`, Funktion `pruefeOeffnungsVetos()`.

## Format

Jedes Veto ist ein strukturiertes Objekt (kein Freitext):

```json
{
  "code": "STOP_WRONG_SIDE",
  "severity": "hard",
  "source": "risk_model",
  "message": "Stop liegt bei einem Long-Setup nicht unterhalb des Einstiegs",
  "observed_value": 102.5,
  "required_value": "< 100.0"
}
```

Ein hart vetoetes Öffnen wird **nicht** als `recommendations`-Zeile geschrieben (wie vor Welle 1), sondern strukturiert in `trading.recommendation_veto_log` protokolliert (sql/028) — sichtbar in `07`/`10` (neue Sektionen "Harte Vetos heute").

## Die 12 Vetos

| # | Code | Quelle der Prüfung | Umsetzung |
|---|---|---|---|
| 1 | `PRICE_MISSING` | technical_signal | `aktueller_kurs` null/leer/NaN/≤0 (bereits seit Paket 15 vorhanden, jetzt strukturiert) |
| 2 | `DATA_QUALITY` | technical_signal | `data_quality_status` ∈ {invalid, stale, session_incomplete} (siehe `docs/DATENQUALITAET_UND_SESSIONS.md`) |
| 3 | `NEWS_STALE` | news | Alter der jüngsten unterstützenden News > strategieabhängiger Schwelle: mean_reversion 6h, breakout 3h, trend_following 24h, unbekannt 12h |
| 4 | `STOP_TARGET_INVALID` | technical_signal | Kein verwertbarer ATR-Stop/-Ziel (bereits seit Paket 17 vorhanden, jetzt strukturiert) |
| 5 | `STOP_WRONG_SIDE` | risk_model | Stop nicht auf der korrekten Seite des Einstiegs (long: Stop < Entry, short: Stop > Entry) — **neu in Welle 1** |
| 6 | `TARGET_WRONG_SIDE` | risk_model | Ziel nicht auf der korrekten Seite des Einstiegs — **neu in Welle 1** |
| 7 | `RRR_TOO_LOW` | risk_model | `reward_risk_ratio < MIN_REWARD_RISK_RATIO` (Konfig, Default 1,5) — **neu in Welle 1** |
| 8 | `THESIS_INVALID` | thesis_engine | Selbst-Konsistenz-Check: die deterministisch berechnete `thesis_expires_at` (AP7) fehlt oder liegt bereits in der Vergangenheit — siehe Auslegung unten |
| 9 | `DB_ERROR` | pipeline | `techRows.length === 0` oder `trendRows.length === 0` (im Normalbetrieb bei 15 aktiven Tickern nie leer) — Lauf-Ebene, blockiert alle Eröffnungen des Laufs |
| 10 | `REFERENZMARKT_FEHLT` | market_context | Vereinfacht: `trading.market_context_history` hat für heute keine Zeile (System-weite Verfügbarkeit von `02b`) — siehe Auslegung unten |
| 11 | `WIDERSPRUECHLICHE_NEWS` | news | Positive und negative starke News am selben Tag für denselben Ticker (bereits seit Paket 15 vorhanden, jetzt strukturiert) |
| 12 | `HISTORY_252_MISSING` | technical_signal | `dominant_strategy === 'breakout'` und `breakout_history_ausreichend === false` |

## Bewusste Auslegungsentscheidungen

**Veto 8 (`thesis_expires_at fehlt oder ist bereits überschritten`)**: der Auftrag formuliert dies als Veto für eine **neue** Eröffnung. Da `thesis_expires_at` erst *bei* der Eröffnung berechnet wird (AP7), gibt es zum Prüfzeitpunkt noch keine "alte" These, die ablaufen könnte. Umgesetzt als Selbst-Konsistenz-Prüfung: **nachdem** `computeThesis()` gelaufen ist, wird geprüft, ob das Ergebnis überhaupt gültig ist (nicht null, nicht bereits abgelaufen). Das fängt einen Bug in der Zeitstop-Berechnung selbst ab, bevor eine kaputte These geschrieben würde — dürfte im Normalbetrieb nie auslösen.

**Veto 10 (`Referenzmarkt erforderlich, aber nicht verfügbar`)**: der Auftrag nennt keine genaue Zuordnungsregel Ticker→Referenzmarkt für diesen speziellen Veto. `stock_instruments.benchmark_symbol` existiert (z.B. `^GDAXI` für alle DAX-Werte), aber `06` lädt diese Zuordnung aktuell nicht pro Ticker. Vereinfacht auf eine **system-weite** Prüfung: liegt für heute überhaupt eine `market_context_history`-Zeile vor (d.h. ist `02b` heute gelaufen)? Das deckt den realistischen Ausfall ("02b ist heute nicht gelaufen") ab, nicht aber eine feingranulare Pro-Ticker-Zuordnung. Dokumentiert als bewusste Vereinfachung, kein Versehen.

**Veto 3 (News-Alter-Schwellen)**: die konkreten Stunden-Schwellen (6h/3h/24h/12h) sind nicht im Auftrag vorgegeben. Deterministisch aus derselben Horizont-Logik wie AP7 abgeleitet (kürzerer Handelshorizont → kürzere zulässige News-Aktualität), aber eine reine Modellannahme, kein empirisch hergeleiteter Wert. Über `docs/HARTE_VETOS.md` dokumentiert, nicht über `pipeline_config` konfigurierbar (Welle 2, falls gewünscht).

## Schließungen sind ausgenommen

**Kein** hartes Veto blockiert eine Schließung vollständig (Auftragsvorgabe). Fehlt/ist der heutige Kurs ungültig, greift ein Fallback auf den letzten bekannten gültigen Kurs der vergangenen 5 Handelstage (mit explizitem Vermerk im `exit_grund`). Gibt es auch keinen solchen Kurs, wird trotzdem geschlossen (ohne Performance-Berechnung, mit Hinweis auf manuelle Prüfung) — nie eine stillschweigende Nicht-Schließung.

**Gefundener und behobener Bestandsfehler**: vor Welle 1 blockierte der `kursUngueltig`-Check OEFFNEN **und** SCHLIESSEN gemeinsam (derselbe `continue` traf beide Pfade), obwohl der Auftrag explizit einen sicheren Schließungspfad fordert. In Welle 1 getrennt.

## Status

- ✅ Umgesetzt: alle 12 Vetos, strukturiertes Logging, Schließungs-Fallback.
- 🔴 Nicht live gegen einen echten Trigger getestet (siehe `docs/TESTPLAN_WELLE_1.md`) — nur Syntax-Check vor dem Push.
