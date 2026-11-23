"""
AGM v3 backtest — does a wider free-agent pool and a goalie streaming rule pick better?
======================================================================================
    python3 scripts/agm_backtest_v3.py            # skaters + goalies, markdown

Decision days: every day with a Yahoo free-agent snapshot (data/inseason/fa_snapshots) and a full
7-day window of box scores after it. Only data before the decision day is used for the call.

Skaters: top 3 picks per day. Value of a pick = what he actually returned over the next 7 days in
G, A, PIM, +/- at even-matchup category weights (same unit as `agm_moves.py grade`). Games he
didn't play count as zero (injury after the pick is the pick's problem).
  - "Yahoo top-50 pool" = what v2 sees: the 2 pages per position Yahoo returns (sorted by
    season-to-date rank) on that day.
  - "Whole pool" = every NHL skater not on a fantasy roster that day who played his team's last game.
Goalies: top 2 available goalies per day; actual starts, wins, GA/start over the next 7 days.
"""
import datetime as dt
import glob
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agm_project as P  # noqa: E402
from agm_counterfactual import daily_rosters  # noqa: E402
from agm_usage import index, match  # noqa: E402
import agm_moves as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "data", "inseason", "fa_snapshots")
WIN = 7
TEST = ["G", "A", "PIM", "PM"]
OUT = {"INJ", "IR", "IR+", "O", "DTD", "NA", "IR-LT", "SUSP"}


def window(d0):
    d1 = (dt.date.fromisoformat(d0) + dt.timedelta(days=WIN - 1)).isoformat()
    return d0, d1


