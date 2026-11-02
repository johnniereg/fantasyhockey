"""
AGM moves — what to add and drop, ranked by what it does to this week's matchup and the season
==============================================================================================
    python3 scripts/agm_moves.py                 # recommendations (markdown)
    python3 scripts/agm_moves.py --json          # also write data/agm/moves_latest.json
    python3 scripts/agm_moves.py --log           # also append recommendations to data/agm/moves_log.json
    python3 scripts/agm_moves.py grade           # grade logged recommendations 7+ days old

1. Projections: agm_project (tested: ~27% lower error than season-to-date stats).
2. Category weights from the matchup: project both teams' week totals (scoreboard so far + each
   remaining night's best lineup), turn each category's margin into a win probability, and weight
   the category by how much one more unit moves that probability. Safe and lost categories get
   little weight; close ones get a lot. Recomputed every run, so nothing is locked in.
3. Player value per game = sum over skater categories of weight x projected rate / spread.
4. Every rostered skater is a drop candidate. No draft-slot tiers. Keepers carry keeper value only
   if they rank in our top 8 by projected value per game (likely kept next year).
5. Each add/drop pair is scored two ways: this week (value of the lineup we'd actually field on
   the remaining nights, from tomorrow since adds take a day) and rest of season (value per game x
   ~games left). Recommended only above thresholds; adds limited to what's left this week.
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
import sys
from collections import defaultdict
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agm_project as P  # noqa: E402
from agm_plan import (IN, KEEPERS, OUT_STATUSES, best_lineup, flat, load, nhl_games_by_date,  # noqa: E402
                      players_in, roster_slots, stat_names, walk)

ET = ZoneInfo("America/Toronto")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "data", "agm")
SK = ["G", "A", "PPP", "PIM", "PM", "GWG"]
YAHOO = {"G": "G", "A": "A", "PPP": "PPP", "PIM": "PIM", "PM": "+/-", "GWG": "GWG"}
# per-game variance multipliers for the matchup model (PIM arrives in 2s and 5s; +/- swings both ways)
VAR = {"G": 1.0, "A": 1.0, "PPP": 1.0, "PIM": 4.0, "PM": None, "GWG": 1.0}
# Value unit: percentage points of category-win probability, summed over the six skater categories.
# A week gain of +10 = +0.1 expected categories won this week.
WEEK_MIN = 3.0      # recommend if this week's gain is at least this
ROS_MIN = 3.0       # ... or the average gain per future week is at least this, with no loss this week
KEEPER_ROS_MIN = 6.0  # dropping a keeper (not in our top 8) needs twice the season gain; flagged as your call
GAMES_PER_WEEK = 3.4
TEAM_STARTS = 50    # typical skater starts per team-week, for season-level weights


def norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def name_index(proj):
    idx = defaultdict(list)
    for p in proj.values():
        idx[norm(p["name"])].append(p)
    return idx


def find(idx, name, team=None):
    c = idx.get(norm(name), [])
    if len(c) > 1 and team:
        c = [p for p in c if p["team"] == team] or c
    return c[0] if c else None


def season_weights(proj):
    """Per-unit value of each category in an even matchup: density of a tie / sigma of team totals."""
    reg = [p for p in proj.values() if p["gp"] >= 5 and p["toi"] >= 14]
    w = {}
    for c in SK:
        r = sum(max(p[c], 0) for p in reg) / len(reg)
        var = 2 * TEAM_STARTS * (1.0 if VAR[c] is None else VAR[c] * r)
        w[c] = 100 * 0.3989 / math.sqrt(var)
    return w


def scoreboard(settings):
    mu = load("my_matchup")
    m = load("manifest") or {}
    names = stat_names(settings)
    if not mu:
        return {}, {}
    mblk = next(walk(mu, "matchup"), {})
    teams = [t for t in walk(mblk, "team") if isinstance(t, list) and t]
    cols = {}
    for t in teams[:2]:
        meta = flat(t[0])
        st = {names.get(str(s.get("stat_id"))): s.get("value") for s in walk(t, "stat") if isinstance(s, dict)}
        cols[meta.get("team_key")] = st
    me = m.get("team_key")
    opp = next((k for k in cols if k != me), None)

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    us = {c: num(cols.get(me, {}).get(YAHOO[c])) for c in SK}
    them = {c: num(cols.get(opp, {}).get(YAHOO[c])) for c in SK}
    return us, them


def week_dates(today):
    m = load("manifest") or {}
    wk = (m.get("week_dates") or {}).get(str(m.get("current_week")))
    w1 = dt.date.fromisoformat(wk[1]) if wk else today + dt.timedelta(days=6)
    return [(today + dt.timedelta(days=i)).isoformat() for i in range((w1 - today).days + 1)]


def roster_on(prefix, d):
    r = players_in(load(f"{prefix}_roster_{d}"))
    return r or players_in(load(f"{prefix}_roster_today")) if prefix == "my" else r


def attach(roster, idx):
    out = []
    for p in roster:
        if "G" in p["elig"]:
            continue
        pr = find(idx, p["name"], p["team"])
        out.append({**p, "proj": pr})
    return out


def lineup_value(roster, dates, games, slots, val, totals=None):
    """Sum of value of skaters we'd start on each date (priority = value). Optionally add rates."""
    v = 0.0
    sk_slots = {k: n for k, n in slots.items() if k != "G"}
    for d in dates:
        playing = [p for p in roster if p["team"] in games.get(d, set()) and p.get("status") not in OUT_STATUSES
                   and p.get("slot") not in ("IR", "IR+") and p["proj"]]
        playing.sort(key=lambda p: -val(p["proj"]))
        placed, _ = best_lineup(playing, sk_slots)
        for p in playing:
            if p["key"] in placed:
                v += val(p["proj"])
                if totals is not None:
                    for c in SK:
                        totals[c] += p["proj"][c]
    return v


