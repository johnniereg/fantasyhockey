"""
Extra in-season data for AGM, called from fetch_inseason.main() after the core fetch.
=====================================================================================
Everything here is pipeline data (no analysis, no briefs). Each block is isolated:
a failure is recorded in the manifest and never stops the rest.

  daily/<date>.json            every team's roster for that date, with the slot each player
                               was in and his fantasy stats for that day (Yahoo type=date).
                               Exact fantasy numbers for recaps and the decision ledger.
  goalie_starts.json           one row per goalie per final NHL game (NHL box scores):
                               starter flag, TOI, SA/SV/GA, decision. Feeds agm_goalies.py.
  waivers_<page>.json          players currently on waivers (Yahoo status=W), so FA lists
                               can tell a waiver claim from a free add.
  archive/scoreboard_week_NN   every completed week's league scoreboard (re-saved while it's
                               the previous week, so stat corrections land). Feeds agm_ranks.py.
"""

import datetime as dt
import json
import os

DAILY_BACKFILL_PER_RUN = 3        # past dates to backfill per fetch (10 Yahoo calls each)
BOX_PER_RUN = 90                  # NHL box scores per fetch (first run backfills the season)
FINAL_STATES = {"OFF", "FINAL"}


def _team_keys(all_rosters, walk, flat):
    out = {}
    for t in walk(all_rosters or {}, "team"):
        if isinstance(t, list) and t:
            meta = flat(t[0])
            if meta.get("team_key"):
                out[meta["team_key"]] = meta.get("name")
    return out


def daily_stats(ctx):
    """Per-day fantasy stats for every team. ctx: dict of helpers and state from fetch_inseason."""
    yahoo_get, token, lk = ctx["yahoo_get"], ctx["token"], ctx["lk"]
    players_in, walk, flat = ctx["players_in"], ctx["walk"], ctx["flat"]
    out_dir = os.path.join(ctx["out_dir"], "daily")
    os.makedirs(out_dir, exist_ok=True)
    teams = _team_keys(ctx["all_rosters"], walk, flat)
    if not teams:
        raise RuntimeError("no team keys in all_rosters")
    names = ctx["stat_names"]
    today, season_start = ctx["today"], ctx["season_start"]
    yday = today - dt.timedelta(days=1)
    y_final = bool(((ctx["manifest"].get("games") or {}).get("yesterday") or {}).get("all_final"))

    def done(d):
        p = os.path.join(out_dir, f"{d}.json")
        if not os.path.exists(p):
            return False
        return bool(json.load(open(p)).get("complete"))

    todo = []
    if yday >= season_start and not done(yday):
        todo.append((yday, y_final))
    back = []
    d = season_start
    while d < yday:
        if not done(d):
            back.append(d)
        d += dt.timedelta(days=1)
    todo += [(d, True) for d in back[-DAILY_BACKFILL_PER_RUN:]]   # newest gaps first

    written = []
    for d, complete in todo:
        rec = {"date": d.isoformat(), "complete": complete,
               "fetched_at_utc": ctx["manifest"]["fetched_at_utc"], "teams": {}}
        for tkey, tname in teams.items():
            raw = yahoo_get(f"/team/{tkey}/roster;date={d}/players/stats;type=date;date={d}", token)
            players = []
            for p in players_in(raw):
                st = {names.get(k, k): v for k, v in p["stats"].items() if v not in (None, "", "-")}
                players.append({"key": p["key"], "name": p["name"], "pos": p["pos"],
                                "team": p["team"], "slot": p["slot"], "status": p["status"], "stats": st})
            rec["teams"][tkey] = {"name": tname, "players": players}
        with open(os.path.join(out_dir, f"{d}.json"), "w") as f:
            json.dump(rec, f, indent=1, sort_keys=True)
        written.append(d.isoformat())
    remaining = max(0, len(back) - DAILY_BACKFILL_PER_RUN)
    return {"written": written, "backfill_remaining": remaining}


