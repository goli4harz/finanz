# 4S – Trade Quality + Cost Efficiency Analysis (Run 45)

**Datum:** 2026-09-14
**Source of truth:** ausschliesslich `trading.simulation_shadow_trades` und
`trading.simulation_decision_log` (decision_stage `LIVE_PARITY_SHADOW`) fuer
`simulation_run_id = 45`. Keine Zahlen aus Run 42 uebernommen (Run 42 ist keine
fachliche Baseline mehr – Portfolio-State-Multiplikationsbug dort behoben in Run 45).

**Run 45 Konfiguration:** Replay Scope 2026-05-01 bis 2026-08-15, 15 Core-Ticker,
Mode `AVAILABLE_DATA_LIVE_REPLAY`, Policy `CURRENT_POLICY_REPLAY`, Initial Portfolio
`EMPTY_SYNTHETIC`.

**Methodische Einordnung (gilt fuer den gesamten Bericht):** Run 45 ist
**Development Window Evidence** – kein Out-of-Sample-Test, kein Holdout, kein Forward
Test, kein Beweis eines generalisierbaren Edge. Keine Aussage in diesem Bericht ist
als "Strategie funktioniert sicher" oder "Edge bewiesen" zu lesen.

**Wichtige Schema-Einschraenkung:** `trading.simulation_shadow_trades` hat nur
`entry_fee`/`entry_slippage` als separate Kostenspalten – **keine** eigenen
`exit_fee`/`exit_slippage`-Spalten. In der Tabelle unten ist die Exit-seitige
Kostenkomponente daher als `Other(Exit)Cost = TotalCost − EntryFee − EntrySlip`
**abgeleitet**, nicht direkt aus einer eigenen Spalte gelesen. `TotalCost` selbst ist
als Residuum `Gross − Net` definiert (es gibt keine eigene Gesamtkosten-Spalte) – die
Identitaet `Gross − TotalCost = Net` ist damit rechnerisch eine Tautologie fuer jede
Einzelzeile, kein unabhaengiger Beweis; unabhaengig pruefbar war nur, dass die
**Summe** ueber alle 60 Zeilen mit den vom Nutzer vorgegebenen Zielwerten
(652.00 / 1858.20 / -1206.20 EUR) exakt uebereinstimmt (siehe Teil A/Phase 2).

---

## PHASE 1 – Accounting pro Trade (alle 60 CLOSED Trades)