def weights(my_r, opp_r, dates, games, slots, us, them):
    pu, pt = dict(us), dict(them)
    nu, nt = defaultdict(float), defaultdict(float)
    one = lambda p: 1.0  # noqa: E731
    lineup_value(my_r, dates, games, slots, one, nu)
    lineup_value(opp_r, dates, games, slots, one, nt)
    games_u = lineup_value(my_r, dates, games, slots, one)
    games_t = lineup_value(opp_r, dates, games, slots, one)
    w, info = {}, {}
    for c in SK:
        mu_u, mu_t = pu.get(c, 0) + nu[c], pt.get(c, 0) + nt[c]
        if VAR[c] is None:
            var = (games_u + games_t) * 1.0
        else:
            var = VAR[c] * (nu[c] + nt[c])
        sig = math.sqrt(max(var, 0.5))
        z = (mu_u - mu_t) / sig
        pwin = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        dens = math.exp(-z * z / 2) / (sig * math.sqrt(2 * math.pi))
        w[c] = 100 * dens   # percentage points of win probability per unit
        info[c] = {"us": round(mu_u, 1), "them": round(mu_t, 1), "p_win": round(pwin, 2)}
    return w, info


def fa_pool(idx):
    m = load("manifest") or {}
    pool = {}
    for f in sorted(glob.glob(os.path.join(IN, "fa_*_*.json"))) + sorted(glob.glob(os.path.join(IN, "waivers_*.json"))):
        if "lastweek" in f or "snapshots" in f:
            continue
        try:
            for p in players_in(json.load(open(f))):
                if "G" in p["elig"]:
                    continue
                p = {**p, "waiver": "waivers_" in os.path.basename(f), "slot": "BN", "status": p.get("status", "")}
                pool.setdefault(p["key"], p)
        except Exception:
            pass
    out = []
    for p in pool.values():
        pr = find(idx, p["name"], p["team"])
        if pr:
            out.append({**p, "proj": pr})
    return out, m.get("fetched_at_utc")


