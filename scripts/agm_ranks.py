"""
AGM category ranks — season-to-date league picture from archived weekly scoreboards
====================================================================================
    python3 scripts/agm_ranks.py              # vs this week's opponent (manifest opp_team_key)
    python3 scripts/agm_ranks.py --next       # vs next week's opponent (Sunday brief)
    python3 scripts/agm_ranks.py --opp 477.l.12088.t.7

Reads data/inseason/archive/scoreboard_week_NN.json (completed weeks only).
Output: H2H record and all-play record per team (all-play = your week vs every team's week,
a luck-free strength measure), our weekly rank per category, and a category-by-category
comparison with the opponent built from average weekly rank (1 = best of 10). With 2-4
weeks of data these are leans, not facts: the output says how many weeks it rests on.
"""

import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import IN, load, walk, flat

CATS = {"1": "G", "2": "A", "4": "+/-", "5": "PIM", "8": "PPP", "12": "GWG",
        "19": "W", "23": "GAA", "26": "SV%", "27": "SHO"}
LOWER = {"GAA"}
ME = "477.l.12088.t.1"


def week_tables():
    weeks = {}
    for p in sorted(glob.glob(os.path.join(IN, "archive", "scoreboard_week_*.json"))):
        wk = int(p[-7:-5])
        teams, pairs = {}, []
        for mu in walk(json.load(open(p)), "matchup"):
            if not isinstance(mu, dict):
                continue
            keys = []
            for t in walk(mu, "team"):
                if not (isinstance(t, list) and len(t) > 1):
                    continue
                meta = flat(t[0])
                st = {}
                for s in walk(t[1], "stat"):
                    if isinstance(s, dict) and str(s.get("stat_id")) in CATS:
                        try:
                            st[CATS[str(s["stat_id"])]] = float(s["value"])
                        except (TypeError, ValueError):
                            st[CATS[str(s["stat_id"])]] = None
                pts = next(walk(t[1], "team_points"), {}) or {}
                teams[meta["team_key"]] = dict(name=meta.get("name", "?"), stats=st,
                                               pts=float(pts.get("total") or 0))
                keys.append(meta["team_key"])
            if len(keys) == 2:
                pairs.append(tuple(keys))
        if teams:
            weeks[wk] = (teams, pairs)
    return weeks


def better(c, a, b):
    if a is None or b is None or a == b:
        return 0
    return (1 if a < b else -1) if c in LOWER else (1 if a > b else -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--opp")
    a = ap.parse_args()
    m = load("manifest") or {}
    opp = a.opp or (m.get("next_opp_team_key") if a.next else m.get("opp_team_key"))

    weeks = week_tables()
    if not weeks:
        print("❌ No archived scoreboards in data/inseason/archive/.")
        return
    names = {}
    h2h = collections.defaultdict(lambda: [0, 0, 0])
    allplay = collections.defaultdict(lambda: [0, 0, 0])
    ranks = collections.defaultdict(lambda: collections.defaultdict(list))   # team -> cat -> [rank per week]
    for wk, (teams, pairs) in sorted(weeks.items()):
        for k, t in teams.items():
            names[k] = t["name"]
        for x, y in pairs:
            px, py = teams[x]["pts"], teams[y]["pts"]
            for me, them, a_, b_ in ((x, y, px, py), (y, x, py, px)):
                h2h[me][0 if a_ > b_ else 1 if a_ < b_ else 2] += 1
        for k, t in teams.items():
            for o, u in teams.items():
                if o == k:
                    continue
                net = sum(better(c, t["stats"].get(c), u["stats"].get(c)) for c in CATS.values())
                allplay[k][0 if net > 0 else 1 if net < 0 else 2] += 1
        for c in CATS.values():
            for k, t in teams.items():
                v = t["stats"].get(c)
                r = 1 + sum(1 for u in teams.values() if better(c, u["stats"].get(c), v) == 1)
                ranks[k][c].append(r)

    n = len(weeks)
    print(f"# AGM category ranks — {n} completed week(s): {', '.join(str(w) for w in sorted(weeks))}\n")
    print(f"_{'Thin sample: treat as a lean, not a finding.' if n < 4 else 'Season-to-date.'} "
          "Rank 1 = best of 10 that week; GAA ranks low-is-best._\n")

    print("## Standings — H2H vs all-play\n")
    print("| Team | H2H (W-L-T) | All-play (W-L-T) | All-play % |\n|---|---|---|---|")
    def pct(r):
        g = sum(r)
        return (r[0] + 0.5 * r[2]) / g if g else 0
    for k in sorted(names, key=lambda k: -pct(allplay[k])):
        tag = " **(us)**" if k == ME else (" **(opp)**" if k == opp else "")
        print(f"| {names[k]}{tag} | {'-'.join(map(str, h2h[k]))} | {'-'.join(map(str, allplay[k]))} | "
              f"{pct(allplay[k]):.3f} |")

    cats = list(CATS.values())
    print("\n## Our rank by week\n")
    print("| Week | " + " | ".join(cats) + " |\n|---|" + "---|" * len(cats))
    for i, wk in enumerate(sorted(weeks)):
        print(f"| {wk} | " + " | ".join(str(ranks[ME][c][i]) for c in cats) + " |")

    if opp and opp in names:
        print(f"\n## Us vs {names[opp]} — average weekly rank\n")
        print("| Cat | Us | Them | Lean (data) |\n|---|---|---|---|")
        for c in cats:
            u = sum(ranks[ME][c]) / n
            t = sum(ranks[opp][c]) / n
            gap = t - u
            lean = "us" if gap >= 2 else "them" if gap <= -2 else "toss-up"
            print(f"| {c} | {u:.1f} | {t:.1f} | {lean} |")
        print("\n_Lean = average-rank gap of 2+ places. Weigh against this week's schedule and roster changes._")
    elif opp:
        print(f"\n_Opponent {opp} not found in archived weeks._")


if __name__ == "__main__":
    main()
