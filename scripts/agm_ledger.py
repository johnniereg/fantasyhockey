"""
AGM decision ledger — what each of our adds and drops has produced since
=========================================================================
    python3 scripts/agm_ledger.py              # every Flow Riders move this season
    python3 scripts/agm_ledger.py --since 2026-10-05

For each move in roster_moves_log.json (our team):
  added player   → fantasy stats in ACTIVE slots while on our roster (BN/IR days excluded),
                   from data/inseason/daily/<date>.json (exact Yahoo per-day numbers)
  dropped player → where he is now, and what he has produced on any fantasy roster since
                   (players sitting in free agency aren't in the daily files: shown as "FA")
The source of each move (AGM plan vs Johnnie) and the verdict are judgment: the morning brief
records them in the weekly doc's Decision ledger. This script only supplies the numbers.
"""

import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import IN, load

ME = "477.l.12088.t.1"
SKATER = ["G", "A", "+/-", "PIM", "PPP", "GWG"]
INACTIVE = {"BN", "IR", "IR+", "IL", "IL+", "NA", ""}


def daily():
    out = {}
    for p in sorted(glob.glob(os.path.join(IN, "daily", "*.json"))):
        d = json.load(open(p))
        out[d["date"]] = d
    return out


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def line(rows, goalie):
    if not rows:
        return "—"
    if goalie:
        w = sum(num(r["W"]) for r in rows if "W" in r)
        ga = sum(num(r.get("GA")) for r in rows)
        sv = sum(num(r.get("SV")) for r in rows)
        sa = sum(num(r.get("SA")) for r in rows)
        so = sum(num(r.get("SHO")) for r in rows)
        starts = sum(1 for r in rows if num(r.get("SA")) > 0)
        return (f"{starts} GP · {int(w)} W · SV% {sv / sa:.3f}".replace("0.", ".") if sa else f"{starts} GP") + \
               f" · GA {int(ga)} · SHO {int(so)}"
    tot = collections.Counter()
    for r in rows:
        for c in SKATER:
            tot[c] += num(r.get(c))
    return f"{len(rows)} GP · " + " ".join(f"{c} {int(tot[c]):+d}" if c == "+/-" else f"{c} {int(tot[c])}"
                                           for c in SKATER)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    a = ap.parse_args()
    moves = [e for e in (load("roster_moves_log") or []) if e.get("team_key") == ME]
    if a.since:
        moves = [e for e in moves if e["date_et"] >= a.since]
    days = daily()
    if not days:
        print("❌ No daily/ files yet — the fetch builds them (backfilling 3 days per run).")
        return
    first, last = min(days), max(days)
    print(f"# AGM decision ledger — Flow Riders moves\n")
    print(f"_Daily stats cover {first} → {last} ({len(days)} days"
          f"{'; backfill still running' if (load('manifest') or {}).get('extras', {}).get('daily_stats', {}).get('backfill_remaining') else ''}). "
          "Added: active-slot production while ours. Dropped: production on any roster since._\n")

    # Where every player is per day, and his stats when he played in an active slot
    where = collections.defaultdict(dict)      # key -> date -> (team_key, slot, stats, pos)
    for d, rec in days.items():
        for tk, t in rec["teams"].items():
            for p in t["players"]:
                where[p["key"]][d] = (tk, p["slot"], p["stats"], p["pos"])
    owner_now = {}
    for k, byd in where.items():
        d = max(byd)
        if d == last:
            owner_now[k] = days[d]["teams"][byd[d][0]]["name"]

    print("| Detected | Added | While ours (active slots) | Dropped (same fetch) | Since drop | Now with |")
    print("|---|---|---|---|---|---|")
    for e in moves:
        d0 = e["date_et"]
        adds = e.get("added") or [{}]
        drops = e.get("dropped") or [{}]
        for i in range(max(len(adds), len(drops))):
            ad = adds[i] if i < len(adds) else {}
            dr = drops[i] if i < len(drops) else {}
            a_rows, a_g = [], "G" in (ad.get("pos") or "")
            for d, (tk, slot, st, pos) in sorted(where.get(ad.get("key"), {}).items()):
                if d >= d0 and tk == ME and slot not in INACTIVE and st:
                    a_rows.append(st)
            d_rows, d_g = [], "G" in (dr.get("pos") or "")
            for d, (tk, slot, st, pos) in sorted(where.get(dr.get("key"), {}).items()):
                if d >= d0 and tk != ME and slot not in INACTIVE and st:
                    d_rows.append(st)
            now = owner_now.get(dr.get("key"), "FA / waivers") if dr else ""
            print(f"| {d0} | {ad.get('name', '—')} | {line(a_rows, a_g) if ad else ''} | "
                  f"{dr.get('name', '—')} | {line(d_rows, d_g) if dr else ''} | {now} |")
    print("\n_A player's GP counts days he was in an active slot with any stat line, so a scratch in an "
          "active slot can show as 0 GP. Season stats before the move aren't counted. "
          "Adds and drops are paired by the fetch that saw them, not by Yahoo's add/drop pairing._")


if __name__ == "__main__":
    main()
