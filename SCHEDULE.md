# AGM data schedule

Every brief reads `data/inseason/`, so each one needs a fetch that (a) ran **today**, (b) ran **after the games it reports on were final**, and (c) actually landed before the brief starts.

## Timeline (all ET, DST-proof)

| Time | What | Why then |
|---|---|---|
| ~01:30 | Last NHL games final (10:30pm starts + OT/SO) | |
| **05:40** | Fetch `reason=morning` | All of last night final in Yahoo; after the Sun 03:00 add reset |
| **07:25** | Fetch `reason=morning-backup` | Second chance; picks up early-morning waiver/opp moves |
| 07:52 | Morning brief (`agm_gate.py morning --wait 30`) | |
| **Sun 11:15** | Fetch `reason=sunday` | Fresh adds-used + next matchup |
| Sun 11:45 | Sunday brief (`agm_gate.py sunday --wait 30`) | |
| **16:15** | Fetch `reason=goalie` | Today's saved lineup + afternoon moves; before any 5pm+ puck drop |
| 16:52 | Goalie check (`agm_gate.py goalie --wait 20`) | |
| 04:23 / 03:23 (EDT/EST) | GitHub `schedule` fallback | Best-effort only; may land hours late |

## External scheduler (cron-job.org)

GitHub `schedule` runs are best-effort and were landing 4–7h late or not at all. `workflow_dispatch` runs start within about a minute, so the fetches are fired from cron-job.org instead.

1. GitHub → Settings → Developer settings → **Fine-grained token**: repository `johnniereg/fantasyhockey` only; permission **Actions: Read and write**. Note the expiry date.
2. cron-job.org → one job per row in bold above, timezone **America/Toronto**:
   - URL: `https://api.github.com/repos/johnniereg/fantasyhockey/actions/workflows/update.yml/dispatches`
   - Method: `POST`
   - Headers: `Authorization: Bearer <token>` · `Accept: application/vnd.github+json` · `X-GitHub-Api-Version: 2022-11-28`
   - Body: `{"ref":"main","inputs":{"reason":"morning"}}` (change `reason` per job)
   - Success = HTTP 204. Turn on failure notifications.
3. Test: run one job manually and confirm a commit `chore: update dashboard data (morning) [skip ci]` appears within ~2 min.

## Brief contract

The first step of every brief is `python3 scripts/agm_gate.py <mode> --wait N`:

- **PASS / WARN** → proceed; WARN lines go in Data.
- **FAIL** (exit 2) → the fetch it needs hasn't landed, or it ran before last night's games were final. Don't treat the Yahoo scoreboard or lineups as current: use box scores for the recap, say "Can't see today's lineup — check Yahoo", and put the FAIL line in Now and Data.

`manifest.json` now carries `games.yesterday.all_final`, `games.live_now`, `trigger`, `finished_at_utc` and `warnings` (e.g. a Yahoo `current_week` mismatch) so the gate and the briefs can tell a clean fetch from a mid-game one.
