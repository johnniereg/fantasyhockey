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
  skater_games/<YYYY-MM>.json  one row per skater per final NHL game (NHL box scores): TOI,
                               shifts, SOG, G, A, PPG, PIM, +/-. Compact rows (see "cols").
                               Feeds agm_usage.py and agm_counterfactual.py.
  fa_snapshots/<date>.json     every free agent and waiver player seen in any fetch that day
                               (Yahoo eligibility, status, ownership, first/last time seen).
                               Who was actually available on a given day.
"""

import datetime as dt
import json
import os

DAILY_BACKFILL_PER_RUN = 3        # past dates to backfill per fetch (10 Yahoo calls each)
BOX_PER_RUN = 90                  # NHL box scores per fetch (first run backfills the season)
SKATER_BOX_PER_RUN = 120          # extra box scores per fetch for the skater log backfill
SKATER_COLS = ["game_id", "date", "team", "opp", "player_id", "name", "pos", "toi_min", "shifts",
               "sog", "g", "a", "ppg", "pim", "pm"]
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
        ctx.setdefault("_boxes", {})[gid] = box       # reused by skater_games, no second call
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


def _toi_min(v):
    try:
        m, s = str(v or "0:00").split(":")
        return round(int(m) + int(s) / 60, 2)
    except Exception:
        return 0.0


def _skater_rows(box):
    rows = []
    gid, gdate = box.get("id"), box.get("gameDate")
    pbg = box.get("playerByGameStats") or {}
    for side, other in (("awayTeam", "homeTeam"), ("homeTeam", "awayTeam")):
        team = (box.get(side) or {}).get("abbrev")
        opp = (box.get(other) or {}).get("abbrev")
        for grp in ("forwards", "defense"):
            for p in (pbg.get(side) or {}).get(grp) or []:
                name = p.get("name")
                name = name.get("default") if isinstance(name, dict) else name
                rows.append([gid, gdate, team, opp, p.get("playerId"), name, p.get("position"),
                             _toi_min(p.get("toi")), p.get("shifts"), p.get("sog"), p.get("goals"),
                             p.get("assists"), p.get("powerPlayGoals"), p.get("pim"), p.get("plusMinus")])
    return rows


def skater_games(ctx):
    """Per-game skater usage from NHL box scores. Game list comes from goalie_starts.json (every
    final game it has seen), so no extra schedule calls; boxes fetched by goalie_starts this run
    are reused. Backfills SKATER_BOX_PER_RUN older games per fetch."""
    nhl_get, out_dir = ctx["nhl_get"], ctx["out_dir"]
    sdir = os.path.join(out_dir, "skater_games")
    os.makedirs(sdir, exist_ok=True)
    gl = os.path.join(out_dir, "goalie_starts.json")
    if not os.path.exists(gl):
        raise RuntimeError("goalie_starts.json missing (it supplies the game list)")
    games = {}
    for r in json.load(open(gl)).get("rows", []):
        if r.get("game_id") and r.get("date"):
            games[r["game_id"]] = r["date"]
    done = set()
    months = {}
    for fn in sorted(os.listdir(sdir)):
        if fn.endswith(".json"):
            blk = json.load(open(os.path.join(sdir, fn)))
            months[fn[:-5]] = blk
            done.update(blk.get("games_done", []))
    cache = ctx.get("_boxes", {})
    todo = sorted((g for g in games if g not in done), key=lambda g: (g not in cache, games[g], g))
    fetched, added = 0, 0
    for gid in todo:
        if gid in cache:
            box = cache[gid]
        elif fetched < SKATER_BOX_PER_RUN:
            box = nhl_get(f"/gamecenter/{gid}/boxscore")
            fetched += 1
        else:
            continue
        rows = _skater_rows(box)
        if not rows:
            continue
        m = (games[gid] or "")[:7]
        blk = months.setdefault(m, {"cols": SKATER_COLS, "games_done": [], "rows": []})
        blk["rows"].extend(rows)
        blk["games_done"].append(gid)
        added += 1
    for m, blk in months.items():
        blk["rows"].sort(key=lambda r: (r[1] or "", r[0] or 0, r[2] or "", r[4] or 0))
        blk["games_done"] = sorted(set(blk["games_done"]))
        blk["updated_at_utc"] = ctx["manifest"]["fetched_at_utc"]
        with open(os.path.join(sdir, f"{m}.json"), "w") as f:
            json.dump(blk, f, separators=(",", ":"))
    pending = len([g for g in todo if g not in cache]) - fetched
    return {"games_added": added, "games_pending": max(0, pending)}


def fa_snapshot(ctx):
    """Union of every FA/waiver player seen today, kept per date (ET). Reads the fa_* and
    waivers_* files this fetch just wrote; never calls Yahoo itself."""
    players_in, out_dir = ctx["players_in"], ctx["out_dir"]
    sdir = os.path.join(out_dir, "fa_snapshots")
    os.makedirs(sdir, exist_ok=True)
    day = ctx["today"].isoformat()
    p = os.path.join(sdir, f"{day}.json")
    snap = json.load(open(p)) if os.path.exists(p) else {"date": day, "players": {}}
    now = ctx["manifest"]["fetched_at_utc"]
    seen = 0
    for fn in sorted(os.listdir(out_dir)):
        if not (fn.startswith("fa_") or fn.startswith("waivers_")) or not fn.endswith(".json"):
            continue
        src = "waivers" if fn.startswith("waivers_") else "fa"
        for pl in players_in(json.load(open(os.path.join(out_dir, fn)))):
            if not pl.get("key"):
                continue
            row = snap["players"].setdefault(pl["key"], {"first_seen_utc": now})
            row.update({"name": pl["name"], "team": pl["team"], "pos": pl["pos"], "elig": pl["elig"],
                        "status": pl["status"], "last_seen_utc": now})
            if pl.get("owned") is not None:
                row["owned"] = pl["owned"]
            if src == "waivers":
                row["waivers"] = True
            seen += 1
    snap["updated_at_utc"] = now
    with open(p, "w") as f:
        json.dump(snap, f, indent=0, sort_keys=True)
    return {"date": day, "players": len(snap["players"]), "rows_read": seen}


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
            ("skater_games", skater_games, None), ("fa_snapshot", fa_snapshot, None),
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