def recommend(adds_left, verbose=True):
    settings = load("league_settings")
    slots = roster_slots(settings)
    games = nhl_games_by_date()
    now = dt.datetime.now(ET)
    today = now.date()
    dates_all = week_dates(today)
    dates_add = dates_all[1:]  # an add made today plays from tomorrow
    proj = P.project()
    idx = name_index(proj)
    sw = season_weights(proj)
    my_r = attach(roster_on("my", today.isoformat()), idx)
    opp_r = attach(roster_on("opp", today.isoformat()) or [], idx)
    us, them = scoreboard(settings)
    w, info = weights(my_r, opp_r, dates_all, games, slots, us, them)

    def val(pr):
        return sum(w[c] * pr[c] for c in SK)

    def val_flat(pr):
        return sum(sw[c] * pr[c] for c in SK)

    # keeper value: keepers in our top 8 by flat value per game are protected unless the gain is large
    ranked = sorted([p for p in my_r if p["proj"]], key=lambda p: -val_flat(p["proj"]))
    top8 = {p["name"] for p in ranked[:8]}
    pool, fetched = fa_pool(idx)
    pool = sorted(pool, key=lambda p: -val(p["proj"]))[:60]
    base = lineup_value(my_r, dates_add, games, slots, val)
    recs, roster = [], list(my_r)
    used = set()
    for _ in range(max(0, adds_left)):
        best = None
        cur_base = lineup_value(roster, dates_add, games, slots, val)
        for a in pool:
            if a["key"] in used:
                continue
            for d in roster:
                if d.get("slot") in ("IR", "IR+") or not d["proj"]:
                    continue
                new = [x for x in roster if x["key"] != d["key"]] + [a]
                dw = lineup_value(new, dates_add, games, slots, val) - cur_base
                dros = (val_flat(a["proj"]) - val_flat(d["proj"])) * GAMES_PER_WEEK  # per future week
                keeper = d["name"] in KEEPERS
                if keeper and d["name"] in top8:
                    continue  # likely kept next year; not a candidate
                ok = (dw >= WEEK_MIN and dros >= -0.5) or (dros >= ROS_MIN and dw >= 0)
                if keeper and dros < KEEPER_ROS_MIN:
                    ok = False
                if not ok:
                    continue
                score = dw + 2 * dros
                if not best or score > best[0]:
                    best = (score, a, d, dw, dros, keeper)
        if not best:
            break
        _, a, d, dw, dros, keeper = best
        recs.append({"add": a["name"], "add_team": a["team"], "add_pos": ",".join(a["elig"]),
                     "waiver": a["waiver"], "own_pct": a.get("owned"), "drop": d["name"],
                     "drop_team": d["team"], "drop_keeper": keeper, "week_gain": round(dw, 1),
                     "ros_gain_per_week": round(dros, 1),
                     "add_proj": {c: round(a["proj"][c], 2) for c in SK},
                     "drop_proj": {c: round(d["proj"][c], 2) for c in SK},
                     "add_games": sum(1 for x in dates_add if a["team"] in games.get(x, set())),
                     "drop_games": sum(1 for x in dates_add if d["team"] in games.get(x, set()))})
        used.add(a["key"])
        roster = [x for x in roster if x["key"] != d["key"]] + [a]
    drops = sorted([p for p in my_r if p["proj"] and p.get("slot") not in ("IR", "IR+")],
                   key=lambda p: val_flat(p["proj"]))
    return {"generated_at_et": now.isoformat(timespec="minutes"), "data_fetched_utc": fetched,
            "dates": dates_all, "weights": {c: round(w[c], 2) for c in SK}, "season_weights": {c: round(sw[c], 2) for c in SK}, "matchup": info,
            "base_week_value": round(base, 2), "adds_left": adds_left, "recommendations": recs,
            "drop_order": [{"name": p["name"], "team": p["team"], "value_pg": round(val_flat(p["proj"]), 2),
                            "keeper": p["name"] in KEEPERS, "keeper_top8": p["name"] in top8}
                           for p in drops]}


def adds_left():
    adds = next((v for v in walk(load("my_team"), "roster_adds")), None)
    try:
        return 4 - int(adds.get("value", 0))
    except Exception:
        return 4


