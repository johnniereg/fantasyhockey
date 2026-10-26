"""
AGM counterfactual — each of our adds vs the best player we could have added instead
===================================================================================
    python3 scripts/agm_counterfactual.py                 # our adds, 14-day window after each
    python3 scripts/agm_counterfactual.py --days 7
    python3 scripts/agm_counterfactual.py --since 2026-10-12
    python3 scripts/agm_counterfactual.py --team all      # every manager's adds (who picks well?)

For each add in roster_moves_log.json:
  available pool = every NHL player on no fantasy roster the day before the move was detected
                   (daily/<date>.json rosters; fa_snapshots/<date>.json adds Yahoo eligibility and
                   the waiver flag once it exists), in the same group: F, D or G
  window         = the N days starting the detection date (the add plays from then)
  production     = NHL box scores in the window (skater_games/, goalie_starts.json), all games,
                   so it measures the player, not our lineup decisions

Skaters rank by G+A, then G, then games. PPG = power-play goals (box scores carry no PP assists).
Goalies rank by wins, then SV% (2+ starts). The output is a measure, not a verdict: a pick made
for schedule or a category can lose on points and still have been right. Windows still open are
marked "open".
"""

import argparse
import datetime as dt
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import IN, load
from agm_usage import load_games, index, match, key_parts

ME = "477.l.12088.t.1"


def group(pos):
    pos = pos or ""
    if "G" in pos.split(","):
        return "G"
    if pos.split(",") == ["D"] or pos == "D":
        return "D"
    return "F"


def nhl_group(p):
    return "D" if p == "D" else "F"