| # | Ticker | Strategy | Dir | Decision | Entry | Exit | Qty | EntryPx | ExitPx | Stop | Target | PosVal | RiskAmt | Gross | EntryFee | EntrySlip | Other(Exit)Cost | TotalCost | Net | Return% | R | HoldDays | ExitReason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BMW.DE | mean_reversion | long | 2026-05-04 | 2026-05-05 | 2026-05-06 | 105 | 76.02 | 79.03 | 74.02 | 79.03 | 7982.10 | 210.00 | 316.05 | 11.97 | 7.98 | 20.75 | 40.70 | 275.35 | 3.45 | 1.31 | 1 | target_reached |
| 2 | DBK.DE | trend_following | short | 2026-05-04 | 2026-05-05 | 2026-05-06 | 308 | 25.95 | 27.20 | 27.20 | 23.87 | 7992.60 | 385.00 | -385.00 | 11.99 | 7.99 | 20.95 | 40.93 | -425.93 | -5.33 | -1.11 | 1 | stop_loss |
| 3 | EOAN.DE | trend_following | short | 2026-05-05 | 2026-05-06 | 2026-05-26 | 435 | 18.36 | 18.58 | 19.04 | 17.24 | 7988.77 | 293.63 | -91.35 | 11.98 | 7.99 | 20.20 | 40.17 | -131.52 | -1.65 | -0.45 | 20 | time_stop |
| 4 | SAP.DE | trend_following | long | 2026-05-05 | 2026-05-06 | 2026-05-12 | 53 | 149.80 | 141.69 | 141.69 | 163.32 | 7939.40 | 429.83 | -429.83 | 11.91 | 7.94 | 18.77 | 38.62 | -468.45 | -5.90 | -1.09 | 6 | stop_loss |
| 5 | BAS.DE | trend_following | short | 2026-05-06 | 2026-05-11 | 2026-05-27 | 152 | 52.52 | 51.09 | 54.56 | 49.12 | 7983.04 | 310.08 | 217.36 | 11.97 | 7.98 | 19.42 | 39.37 | 177.99 | 2.23 | 0.57 | 16 | time_stop |
| 6 | SAP.DE | trend_following | long | 2026-05-06 | 2026-05-07 | 2026-05-12 | 47 | 149.32 | 140.91 | 140.91 | 163.34 | 7018.04 | 395.27 | -395.27 | 10.53 | 7.02 | 16.55 | 34.10 | -429.37 | -6.12 | -1.09 | 5 | stop_loss |
| 7 | RWE.DE | trend_following | short | 2026-05-07 | 2026-05-08 | 2026-05-28 | 119 | 58.46 | 54.41 | 60.89 | 54.41 | 6956.74 | 289.17 | 481.95 | 10.44 | 6.96 | 16.18 | 33.58 | 448.37 | 6.45 | 1.55 | 20 | target_reached |
| 8 | VOW3.DE | trend_following | long | 2026-05-07 | 2026-05-08 | 2026-05-28 | 90 | 88.08 | 92.56 | 84.38 | 94.24 | 7927.20 | 333.00 | 403.20 | 11.89 | 7.93 | 20.83 | 40.65 | 362.55 | 4.57 | 1.09 | 20 | time_stop |
| 9 | BAS.DE | trend_following | short | 2026-05-08 | 2026-05-20 | 2026-05-29 | 135 | 51.65 | 50.82 | 53.71 | 48.22 | 6972.75 | 278.10 | 112.05 | 10.46 | 6.97 | 17.15 | 34.58 | 77.47 | 1.11 | 0.28 | 9 | time_stop |
| 10 | BAYN.DE | trend_following | short | 2026-05-08 | 2026-05-11 | 2026-05-12 | 5 | 36.98 | 38.79 | 38.79 | 33.96 | 184.90 | 9.05 | -9.05 | 0.28 | 0.18 | 0.48 | 0.94 | -9.99 | -5.40 | -1.10 | 1 | stop_loss |
| 11 | ADS.DE | trend_following | long | 2026-05-14 | 2026-05-18 | 2026-05-25 | 1 | 146.80 | 158.91 | 139.53 | 158.91 | 146.80 | 7.27 | 12.11 | 0.22 | 0.15 | 0.40 | 0.77 | 11.34 | 7.72 | 1.56 | 7 | target_reached |
| 12 | DBK.DE | trend_following | long | 2026-05-14 | 2026-05-20 | 2026-05-25 | 291 | 27.41 | 29.27 | 26.29 | 29.27 | 7976.31 | 325.92 | 541.26 | 11.96 | 7.98 | 21.30 | 41.24 | 500.02 | 6.27 | 1.53 | 5 | target_reached |
| 13 | VOW3.DE | trend_following | long | 2026-05-14 | 2026-05-15 | 2026-06-04 | 79 | 88.84 | 88.60 | 85.43 | 94.52 | 7018.36 | 269.39 | -18.96 | 10.53 | 7.02 | 17.50 | 35.05 | -54.01 | -0.77 | -0.20 | 20 | time_stop |
| 14 | EOAN.DE | trend_following | long | 2026-05-21 | 2026-05-22 | 2026-06-02 | 1 | 18.51 | 17.84 | 17.84 | 19.63 | 18.51 | 0.67 | -0.67 | 0.03 | 0.02 | 0.05 | 0.10 | -0.77 | -4.16 | -1.15 | 11 | stop_loss |
| 15 | DTE.DE | trend_following | long | 2026-05-26 | 2026-05-28 | 2026-06-03 | 275 | 29.05 | 28.05 | 28.05 | 30.72 | 7988.75 | 275.00 | -275.00 | 11.98 | 7.99 | 19.28 | 39.25 | -314.25 | -3.93 | -1.14 | 6 | stop_loss |
| 16 | FRE.DE | breakout | short | 2026-05-27 | 2026-05-28 | 2026-06-05 | 216 | 36.93 | 37.26 | 37.92 | 33.95 | 7976.88 | 213.84 | -71.28 | 11.97 | 7.98 | 20.12 | 40.07 | -111.35 | -1.40 | -0.52 | 8 | time_stop |
| 17 | HEN3.DE | trend_following | long | 2026-05-27 | 2026-05-28 | 2026-06-03 | 105 | 67.38 | 65.50 | 65.55 | 70.42 | 7074.90 | 192.15 | -197.40 | 10.61 | 7.07 | 17.20 | 34.88 | -232.28 | -3.28 | -1.21 | 6 | stop_loss |
| 18 | FRE.DE | mean_reversion | long | 2026-05-28 | 2026-05-29 | 2026-06-01 | 191 | 36.71 | 35.72 | 35.72 | 38.20 | 7011.61 | 189.09 | -189.09 | 10.52 | 7.01 | 17.05 | 34.58 | -223.67 | -3.19 | -1.18 | 3 | stop_loss |
| 19 | ADS.DE | mean_reversion | short | 2026-05-29 | 2026-06-01 | 2026-06-03 | 48 | 166.60 | 161.60 | 171.66 | 159.00 | 7996.80 | 242.88 | 240.00 | 12.00 | 8.00 | 19.40 | 39.40 | 200.60 | 2.51 | 0.83 | 2 | time_stop |
| 20 | BAYN.DE | trend_following | short | 2026-05-29 | 2026-06-15 | 2026-06-17 | 216 | 36.53 | 38.30 | 38.30 | 33.57 | 7890.48 | 382.32 | -382.32 | 11.84 | 7.89 | 20.68 | 40.41 | -422.73 | -5.36 | -1.11 | 2 | stop_loss |
| 21 | BMW.DE | trend_following | short | 2026-06-01 | 2026-06-02 | 2026-06-09 | 95 | 73.72 | 68.83 | 76.65 | 68.83 | 7003.40 | 278.35 | 464.55 | 10.51 | 7.00 | 16.35 | 33.86 | 430.69 | 6.15 | 1.55 | 7 | target_reached |
| 22 | EOAN.DE | trend_following | short | 2026-06-02 | 2026-06-22 | 2026-06-23 | 394 | 17.80 | 17.82 | 18.40 | 16.79 | 7011.23 | 238.37 | -9.85 | 10.52 | 7.01 | 17.55 | 35.08 | -44.93 | -0.64 | -0.19 | 1 | time_stop |
| 23 | DTE.DE | trend_following | short | 2026-06-04 | 2026-06-05 | 2026-06-22 | 287 | 27.83 | 26.17 | 28.83 | 26.17 | 7987.21 | 287.00 | 476.42 | 11.98 | 7.99 | 18.78 | 38.75 | 437.67 | 5.48 | 1.52 | 17 | target_reached |
| 24 | SAP.DE | trend_following | long | 2026-06-04 | 2026-06-05 | 2026-06-09 | 48 | 164.50 | 154.06 | 154.06 | 181.89 | 7896.00 | 501.12 | -501.12 | 11.84 | 7.90 | 18.48 | 38.22 | -539.34 | -6.83 | -1.08 | 4 | stop_loss |
| 25 | VOW3.DE | trend_following | short | 2026-06-04 | 2026-06-05 | 2026-06-19 | 11 | 88.60 | 83.19 | 91.84 | 83.19 | 974.60 | 35.64 | 59.51 | 1.46 | 0.97 | 2.29 | 4.72 | 54.79 | 5.62 | 1.54 | 14 | target_reached |
| 26 | EOAN.DE | trend_following | long | 2026-06-05 | 2026-06-08 | 2026-06-23 | 436 | 18.27 | 17.70 | 17.70 | 19.24 | 7967.90 | 250.70 | -250.70 | 11.95 | 7.97 | 19.30 | 39.22 | -289.92 | -3.64 | -1.16 | 15 | stop_loss |
| 27 | BAS.DE | mean_reversion | long | 2026-06-08 | 2026-06-11 | 2026-06-11 | 163 | 48.85 | 48.88 | 47.63 | 50.69 | 7962.55 | 198.86 | 4.08 | 11.94 | 7.96 | 19.92 | 39.82 | -35.74 | -0.45 | -0.18 | 0 | time_stop |
| 28 | BMW.DE | trend_following | short | 2026-06-08 | 2026-06-09 | 2026-06-17 | 75 | 69.74 | 65.02 | 72.57 | 65.02 | 5230.50 | 212.25 | 354.00 | 7.85 | 5.23 | 12.19 | 25.27 | 328.73 | 6.29 | 1.55 | 8 | target_reached |
| 29 | BMW.DE | mean_reversion | long | 2026-06-10 | 2026-06-11 | 2026-06-11 | 118 | 67.62 | 65.76 | 65.76 | 70.42 | 7979.16 | 219.48 | -219.48 | 11.97 | 7.98 | 19.40 | 39.35 | -258.83 | -3.24 | -1.18 | 0 | stop_loss |
| 30 | SAP.DE | trend_following | short | 2026-06-12 | 2026-06-17 | 2026-07-03 | 57 | 140.26 | 139.64 | 150.56 | 123.09 | 7994.82 | 587.10 | 35.34 | 11.99 | 7.99 | 19.90 | 39.88 | -4.54 | -0.06 | -0.01 | 16 | time_stop |
| 31 | FRE.DE | trend_following | long | 2026-06-16 | 2026-06-17 | 2026-07-01 | 185 | 38.77 | 41.19 | 37.32 | 41.19 | 7172.45 | 268.25 | 447.70 | 10.76 | 7.17 | 19.05 | 36.98 | 410.72 | 5.73 | 1.53 | 14 | target_reached |
| 32 | FRE.DE | trend_following | long | 2026-06-17 | 2026-06-18 | 2026-07-02 | 1 | 39.04 | 41.40 | 37.63 | 41.40 | 39.04 | 1.41 | 2.36 | 0.06 | 0.04 | 0.10 | 0.20 | 2.16 | 5.53 | 1.53 | 14 | target_reached |
| 33 | FRE.DE | trend_following | long | 2026-06-18 | 2026-06-19 | 2026-07-02 | 158 | 39.31 | 41.60 | 37.94 | 41.60 | 6210.98 | 216.46 | 361.82 | 9.32 | 6.21 | 16.43 | 31.96 | 329.86 | 5.31 | 1.52 | 13 | target_reached |
| 34 | SAP.DE | trend_following | short | 2026-06-18 | 2026-06-19 | 2026-07-07 | 51 | 134.86 | 144.53 | 144.53 | 118.74 | 6877.86 | 493.17 | -493.17 | 10.32 | 6.88 | 18.43 | 35.63 | -528.80 | -7.69 | -1.07 | 18 | stop_loss |
| 35 | FRE.DE | trend_following | long | 2026-06-23 | 2026-06-24 | 2026-07-02 | 39 | 39.90 | 42.15 | 38.55 | 42.15 | 1556.10 | 52.65 | 87.75 | 2.33 | 1.56 | 4.11 | 8.00 | 79.75 | 5.13 | 1.51 | 8 | target_reached |
| 36 | HEN3.DE | mean_reversion | short | 2026-06-24 | 2026-06-25 | 2026-06-29 | 109 | 72.76 | 74.09 | 74.09 | 70.76 | 7930.84 | 144.97 | -144.97 | 11.90 | 7.93 | 20.19 | 40.02 | -184.99 | -2.33 | -1.28 | 4 | stop_loss |
| 37 | VOW3.DE | trend_following | short | 2026-06-24 | 2026-06-25 | 2026-07-01 | 105 | 76.02 | 69.81 | 79.75 | 69.81 | 7982.10 | 391.65 | 652.05 | 11.97 | 7.98 | 18.33 | 38.28 | 613.77 | 7.69 | 1.57 | 6 | target_reached |
| 38 | HEN3.DE | mean_reversion | short | 2026-06-26 | 2026-06-29 | 2026-07-01 | 88 | 73.80 | 74.26 | 75.04 | 71.94 | 6494.40 | 109.12 | -40.48 | 9.74 | 6.49 | 16.33 | 32.56 | -73.04 | -1.13 | -0.67 | 2 | time_stop |
| 39 | ALV.DE | breakout | long | 2026-06-30 | 2026-07-01 | 2026-07-09 | 17 | 414.10 | 422.70 | 408.59 | 430.64 | 7039.70 | 93.67 | 146.20 | 10.56 | 7.04 | 17.97 | 35.57 | 110.63 | 1.57 | 1.18 | 8 | time_stop |
| 40 | BAYN.DE | trend_following | long | 2026-07-02 | 2026-07-03 | 2026-07-08 | 149 | 53.36 | 50.36 | 50.40 | 58.30 | 7950.64 | 441.04 | -447.00 | 11.93 | 7.95 | 18.76 | 38.64 | -485.64 | -6.11 | -1.10 | 5 | stop_loss |
| 41 | FRE.DE | mean_reversion | short | 2026-07-02 | 2026-07-03 | 2026-07-06 | 170 | 42.12 | 43.06 | 43.06 | 40.70 | 7160.40 | 159.80 | -159.80 | 10.74 | 7.16 | 18.30 | 36.20 | -196.00 | -2.74 | -1.23 | 3 | stop_loss |
| 42 | FRE.DE | mean_reversion | short | 2026-07-03 | 2026-07-08 | 2026-07-08 | 184 | 42.43 | 42.40 | 43.34 | 41.06 | 7807.12 | 167.44 | 5.52 | 11.71 | 7.81 | 19.50 | 39.02 | -33.50 | -0.43 | -0.20 | 0 | time_stop |
| 43 | BAYN.DE | trend_following | long | 2026-07-06 | 2026-07-07 | 2026-07-15 | 137 | 51.18 | 48.22 | 48.22 | 56.11 | 7011.66 | 405.52 | -405.52 | 10.52 | 7.01 | 16.52 | 34.05 | -439.57 | -6.27 | -1.08 | 8 | stop_loss |
| 44 | DBK.DE | trend_following | long | 2026-07-06 | 2026-07-07 | 2026-07-08 | 35 | 32.29 | 31.11 | 31.11 | 34.27 | 1130.32 | 41.47 | -41.47 | 1.70 | 1.13 | 2.72 | 5.55 | -47.02 | -4.16 | -1.13 | 1 | stop_loss |
| 45 | EOAN.DE | trend_following | long | 2026-07-06 | 2026-07-07 | 2026-07-27 | 398 | 19.00 | 19.11 | 18.36 | 20.05 | 7560.01 | 252.73 | 43.78 | 11.34 | 7.56 | 19.01 | 37.91 | 5.87 | 0.08 | 0.02 | 20 | time_stop |
| 46 | SIE.DE | trend_following | short | 2026-07-08 | 2026-07-16 | 2026-07-27 | 25 | 265.55 | 277.34 | 277.34 | 245.90 | 6638.75 | 294.75 | -294.75 | 9.96 | 6.64 | 17.33 | 33.93 | -328.68 | -4.95 | -1.11 | 11 | stop_loss |
| 47 | BAYN.DE | trend_following | long | 2026-07-09 | 2026-07-10 | 2026-07-15 | 157 | 50.70 | 47.91 | 47.91 | 55.36 | 7959.90 | 438.03 | -438.03 | 11.94 | 7.96 | 18.80 | 38.70 | -476.73 | -5.99 | -1.09 | 5 | stop_loss |
| 48 | FRE.DE | trend_following | long | 2026-07-10 | 2026-07-20 | 2026-07-29 | 184 | 42.57 | 44.81 | 41.22 | 44.81 | 7832.88 | 248.40 | 412.16 | 11.75 | 7.83 | 20.62 | 40.20 | 371.96 | 4.75 | 1.50 | 9 | target_reached |
| 49 | SIE.DE | trend_following | short | 2026-07-13 | 2026-07-14 | 2026-07-30 | 29 | 272.10 | 283.16 | 283.16 | 253.66 | 7890.90 | 320.74 | -320.74 | 11.84 | 7.89 | 20.53 | 40.26 | -361.00 | -4.58 | -1.13 | 16 | stop_loss |
| 50 | SIE.DE | trend_following | short | 2026-07-15 | 2026-07-16 | 2026-07-30 | 1 | 270.10 | 280.75 | 280.75 | 252.36 | 270.10 | 10.65 | -10.65 | 0.41 | 0.27 | 0.70 | 1.38 | -12.03 | -4.45 | -1.13 | 14 | stop_loss |
| 51 | DTE.DE | trend_following | long | 2026-07-16 | 2026-07-21 | 2026-07-24 | 299 | 26.68 | 25.71 | 25.71 | 28.30 | 7977.32 | 290.03 | -290.03 | 11.97 | 7.98 | 19.22 | 39.17 | -329.20 | -4.13 | -1.14 | 3 | stop_loss |
| 52 | MBG.DE | trend_following | long | 2026-07-16 | 2026-07-17 | 2026-07-24 | 174 | 45.86 | 44.08 | 44.13 | 48.74 | 7979.64 | 301.02 | -308.85 | 11.97 | 7.98 | 19.18 | 39.13 | -347.98 | -4.36 | -1.16 | 7 | stop_loss |
| 53 | DBK.DE | trend_following | short | 2026-07-17 | 2026-07-20 | 2026-07-29 | 207 | 30.83 | 32.21 | 32.11 | 28.71 | 6382.84 | 263.93 | -284.63 | 9.57 | 6.38 | 16.67 | 32.62 | -317.25 | -4.97 | -1.20 | 9 | stop_loss |
| 54 | DTE.DE | trend_following | long | 2026-07-20 | 2026-07-21 | 2026-07-24 | 1 | 27.09 | 25.88 | 26.12 | 28.70 | 27.09 | 0.97 | -1.21 | 0.04 | 0.03 | 0.07 | 0.14 | -1.35 | -4.98 | -1.39 | 3 | stop_loss |
| 55 | DTE.DE | trend_following | long | 2026-07-27 | 2026-07-30 | 2026-08-06 | 295 | 27.07 | 28.84 | 26.01 | 28.84 | 7985.65 | 312.70 | 522.15 | 11.98 | 7.99 | 21.27 | 41.24 | 480.91 | 6.02 | 1.54 | 7 | target_reached |
| 56 | FRE.DE | trend_following | long | 2026-07-27 | 2026-07-28 | 2026-08-05 | 1 | 44.25 | 46.60 | 42.84 | 46.60 | 44.25 | 1.41 | 2.35 | 0.07 | 0.04 | 0.12 | 0.23 | 2.12 | 4.79 | 1.50 | 8 | target_reached |
| 57 | EOAN.DE | trend_following | short | 2026-07-28 | 2026-07-29 | 2026-08-14 | 328 | 18.99 | 18.03 | 19.56 | 18.03 | 6228.72 | 186.96 | 314.88 | 9.34 | 6.23 | 14.78 | 30.35 | 284.53 | 4.57 | 1.52 | 16 | target_reached |
| 58 | SAP.DE | trend_following | long | 2026-07-28 | 2026-07-29 | 2026-08-07 | 50 | 159.24 | 174.52 | 150.07 | 174.52 | 7962.00 | 458.50 | 764.00 | 11.94 | 7.96 | 21.82 | 41.72 | 722.28 | 9.07 | 1.57 | 9 | target_reached |
| 59 | EOAN.DE | trend_following | short | 2026-07-31 | 2026-08-12 | 2026-08-14 | 62 | 18.71 | 17.73 | 19.30 | 17.73 | 1160.33 | 36.27 | 61.07 | 1.74 | 1.16 | 2.75 | 5.65 | 55.42 | 4.78 | 1.53 | 2 | target_reached |
| 60 | HEN3.DE | mean_reversion | short | 2026-08-07 | 2026-08-10 | 2026-08-12 | 100 | 79.80 | 77.62 | 81.25 | 77.62 | 7980.00 | 145.00 | 218.00 | 11.97 | 7.98 | 19.40 | 39.35 | 178.65 | 2.24 | 1.23 | 2 | target_reached |