def goalies():
    """Goalie view. Tested: individual SV% doesn't carry over (r -0.12); team shots/goals against do.
    So rank by expected starts and the team in front of him, not by his save percentage."""
    gp, teams = P.goalie_projection()
    games = nhl_games_by_date()
    today = dt.datetime.now(ET).date()
    dates = week_dates(today)[1:]
    mine = {p["name"] for p in players_in(load("my_roster_today")) if "G" in p["elig"]}
    fa = set()
    for f in glob.glob(os.path.join(IN, "fa_G_*.json")) + glob.glob(os.path.join(IN, "waivers_*.json")):
        if "lastweek" in f:
            continue
        try:
            fa |= {p["name"] for p in players_in(json.load(open(f))) if "G" in p["elig"]}
        except Exception:
            pass
    # Yahoo status for every goalie we can see; injured goalies' starts go to their teammates
    status = {}
    for src in [load("my_roster_today"), load("all_rosters")] + [json.load(open(f)) for f in
                glob.glob(os.path.join(IN, "fa_G_*.json")) if "lastweek" not in f]:
        for p in players_in(src) if src else []:
            if "G" in p["elig"]:
                status[p["name"]] = p.get("status") or ""
    out_g = {n for n, s in status.items() if s in OUT_STATUSES}
    # start share = share of the team's last 6 games (recent role beats season totals after returns/injuries)
    gs_rows = [r for r in (load("goalie_starts") or {}).get("rows", []) if r.get("starter")]
    by_team = defaultdict(list)
    for r in sorted(gs_rows, key=lambda r: r["date"]):
        by_team[r["team"]].append(r)
    recent = defaultdict(int)
    for t, rs in by_team.items():
        for r in rs[-6:]:
            recent[(t, r["last"].lower())] += 1
    team_gs = defaultdict(int)
    for g in gp.values():
        if g["name"] not in out_g:
            team_gs[g["team"]] += recent[(g["team"], g["name"].split()[-1].lower())]
    rows = []
    for g in gp.values():
        if g["name"] not in mine and g["name"] not in fa:
            continue
        t = teams.get(g["team"], {})
        mine_recent = recent[(g["team"], g["name"].split()[-1].lower())]
        share = 0 if g["name"] in out_g else (mine_recent / team_gs[g["team"]] if team_gs[g["team"]] else 0)
        tg = sum(1 for d in dates if g["team"] in games.get(d, set()))
        rows.append({**g, "share": round(share, 2), "team_games": tg, "exp_starts": round(share * tg, 1),
                     "team_win_pct": round(t.get("win_pct", 0), 3), "team_ga_pg": round(t.get("ga_pg", 0), 2),
                     "team_sa_pg": round(t.get("sa_pg", 0), 1), "ours": g["name"] in mine,
                     "status": status.get(g["name"], "")})
    # quality = team goals against (lower better) and win%, for goalies who actually start
    return sorted(rows, key=lambda r: (r["share"] < 0.4, r["team_ga_pg"] - 2 * r["team_win_pct"])), None


