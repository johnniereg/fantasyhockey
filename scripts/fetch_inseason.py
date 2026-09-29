"""
In-season data fetch for AGM (weekly plan / daily lineup checks)
=================================================================
Runs in GitHub Actions (full network). Saves RAW API responses to data/inseason/
so parsing can happen downstream (Claude reads them after `git pull`) and a bad
parser never needs a re-run. Each endpoint is isolated: one failure is recorded
in manifest.json and the rest still save.

Run:  python3 scripts/fetch_inseason.py
"""

import datetime as dt
import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import LEAGUE_IDS, CURRENT_SEASON, DATA_DIR
from scripts.yahoo_auth import get_valid_token
from scripts.fetch_data import yahoo_get

OUT_DIR   = os.path.join(DATA_DIR, "inseason")
MY_TEAM   = os.environ.get("AGM_TEAM_NUM", "1")          # Flow Riders = t.1
POSITIONS = ["C", "LW", "RW", "D", "G"]
FA_PAGES  = 2                                            # 25 per page
NHL_BASE  = "https://api-web.nhle.com/v1"

manifest = {"fetched_at_utc": None, "ok": [], "errors": {}}


def save(name, payload):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)


def grab(name, fn):
    """Run fn(), save its result under name, record success/failure. Never raises."""
    try:
        payload = fn()
        save(name, payload)
        manifest["ok"].append(name)
        print(f"   ✅ {name}")
        return payload
    except Exception as e:
        msg = str(e)[:600]
        manifest["errors"][name] = msg
        print(f"   ❌ {name}: {msg}")
        return None


def nhl_get(path):
    req = urllib.request.Request(f"{NHL_BASE}{path}", headers={"User-Agent": "agm-fetch"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def league_key_for(token):
    try:
        game = yahoo_get("/game/nhl", token)["fantasy_content"]["game"]
        game_meta = game[0] if isinstance(game, list) else game
        gk = str(game_meta["game_key"])
    except Exception as e:
        print(f"   ⚠️  game key lookup failed ({e}); using 477")
        gk = "477"
    return f"{gk}.l.{LEAGUE_IDS[CURRENT_SEASON]}", gk


def find_week_dates(game_weeks_raw, today):
    """Return [(week, start, end)] from /game/{key}/game_weeks. Tolerant of shape."""
    out = []
    def walk(o):
        if isinstance(o, dict):
            if "start" in o and "end" in o and "week" in o:
                out.append((int(o["week"]), o["start"], o["end"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(game_weeks_raw)
    return sorted(set(out))


def main():
    manifest["fetched_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).date()   # ET-ish; exact tz irrelevant here
    token = get_valid_token()     # exits loudly if the refresh token is rejected

    print("\n🏒 In-season fetch")
    lk, game_key = league_key_for(token)
    tk = f"{lk}.t.{MY_TEAM}"
    manifest.update({"league_key": lk, "team_key": tk, "date_et": today.isoformat()})
    print(f"   league {lk} · team {tk} · {today}")

    # ── League shape ──────────────────────────────────────────────────────
    settings = grab("league_settings", lambda: yahoo_get(f"/league/{lk}/settings", token))
    meta     = grab("league_meta",     lambda: yahoo_get(f"/league/{lk}/metadata", token))
    weeks    = grab("game_weeks",      lambda: yahoo_get(f"/game/{game_key}/game_weeks", token))

    cur_week = None
    try:
        league = meta["fantasy_content"]["league"]
        league = league[0] if isinstance(league, list) else league
        cur_week = int(league["current_week"])
    except Exception:
        pass
    week_dates = find_week_dates(weeks, today) if weeks else []
    wd = {w: (s, e) for w, s, e in week_dates}
    manifest["current_week"] = cur_week
    manifest["week_dates"] = {str(w): wd[w] for w in (cur_week, (cur_week or 0) + 1) if w in wd}

    # ── My team ───────────────────────────────────────────────────────────
    grab("my_team",          lambda: yahoo_get(f"/team/{tk}/metadata", token))   # includes roster_adds used this week
    grab("my_roster_today",  lambda: yahoo_get(f"/team/{tk}/roster;date={today}/players", token))
    grab("my_roster_stats",  lambda: yahoo_get(f"/team/{tk}/roster;date={today}/players/stats;type=season", token))
    if cur_week:
        grab("my_matchup",   lambda: yahoo_get(f"/team/{tk}/matchups;weeks={cur_week}", token))

    # ── League-wide ───────────────────────────────────────────────────────
    if cur_week:
        grab("scoreboard_current", lambda: yahoo_get(f"/league/{lk}/scoreboard;week={cur_week}", token))
        if cur_week > 1:
            grab("scoreboard_previous", lambda: yahoo_get(f"/league/{lk}/scoreboard;week={cur_week-1}", token))
    grab("all_rosters",  lambda: yahoo_get(f"/league/{lk}/teams/roster;date={today}", token))
    grab("transactions", lambda: yahoo_get(f"/league/{lk}/transactions;types=add,drop,trade;count=40", token))

    # ── Free agents, by position, preseason-rank order + ownership ────────
    for pos in POSITIONS:
        for page in range(FA_PAGES):
            start = page * 25
            grab(f"fa_{pos}_{page}", lambda pos=pos, start=start: yahoo_get(
                f"/league/{lk}/players;status=A;position={pos};sort=AR;count=25;start={start}"
                f"/percent_owned", token))
    # Last-7-days stats for the top of each FA list (separate call so a bad stats param can't sink the list)
    for pos in POSITIONS:
        grab(f"fa_{pos}_lastweek", lambda pos=pos: yahoo_get(
            f"/league/{lk}/players;status=A;position={pos};sort=AR;count=25;start=0"
            f"/stats;type=lastweek", token))

    # ── NHL schedule: current fantasy week through end of next week ──────
    try:
        start = dt.date.fromisoformat(wd[cur_week][0]) if cur_week in wd else today
        nxt   = (cur_week or 0) + 1
        end   = dt.date.fromisoformat(wd[nxt][1]) if nxt in wd else today + dt.timedelta(days=14)
    except Exception:
        start, end = today, today + dt.timedelta(days=14)
    manifest["nhl_range"] = [start.isoformat(), end.isoformat()]
    d, blocks = start, []
    while d <= end and len(blocks) < 5:
        blk = grab(f"nhl_schedule_{d}", lambda d=d: nhl_get(f"/schedule/{d}"))
        blocks.append(d.isoformat())
        nxt_start = (blk or {}).get("nextStartDate")
        d = dt.date.fromisoformat(nxt_start) if nxt_start else d + dt.timedelta(days=7)
    manifest["nhl_blocks"] = blocks
    grab("nhl_standings", lambda: nhl_get("/standings/now"))

    # Remove NHL blocks from earlier runs that are no longer in range
    for fn in os.listdir(OUT_DIR):
        if fn.startswith("nhl_schedule_") and fn[len("nhl_schedule_"):-5] not in blocks:
            os.remove(os.path.join(OUT_DIR, fn))

    save("manifest", manifest)
    n_err = len(manifest["errors"])
    print(f"\n💾 {len(manifest['ok'])} saved, {n_err} failed → {OUT_DIR}")
    if n_err:
        for k, v in manifest["errors"].items():
            print(f"::warning title=AGM fetch: {k}::{v[:200]}")


if __name__ == "__main__":
    main()