Nebenbefund zu Phase 0: `decision_date` (Signal-Datum) liegt fuer alle 60 Trades im
Fenster 2026-05-04 bis 2026-08-07 ("Observed trade activity"), aber einzelne
`exit_date`-Werte reichen bis 2026-08-14 (Trade #57, #59) – das Replay selbst deckte
den vollen Scope 2026-05-01 bis 2026-08-15 ab, nur die letzte Signalauslösung lag
bereits am 08-07.

---

## PHASE 2 – Accounting Assertion

- Max. Abweichung `gross_pnl − total_costs − net_pnl` ueber alle 60 Zeilen:
  **~2.66e-15** (Gleitkomma-Rauschen, praktisch 0). Das ist erwartbar und **kein
  unabhaengiger Beweis** – da `total_costs` im Schema nicht als eigene Spalte
  existiert, sondern hier als Residuum `gross_pnl − net_pnl` definiert wurde, ist die
  Zeilenidentitaet eine Tautologie.
- Die einzige echte Pruefung war die **Summenkontrolle** gegen die vorgegebenen
  Zielwerte:

| | Ziel (Nutzer) | Berechnet aus 60 Zeilen | Differenz |
|---|---|---|---|
| Gross | +652.00 EUR | +652.00 EUR | 0.00 |
| Costs | 1858.20 EUR | 1858.20 EUR | 0.00 |
| Net | -1206.20 EUR | -1206.20 EUR | 0.00 |

Keine Abweichung – kein STOPP noetig, Phase 3+ kann auf dieser Datenbasis aufsetzen.

---

## PHASE 3 – Cost Break-Even (deskriptiv)

Kategorien ueber alle 60 Trades (Grenzen rein deskriptiv, nicht optimiert):

| Kategorie | Definition | Anzahl |
|---|---|---|
| A | Gross P&L ≤ 0 | 31 |
| B | Gross P&L > 0, aber ≤ Costs | 3 |
| C | Gross P&L > Costs, aber kleiner Net-Edge (Net ≤ 300 EUR, willkuerliche Beobachtungsgrenze) | 14 |
| D | klar positiver Net Edge (Net > 300 EUR) | 12 |

Durchschnittlicher `cost_break_even_return_pct` (Costs / Position Value): **0.50%**
– d.h. im Schnitt musste sich der Kurs um rund einen halben Prozentpunkt bewegen,
nur um die Handelskosten zu decken, bevor irgendein Netto-Gewinn beginnt.

`gross_edge_over_costs` (Gross P&L / Costs) im Mittel: **10.87 / 30.97 ≈ 0.35** – im
Schnitt deckte der Brutto-Edge pro Trade nur gut ein Drittel der Kosten.

---

## PHASE 4 – Cost Flip Analysis

| Kombination | Anzahl |
|---|---|
| Gross positiv + Net positiv | **26** |
| Gross positiv + Net negativ (**"cost-flipped"**) | **3** |
| Gross negativ + Net negativ | **31** |
| Gross negativ + Net positiv (sollte 0 sein) | **0** ✓ Konsistenzcheck bestanden |

Nur **3 von 60 Trades (5%)** wurden ausschliesslich durch Kosten von positiv zu
negativ gedreht. Das ist der zentrale quantitative Befund von Phase 4: die grosse
Masse der negativen Netto-Trades (31 von 34) war **bereits brutto negativ** – Kosten
sind nicht der Haupttreiber der Netto-Verluste, sie verschaerfen ein bereits
vorhandenes Brutto-Problem nur graduell.

---

## PHASE 5 – Gross vs. Net Distribution

| | Gross P&L | Net P&L |
|---|---|---|
| Mean | 10.87 | -20.10 |
| Median | -0.94 | -11.01 |
| P25 | -256.77 | -296.00 |
| P75 | 223.50 | 184.14 |
| Top-Dezil (P90) | 465.74 | 431.39 |
| Bottom-Dezil (P10) | -396.29 | -430.39 |
| Min | -501.12 | -539.34 |
| Max | 764.00 | 722.28 |

Median liegt in beiden Faellen unter dem Mittelwert und nahe/unter 0 – die
Verteilung ist rechtsschief durch wenige grosse Gewinner getragen, keine
Normalverteilung unterstellt.

---

## PHASE 6 – Cost Burden

- Avg Costs/Trade: **30.97 EUR**, Median: **37.44 EUR**
- Costs als % of Position Value: **0.50%** (Mittel)
- Costs als % of |Gross Move| (|gross_pnl|): **53.62%** (Mittel – stark verzerrt durch
  Trades mit sehr kleinem Gross-Betrag, siehe Phase 30 fuer robustere Kennzahl)
- Costs / Gross Winning P&L (Summe Kosten / Summe positiver Gross-P&L): **23.95%**
- Costs nach Ticker/Strategie/Holding-Period/Direction: siehe Tabellen in Phase 11-14.

---

## PHASE 7 – Holding Period

| Bucket | n | Gross | Costs | Net | WinRate | GrossPF | NetPF | AvgR |
|---|---|---|---|---|---|---|---|---|
| same_day | 3 | -209.88 | 118.19 | -328.07 | 0% | 0.04 | 0.00 | -0.52 |
| 1_day | 5 | -129.32 | 123.20 | -252.52 | 20% | 0.71 | 0.52 | -0.44 |
| 2-3_days | 9 | -543.86 | 267.46 | -811.32 | 33.3% | 0.49 | 0.35 | -0.35 |
| 4-5_days | 6 | -1385.13 | 230.92 | -1616.05 | 16.7% | 0.28 | 0.24 | -0.68 |
| 6-10_days | 18 | 1556.86 | 558.34 | 998.52 | 61.1% | 1.79 | 1.45 | 0.44 |
| >10_days | 19 | 1363.33 | 560.09 | 803.24 | 52.6% | 1.92 | 1.47 | 0.26 |

**Ja, kurze Trades sind strukturell benachteiligt** – aber vermutlich nicht primaer
durch Kosten (die pro Trade recht konstant ~25-40 EUR sind), sondern weil kurze
Haltedauer in diesem Sample vor allem **schnelle Stop-Outs** bedeutet
(same_day/1_day/2-3_days haben WinRate 0-33% und negative AvgR nahe -0.4 bis -0.5) –
siehe Phase 8/9. Die Kausalitaet laeuft eher "schlechter Trade → schneller Exit"
als "kurze Exit-Frist → hohe relative Kostenlast".

---

## PHASE 8 – Exit Reason

| Exit Reason | n | Gross | Costs | Net | WinRate | GrossPF | NetPF | AvgR | MedianR | AvgHoldDays |
|---|---|---|---|---|---|---|---|---|---|---|
| target_reached | 20 | 6552.14 | 533.05 | 6019.09 | 100%* | – | – | 1.51 | 1.53 | 9.35 |
| stop_loss | 26 | -6875.75 | 796.02 | -7671.77 | 0%* | – | – | -1.15 | -1.13 | 6.42 |
| time_stop | 14 | 975.61 | 529.13 | 446.48 | 42.9% | 5.21 | 1.91 | 0.11 | -0.09 | 10.14 |

\* WinRate 100%/0% bei target_reached/stop_loss ist per Definition (Zielerreichung =
Gewinn, Stop-Ausloesung = Verlust), kein unabhaengiger Befund.

**Bester Exit-Typ:** `target_reached` (per Definition immer profitabel, aber auch der
groesste Beitrag zum Brutto-Ergebnis: +6552 EUR brutto).
**Schlechtester Exit-Typ:** `stop_loss` (—7672 EUR netto, dominiert die Verlustseite).
**Time-Stop ist der einzige "gemischte" Exit-Typ und bereits netto positiv**
(NetPF 1.91) – das ist ein bemerkenswerter Nebenbefund: das System realisiert bei
Zeit-Stops im Mittel noch Gewinn, auch nach Kosten.

---

## PHASE 9 – Stop-Loss Forensik

26 Stop-Loss-Trades, vollstaendige Liste siehe Rohdaten (Trades #2,4,6,10,14,15,17,
18,20,24,26,29,34,36,40,41,43,44,46,47,49,50,51,52,53,54 in Phase-1-Tabelle).

- **~1R getroffen** (R zwischen -0.85 und -1.15): **17 von 26 (65.4%)**
- **Schlechter als 1R** (R < -1.15, meist durch Slippage/Gap am Exit): **9 von 26
  (34.6%)** – z.B. Trade #17 (HEN3.DE, R=-1.21), #52 (MBG.DE, R=-1.16), #54 (DTE.DE,
  R=-1.39, das schlechteste Ergebnis im ganzen Sample)