def daily_rosters():
    out = {}
    for p in sorted(glob.glob(os.path.join(IN, "daily", "*.json"))):
        d = json.load(open(p))
        out[d["date"]] = [(pl["name"], pl["team"]) for t in d["teams"].values() for pl in t["players"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--since")
    ap.add_argument("--team", default=ME, help="team key, or 'all'")
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()

    rows = load_games()
    gl = (load("goalie_starts") or {}).get("rows", [])
    if not rows:
        print("❌ No skater_games/ data yet — the fetch builds it (backfilling ~120 games per run).")
        return
    by_id, by_full, by_name = index(rows)
    last_box = max(r["date"] for r in rows)
    rosters = daily_rosters()
    moves = [e for e in (load("roster_moves_log") or []) if a.team == "all" or e.get("team_key") == a.team]
    if a.since:
        moves = [e for e in moves if e["date_et"] >= a.since]

    # goalie lookups by (initial, last, team) from goalie_starts names ("B. Bussi")
    g_by_id = defaultdict(list)
    g_full, g_name = defaultdict(set), defaultdict(set)
    for r in gl:
        g_by_id[r["player_id"]].append(r)
        k = key_parts(r["goalie"])
        g_full[k + (r["team"],)].add(r["player_id"])
        g_name[k].add(r["player_id"])

    rost_ids_cache = {}

    def rostered_ids(day):
        """NHL ids of every rostered player on `day` (nearest earlier daily file)."""
        days = [d for d in rosters if d <= day]
        if not days:
            return None, None
        d = max(days)
        if d not in rost_ids_cache:
            ids = set()
            for name, team in rosters[d]:
                pid = match(name, team, by_full, by_name) or match(name, team, g_full, g_name)
                if pid:
                    ids.add(pid)
            rost_ids_cache[d] = ids
        return d, rost_ids_cache[d]

    def snap(day):
        p = os.path.join(IN, "fa_snapshots", f"{day}.json")
        return json.load(open(p))["players"] if os.path.exists(p) else None

    def sk_line(rs):
        g = sum(r["g"] or 0 for r in rs); a_ = sum(r["a"] or 0 for r in rs)
        return {"gp": len(rs), "g": g, "a": a_, "ppg": sum(r["ppg"] or 0 for r in rs),
                "pim": sum(r["pim"] or 0 for r in rs), "pm": sum(r["pm"] or 0 for r in rs),
                "toi": (sum(r["toi_min"] or 0 for r in rs) / len(rs)) if rs else 0}

    def sk_txt(s):
        return (f"{s['gp']} GP {s['g']} G {s['a']} A {s['ppg']} PPG {s['pim']} PIM {s['pm']:+d}"
                f" · {s['toi']:.0f} min" if s["gp"] else "0 GP")

    def g_line(rs):
        st = [r for r in rs if r.get("starter")]
        sa = sum(r["sa"] or 0 for r in rs); sv = sum(r["sv"] or 0 for r in rs)
        return {"gp": len(st), "w": sum(1 for r in rs if r.get("decision") == "W"),
                "sv": (sv / sa) if sa else 0.0}

    def g_txt(s):
        return f"{s['gp']} GS {s['w']} W {s['sv']:.3f}".replace(" 0.", " .") if s["gp"] else "0 GS"

    print(f"# AGM counterfactual — adds vs best available ({a.days}-day window)\n")
    print(f"_Box scores through {last_box}. Pool = players on no fantasy roster the day before the move. "
          "Production = all NHL games in the window, not our lineup. A measure, not a verdict._\n")
    print("| Detected | Team | Added | His window | Rank in pool | Best available instead | Window |")
    print("|---|---|---|---|---|---|---|")
    scored = []
    for e in moves:
        d0 = e["date_et"]
        start = dt.date.fromisoformat(d0)
        end = start + dt.timedelta(days=a.days - 1)
        w0, w1 = start.isoformat(), end.isoformat()
        status = "open" if w1 > last_box else "closed"
        rday, rost = rostered_ids((start - dt.timedelta(days=1)).isoformat())
        if rost is None:
            continue
        sn = snap((start - dt.timedelta(days=1)).isoformat())
        team_lbl = "us" if e["team_key"] == ME else (e.get("team_name") or "")[:14]
        for ad in e.get("added") or []:
            grp = group(ad.get("pos"))
            if grp == "G":
                pid = match(ad["name"], ad["team"], g_full, g_name)
                pool = {}
                for gid, rs in g_by_id.items():
                    if gid in rost and gid != pid:
                        continue
                    win = [r for r in rs if w0 <= r["date"] <= w1]
                    pool[gid] = (g_line(win), rs[-1]["goalie"], rs[-1]["team"])
                ranked = sorted(pool.items(), key=lambda kv: (-kv[1][0]["w"],
                                -(kv[1][0]["sv"] if kv[1][0]["gp"] >= 2 else 0)))
                mine = pool.get(pid, (g_line([]), ad["name"], ad["team"]))
                txt, fmt = g_txt(mine[0]), g_txt
            else:
                pid = match(ad["name"], ad["team"], by_full, by_name)
                pool = {}
                for sid, rs in by_id.items():
                    if (sid in rost and sid != pid) or nhl_group(rs[-1]["pos"]) != grp:
                        continue
                    win = [r for r in rs if w0 <= r["date"] <= w1]
                    if not win and sid != pid:
                        continue
                    pool[sid] = (sk_line(win), rs[-1]["name"], rs[-1]["team"])
                ranked = sorted(pool.items(), key=lambda kv: (-(kv[1][0]["g"] + kv[1][0]["a"]),
                                -kv[1][0]["g"], -kv[1][0]["gp"]))
                mine = pool.get(pid, (sk_line([]), ad["name"], ad["team"]))
                txt, fmt = sk_txt(mine[0]), sk_txt
            ids = [k for k, _ in ranked]
            rank = (ids.index(pid) + 1) if pid in ids else None
            best = [f"{v[1]} ({v[2]}): {fmt(v[0])}" for k, v in ranked if k != pid][:a.top]
            rk = f"{rank} of {len(ids)}" if rank else "no match"
            print(f"| {d0} | {team_lbl} | {ad['name']} ({grp}) | {txt} | {rk} | {'<br>'.join(best)} | {status} |")
            if rank:
                scored.append((team_lbl, rank, len(ids), status))
    if a.team == "all" and scored:
        print("\n## Median pool rank of closed-window adds, by team\n")
        by = defaultdict(list)
        for t, r, n, s in scored:
            if s == "closed":
                by[t].append(r)
        print("| Team | Adds | Median rank |\n|---|---|---|")
        for t, rs in sorted(by.items(), key=lambda kv: sorted(kv[1])[len(kv[1]) // 2]):
            print(f"| {t} | {len(rs)} | {sorted(rs)[len(rs) // 2]} |")
    print("\n_Names in the pool are NHL box-score names. Pool can include players who were on waivers "
          "(a claim, not a free add) and, before fa_snapshots exist, can't tell them apart. "
          "Positions are NHL F/D, not Yahoo eligibility._")


if __name__ == "__main__":
    main()
