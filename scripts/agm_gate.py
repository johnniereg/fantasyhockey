#!/usr/bin/env python3
"""
AGM data gate — run FIRST in every brief, before any analysis.
================================================================
Decides whether data/inseason is clean enough for this brief, and can wait for a
fetch that is still running.

  python3 scripts/agm_gate.py morning [--wait 30]
  python3 scripts/agm_gate.py goalie  [--wait 20]
  python3 scripts/agm_gate.py sunday  [--wait 30]

--wait N : if the gate fails, `git pull` every 3 min for up to N minutes and re-check.

Exit 0 = PASS (or WARN: usable, print the warnings in Data).
Exit 2 = FAIL: the data predates what this brief needs. The brief must NOT use the Yahoo
scoreboard or lineups as current; it writes the one-line FAIL reason in Now and Data.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/Toronto")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "inseason", "manifest.json")
CORE = ("league_settings", "my_matchup", "scoreboard_current")

# Earliest ET time-of-day a fetch must have started at, on the brief's own date.
# morning: after every game from last night is final (latest finish ~01:30 ET).
# goalie:  an afternoon fetch, so lineup/moves reflect today.
# sunday:  after the Sunday 03:00 ET add reset, so adds-used and the next matchup are current.
MIN_FETCH_TIME = {"morning": dt.time(3, 0), "goalie": dt.time(14, 0), "sunday": dt.time(3, 0)}


def check(mode):
    fails, warns = [], []
    try:
        m = json.load(open(MANIFEST))
    except Exception as e:
        return [f"manifest unreadable: {e}"], [], {}
    now = dt.datetime.now(ET)
    today = now.date()
    try:
        fetched = dt.datetime.fromisoformat(m["fetched_at_utc"]).astimezone(ET)
    except Exception:
        return ["manifest has no fetched_at_utc"], [], m

    age_h = (now - fetched).total_seconds() / 3600
    need = dt.datetime.combine(today, MIN_FETCH_TIME[mode], ET)
    if fetched < need:
        fails.append(f"latest fetch {fetched:%m-%d %H:%M} ET is before {need:%m-%d %H:%M} ET "
                     f"({age_h:.1f}h old) — today's {mode} fetch hasn't landed")
    if m.get("date_et") != today.isoformat():
        fails.append(f"fetch is for {m.get('date_et')}, not today {today}: lineups/scoreboard are a day behind")

    g = m.get("games")
    if g is None:
        warns.append("fetch has no NHL game-state summary (old fetch script) — can't confirm games were final")
    else:
        y = g.get("yesterday") or {}
        if mode in ("morning", "sunday") and y.get("games") and not y.get("all_final"):
            fails.append(f"only {y.get('final')}/{y.get('games')} of {y.get('date')}'s NHL games were final "
                         "at fetch time — Yahoo scoreboard is missing last night")
        if g.get("live_now"):
            warns.append(f"{g['live_now']} NHL games were live during the fetch — scoreboard is mid-game")

    bad_core = [k for k in CORE if k in m.get("errors", {})]
    if bad_core:
        fails.append(f"core endpoints failed: {', '.join(bad_core)}")
    other = [k for k in m.get("errors", {}) if k not in CORE]
    if other:
        warns.append(f"failed endpoints: {', '.join(other)}")
    if today.isoformat() not in (m.get("roster_dates") or []):
        fails.append(f"no saved lineup for {today} (my_roster_{today}.json) — no lineup calls")
    if mode == "sunday" and not m.get("next_opp_team_key"):
        warns.append("next opponent unknown (next_matchup missing)")
    warns += m.get("warnings", [])
    return fails, warns, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=sorted(MIN_FETCH_TIME))
    ap.add_argument("--wait", type=int, default=0, help="minutes to keep pulling for a fresh fetch")
    a = ap.parse_args()

    deadline = time.time() + a.wait * 60
    while True:
        fails, warns, m = check(a.mode)
        if not fails or time.time() >= deadline:
            break
        print(f"… gate not met ({fails[0]}); pulling again in 3 min", flush=True)
        time.sleep(180)
        subprocess.run(["git", "-C", ROOT, "pull", "-q", "--ff-only"], check=False)

    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    print(f"GATE {status} · {a.mode} · fetched {m.get('fetched_at_utc')} UTC · trigger {m.get('trigger', '?')} "
          f"· week {m.get('current_week')}")
    for f in fails:
        print(f"  FAIL: {f}")
    for w in warns:
        print(f"  WARN: {w}")
    sys.exit(2 if fails else 0)


if __name__ == "__main__":
    main()