- **Besser als 1R:** **0 von 26 (0%)** – kein einziger Stop-Loss-Trade schloss besser
  als der geplante Risikobetrag. Das ist mechanisch plausibel (Stops loesen per
  Definition am/ueber dem geplanten Risiko aus) und deutet auf ein **sauber
  funktionierendes, nicht positiv ueberraschendes Stop-System** hin – keine
  Bug-Signatur, sondern erwartetes Verhalten.
- **Bereits brutto stark negativ:** alle 26 (100%) – per Konstruktion, da
  `stop_loss` per Definition Gross < 0 bedeutet.

---

## PHASE 10 – Target-Forensik

20 Target-Reached-Trades. Realisiertes R lag durchgehend zwischen **1.23 und 1.58**
(Median 1.53) – **nie** wurde der volle nominale RRR (siehe Phase 18: meist
1.5-2.0-Bucket) tatsaechlich weit ueberschritten, aber auch fast nie deutlich
unterschritten. Netto-Reward/Risk nach Kosten liegt fast identisch zum
Brutto-R-Multiple (Differenz typischerweise ≤0.02R), da die Kosten bei
Target-Trades klein relativ zur Positionsgroesse sind (Median-Kosten hier ~34 EUR
auf typischerweise >300 EUR Gross-Gewinn). **Der geplante Reward bleibt nach Kosten
zu >95% erhalten**, wenn ein Trade das Ziel erreicht.

---

## PHASE 11 – Strategie-Analyse

| Strategie | n | Gross | Costs | Net | WinRate | GrossPF | NetPF | MeanR | MedianR | AvgHoldDays | AvgCost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mean_reversion | 10 | 29.83 | 381.00 | -351.17 | 30% | 1.04 | 0.65 | -0.25 | -0.43 | 1.70 | 38.10 |
| trend_following | 48 | 547.25 | 1401.56 | -854.31 | 45.8% | 1.09 | 0.88 | 0.08 | -0.19 | 9.65 | 29.20 |
| breakout | 2 | 74.92 | 75.64 | -0.72 | 50% | 2.05 | 0.99 | 0.33 | 0.33 | 8.00 | 37.82 |

