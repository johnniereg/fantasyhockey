# Projection backtest — 12 decision days 2026-10-10..2026-11-01, next 7 days

_Error = games-weighted mean squared error per game (lower is better), 19371 player-games. 'vs STD' = error relative to season-to-date (100% = same)._

_Parameters (K, beta, age) were chosen on these same days: no holdout yet. The fair comparison for what this season adds is vs 'last 3 seasons only'; vs season-to-date is flattered early in the season._

| Model | G | A | PIM | PM | PTS | PTS vs STD (gp 3+) | vs STD (gp 10+) | vs prior only (gp 3+ / 10+) |
|---|---|---|---|---|---|---|---|---|
| season-to-date only | 0.085 | 0.136 | 0.970 | 0.667 | 0.219 | 100% | 100% | 124% / 106% |
| last 3 seasons only | 0.067 | 0.108 | 0.691 | 0.489 | 0.176 | 80% | 94% | 100% / 100% |
| blend (no role, no age) | 0.066 | 0.106 | 0.697 | 0.487 | 0.172 | 79% | 91% | 98% / 96% |
| blend + role | 0.065 | 0.105 | 0.697 | 0.487 | 0.168 | 77% | 88% | 96% / 94% |
| blend + role + age | 0.065 | 0.105 | 0.697 | 0.487 | 0.168 | 77% | 89% | 96% / 94% |
| blend + role, K x0.5 | 0.066 | 0.106 | 0.721 | 0.489 | 0.170 | 78% | 89% | 96% / 94% |
| blend + role, K x2 | 0.065 | 0.105 | 0.689 | 0.487 | 0.169 | 77% | 89% | 96% / 95% |
| blend + role beta=1 | 0.065 | 0.105 | 0.697 | 0.487 | 0.168 | 76% | 88% | 95% / 94% |
| blend + role beta=0.4 | 0.066 | 0.106 | 0.697 | 0.487 | 0.170 | 77% | 89% | 96% / 95% |

# Rule backtest — top 3 available forwards each day, 2026-10-08..2026-11-02 (26 days)

_Picks that didn't play in the window count as 0 games. Points/pick = points over the 7 days per pick (what a roster spot actually returned). Picks overlap heavily day to day: unique players is the real n._

| Rule | Picks | Unique players | Points/pick (7d) | Points/GP | G | A | PIM | +/- | No-game picks |
|---|---|---|---|---|---|---|---|---|---|
| projection value (G,A,PIM,+/-) | 78 | 18 | 1.72 | 0.61 | 0.36 | 0.26 | 0.28 | -0.10 | 1 |
| projection points | 78 | 15 | 2.53 | 0.94 | 0.33 | 0.62 | 0.28 | -0.17 | 2 |
| projection points, TOI 16+ | 76 | 13 | 2.53 | 0.95 | 0.32 | 0.63 | 0.29 | -0.18 | 2 |
| season-to-date points, TOI 16+ | 76 | 21 | 1.72 | 0.60 | 0.22 | 0.39 | 0.32 | -0.40 | 2 |
| hot last 5 points, TOI 16+ | 76 | 25 | 1.96 | 0.68 | 0.26 | 0.42 | 0.42 | -0.18 | 2 |
| most ice time | 78 | 22 | 2.44 | 0.86 | 0.41 | 0.45 | 0.21 | +0.09 | 0 |
| random role player (TOI 16+) | 76 | 53 | 1.99 | 0.68 | 0.32 | 0.36 | 0.47 | +0.05 | 0 |

_projection points no-game picks: J. Tavares (injured or scratched after the decision day)_

_projection points, TOI 16+ no-game picks: J. Tavares (injured or scratched after the decision day)_

# Signal backtest — forwards, next 7 days vs base projection (no role term)

| Signal | n | Projected P/GP | Actual P/GP | Actual - projected |
|---|---|---|---|---|
| all | 3406 | 0.56 | 0.58 | +0.03 |
| ice time up 2+ min (last 3 vs before) | 413 | 0.53 | 0.63 | +0.09 |
| ice time down 2+ min | 291 | 0.60 | 0.55 | -0.05 |
| hot: last 5 >= projection + 0.5 | 235 | 0.78 | 0.79 | +0.01 |
| cold: last 5 <= projection - 0.4 | 205 | 0.69 | 0.67 | -0.01 |
| cold and ice time down 1.5+ | 40 | 0.63 | 0.61 | -0.03 |

Wrote /home/runner/work/fantasyhockey/fantasyhockey/data/agm/rules_ledger.json
