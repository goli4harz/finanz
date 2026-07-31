# Opportunity / Risk / Evidence (Welle 2, AP4)

Stand: 2026-08-01. Ersetzt die fachliche Bedeutung des bisherigen `decision_score` (ein einziger gemischter Wert, seit Paket 7/Welle 1) durch drei getrennte Dimensionen auf `trading.recommendations` (sql/033).

## `decision_score` — veraltet, nicht entfernt

Bleibt aus Rückwärtskompatibilität bestehen (kein Consumer bricht), wird aber nur noch als `round(opportunity_score × 100)` abgeleitet befüllt — **kein eigenständiger Wert mehr**. Als veraltet dokumentiert (Spalten-Kommentar in `sql/033`). Migrationsplan für eine echte Entfernung: erst wenn `07`/`10` nachweislich nicht mehr darauf zugreifen (aktuell zeigt `07` ihn noch nicht separat an, `10` erhält ihn nur als Teil des vollständigen `recommendations`-Objekts für den Prüf-Agent).

## Opportunity Score

**Miss die Attraktivität des Setups, NICHT die Gewinnwahrscheinlichkeit.** Formel (0–1):

```
opportunity = 0.35 × min(1, raw_score)               (Staerke des Strategiesignals)
            + 0.25 × min(1, fit_multiplier)           (Regime-Passung, aus der Strategie-Regime-Matrix)
            + fundamentaler Bonus (0.15 gleichgerichtet, 0.05 unbekannt, 0 gegenlaeufig)
            + 0.25 × min(1, reward_risk_ratio / 3)     (Chance-Risiko-Verhaeltnis)
```

Alle vier Komponenten sind bereits an anderer Stelle real berechnete Werte (Strategiesignal, Regime-Matrix, Fundamentaltrend, Risikomodell) — keine KI-Schätzung, keine erfundene Zahl.

## Risk Score

**Miss die Gefährlichkeit. Ein hoher Wert bedeutet hohes Risiko** (nicht invertiert, wie im Auftrag explizit gefordert):

```
risk = min(0.3, stop_distance_pct × 3)                (relative Stopdistanz)
     + 0.15 (limited) / 0.3 (invalid) bei Datenqualitaet
     + 0.3 (stress) / 0.1 (unknown) beim Marktregime
     + 0.15 bei widersprüchlichen News am selben Tag
```

**Liquiditätsrisiko** und **Korrelation/Konzentration** (im Auftrag als mögliche Komponenten genannt) sind **nicht** enthalten — keine Datenquelle für aggregierte Liquidität (siehe `docs/MARKTREGIME.md`, `liquidity_regime` bleibt `not_available`) bzw. für andere offene Positionen im selben Sektor/Faktor (Welle 3, falls gewünscht).

## Evidence Confidence

**Miss die Belastbarkeit, unter Vermeidung von Doppelzählung korrelierter Indikatoren.**

### Evidenzgruppen (dokumentierte Korrelationslogik)

| Gruppe | Zugehörige Evidenz-Stichworte |
|---|---|
| `overextension` | RSI, Bollinger-Band-Berührung (beide messen "Abweichung vom gleitenden Durchschnitt") |
| `momentum` | MACD (Linie, Kreuzung, Histogramm — alle aus derselben EMA12/EMA26-Differenz) |
| `trend_confirmation` | EMA20, EMA200, allgemeine Trendaussagen |
| `volume` | Volumenfaktor |
| `price_move` | Tagesbewegung, 52-Wochen-Nähe, Ausbruch |
| `fundamental` | Fundamentaltrend (eigene Datenquelle, nicht technisch korreliert) |
| `news` | Nachrichtenkatalysator (eigene Datenquelle) |

Jedes Evidenz-Stichwort aus dem Strategiesignal wird per Schlüsselwort-Erkennung genau EINER Gruppe zugeordnet (`classifyEvidenceGroup()`), Formel zählt **Gruppen**, nicht einzelne Belege:

```
evidence = (Anzahl distinkter belegter Gruppen / 6)
         × max(0.3, data_quality_score)
         × 0.8 (falls Fallzahl der Fundamentaldaten-Revisionen < 3, sonst 1.0)
```

Fünf RSI-nahe Belege zählen damit als EINE Gruppe (`overextension`), nicht als fünf unabhängige Bestätigungen — genau die im Auftrag genannte Falle ("RSI und Bollinger sind häufig dieselbe Überdehnungsinformation") wird dadurch vermieden.

### Fallzahl

`fundamentalTrend().momentum.revisions_verglichen` (Anzahl verglichener Fundamentaldaten-Revisionen) dient als einzige verfügbare Fallzahl-Größe — ein Abschlag bei weniger als 3 Revisionen, kein hartes Veto (Datenlage ist zu Beginn des Systems naturgemäß noch dünn).

## Nicht umgesetzt / bewusst offen

- Korrelation/Konzentration über mehrere gleichzeitig offene Positionen hinweg (Risk Score) — Welle 3.
- Ein echtes "unabhängige Quelle bestätigt dieselbe Aussage"-Modell für Evidence Confidence (aktuell gruppenbasiert, nicht quellenbasiert) — Welle 3, falls mehr unabhängige Datenquellen hinzukommen.

## Status

- ✅ Umgesetzt: alle drei Scores, Evidenzgruppen-Logik, `decision_score` sauber deprecated.
- 🔴 Nicht live getestet (siehe `docs/TESTPLAN_WELLE_2.md`).