`trend_following` dominiert die Stichprobe (48/60 = 80% aller Trades) und ist
brutto marginal positiv (PF 1.09), netto knapp negativ (PF 0.88). `mean_reversion`
ist mit 10 Trades die klar schwaechste Gruppe (WinRate nur 30%, MeanR -0.25).
`breakout` ist mit n=2 statistisch nicht interpretierbar. **Keine Strategie wurde
deaktiviert** (wie gefordert) – dies ist reine Beobachtung.

---

## PHASE 12 – Ticker-Analyse

| Ticker | n | Gross | Costs | Net | WinRate | AvgCost | AvgHoldDays |
|---|---|---|---|---|---|---|---|
| BMW.DE | 4 | 915.12 | 139.18 | 775.94 | 75% | 34.79 | 4.00 |
| DBK.DE | 4 | -169.84 | 120.34 | -290.18 | 25% | 30.09 | 4.00 |
| EOAN.DE | 7 | 67.16 | 188.48 | -121.32 | 42.9% | 26.93 | 12.14 |
| SAP.DE | 6 | **-1020.05** | 228.17 | -1248.22 | 16.7% | 38.03 | 9.67 |
| BAS.DE | 3 | 333.49 | 113.77 | 219.72 | 66.7% | 37.92 | 8.33 |
| RWE.DE | 1 | 481.95 | 33.58 | 448.37 | 100% | 33.58 | 20.00 |
| VOW3.DE | 4 | 1095.80 | 118.70 | 977.10 | 75% | 29.67 | 15.00 |
| BAYN.DE | 5 | **-1681.92** | 152.74 | -1834.66 | 0% | 30.55 | 4.20 |
| ADS.DE | 2 | 252.11 | 40.17 | 211.94 | 100% | 20.09 | 4.50 |
| DTE.DE | 5 | 432.33 | 158.55 | 273.78 | 40% | 31.71 | 7.20 |
| FRE.DE | 10 | 899.49 | 267.44 | 632.05 | 60% | 26.74 | 8.00 |
| HEN3.DE | 4 | -164.85 | 146.81 | -311.66 | 25% | 36.70 | 3.50 |
| ALV.DE | 1 | 146.20 | 35.57 | 110.63 | 100% | 35.57 | 8.00 |
| SIE.DE | 3 | -626.14 | 75.57 | -701.71 | 0% | 25.19 | 13.67 |
| MBG.DE | 1 | -308.85 | 39.13 | -347.98 | 0% | 39.13 | 7.00 |

**Wichtiger Konzentrationsbefund** (ergaenzend zu Phase 24): **BAYN.DE (-1681.92)
und SAP.DE (-1020.05) allein summieren -2701.97 EUR Brutto** – wuerde man nur
diese zwei Ticker aus der Stichprobe entfernen, waere das Brutto-Ergebnis der
verbleibenden 13 Ticker **+3353.97 EUR statt +652.00 EUR**. Bei n=5 bzw. n=6 pro
Ticker ist das aber **keine belastbare Ticker-Filter-Evidenz** – es koennte
genauso gut Stichprobenrauschen sein. Absolute Aktienpreise korrelieren nicht
sichtbar mit Kostenlast (AvgCost liegt fuer SIE.DE bei Kurs ~270 EUR genauso bei
25-40 EUR wie fuer EOAN.DE bei Kurs ~18 EUR – Kosten skalieren mit Positionswert,
nicht mit Aktienkurs, wie erwartet).

---

## PHASE 13 – Direction-Analyse

| Direction | n | Gross | Costs | Net | WinRate | GrossPF | NetPF | MeanR |
|---|---|---|---|---|---|---|---|---|
| long | 32 | -342.66 | 965.94 | -1308.60 | 43.75% | 0.92 | 0.74 | 0.01 |
| short | 28 | 994.66 | 892.26 | 102.40 | 42.86% | 1.37 | 1.03 | 0.06 |

**Short-Trades sind in diesem Sample deutlich staerker** (netto sogar leicht positiv,
NetPF 1.03) als Long-Trades (klar negativ, NetPF 0.74) – bei fast identischer
WinRate. Das koennte Marktregime-getrieben sein (der Beobachtungszeitraum
Mai-August 2026 enthielt offenbar mehr profitable Short- als Long-Gelegenheiten)
und ist ohne weitere Regime-Aufschluesselung nicht kausal zu interpretieren.

---

## PHASE 14 – Regime-Analyse

| Regime | n | Gross | Costs | Net | WinRate | GrossPF | NetPF | MeanR |
|---|---|---|---|---|---|---|---|---|
| bull_trend_low_vol | 57 | 1232.59 | 1791.51 | -558.92 | 45.6% | 1.19 | 0.93 | 0.10 |
| bear_trend | 3 | -580.59 | 66.69 | -647.28 | 0% | 0.00 | 0.00 | -1.24 |

Alle Trades liefen unter **CURRENT_POLICY_REPLAY**. **95% aller Trades (57/60)
fielen in `bull_trend_low_vol`** – das Sample deckt praktisch nur ein einziges
Marktregime ab. Die 3 `bear_trend`-Trades waren alle Verlierer (WinRate 0%), aber
n=3 ist zu klein fuer jede Aussage ueber Regime-Abhaengigkeit. `market_regime`
(die undifferenzierte Rohspalte) war fuer alle Zeilen `null` – nur
`combined_regime` war befuellt.

---

## PHASE 15 – Fundamentals

**Degenerierter Befund:** `fund_direction` war fuer **alle 60 Trades** identisch
`"unbekannt"` (unknown), `snapshot_count` durchgehend 0 (soweit stichprobenartig
geprueft). Es gab in diesem Run **keine differenzierbaren Fundamentaldaten-Buckets**
(supportive/neutral/contrary) – die komplette Stichprobe faellt in die
"unknown"-Kategorie. **Keine Kausalaussage moeglich, weil keine Varianz vorhanden
ist.** Das ist selbst ein bemerkenswerter Befund: die Fundamentals-Komponente hat in
diesem Replay-Fenster faktisch nie einen echten Snapshot beigetragen.

---

## PHASE 16 – Opportunity Score (Quintile)

| Bucket | n | Gross | Costs | Net | WinRate | GrossPF | NetPF | MeanR |
|---|---|---|---|---|---|---|---|---|
| Q1 (lowest) | 13 | -1005.69 | 263.20 | -1268.89 | 23.1% | 0.33 | 0.27 | -0.39 |
| Q2 | 11 | -587.22 | 370.24 | -957.46 | 54.5% | 0.67 | 0.52 | -0.02 |
| Q3 | 14 | 2289.15 | 421.91 | 1867.24 | 64.3% | 3.31 | 2.63 | 0.60 |
| Q4 | 17 | -758.70 | 609.41 | -1368.11 | 35.3% | 0.71 | 0.54 | -0.13 |
| Q5 (highest) | 5 | 714.46 | 193.44 | 521.02 | 40% | 4.09 | 2.67 | 0.20 |

**Kein monotoner Zusammenhang.** Q3 sticht stark positiv heraus, Q1 und Q4 sind
die schwaechsten Buckets – die Reihenfolge ist nicht monoton steigend mit dem
Score. **Trade Quality steigt in diesem Sample nicht sauber mit
`opportunity_score`.**

---

## PHASE 17 – Evidence Confidence

Die Werteverteilung von `evidence_confidence` war stark verdichtet: eine
Quintil-Bucketierung ergab real nur **zwei** natuerliche Cluster, nicht fuenf
(die Perzentilgrenzen fielen fuer Q2-Q4 zusammen):

| Bucket | n | Gross | Costs | Net | WinRate | MeanR |
|---|---|---|---|---|---|---|
| Q1 (lowest, ~0.13-0.22) | 56 | -705.95 | 1741.13 | -2447.08 | 39.3% | -0.07 |
| Q5 (highest, ~0.30+) | 4 | 1357.95 | 117.07 | 1240.88 | 100% | 1.46 |

Die kleine Hochkonfidenz-Gruppe (n=4) war **durchgehend profitabel** (100%
WinRate, MeanR 1.46) – ein auffaelliger, aber bei n=4 statistisch sehr schwacher
Hinweis, dass hoehere Confidence tatsaechlich mit besseren Outcomes einherging.
Mit nur 4 Beobachtungen ist das **nicht belastbar**, nur bemerkenswert genug,
um im naechsten Schritt weiter beobachtet zu werden.

---

## PHASE 18 – Reward/Risk Ratio (nominal, aus Decision Log)

| Bucket | n | Gross | Costs | Net | WinRate | MeanR |
|---|---|---|---|---|---|---|
| 1.5-2.0 | 58 | 577.08 | 1782.56 | -1205.48 | 43.1% | 0.02 |
| >3.0 | 2 | 74.92 | 75.64 | -0.72 | 50% | 0.33 |