def _goalie_rows(box):
    rows = []
    gid, gdate = box.get("id"), box.get("gameDate")
    sides = {"awayTeam": "homeTeam", "homeTeam": "awayTeam"}
    pbg = box.get("playerByGameStats") or {}
    for side, other in sides.items():
        team = (box.get(side) or {}).get("abbrev")
        opp = (box.get(other) or {}).get("abbrev")
        gs = ((pbg.get(side) or {}).get("goalies")) or []
        def toi_min(g):
            try:
                m, s = str(g.get("toi", "0:00")).split(":")
                return int(m) + int(s) / 60
            except Exception:
                return 0.0
        has_flag = any("starter" in g for g in gs)
        longest = max(gs, key=toi_min) if gs else None
        for g in gs:
            sa, sv = g.get("shotsAgainst"), g.get("saves")
            if (sa is None or sv is None) and g.get("saveShotsAgainst"):
                try:
                    sv, sa = (int(x) for x in str(g["saveShotsAgainst"]).split("/"))
                except Exception:
                    pass
            name = (g.get("name") or {}).get("default") if isinstance(g.get("name"), dict) else g.get("name")
            starter = g.get("starter") if has_flag else (g is longest)
            rows.append({
                "game_id": gid, "date": gdate, "team": team, "opp": opp, "home": side == "homeTeam",
                "player_id": g.get("playerId"), "goalie": name,
                "last": (name or "").split(" ")[-1], "starter": bool(starter),
                "toi": g.get("toi"), "toi_min": round(toi_min(g), 2),
                "sa": sa, "sv": sv, "ga": g.get("goalsAgainst"), "decision": g.get("decision"),
                "team_score": (box.get(side) or {}).get("score"), "opp_score": (box.get(other) or {}).get("score"),
            })
    return rows


def goalie_starts(ctx):
    nhl_get, out_dir = ctx["nhl_get"], ctx["out_dir"]
    p = os.path.join(out_dir, "goalie_starts.json")
    log = json.load(open(p)) if os.path.exists(p) else {"games_done": [], "rows": []}
    done = set(log["games_done"])
    yday = ctx["today"] - dt.timedelta(days=1)
    d, todo = ctx["season_start"], []
    while d <= yday:
        blk = nhl_get(f"/schedule/{d}")
        for day in blk.get("gameWeek", []):
            if day["date"] > yday.isoformat():
                continue
            for g in day.get("games", []):
                if g.get("gameType", 2) in (2, 3) and g.get("gameState") in FINAL_STATES and g["id"] not in done:
                    todo.append(g["id"])
        nxt = blk.get("nextStartDate")
        d = dt.date.fromisoformat(nxt) if nxt else d + dt.timedelta(days=7)
    added, sample = 0, None
    for gid in todo[:BOX_PER_RUN]:
        box = nhl_get(f"/gamecenter/{gid}/boxscore")
        rows = _goalie_rows(box)
        if rows:
            log["rows"].extend(rows)
            log["games_done"].append(gid)
            added += 1
            sample = box
    log["rows"].sort(key=lambda r: (r["date"] or "", r["game_id"] or 0, r["team"] or ""))
    log["updated_at_utc"] = ctx["manifest"]["fetched_at_utc"]
    with open(p, "w") as f:
        json.dump(log, f, indent=1, sort_keys=True)
    if sample:   # one raw box score kept for debugging the parser
        with open(os.path.join(out_dir, "nhl_boxscore_sample.json"), "w") as f:
            json.dump(sample, f, indent=1, sort_keys=True)
    return {"games_added": added, "games_pending": max(0, len(todo) - BOX_PER_RUN), "rows": len(log["rows"])}


def archive_scoreboard(ctx):
    prev, week = ctx.get("scoreboard_previous"), ctx.get("cur_week")
    if not prev or not week or week < 2:
        return {"archived": None}
    adir = os.path.join(ctx["out_dir"], "archive")
    os.makedirs(adir, exist_ok=True)
    name = f"scoreboard_week_{week - 1:02d}.json"
    with open(os.path.join(adir, name), "w") as f:
        json.dump(prev, f, indent=1, sort_keys=True)
    return {"archived": name}


def run_all(ctx, grab):
    """Extras never fail the fetch: problems go to manifest warnings + extras_errors, so the
    core data (and the brief gate) stay green while a new parser is being shaken out."""
    m = ctx["manifest"]
    yahoo_get, token, lk = ctx["yahoo_get"], ctx["token"], ctx["lk"]
    m.setdefault("extras", {})
    m.setdefault("extras_errors", {})
    jobs = [(f"waivers_{page}", None, page) for page in range(2)] + \
           [("daily_stats", daily_stats, None), ("goalie_starts", goalie_starts, None),
            ("scoreboard_archive", archive_scoreboard, None)]
    for name, fn, page in jobs:
        try:
            if fn is None:
                payload = yahoo_get(f"/league/{lk}/players;status=W;count=25;start={page * 25}", token)
                with open(os.path.join(ctx["out_dir"], f"{name}.json"), "w") as f:
                    json.dump(payload, f, indent=1, sort_keys=True)
                result = "saved"
            else:
                result = fn(ctx)
            m["extras"][name] = result
            m["ok"].append(name)
            print(f"   ✅ {name}: {result}")
        except Exception as e:
            m["extras_errors"][name] = str(e)[:600]
            m["warnings"].append(f"extra '{name}' failed: {str(e)[:160]}")
            print(f"   ⚠️ {name}: {str(e)[:300]}")
