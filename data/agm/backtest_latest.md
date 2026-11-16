# Projection backtest — 16 decision days 2026-10-10..2026-11-09, next 7 days

_Error = games-weighted mean squared error per game (lower is better), 26039 player-games. 'vs STD' = error relative to season-to-date (100% = same)._

_Parameters (K, beta, age) were chosen on these same days: no holdout yet. The fair comparison for what this season adds is vs 'last 3 seasons only'; vs season-to-date is flattered early in the season._

| Model | G | A | PIM | PM | PTS | PTS vs STD (gp 3+) | vs STD (gp 10+) | vs prior only (gp 3+ / 10+) |
|---|---|---|---|---|---|---|---|---|
| season-to-date only | 0.081 | 0.135 | 1.016 | 0.659 | 0.212 | 100% | 100% | 121% / 107% |
| last 3 seasons only | 0.064 | 0.110 | 0.770 | 0.511 | 0.176 | 83% | 93% | 100% / 100% |
| blend (no role, no age) | 0.064 | 0.109 | 0.781 | 0.508 | 0.172 | 81% | 90% | 98% / 97% |
| blend + role | 0.063 | 0.107 | 0.781 | 0.508 | 0.169 | 79% | 89% | 96% / 95% |
| blend + role + age | 0.063 | 0.108 | 0.781 | 0.508 | 0.169 | 79% | 89% | 96% / 96% |
| blend + role, K x0.5 | 0.064 | 0.109 | 0.805 | 0.509 | 0.171 | 80% | 89% | 97% / 96% |
| blend + role, K x2 | 0.063 | 0.107 | 0.771 | 0.509 | 0.169 | 80% | 89% | 96% / 96% |
| blend + role beta=1 | 0.063 | 0.107 | 0.781 | 0.508 | 0.168 | 79% | 89% | 96% / 95% |
| blend + role beta=0.4 | 0.064 | 0.108 | 0.781 | 0.508 | 0.170 | 80% | 89% | 96% / 96% |

# Rule backtest — top 3 available forwards each day, 2026-10-08..2026-11-09 (33 days)

_Picks that didn't play in the window count as 0 games. Points/pick = points over the 7 days per pick (what a roster spot actually returned). Picks overlap heavily day to day: unique players is the real n._

| Rule | Picks | Unique players | Points/pick (7d) | Points/GP | G | A | PIM | +/- | No-game picks |
|---|---|---|---|---|---|---|---|---|---|
| projection value (G,A,PIM,+/-) | 99 | 18 | 1.69 | 0.61 | 0.36 | 0.25 | 0.32 | -0.05 | 2 |
| projection points | 99 | 18 | 2.69 | 0.99 | 0.33 | 0.65 | 0.28 | -0.16 | 2 |
| projection points, TOI 16+ | 97 | 16 | 2.69 | 0.99 | 0.33 | 0.67 | 0.28 | -0.16 | 2 |
| season-to-date points, TOI 16+ | 97 | 22 | 1.78 | 0.62 | 0.21 | 0.42 | 0.33 | -0.48 | 2 |
| hot last 5 points, TOI 16+ | 97 | 28 | 2.05 | 0.71 | 0.25 | 0.46 | 0.42 | -0.24 | 2 |
| most ice time | 99 | 23 | 2.43 | 0.85 | 0.39 | 0.47 | 0.27 | +0.04 | 0 |
| random role player (TOI 16+) | 97 | 62 | 1.95 | 0.67 | 0.29 | 0.38 | 0.49 | +0.02 | 0 |

_projection points no-game picks: J. Tavares (injured or scratched after the decision day)_

_projection points, TOI 16+ no-game picks: J. Tavares (injured or scratched after the decision day)_

# Signal backtest — forwards, next 7 days vs base projection (no role term)

| Signal | n | Projected P/GP | Actual P/GP | Actual - projected |
|---|---|---|---|---|
| all | 4831 | 0.56 | 0.57 | +0.02 |
| ice time up 2+ min (last 3 vs before) | 561 | 0.54 | 0.63 | +0.09 |
| ice time down 2+ min | 419 | 0.58 | 0.52 | -0.06 |
| hot: last 5 >= projection + 0.5 | 325 | 0.76 | 0.77 | +0.01 |
| cold: last 5 <= projection - 0.4 | 286 | 0.70 | 0.67 | -0.03 |
| cold and ice time down 1.5+ | 62 | 0.65 | 0.61 | -0.04 |

Wrote /home/runner/work/fantasyhockey/fantasyhockey/data/agm/rules_ledger.json