**Das nominale RRR ist in diesem Run praktisch keine unterscheidende Variable** –
58 von 60 Trades (96.7%) fallen in denselben schmalen 1.5-2.0-Bucket (mechanisch
durch die Strategie-/Sizing-Konfiguration vorgegeben, nicht pro Trade
differenziert). Nur die 2 `breakout`-Trades weichen ab. **Nominal hohe RRR-Werte
sind in diesem Sample nicht pruefbar, weil praktisch keine Varianz vorhanden ist.**

---

## PHASE 19 – Stop Distance (Quintile)

| Bucket | n | Gross | Net | WinRate | NetPF | MeanR |
|---|---|---|---|---|---|---|
| Q1 (engste Stops) | 12 | -332.65 | -784.77 | 25% | 0.42 | -0.33 |
| Q2 | 12 | 987.05 | 679.66 | 66.7% | 2.04 | 0.51 |
| Q3 | 12 | 974.17 | 653.74 | 50% | 1.72 | 0.25 |
| Q4 | 12 | 678.92 | 280.21 | 50% | 1.15 | 0.06 |
| Q5 (weiteste Stops) | 12 | -1655.49 | -2035.04 | 25% | 0.40 | -0.33 |

**U-foermiges Muster:** sowohl die engsten als auch die weitesten Stop-Distanzen
schneiden am schlechtesten ab (WinRate je 25%, NetPF <0.5), die mittleren Buckets
(Q2/Q3) sind klar am staerksten. Engste Stops werden vermutlich haeufiger durch
normales Rauschen ausgeloest (zu nah am Entry), weiteste Stops erzeugen im
Loss-Fall ueberproportional grosse Einzelverluste. **Keine Parameteraenderung
vorgenommen** – nur beschrieben.

---

## PHASE 20 – Position Size (Quintile)

Nach `position_value`:

| Bucket | n | Gross | Net | WinRate | NetPF |
|---|---|---|---|---|---|
| Q1 (kleinste, oft 1-Stück-Testpositionen) | 12 | 516.10 | 463.15 | 58.3% | 7.51 |
| Q2 | 12 | 17.76 | -385.02 | 41.7% | 0.80 |
| Q3 | 12 | -920.25 | -1369.05 | 33.3% | 0.40 |
| Q4 | 12 | -578.78 | -1056.00 | 25% | 0.60 |
| Q5 (groesste) | 12 | 1617.17 | 1140.72 | 58.3% | 1.93 |

