"""
AGM usage trends — ice time and shot volume per player, from NHL box scores
===========================================================================
    python3 scripts/agm_usage.py                     # our roster (my_roster_today)
    python3 scripts/agm_usage.py --last 5            # recent window (default 5 games)
    python3 scripts/agm_usage.py --players "Bo Horvat,Dylan Holloway"
    python3 scripts/agm_usage.py --fa 30             # top 30 skaters on today's FA/waiver list, by recent TOI

Reads data/inseason/skater_games/*.json (built by the fetch). For each player: games, season
and recent TOI, the change, shots per game season vs recent, G/A/PPG, shooting %, and flags:
  ⬇ min   recent TOI 1.5+ min below season       ⬆ min   1.5+ min above
  low SOG  under 1.5 shots/game in the recent window (goals follow shots; SOG itself isn't scored)
  hot S%   season shooting % 18+ on 15+ shots (likely to cool)    cold S%   under 7% on 25+ shots
Names are matched Yahoo full name -> NHL "F. Last" + team; unmatched players are listed.
"""

import argparse
import glob
import json
import os
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import IN, load, players_in

COLS = None


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower().replace(".", "").replace("'", "").strip()


def key_parts(full):
    """'J.T. Miller' -> ('j', 'miller'); 'Joel Eriksson Ek' -> ('j', 'eriksson ek')."""
    full = (full or "").strip()
    if " " not in full:
        return ("", norm(full))
    first, last = full.split(" ", 1)
    return (norm(first)[:1], norm(last))


def load_games():
    """All skater rows as dicts, oldest first."""
    global COLS
    rows = []
    for p in sorted(glob.glob(os.path.join(IN, "skater_games", "*.json"))):
        blk = json.load(open(p))
        COLS = blk["cols"]
        rows += [dict(zip(COLS, r)) for r in blk["rows"]]
    rows.sort(key=lambda r: (r["date"] or "", r["game_id"] or 0))
    return rows


def index(rows):
    """player_id -> rows; plus lookup tables (initial,last,team) and (initial,last) -> ids."""
    by_id, by_full, by_name = defaultdict(list), defaultdict(set), defaultdict(set)
    for r in rows:
        by_id[r["player_id"]].append(r)
        k = key_parts(r["name"])
        by_full[k + (r["team"],)].add(r["player_id"])
        by_name[k].add(r["player_id"])
    return by_id, by_full, by_name


def match(full_name, team, by_full, by_name):
    k = key_parts(full_name)
    ids = by_full.get(k + (team,)) or set()
    if len(ids) == 1:
        return next(iter(ids))
    ids = by_name.get(k) or set()
    return next(iter(ids)) if len(ids) == 1 else None


def summary(rs, last):
    def agg(sub):
        n = len(sub)
        if not n:
            return None
        return {"gp": n, "toi": sum(r["toi_min"] or 0 for r in sub) / n,
                "sog": sum(r["sog"] or 0 for r in sub), "g": sum(r["g"] or 0 for r in sub),
                "a": sum(r["a"] or 0 for r in sub), "ppg": sum(r["ppg"] or 0 for r in sub)}
    return agg(rs), agg(rs[-last:])


def flags(s, r):
    out = []
    if s["gp"] >= last_min_gp and r["gp"] >= 3:
        d = r["toi"] - s["toi"]
        if d <= -1.5:
            out.append("⬇ min")
        elif d >= 1.5:
            out.append("⬆ min")
    if r["gp"] >= 3 and r["sog"] / r["gp"] < 1.5:
        out.append("low SOG")
    if s["sog"] >= 15 and s["g"] / s["sog"] >= 0.18:
        out.append("hot S%")
    if s["sog"] >= 25 and s["g"] / s["sog"] < 0.07:
        out.append("cold S%")
    return " ".join(out)


last_min_gp = 6


def fmt_min(m):
    return f"{int(m)}:{int(round((m - int(m)) * 60)):02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=5)
    ap.add_argument("--players")
    ap.add_argument("--fa", type=int, default=0)
    a = ap.parse_args()
    rows = load_games()
    if not rows:
        print("❌ No skater_games/ data yet — the fetch builds it (backfilling ~120 games per run).")
        return
    by_id, by_full, by_name = index(rows)
    m = load("manifest") or {}
    pend = (m.get("extras") or {}).get("skater_games", {}).get("games_pending")
    print(f"# AGM usage — TOI and shots, last {a.last} games vs season\n")
    print(f"_Box scores {rows[0]['date']} → {rows[-1]['date']} ({len({r['game_id'] for r in rows})} games"
          f"{f'; {pend} still backfilling' if pend else ''}). Data fetched {m.get('fetched_at_utc', '?')}._\n")

    targets = []      # (label, name, team)
    if a.players:
        names = [n.strip() for n in a.players.split(",") if n.strip()]
        targets = [("", n, None) for n in names]
    elif a.fa:
        snaps = sorted(glob.glob(os.path.join(IN, "fa_snapshots", "*.json")))
        pool = {}
        if snaps:
            for k, p in json.load(open(snaps[-1]))["players"].items():
                pool[k] = (p["name"], p["team"], p["pos"], "W" if p.get("waivers") else "FA")
        else:
            for fn in sorted(glob.glob(os.path.join(IN, "fa_*_[0-9].json")) + glob.glob(os.path.join(IN, "waivers_*.json"))):
                for p in players_in(json.load(open(fn))):
                    pool[p["key"]] = (p["name"], p["team"], p["pos"], "W" if "waivers" in fn else "FA")
        cands = []
        for name, team, pos, st in pool.values():
            if pos == "G":
                continue
            pid = match(name, team, by_full, by_name)
            if pid:
                s, r = summary(by_id[pid], a.last)
                cands.append((r["toi"], f"{st} {pos}", name, team))
        cands.sort(reverse=True)
        targets = [(lab, n, t) for _, lab, n, t in cands[:a.fa]]
    else:
        for fn in ("my_roster_today",):
            for p in players_in(load(fn) or {}):
                if p["pos"] != "G":
                    targets.append((p["slot"], p["name"], p["team"]))

    print("| Player | Tag | Team | GP | TOI season | TOI recent | Δ | SOG/GP season | SOG/GP recent | G | A | PPG | S% | Flags |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    missing = []
    for lab, name, team in targets:
        pid = match(name, team, by_full, by_name) if team else match(name, None, by_full, by_name)
        if not pid:
            missing.append(name)
            continue
        rs = by_id[pid]
        s, r = summary(rs, a.last)
        d = r["toi"] - s["toi"]
        sp = f"{100 * s['g'] / s['sog']:.0f}%" if s["sog"] else "—"
        print(f"| {name} | {lab} | {rs[-1]['team']} | {s['gp']} | {fmt_min(s['toi'])} | {fmt_min(r['toi'])} | "
              f"{d:+.1f} | {s['sog'] / s['gp']:.1f} | {r['sog'] / r['gp']:.1f} | {s['g']} | {s['a']} | {s['ppg']} | "
              f"{sp} | {flags(s, r)} |")
    if missing:
        print(f"\n_No box-score match: {', '.join(missing)} (not played yet, name mismatch, or backfill pending)._")
    print("\n_TOI is all situations; the box score has no PP TOI, so PP role still comes from line "
          "combinations (deployment log in the vault). PPG = power-play goals only (no PP assists in box scores)._")


if __name__ == "__main__":
    main()
