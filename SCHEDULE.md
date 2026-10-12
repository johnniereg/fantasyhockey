# AGM data schedule

Every brief reads `data/inseason/`, so each one needs a fetch that (a) ran **today**, (b) ran **after the games it reports on were final**, and (c) actually landed before the brief starts.

## Timeline (all ET, DST-proof)

| Time | What | Why then |
|---|---|---|
| ~01:30 | Last NHL games final (10:30pm starts + OT/SO) | |
| **05:40** | Fetch `reason=morning` | All of last night final in Yahoo; on Mondays, after the 03:00 ET add reset |
| **07:25** | Fetch `reason=morning-backup` | Second chance; picks up early-morning waiver/opp moves |
| 07:52 | Morning brief (`agm_gate.py morning --wait 30`) | |
| 08:30 | AGM watchdog | Alerts if any AGM scheduled task is off, suspended or failing |
| **Sun 11:15** | Fetch `reason=sunday` | Fresh adds-used + next matchup |
| Sun 11:45 | Sunday brief (`agm_gate.py sunday --wait 30`) | |
| **16:15** | Fetch `reason=goalie` | Today's saved lineup + afternoon moves; before any 5pm+ puck drop |
| 16:52 | 5pm check (`agm_gate.py goalie --wait 20`), alert-only | |
| 04:23 / 03:23 (EDT/EST) | GitHub `schedule` fallback | Best-effort only; may land hours late |

Bold rows are fired by the Claude scheduled tasks below. The other rows are the briefs, which run as their own scheduled tasks.

## Fetch triggers: Claude scheduled tasks (primary)

GitHub `schedule` runs are best-effort and were landing 2–7h late or not at all. `workflow_dispatch` runs start within about a minute, so four Claude cloud scheduled tasks (routines, America/Toronto time) fire the fetches:

| Task | Fires (ET) | `reason` | ID |
|---|---|---|---|
| AGM fetch dispatch: morning (5:40am ET) | 05:40 daily | `morning` | [trig_01RXmNYJiA7nQC4vSc54QpFM](https://claude.ai/code/routines/trig_01RXmNYJiA7nQC4vSc54QpFM) |
| AGM fetch dispatch: morning-backup (7:25am ET) | 07:25 daily | `morning-backup` | [trig_01NBRvLHfGF93tNT9r3rmMW2](https://claude.ai/code/routines/trig_01NBRvLHfGF93tNT9r3rmMW2) |
| AGM fetch dispatch: sunday (Sun 11:15am ET) | 11:15 Sundays | `sunday` | [trig_01DjDxbhp4estd1YTYTBT2Rp](https://claude.ai/code/routines/trig_01DjDxbhp4estd1YTYTBT2Rp) |
| AGM fetch dispatch: goalie (4:15pm ET) | 16:15 daily | `goalie` | [trig_01Rw1ETwwMRnARwVSXi2FWAH](https://claude.ai/code/routines/trig_01Rw1ETwwMRnARwVSXi2FWAH) |

Each task runs `gh workflow run update.yml --ref main -f reason=<reason>`, watches the run, and sends a push notification only if the dispatch or the run fails. Success = a commit `chore: update dashboard data (<reason>) [skip ci]` and `"trigger": "workflow_dispatch:<reason>"` in `manifest.json`. Edit, pause or run them at https://claude.ai/code/routines.

## GitHub fallback cron

`update.yml` keeps `23 8 * * *` as a last resort only. The three TEMP fallback crons were removed 2026-10-12: the dispatch tasks have landed on time every day since 10-04, and the extra GitHub runs landed 10:00–21:00 ET, some mid-game.

## Add budget

4 adds per week, reset **Monday 03:00 ET** (Sunday midnight PT). A Sunday add counts against the week that is ending.

## Backup option: cron-job.org

If the Claude scheduled tasks stop working, the same dispatches can be fired from cron-job.org:

1. GitHub → Settings → Developer settings → **Fine-grained token**: repository `johnniereg/fantasyhockey` only; permission **Actions: Read and write**. Note the expiry date.
2. cron-job.org → one job per bold row above, timezone **America/Toronto**:
   - URL: `https://api.github.com/repos/johnniereg/fantasyhockey/actions/workflows/update.yml/dispatches`
   - Method: `POST`
   - Headers: `Authorization: Bearer <token>` · `Accept: application/vnd.github+json` · `X-GitHub-Api-Version: 2022-11-28`
   - Body: `{"ref":"main","inputs":{"reason":"morning"}}` (change `reason` per job)
   - Success = HTTP 204. Turn on failure notifications.
3. Test: run one job manually and confirm a commit `chore: update dashboard data (morning) [skip ci]` appears within ~2 min.
4. Pause the matching Claude tasks so fetches aren't doubled.

## Brief contract

The first step of every brief is `python3 scripts/agm_gate.py <mode> --wait N`:

- **PASS / WARN** → proceed; WARN lines go in Data.
- **FAIL** (exit 2) → the fetch it needs hasn't landed, or it ran before last night's games were final. Don't treat the Yahoo scoreboard or lineups as current: use box scores for the recap, say "Can't see today's lineup — check Yahoo", and put the FAIL line in Now and Data.

`manifest.json` now carries `games.yesterday.all_final`, `games.live_now`, `trigger`, `finished_at_utc` and `warnings` (e.g. a Yahoo `current_week` mismatch) so the gate and the briefs can tell a clean fetch from a mid-game one.

## Data files (added 2026-10-12)

Pipeline data only. AGM output (briefs, analysis) lives in the BrainPal vault, never in this repo.

| File | What | Reader |
|---|---|---|
| `daily/<date>.json` | Every team's roster for the date: slot, status and that day's fantasy stats (Yahoo `type=date`). Yesterday each run; backfills 3 past days per run | `agm_ledger.py`, recaps |
| `goalie_starts.json` | One row per goalie per final NHL game: starter, TOI, SA/SV/GA, decision (NHL box scores) | `agm_goalies.py` |
| `waivers_<page>.json` | Players on waivers (Yahoo `status=W`) | `agm_plan.py` (W flag), `agm_goalies.py` |
| `archive/scoreboard_week_NN.json` | Each completed week's league scoreboard | `agm_ranks.py` |

These "extras" never fail the fetch: a problem lands in `manifest.json` `warnings` and `extras_errors`, and the core data stays green.

## Scripts

| Script | Use |
|---|---|
| `agm_gate.py <mode> --wait N` | First step of every brief |
| `agm_week.py` | Morning brief: scoreboard, per-date lineups, starts remaining |
| `agm_plan.py [--week N]` | Nights, projected starts, FA start math. Drop column respects keepers and the `UNLIKELY` tier; `(W)` marks waiver players |
| `agm_goalies.py` | Goalie market: our goalies, trigger 1 hits, trigger 2 hints, every goalie's last-5 |
| `agm_ranks.py [--next]` | H2H vs all-play standings, our weekly category ranks, data lean vs the opponent |
| `agm_ledger.py` | Our moves and what each add/drop has produced since |