def main(seed=11):
    rows = P._CACHE.setdefault("box", P._box_rows())
    by_id, by_full, by_name = index(rows)
    for v in by_id.values():
        v.sort(key=lambda r: r["date"])
    last = max(r["date"] for r in rows)
    rosters = daily_rosters()
    snaps = sorted(glob.glob(os.path.join(SNAP, "*.json")))
    days = [os.path.basename(s)[:10] for s in snaps if window(os.path.basename(s)[:10])[1] <= last]
    team_games = defaultdict(set)
    for r in rows:
        team_games[r["team"]].add(r["date"])
    gs = (json.load(open(os.path.join(ROOT, "data", "inseason", "goalie_starts.json")))["rows"])
    rnd = random.Random(seed)

    sk = defaultdict(list)   # rule -> list of (value, name, gp)
    gl = defaultdict(list)   # rule -> list of (starts, wins, ga, name)
    for d0 in days:
        _, d1 = window(d0)
        prev = (dt.date.fromisoformat(d0) - dt.timedelta(days=1)).isoformat()
        rd = max([d for d in rosters if d <= prev] or [None]) if rosters else None
        rost = set()
        for n, t in rosters.get(rd, []):
            pid = match(n, t, by_full, by_name)
            if pid:
                rost.add(pid)
        proj = P.project(as_of=d0)
        sw = M.season_weights(proj)
        team_last = {}
        for r in rows:
            if r["date"] < d0 and r["date"] > team_last.get(r["team"], ""):
                team_last[r["team"]] = r["date"]

        def ngames(team):
            return sum(1 for x in team_games[team] if d0 <= x <= d1)

        def flat(p):
            return sum(sw[c] * p[c] for c in M.SK)

        def actual(pid):
            rs = [r for r in by_id.get(pid, []) if d0 <= r["date"] <= d1]
            return sum(sw[c] * sum((r[{"G": "g", "A": "a", "PIM": "pim", "PM": "pm"}[c]] or 0) for r in rs)
                       for c in TEST), len(rs)

        def healthy(pid):
            rs = [r for r in by_id.get(pid, []) if r["date"] < d0]
            return rs and rs[-1]["date"] == team_last.get(rs[-1]["team"])

        snap = json.load(open(os.path.join(SNAP, f"{d0}.json")))["players"].values()
        ypool = set()
        for p in snap:
            if "G" in p.get("elig", []) or (p.get("status") or "") in OUT:
                continue
            pid = match(p["name"], p["team"], by_full, by_name)
            if pid in proj:
                ypool.add(pid)
        wpool = {pid for pid, p in proj.items() if pid not in rost and p["gp"] >= 3 and healthy(pid)}
        ypool = {pid for pid in ypool if healthy(pid)}  # same availability filter for both

        def score(pid):
            p = proj[pid]
            return flat(p) * ngames(p["team"])

        rules = {
            "v2: Yahoo top-50 pool, projection x games": sorted(ypool, key=score, reverse=True)[:3],
            "v3: whole pool, projection x games": sorted(wpool, key=score, reverse=True)[:3],
            "whole pool, most ice time (last 5)": sorted(wpool, key=lambda x: proj[x]["toi_recent"], reverse=True)[:3],
            "Yahoo pool, season-to-date (Yahoo's own order)": [],
            "random healthy player, whole pool, TOI 16+": rnd.sample(
                sorted(x for x in wpool if proj[x]["toi"] >= 16), 3),
        }
        std = P.project(as_of=d0, current_only=True)
        rules["Yahoo pool, season-to-date (Yahoo's own order)"] = sorted(
            [x for x in ypool if x in std], key=lambda x: flat(std[x]), reverse=True)[:3]
        for name, sel in rules.items():
            for pid in sel:
                v, n = actual(pid)
                sk[name].append((v, proj[pid]["name"], n))

        # goalies: who's available, recent start share (last 6 team games before d0), team quality
        tc = P.team_context()  # season-level; small leak of team record, same for every rule
        before = [r for r in gs if r["date"] < d0 and r.get("starter")]
        bt = defaultdict(list)
        for r in sorted(before, key=lambda r: r["date"]):
            bt[r["team"]].append(r)
        cand = {}
        for t, rs in bt.items():
            last6 = rs[-6:]
            for r in last6:
                c = cand.setdefault(r["player_id"], {"pid": r["player_id"], "team": t, "name": r["goalie"], "n": 0})
                c["n"] += 1
        for c in cand.values():
            c["share"] = c["n"] / 6
            c["tg"] = ngames(c["team"])
            t = tc.get(c["team"], {})
            c["exp_w"] = c["share"] * c["tg"] * t.get("win_pct", 0.45)
            c["q"] = t.get("ga_pg", 3.2) - 2 * t.get("win_pct", 0.45)
        avail = [c for c in cand.values() if c["pid"] not in rost]
        grules = {
            "v2 table order (share>=0.4, then team GA/W%)": sorted(avail, key=lambda c: (c["share"] < 0.4, c["q"]))[:2],
            "v3: expected wins (share x games x team W%)": sorted(avail, key=lambda c: -c["exp_w"])[:2],
            "most expected starts": sorted(avail, key=lambda c: -(c["share"] * c["tg"]))[:2],
        }
        for name, sel in grules.items():
            for c in sel:
                rs = [r for r in gs if r["player_id"] == c["pid"] and d0 <= r["date"] <= d1 and r.get("starter")]
                gl[name].append((len(rs), sum(1 for r in rs if r["decision"] == "W"),
                                 sum(r["ga"] for r in rs), sum(r["sa"] for r in rs), c["name"]))

    print(f"# AGM v3 backtest — {len(days)} decision days {days[0]}..{days[-1]}, next {WIN} days\n")
    print("_Skaters: top 3 picks a day. Value = actual G/A/PIM/+/- over 7 days at even-matchup weights "
          "(+10 = +0.1 categories). Picks overlap day to day: unique players is the real sample._\n")
    print("| Rule | Picks | Unique | Value/pick (7d) | Games/pick | Pts/pick |")
    print("|---|---|---|---|---|---|")
    res = {}
    for name, L in sk.items():
        vp = sum(v for v, _, _ in L) / len(L)
        res[name] = vp
        print(f"| {name} | {len(L)} | {len({x for _, x, _ in L})} | {vp:.1f} | {sum(n for *_, n in L) / len(L):.2f} | – |")
    print("\n_Goalies: top 2 available a day; what they did over the next 7 days._\n")
    print("| Rule | Picks | Unique | Starts/pick | Wins/pick | GAA-ish (GA/start) | SV% |")
    print("|---|---|---|---|---|---|---|")
    for name, L in gl.items():
        st = sum(x[0] for x in L)
        print(f"| {name} | {len(L)} | {len({x[4] for x in L})} | {st / len(L):.2f} | "
              f"{sum(x[1] for x in L) / len(L):.2f} | {sum(x[2] for x in L) / max(st, 1):.2f} | "
              f"{1 - sum(x[2] for x in L) / max(sum(x[3] for x in L), 1):.3f} |")
    for name, L in sk.items():
        names = defaultdict(int)
        for _, x, _ in L:
            names[x] += 1
        print(f"\n_{name}: most-picked_ " + ", ".join(f"{k} ({v})" for k, v in sorted(names.items(), key=lambda kv: -kv[1])[:6]))
    return res


if __name__ == "__main__":
    main()
