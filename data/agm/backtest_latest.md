# Projection backtest — 9 decision days 2026-10-10..2026-10-26, next 7 days

_Error = games-weighted mean squared error per game (lower is better), 14303 player-games. 'vs STD' = error relative to season-to-date (100% = same)._

| Model | G | A | PIM | PM | PTS | PTS vs STD |
|---|---|---|---|---|---|---|
| season-to-date only | 0.087 | 0.140 | 0.924 | 0.703 | 0.229 | 100% |
| last 3 seasons only | 0.065 | 0.105 | 0.596 | 0.484 | 0.174 | 76% |
| blend (no role, no age) | 0.065 | 0.104 | 0.604 | 0.484 | 0.171 | 75% |
| blend + role | 0.064 | 0.103 | 0.604 | 0.484 | 0.167 | 73% |
| blend + role + age | 0.064 | 0.103 | 0.604 | 0.484 | 0.167 | 73% |
| blend + role, K x0.5 | 0.065 | 0.104 | 0.630 | 0.488 | 0.169 | 74% |
| blend + role, K x2 | 0.064 | 0.103 | 0.595 | 0.483 | 0.167 | 73% |
| blend + role beta=1 | 0.064 | 0.103 | 0.604 | 0.484 | 0.166 | 73% |
| blend + role beta=0.4 | 0.064 | 0.103 | 0.604 | 0.484 | 0.168 | 74% |

# Rule backtest — top 3 available forwards each day, 2026-10-08..2026-10-26 (19 days)

| Rule | Picks | Unique | Points/GP | G | A | PIM | +/- | Value/GP |
|---|---|---|---|---|---|---|---|---|
| projection value (G,A,PIM,+/-) | 57 | 16 | 0.62 | 0.38 | 0.24 | 0.32 | -0.11 | 3.72 |
| projection points | 57 | 15 | 0.94 | 0.38 | 0.56 | 0.36 | -0.13 | 5.22 |
| season-to-date points, TOI 16+ | 55 | 13 | 0.71 | 0.25 | 0.47 | 0.36 | -0.43 | 3.15 |
| hot last 5 points, TOI 16+ | 55 | 18 | 0.68 | 0.29 | 0.39 | 0.38 | -0.17 | 3.81 |
| most ice time | 57 | 21 | 0.86 | 0.44 | 0.43 | 0.23 | +0.07 | 5.25 |
| random role player (TOI 16+) | 55 | 40 | 0.65 | 0.31 | 0.34 | 0.35 | -0.16 | 3.69 |

# Signal backtest — forwards, next 7 days vs base projection (no role term)

| Signal | n | Projected P/GP | Actual P/GP | Actual - projected |
|---|---|---|---|---|
| all | 2356 | 0.56 | 0.58 | +0.02 |
| ice time up 2+ min (last 3 vs before) | 313 | 0.54 | 0.62 | +0.08 |
| ice time down 2+ min | 195 | 0.63 | 0.54 | -0.09 |
| hot: last 5 >= projection + 0.5 | 150 | 0.81 | 0.78 | -0.03 |
| cold: last 5 <= projection - 0.4 | 138 | 0.67 | 0.63 | -0.04 |
| cold and ice time down 1.5+ | 22 | 0.68 | 0.47 | -0.21 |

Wrote /home/claude/fantasyhockey/data/agm/rules_ledger.json
