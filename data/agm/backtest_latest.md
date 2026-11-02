# Projection backtest — 9 decision days 2026-10-10..2026-10-26, next 7 days

_Error = games-weighted mean squared error per game (lower is better), 14303 player-games. 'vs STD' = error relative to season-to-date (100% = same)._

_Parameters (K, beta, age) were chosen on these same days: no holdout yet. The fair comparison for what this season adds is vs 'last 3 seasons only'; vs season-to-date is flattered early in the season._

| Model | G | A | PIM | PM | PTS | PTS vs STD (gp 3+) | vs STD (gp 10+) | vs prior only (gp 3+ / 10+) |
|---|---|---|---|---|---|---|---|---|
| season-to-date only | 0.087 | 0.140 | 0.924 | 0.703 | 0.229 | 100% | 100% | 132% / 109% |
| last 3 seasons only | 0.065 | 0.105 | 0.596 | 0.484 | 0.174 | 76% | 91% | 100% / 100% |
| blend (no role, no age) | 0.065 | 0.104 | 0.604 | 0.484 | 0.171 | 75% | 89% | 99% / 97% |
| blend + role | 0.064 | 0.103 | 0.604 | 0.484 | 0.167 | 73% | 86% | 96% / 95% |
| blend + role + age | 0.064 | 0.103 | 0.604 | 0.484 | 0.167 | 73% | 86% | 96% / 94% |
| blend + role, K x0.5 | 0.065 | 0.104 | 0.630 | 0.488 | 0.169 | 74% | 87% | 97% / 95% |
| blend + role, K x2 | 0.064 | 0.103 | 0.595 | 0.483 | 0.167 | 73% | 87% | 96% / 95% |
| blend + role beta=1 | 0.064 | 0.103 | 0.604 | 0.484 | 0.166 | 73% | 86% | 96% / 94% |
| blend + role beta=0.4 | 0.064 | 0.103 | 0.604 | 0.484 | 0.168 | 74% | 87% | 97% / 95% |

# Rule backtest — top 3 available forwards each day, 2026-10-08..2026-10-26 (19 days)

_Picks that didn't play in the window count as 0 games. Points/pick = points over the 7 days per pick (what a roster spot actually returned). Picks overlap heavily day to day: unique players is the real n._

| Rule | Picks | Unique players | Points/pick (7d) | Points/GP | G | A | PIM | +/- | No-game picks |
|---|---|---|---|---|---|---|---|---|---|
| projection value (G,A,PIM,+/-) | 57 | 16 | 1.84 | 0.62 | 0.38 | 0.24 | 0.32 | -0.11 | 0 |
| projection points | 57 | 14 | 2.39 | 0.98 | 0.41 | 0.57 | 0.33 | -0.01 | 2 |
| projection points, TOI 16+ | 55 | 12 | 2.38 | 0.98 | 0.40 | 0.59 | 0.35 | -0.02 | 2 |
| season-to-date points, TOI 16+ | 55 | 17 | 1.67 | 0.60 | 0.22 | 0.38 | 0.39 | -0.35 | 2 |
| hot last 5 points, TOI 16+ | 55 | 18 | 1.89 | 0.69 | 0.28 | 0.40 | 0.41 | -0.16 | 2 |
| most ice time | 57 | 21 | 2.46 | 0.86 | 0.45 | 0.41 | 0.28 | +0.06 | 0 |
| random role player (TOI 16+) | 55 | 41 | 2.27 | 0.77 | 0.36 | 0.40 | 0.53 | +0.08 | 0 |

_projection points no-game picks: J. Tavares (injured or scratched after the decision day)_

_projection points, TOI 16+ no-game picks: J. Tavares (injured or scratched after the decision day)_

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
