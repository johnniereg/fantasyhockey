# Projection backtest — 19 decision days 2026-10-10..2026-11-15, next 7 days

_Error = games-weighted mean squared error per game (lower is better), 31141 player-games. 'vs STD' = error relative to season-to-date (100% = same)._

_Parameters (K, beta, age) were chosen on these same days: no holdout yet. The fair comparison for what this season adds is vs 'last 3 seasons only'; vs season-to-date is flattered early in the season._

| Model | G | A | PIM | PM | PTS | PTS vs STD (gp 3+) | vs STD (gp 10+) | vs prior only (gp 3+ / 10+) |
|---|---|---|---|---|---|---|---|---|
| season-to-date only | 0.079 | 0.134 | 0.956 | 0.653 | 0.209 | 100% | 100% | 118% / 107% |
| last 3 seasons only | 0.064 | 0.111 | 0.732 | 0.518 | 0.177 | 85% | 93% | 100% / 100% |
| blend (no role, no age) | 0.064 | 0.110 | 0.744 | 0.515 | 0.173 | 83% | 91% | 98% / 97% |
| blend + role | 0.063 | 0.109 | 0.744 | 0.515 | 0.169 | 81% | 89% | 96% / 96% |
| blend + role + age | 0.063 | 0.109 | 0.744 | 0.515 | 0.169 | 81% | 89% | 96% / 96% |
| blend + role, K x0.5 | 0.064 | 0.110 | 0.766 | 0.517 | 0.171 | 82% | 90% | 97% / 96% |
| blend + role, K x2 | 0.063 | 0.108 | 0.733 | 0.515 | 0.169 | 81% | 89% | 96% / 96% |
| blend + role beta=1 | 0.063 | 0.109 | 0.744 | 0.515 | 0.169 | 81% | 89% | 96% / 95% |
| blend + role beta=0.4 | 0.063 | 0.109 | 0.744 | 0.515 | 0.170 | 81% | 90% | 96% / 96% |

# Rule backtest — top 3 available forwards each day, 2026-10-08..2026-11-16 (40 days)

_Picks that didn't play in the window count as 0 games. Points/pick = points over the 7 days per pick (what a roster spot actually returned). Picks overlap heavily day to day: unique players is the real n._

| Rule | Picks | Unique players | Points/pick (7d) | Points/GP | G | A | PIM | +/- | No-game picks |
|---|---|---|---|---|---|---|---|---|---|
| projection value (G,A,PIM,+/-) | 120 | 19 | 1.52 | 0.55 | 0.33 | 0.22 | 0.40 | -0.13 | 2 |
| projection points | 120 | 19 | 2.58 | 0.94 | 0.32 | 0.62 | 0.32 | -0.18 | 2 |
| projection points, TOI 16+ | 118 | 17 | 2.58 | 0.94 | 0.31 | 0.63 | 0.32 | -0.18 | 2 |
| season-to-date points, TOI 16+ | 118 | 23 | 1.80 | 0.63 | 0.21 | 0.42 | 0.38 | -0.46 | 2 |
| hot last 5 points, TOI 16+ | 118 | 35 | 1.94 | 0.68 | 0.23 | 0.45 | 0.44 | -0.21 | 2 |
| most ice time | 120 | 25 | 2.46 | 0.87 | 0.38 | 0.49 | 0.34 | +0.08 | 0 |
| random role player (TOI 16+) | 118 | 69 | 1.95 | 0.67 | 0.28 | 0.39 | 0.49 | +0.01 | 0 |

_projection points no-game picks: J. Tavares (injured or scratched after the decision day)_

_projection points, TOI 16+ no-game picks: J. Tavares (injured or scratched after the decision day)_

# Signal backtest — forwards, next 7 days vs base projection (no role term)

| Signal | n | Projected P/GP | Actual P/GP | Actual - projected |
|---|---|---|---|---|
| all | 5901 | 0.55 | 0.57 | +0.02 |
| ice time up 2+ min (last 3 vs before) | 660 | 0.54 | 0.64 | +0.09 |
| ice time down 2+ min | 545 | 0.56 | 0.52 | -0.04 |
| hot: last 5 >= projection + 0.5 | 391 | 0.76 | 0.78 | +0.02 |
| cold: last 5 <= projection - 0.4 | 366 | 0.70 | 0.66 | -0.04 |
| cold and ice time down 1.5+ | 83 | 0.68 | 0.58 | -0.10 |

Wrote /home/runner/work/fantasyhockey/fantasyhockey/data/agm/rules_ledger.json