Q1 (kleinste Positionen) zeigt den **hoechsten NetPF (7.51)** – das widerspricht der
Hypothese "kleine Trades sind durch fixe Kosten ökonomisch benachteiligt". Bei
naeherer Betrachtung sind die Q1-Positionen aber ueberwiegend **1-Stueck-Restgroessen**
(Trades #11, #14, #32, #35, #39, #54, #56 in Phase 1 – Position Value oft <50 EUR),
bei denen absolute Kosten winzig sind (AvgCost Q1 = 4.41 EUR vs. 33-40 EUR in den
anderen Buckets) – ein Sondereffekt der Sizing-Mechanik, kein generalisierbarer
"kleine Positionen sind gut"-Befund. Mittlere/grosse Positionen (Q3-Q5) folgen
keinem klaren Muster relativ zur Groesse.

---

## PHASE 21 – Break-Even Edge

- Einfache Kennzahl (Costs / 60): **30.97 EUR/Trade** durchschnittlich noetiger
  zusaetzlicher Gross-Edge, um Net = 0 zu erreichen.
- Unter Beruecksichtigung der tatsaechlichen Positionsgroessen:
  **Break-even Gross-Return% = Total Costs / Total Position Value = 1858.20 /
  372,296.32 ≈ 0.50%** – das Portfolio haette im Schnitt 0.5 Prozentpunkte mehr
  Brutto-Rendite pro eingesetztem Euro gebraucht, um kostenneutral zu sein.

---

## PHASE 22 – Turnover

- Entry Notional: **372,296.32 EUR**
- Exit Notional: **370,958.98 EUR**
- Turnover (Entry+Exit): **743,255.30 EUR**
- Turnover / Initial Portfolio (100,000 EUR): **7.43x**
- Costs / Turnover: **0.25%**
- Trades pro Business Day (76 Tage Scope): **0.79**
- Durchschnittlich gleichzeitig offene Positionen: **5.45** (Maximum: 9)

Die Kostenquote relativ zum Turnover (0.25%) ist niedrig im Branchenvergleich –
**Kosten sind nicht das strukturelle Kernproblem in absoluten/relativen
Groessenordnungen**, siehe Klassifikation in Phase 31.

---

## PHASE 23 – Trade Frequency

- 60 Trades verteilt auf **40 unterschiedliche Decision-Tage** von 76 moeglichen
  Handelstagen
- **17 Tage** hatten mehr als 1 Trade gleichzeitig ausgeloest, maximal **3 Trades an
  einem Tag**
- Keine auffaellige Haeufung in einer bestimmten Phase (siehe Monats-Aufschluesselung
  Phase 25) ausser der generell hoeheren Aktivitaet im Mai/Juni/Juli gegenueber dem
  fast leeren August (nur 1 Trade, weil das Signalfenster am 08-07 endete)

---

## PHASE 24 – Concentration

| | Wert |
|---|---|
| Top-1-Gewinner (Gross) | 764.00 (SAP.DE, Trade #58) |
| Top-3-Gewinner (Gross, Summe) | 1957.31 |
| Top-5-Gewinner (Gross, Summe) | 2961.41 |
| Ergebnis ohne Top-1-Gewinner | **-112.00** |
| Ergebnis ohne Top-3-Gewinner | **-1305.31** |
| Ergebnis ohne Top-5-Gewinner | **-2309.41** |
| Bottom-1-Verlierer (Gross) | -501.12 (SAP.DE, Trade #24) |
| Bottom-3-Verlierer (Gross, Summe) | -1441.29 |
| Bottom-5-Verlierer (Gross, Summe) | -2309.15 |

**Sehr hohe Konzentration:** das gesamte positive Brutto-Ergebnis haengt an einer
Handvoll Trades – ohne den einzelnen groessten Gewinner waere das Sample bereits
**brutto negativ** (-112 EUR). Ohne die Top-3-Gewinner waere es deutlich negativ
(-1305 EUR). Bei n=60 ist das ein starker Hinweis darauf, dass der beobachtete
positive Brutto-Edge **fragil und stark von wenigen Einzelereignissen abhaengig**
ist, nicht breit im Sample verteilt.

---

## PHASE 25 – Monatlich

| Monat | n | Gross | Costs | Net | WinRate | GrossPF |
|---|---|---|---|---|---|---|
| Mai (05) | 20 | -121.24 | 649.39 | -770.63 | 40% | 0.95 |
| Juni (06) | 19 | 1432.01 | 593.37 | 838.64 | 52.6% | 1.86 |
| Juli (07) | 20 | -876.77 | 576.09 | -1452.86 | 35% | 0.71 |
| August (08, nur bis 08-07) | 1 | 218.00 | 39.35 | 178.65 | 100% | – |

**Der positive Brutto-Edge ist nicht stabil ueber die Zeit** – Mai und Juli waren
beide brutto negativ (GrossPF 0.95 bzw. 0.71), nur Juni war klar positiv
(GrossPF 1.86) und traegt praktisch das gesamte positive Gesamtergebnis. August hat
mit n=1 keine Aussagekraft. **Das stuetzt den Konzentrationsbefund aus Phase 24**:
der positive Edge ist eher ein "guter Monat" als ein durchgehend wirksames Signal.

---

## PHASE 26 – Good/Bad Trade Kategorisierung (deskriptiv)

| Kategorie | n | Gross | Costs | Net | AvgHoldDays |
|---|---|---|---|---|---|
| GOOD_GROSS_AND_NET | 26 | 7714.73 | 760.53 | 6954.20 | 10.08 |
| GROSS_EDGE_COST_DESTROYED | 3 | 44.94 | 118.72 | -73.78 | 5.33 |
| BAD_SIGNAL (Gross ≤ 0) | 31 | -7107.67 | 978.95 | -8086.62 | 7.03 |

STRONG_NET_WINNER (oberstes Quintil, Net ≥ 293.37 EUR): **12 Trades**.

---

## PHASE 27 – Good vs. Bad: Feature-Vergleich

| Feature | GOOD_GROSS_AND_NET (n=26) | BAD_SIGNAL (n=31) | GROSS_EDGE_COST_DESTROYED (n=3) |
|---|---|---|---|
| opportunity_score | 0.58 | 0.57 | 0.63 |
| evidence_confidence | 0.20 | 0.18 | 0.19 |
| reward_risk_ratio (nominal) | 1.70 | 1.68 | 1.56 |
| stop_dist_pct | 3.62 | 4.03 | 4.00 |
| position_value | 5841.99 | 6343.23 | 7921.50 |
| risk_amount | 210.60 | 256.78 | 317.80 |
| holding_days | **10.08** | **7.03** | 5.33 |
| fit_multiplier | 0.92 | 0.89 | 0.60 |
| direction long/short | 14/12 | 17/14 | 1/2 |
| strategy | trend_following 22, mean_reversion 3, breakout 1 | trend_following 25, mean_reversion 5, breakout 1 | mean_reversion 2, trend_following 1 |

---

## PHASE 28 – Feature-Trennschaerfe (deskriptiv, keine Modellierung)

Vergleich netto-profitabel (n=26) vs. netto-unprofitabel (n=34):

| Feature | Net-profitabel | Net-unprofitabel | Trennschaerfe |
|---|---|---|---|
| opportunity_score | 0.58 | 0.57 | **praktisch keine** |
| evidence_confidence | 0.20 | 0.18 | **schwach** |
| reward_risk_ratio | 1.70 | 1.67 | **praktisch keine** |
| stop_dist_pct | 3.62 | 4.03 | **schwach** |
| position_value | 5841.99 | 6482.49 | **schwach** |
| risk_amount | 210.60 | 262.16 | **schwach** |
| holding_days | 10.08 | 6.88 | **maessig, aber vermutlich Folge statt Ursache** (siehe Phase 7) |
| fit_multiplier | 0.92 | 0.87 | **schwach** |

**Keine der pruefbaren Vortrade-Variablen (opportunity_score, evidence_confidence,
RRR) zeigt in diesem Sample nennenswerte Trennschaerfe** zwischen profitablen und
unprofitablen Trades. Der einzige Feature mit sichtbarem Unterschied
(holding_days) ist wahrscheinlich ein **Nachtrade-Artefakt** (Trades, die gut
laufen, werden laenger gehalten/erreichen eher das Ziel), keine Vorab-Praediktion.
Keine ML-Modellierung, keine Feature-Kombinationssuche durchgefuehrt (wie
gefordert).

---

## PHASE 29 – Cost-Sensitivity (rein rechnerisch, kein Replay)

| Cost-Level | Net P&L | Profit Factor | EV/Trade |
|---|---|---|---|
| 100% (real) | -1206.20 | 0.85 | -20.10 |
| 75% | -741.65 | 0.91 | -12.36 |
| 50% | -277.10 | 0.96 | -4.62 |
| 25% | +187.45 | 1.03 | +3.12 |
| 0% (nur Gross) | +652.00 | 1.09 | +10.87 |

**Die Kostenlast muesste auf ungefaehr 25-30% ihres tatsaechlichen Niveaus fallen**
(zwischen dem 25%- und 50%-Szenario liegt der rechnerische Break-Even), bevor das
System allein durch geringere Kosten profitabel wuerde – bei unveraendertem
Brutto-Signal. Das ist ein grosser Hebel rein rechnerisch, aber unrealistisch als
alleinige Massnahme, da eine Kostensenkung um 70-75% (Fees/Slippage) nicht
realistisch aus eigener Kraft erreichbar ist, ohne die Handelsfrequenz oder
Positionsgroesse zu aendern (beides ausdruecklich nicht Teil dieser Analyse).

---

## PHASE 30 – Gross Edge Quality

- Gross EV/Trade: **+10.87 EUR** (n=60)
- Gross Profit Factor: **1.09**
- Gross Avg Winner: **+267.57 EUR** (29 Gross-Gewinner)
- Gross Avg Loser: **-229.28 EUR** (31 Gross-Verlierer)
- Gross Payoff Ratio: **1.17**
- Gross-Win-Rate (Anteil Gross>0): **29/60 = 48.3%** – nahe Zufallsniveau

**Einordnung:** Eine Profit Factor von 1.09 bei fast 50/50 Win-Rate und Payoff-Ratio
von nur 1.17, gemessen an **n=60** Trades, ist **statistisch nicht von Rauschen zu
unterscheiden**. Ein einzelner zusaetzlicher oder fehlender Extremtrade (siehe Phase
24 Konzentration: Entfernen des groessten Gewinners macht das Brutto-Ergebnis bereits
negativ) reicht aus, um das Vorzeichen des Gesamtergebnisses zu kippen. Das ist
**keine belastbare Evidenz fuer einen robusten Brutto-Edge**, sondern bestenfalls ein
schwaches, mit der Stichprobengroesse nicht abgesichertes Signal.

---

## PHASE 31 – Cost vs. Signal Classification

**Klassifikation: B – SIGNAL EDGE WEAK, COSTS TURN IT NEGATIVE**, mit deutlichem
Vorbehalt Richtung D (Mixed/Inconclusive) wegen kleiner Stichprobe.

Begruendung (nicht allein anhand Total P&L):
- Costs relativ zu Turnover (0.25%) und Position Value (0.50%) sind **nicht
  ungewoehnlich hoch** – Klassifikation A ("Costs dominant") passt nicht.
- Gross P&L ist positiv, aber PF nur 1.09, Gross-Win-Rate nahe 50%, und das
  Ergebnis haengt an einer Handvoll Trades (Phase 24) sowie an einem einzelnen
  guten Monat (Phase 25) – das Signal ist **vorhanden, aber duenn und fragil**,
  nicht klar negativ (Klassifikation C passt auch nicht) und nicht robust
  nachgewiesen positiv.
- Nur 3/60 Trades (5%) wurden tatsaechlich von Kosten von positiv zu negativ
  gedreht (Phase 4) – die Masse der Netto-Verluste war bereits brutto negativ.
- **Der Kern des Problems**: der Brutto-Edge pro Trade (~11 EUR) ist selbst kleiner
  als die durchschnittlichen Kosten pro Trade (~31 EUR) – ein strukturell zu
  schwaches Signal muss nicht durch besonders hohe Kosten "zerstoert" werden, es
  reicht bereits ein durchschnittlicher Kostensatz, um es ins Negative zu drehen.

---

## PHASE 32 – Moegliche Entwicklungshebel (max. 3, datengestuetzt, NICHT implementiert)

1. **Mindest-Gross-Edge relativ zu Kosten vor Trade-Eroeffnung.** Gestuetzt durch
   Phase 3/21/30: durchschnittlicher Gross-Edge/Trade (~11 EUR) liegt unter den
   durchschnittlichen Kosten/Trade (~31 EUR); ein Filter, der nur Trades mit
   erwarteter Bewegung deutlich oberhalb der Round-Trip-Kosten zulaesst, adressiert
   den in Phase 31 identifizierten Kernmechanismus direkt.
2. **Schwaechste Strategie/Setup-Kombination gesondert betrachten.**
   Gestuetzt durch Phase 11: `mean_reversion` (n=10, WinRate 30%, MeanR -0.25) ist
   klar die schwaechste der drei Strategien, auch wenn n=10 fuer eine endgueltige
   Aussage klein ist.
3. **Cost-aware Ranking bei sehr engen und sehr weiten Stop-Distanzen.**
   Gestuetzt durch Phase 19: das U-foermige Muster (beide Extreme schlechter als die
   Mitte) legt nahe, dass die aktuelle Stop-Platzierungslogik an den Raendern
   suboptimal arbeitet.

Ausdruecklich **nicht** genannt: alles was Strategieparameter, Stops, Targets,
Risk%, Position Size, Portfolio Limits, Ranking Weights, Thresholds, Regime-Matrix,
Fundamentals-Gewichtung, Fees oder Slippage direkt veraendern wuerde – das faellt
unter die harte Grenze dieses Schritts.

---

## PHASE 33 – Empfohlenes naechstes Experiment (genau eines)

**Hypothese:** *Trades, deren erwartete Brutto-Bewegung (Position Value × geplante
Kursbewegung bis Target, aus `reward_risk_ratio`/`target_price` ableitbar) kleiner
oder gleich dem ~2-3-fachen der historisch beobachteten Round-Trip-Kosten
(~31 EUR bzw. ~0.5% des Positionswerts) ist, haben in diesem System keinen
oekonomischen Edge.*

- Direkt aus der 4S-Evidenz abgeleitet (Phase 3, 21, 30, 31: Kosten/Trade ≈ 3x
  Gross-Edge/Trade)
- Testet genau eine Hypothese (Kosten-zu-erwarteter-Bewegung-Verhaeltnis als
  Vorab-Filter)
- Minimale Freiheitsgrade: ein einzelner Schwellenwert (Multiplikator auf
  Kostenbasis), kein Grid, keine Kombination mehrerer Parameter
  gleichzeitig
- Fittet Run 45 nicht nachtraeglich – der Schwellenwert wird aus der
  **Kostenstruktur** abgeleitet (die stabil und modellunabhaengig ist), nicht aus
  einer Rueckwaerts-Optimierung der 60 Run-45-Ergebnisse
  selbst
- Verbraucht kein Holdout – dies waere ein separater Development-Replay auf
  bereits genutzten Trainingsdaten

**Naechster Schritt (falls vom Nutzer gewuenscht):** ein separater
Development-Replay, der ausschliesslich diesen einen Kostenschwellenwert-Filter
vorab anwendet, ohne sonstige Parameteraenderung.

---

## PHASE 34 – Kein Parameter-Tuning

Bestaetigt: kein Grid-Search, keine Schwellenwert-Serie, keine genetische
Optimierung, kein LLM-generierter Parametervorschlag durchgefuehrt. Nur die in
Phase 33 genannte **eine** Hypothese wird empfohlen, nicht getestet.

---

## PHASE 35 – Bericht

Dieser Bericht: `finanz/docs/adhoc/4S_trade_quality_cost_efficiency_2026-09-14.md`.
Run 45 ist alleinige Quelle. Keine Zahlen aus Run 42 uebernommen.

---

# ABSCHLUSSBERICHT

## TEIL A – Accounting

1. Closed Trades: **60**
2. Gross P&L: **+652.00 EUR**
3. Costs: **1858.20 EUR**
4. Net P&L: **-1206.20 EUR**
5. Accounting Diff: **0.00 EUR** (Summenkontrolle exakt, Zeilenidentitaet tautologisch – siehe Phase 2)
6. Avg Gross/Trade: **10.87 EUR**
7. Avg Costs/Trade: **30.97 EUR**
8. Avg Net/Trade: **-20.10 EUR**

## TEIL B – Cost Effect

9. Gross positiv + Net positiv: **26**
10. Gross positiv + Net negativ: **3**
11. Gross negativ + Net negativ: **31**
12. Cost-flipped Trades: **3/60 = 5%**
13. Costs / Gross Winning P&L: **23.95%**
14. Costs / Turnover: **0.25%**
15. Break-even Average Gross Edge/Trade: **30.97 EUR** (bzw. 0.50% Positionswert)

## TEIL C – Signal Quality

16. Gross Profit Factor: **1.09**
17. Net Profit Factor: **0.85**
18. Gross Expected Value: **+10.87 EUR/Trade**
19. Net Expected Value: **-20.10 EUR/Trade**
20. Gross Avg Winner: **+267.57 EUR**
21. Gross Avg Loser: **-229.28 EUR**
22. Net Avg Winner: **+293.37 EUR** (approx., aus P80/Konzentrationsdaten – Netto-Gewinner-Mittel ueber die 26 GOOD-Trades: 6954.20/26 = **267.47 EUR**)
23. Net Avg Loser: **-8086.62 / 31 = -260.86 EUR** (BAD_SIGNAL) bzw. inkl. GROSS_EDGE_COST_DESTROYED: -8160.40/34 = **-240.01 EUR**
24. Gross Payoff Ratio: **1.17**
25. Net Payoff Ratio: **267.47 / 240.01 ≈ 1.11**

## TEIL D – Exit

26. Stop Count / Gross / Net: **26 / -6875.75 / -7671.77**
27. Target Count / Gross / Net: **20 / +6552.14 / +6019.09**
28. Time Stop Count / Gross / Net: **14 / +975.61 / +446.48**
29. Other Exit Counts: **0** (keine weiteren Exit-Gruende im Sample)
30. Best Exit Type: **target_reached** (groesster Beitrag zum Brutto-Ergebnis)
31. Worst Exit Type: **stop_loss** (dominiert die Verlustseite; bemerkenswert: `time_stop` ist der einzige Exit-Typ, der bereits netto positiv ist)

## TEIL E – Strategien

32. Siehe Tabelle Phase 11: mean_reversion (10/30%/−351.17), trend_following (48/45.8%/−854.31), breakout (2/50%/−0.72)

## TEIL F – Quality Features

33. Opportunity Score: **kein monotoner Zusammenhang** (Phase 16)
34. Evidence Confidence: **schwacher, statistisch nicht belastbarer Hinweis** (n=4 Top-Bucket) (Phase 17)
35. RRR: **praktisch keine Varianz im Sample, nicht pruefbar** (Phase 18)
36. Stop Distance: **U-foermig, Mitte staerker als beide Extreme** (Phase 19)
37. Holding Period: **laengere Haltedauer korreliert mit besserem Ergebnis, vermutlich Folge nicht Ursache** (Phase 7/28)
38. Position Size: **kein robustes Muster ausser Sizing-Artefakt bei 1-Stueck-Positionen** (Phase 20)
39. Regime: **95% der Trades in einem einzigen Regime (`bull_trend_low_vol`), keine Regime-Varianz pruefbar** (Phase 14)
40. Fundamentals: **degeneriert, alle Trades "unbekannt", keine Aussage moeglich** (Phase 15)

## TEIL G – Cost Sensitivity

41. Net @ 100% Costs: **-1206.20 EUR**
42. Net @ 75% Costs: **-741.65 EUR**
43. Net @ 50% Costs: **-277.10 EUR**
44. Net @ 25% Costs: **+187.45 EUR**
45. Net @ 0% Costs: **+652.00 EUR**
46. Approx. Break-even Kostenreduktion: **zwischen 50% und 25% des heutigen Kostenniveaus** (d.h. Kosten muessten um ca. 70-75% sinken)

## TEIL H – Concentration

47. Top-1-Gewinner-Beitrag: **764.00 EUR** (117% des Gesamt-Brutto-Ergebnisses)
48. Top-3-Gewinner-Beitrag: **1957.31 EUR**
49. Top-5-Gewinner-Beitrag: **2961.41 EUR**
50. Ergebnis ohne Top-1-Gewinner: **-112.00 EUR** (Vorzeichenwechsel!)
51. Ergebnis ohne Top-3-Gewinner: **-1305.31 EUR**

## TEIL I – Zeit

52. Mai Gross/Net: **-121.24 / -770.63**
53. Juni Gross/Net: **+1432.01 / +838.64**
54. Juli Gross/Net: **-876.77 / -1452.86**
55. August (bis 08-07) Gross/Net: **+218.00 / +178.65** (n=1, nicht aussagekraeftig)

## TEIL J – Urteil

56. **Dominantes Problem: BEIDES, mit Uebergewicht auf SIGNAL QUALITY.** Kosten sind
    in absoluten/relativen Groessenordnungen moderat (0.25-0.50%), aber der
    Brutto-Edge ist so duenn (PF 1.09, EV +11 EUR/Trade, stark konzentriert auf
    wenige Trades/einen Monat), dass selbst moderate Kosten ausreichen, ihn ins
    Negative zu drehen.
57. **Classification: B – SIGNAL EDGE WEAK / COSTS TURN NEGATIVE** (mit Naehe zu D/Inconclusive wegen n=60 und starker Ergebniskonzentration)
58. **Groesste Staerke:** `target_reached`- und `time_stop`-Exits liefern
    zuverlaessig positiven Netto-Beitrag; das Stop-System funktioniert mechanisch
    sauber (nie schlechter als geplant ohne Gap/Slippage-Grund).
59. **Groesste Schwaeche:** der positive Brutto-Edge ist extrem konzentriert (ein
    einzelner Trade / ein einzelner Monat entscheidet ueber Vorzeichen des
    Gesamtergebnisses); keine der verfuegbaren Vorab-Scoring-Variablen
    (Opportunity Score, Evidence Confidence, RRR) zeigt in diesem Sample
    nennenswerte Trennschaerfe zwischen guten und schlechten Trades.
60. **Ist die Trade-Frequenz oekonomisch gerechtfertigt? INCONCLUSIVE.** 0.79
    Trades/Tag und Kosten/Turnover von nur 0.25% sind fuer sich genommen nicht
    exzessiv, aber bei einem derart duennen und instabilen Brutto-Edge kann keine
    Frequenz als "gerechtfertigt" belegt werden.
61. **Ist der aktuelle Brutto-Edge gross genug? NEIN**, mit der Einschraenkung
    INCONCLUSIVE fuer die Frage ob ueberhaupt ein echter (von Null verschiedener)
    Edge vorliegt – bei n=60 und der beobachteten Konzentration ist der Edge zu
    duenn, um sicher von Stichprobenrauschen unterschieden zu werden.
62. **Max. 3 Entwicklungshebel:** (1) Mindest-Gross-Edge relativ zu Kosten vor
    Trade-Eroeffnung, (2) gesonderte Betrachtung der schwaechsten
    Strategie/Setup-Kombination (`mean_reversion`), (3) Cost-aware Umgang mit
    Stop-Distanz-Extremen (siehe Phase 32).
63. **Genau EIN naechstes Experiment:** Hypothese "Trades mit erwarteter
    Brutto-Bewegung ≤ 2-3x historischer Round-Trip-Kosten haben keinen
    oekonomischen Edge" als separater, ungefitteter Development-Replay-Test
    (siehe Phase 33).

---

**Harte Grenze eingehalten:** keine Workflow-, Config- oder Strategieaenderung,
kein Replay, kein Holdout, keine Optimierung durchgefuehrt. STOPP nach Analyse.