def grade():
    p = os.path.join(OUTDIR, "moves_log.json")
    log = json.load(open(p)) if os.path.exists(p) else []
    rows = P._box_rows()
    by = defaultdict(list)
    for r in rows:
        by[(norm(r["name"].split(". ")[-1]), r["team"])].append(r)
    last = max(r["date"] for r in rows)
    print("| Logged | Add | Drop | Add next 7d (G-A-PIM-+/-) | Drop next 7d | Verdict |\n|---|---|---|---|---|---|")
    for e in log:
        d0 = e["generated_at_et"][:10]
        d1 = (dt.date.fromisoformat(d0) + dt.timedelta(days=7)).isoformat()
        if d1 > last:
            continue
        for rc in e["recommendations"]:
            def line(name, team):
                rs = [r for r in by.get((norm(name.split()[-1]), team), []) if d0 < r["date"] <= d1]
                return (len(rs), sum(r["g"] for r in rs), sum(r["a"] for r in rs),
                        sum(r["pim"] for r in rs), sum(r["pm"] for r in rs))
            a, d = line(rc["add"], rc["add_team"]), line(rc["drop"], rc["drop_team"])
            pa, pd = a[1] + a[2], d[1] + d[2]
            print(f"| {d0} | {rc['add']} | {rc['drop']} | {a[0]} GP {a[1]}-{a[2]}-{a[3]}-{a[4]:+d} | "
                  f"{d[0]} GP {d[1]}-{d[2]}-{d[3]}-{d[4]:+d} | {'add better' if pa > pd else 'drop better' if pd > pa else 'even'} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="recommend", choices=["recommend", "grade"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()
    if a.cmd == "grade":
        return grade()
    res = recommend(adds_left())
    gl, lg = goalies()
    res["goalies"] = [{k: r[k] for k in ("name", "team", "ours", "status", "sv_season", "gs", "share", "team_games",
                                         "exp_starts", "team_win_pct", "team_ga_pg", "team_sa_pg")} for r in gl]
    print(f"# AGM moves — {res['generated_at_et']} ET (data {res['data_fetched_utc']} UTC)\n")
    print("## Matchup categories (projected end-of-week totals)\n")
    print("_Weight = percentage points of win probability per unit (one goal, one PIM...) this week; "
          "season weight = same for an even matchup._\n")
    print("| Cat | Us | Them | P(win) | Weight | Season weight |\n|---|---|---|---|---|---|")
    for c in SK:
        i = res["matchup"][c]
        print(f"| {YAHOO[c]} | {i['us']} | {i['them']} | {i['p_win']:.0%} | {res['weights'][c]} | {res['season_weights'][c]} |")
    print(f"\n## Recommended moves ({res['adds_left']} adds left this week)\n")
    print("_Gain = percentage points of category wins (+10 = +0.1 categories). This week counts nights from "
          "tomorrow; later weeks = average per future week._\n")
    if not res["recommendations"]:
        print("None clear the bar.")
    for r in res["recommendations"]:
        print(f"- **Add {r['add']}** ({r['add_team']} {r['add_pos']}{', WAIVERS' if r['waiver'] else ''}) · "
              f"**drop {r['drop']}** ({r['drop_team']}{', keeper' if r['drop_keeper'] else ''}) — "
              f"week +{r['week_gain']} ({r['add_games']} vs {r['drop_games']} games left), later weeks {r['ros_gain_per_week']:+}/wk")
        print(f"  - add proj/g: {r['add_proj']}\n  - drop proj/g: {r['drop_proj']}")
    print("\n## Drop order (lowest projected value first, all skaters)\n")
    for d in res["drop_order"][:8]:
        print(f"- {d['name']} ({d['team']}) {d['value_pg']}{' · keeper' if d['keeper'] else ''}"
              f"{' (top-8, protected)' if d['keeper_top8'] and d['keeper'] else ''}")
    print("\n## Goalies — starters first, ranked by team goals against and win % (blend of last season and this)\n")
    print("_Individual save % doesn't predict next season (tested r = -0.12); team defence does. Shown for reference._\n")
    print("| Goalie | Team | Ours | Share of last 6 (healthy) | Starts this season | Team games left | Exp starts | "
          "Team W% | Team GA/GP | Team SA/GP | Season SV% |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in [g for g in res["goalies"] if g["ours"]] + [g for g in res["goalies"] if not g["ours"]][:10]:
        print(f"| {r['name']}{' (' + r['status'] + ')' if r['status'] else ''} | {r['team']} | {'✔' if r['ours'] else ''} | {r['share']} | {r['gs']} | {r['team_games']} | "
              f"{r['exp_starts']} | {r['team_win_pct']:.3f} | {r['team_ga_pg']} | {r['team_sa_pg']} | {(r['sv_season'] or 0):.3f} |")
    if a.json or a.log:
        os.makedirs(OUTDIR, exist_ok=True)
        json.dump(res, open(os.path.join(OUTDIR, "moves_latest.json"), "w"), indent=1)
    if a.log and res["recommendations"]:
        p = os.path.join(OUTDIR, "moves_log.json")
        log = json.load(open(p)) if os.path.exists(p) else []
        log.append({k: res[k] for k in ("generated_at_et", "data_fetched_utc", "weights", "recommendations")})
        json.dump(log, open(p, "w"), indent=1)


if __name__ == "__main__":
    main()
