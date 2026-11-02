"""
AGM backtest — does a model or rule predict what players do next?
=================================================================
    python3 scripts/agm_backtest.py models     # projection variants vs next-7-day results
    python3 scripts/agm_backtest.py rules      # pick rules on the free-agent pool vs baseline
    python3 scripts/agm_backtest.py signals    # ice-time / streak signals vs a player's projection
    python3 scripts/agm_backtest.py all --write  # all three; save data/agm/rules_ledger.json

Decision days: every 2nd day from 2026-10-10 while a full 7-day window exists in the box scores.
Only data before a decision day is used to make the call. Outcomes are per-game rates over the
next 7 days, weighted by games. Categories testable from box scores: G, A, PIM, +/- (PM).
Windows overlap, so effective sample sizes are smaller than n: read differences as directions.
"""
import argparse
import datetime as dt
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agm_project as P  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "data", "agm")
TEST = ["G", "A", "PIM", "PM"]
WIN = 7


def box():
    rows = P._CACHE.setdefault("box", P._box_rows())
    by = defaultdict(list)
    for r in rows:
        by[r["player_id"]].append(r)
    for v in by.values():
        v.sort(key=lambda r: r["date"])
    return by, max(r["date"] for r in rows)


def decision_days(last, start="2026-10-10", step=2):
    d = dt.date.fromisoformat(start)
    out = []
    while (d + dt.timedelta(days=WIN - 1)).isoformat() <= last:
        out.append(d.isoformat())
        d += dt.timedelta(days=step)
    return out


def outcome(rs, d0):
    d1 = (dt.date.fromisoformat(d0) + dt.timedelta(days=WIN - 1)).isoformat()
    w = [r for r in rs if d0 <= r["date"] <= d1]
    if not w:
        return None
    n = len(w)
    return {"n": n, "G": sum(r["g"] or 0 for r in w) / n, "A": sum(r["a"] or 0 for r in w) / n,
            "PIM": sum(r["pim"] or 0 for r in w) / n, "PM": sum(r["pm"] or 0 for r in w) / n}


def score(preds, by, days):
    """Games-weighted mean squared error per category, and for points (G+A)."""
    err, wsum = defaultdict(float), 0
    for d0 in days:
        pr = preds[d0]
        for pid, p in pr.items():
            if p["gp"] < 3:
                continue
            o = outcome(by.get(pid, []), d0)
            if not o:
                continue
            for c in TEST:
                err[c] += o["n"] * (p[c] - o[c]) ** 2
            err["PTS"] += o["n"] * ((p["G"] + p["A"]) - (o["G"] + o["A"])) ** 2
            wsum += o["n"]
    return {c: err[c] / wsum for c in err}, wsum


def run_models():
    by, last = box()
    days = decision_days(last)
    variants = {
        "season-to-date only": dict(current_only=True),
        "last 3 seasons only": dict(prior_only=True),
        "blend (no role, no age)": dict(beta=0, use_age=False),
        "blend + role": dict(beta=P.BETA, use_age=False),
        "blend + role + age": dict(beta=P.BETA, use_age=True),
        "blend + role, K x0.5": dict(beta=P.BETA, k_scale=0.5),
        "blend + role, K x2": dict(beta=P.BETA, k_scale=2.0),
        "blend + role beta=1": dict(beta=1.0),
        "blend + role beta=0.4": dict(beta=0.4),
    }
    res = {}
    for name, kw in variants.items():
        preds = {d0: P.project(as_of=d0, **kw) for d0 in days}
        res[name], n = score(preds, by, days)
    base = res["season-to-date only"]
    print(f"# Projection backtest — {len(days)} decision days {days[0]}..{days[-1]}, next {WIN} days\n")
    print(f"_Error = games-weighted mean squared error per game (lower is better), {n:.0f} player-games. "
          "'vs STD' = error relative to season-to-date (100% = same)._\n")
    print("| Model | " + " | ".join(TEST + ["PTS"]) + " | PTS vs STD |")
    print("|---|" + "---|" * (len(TEST) + 2))
    for name, r in res.items():
        print(f"| {name} | " + " | ".join(f"{r[c]:.3f}" for c in TEST + ["PTS"])
              + f" | {100 * r['PTS'] / base['PTS']:.0f}% |")
    return res


def value(p, cats=("G", "A", "PIM", "PM")):
    # equal-weight z-ish: divide by typical spread of per-game rates among regulars
    sd = {"G": 0.17, "A": 0.22, "PIM": 0.45, "PM": 0.35}
    return sum(p[c] / sd[c] for c in cats)


def run_rules(seed=7):
    from agm_counterfactual import daily_rosters
    from agm_usage import index, match
    by, last = box()
    days = decision_days(last, start="2026-10-08", step=1)
    rosters = daily_rosters()
    _, by_full, by_name = index(P._CACHE["box"])
    rost_cache = {}

    def rostered(day):
        ds = [d for d in rosters if d <= day]
        if not ds:
            return set()
        d = max(ds)
        if d not in rost_cache:
            rost_cache[d] = {match(n, t, by_full, by_name) for n, t in rosters[d]} - {None}
        return rost_cache[d]

    picks = defaultdict(list)
    rnd = random.Random(seed)
    for d0 in days:
        prev = (dt.date.fromisoformat(d0) - dt.timedelta(days=1)).isoformat()
        rost = rostered(prev)
        proj = P.project(as_of=d0)
        std = P.project(as_of=d0, current_only=True)
        pool = [p for pid, p in proj.items() if pid not in rost and p["grp"] == "F" and p["gp"] >= 5
                and outcome(by.get(pid, []), d0)]
        role = [p for p in pool if p["toi"] >= 16]

        def top(key, src, k=3):
            return sorted(src, key=key, reverse=True)[:k]
        rules = {
            "projection value (G,A,PIM,+/-)": top(value, pool),
            "projection points": top(lambda p: p["G"] + p["A"], pool),
            "season-to-date points, TOI 16+": top(lambda p: std[p["pid"]]["G"] + std[p["pid"]]["A"], role),
            "hot last 5 points, TOI 16+": top(lambda p: sum((r["g"] or 0) + (r["a"] or 0) for r in
                                                       [x for x in by[p["pid"]] if x["date"] < d0][-5:]), role),
            "most ice time": top(lambda p: p["toi_recent"], pool),
            "random role player (TOI 16+)": rnd.sample(role, min(3, len(role))),
        }
        for name, sel in rules.items():
            for p in sel:
                o = outcome(by[p["pid"]], d0)
                picks[name].append((o, p["name"]))
    print(f"\n# Rule backtest — top 3 available forwards each day, {days[0]}..{days[-1]} ({len(days)} days)\n")
    print("| Rule | Picks | Unique | Points/GP | G | A | PIM | +/- | Value/GP |")
    print("|---|---|---|---|---|---|---|---|---|")
    out = {}
    for name, L in picks.items():
        n = sum(o["n"] for o, _ in L)
        m = {c: sum(o[c] * o["n"] for o, _ in L) / n for c in TEST}
        v = value(m)
        out[name] = {"points_pg": m["G"] + m["A"], "value_pg": v, **m, "picks": len(L),
                     "unique": len({x for _, x in L})}
        print(f"| {name} | {len(L)} | {out[name]['unique']} | {m['G'] + m['A']:.2f} | {m['G']:.2f} | {m['A']:.2f} | "
              f"{m['PIM']:.2f} | {m['PM']:+.2f} | {v:.2f} |")
    return out


def run_signals():
    by, last = box()
    days = decision_days(last)
    rows = []
    for d0 in days:
        proj = P.project(as_of=d0, beta=0)  # signal must add something beyond the base projection
        for pid, p in proj.items():
            if p["grp"] != "F" or p["gp"] < 6:
                continue
            o = outcome(by.get(pid, []), d0)
            if not o or o["n"] < 2:
                continue
            past = [r for r in by[pid] if r["date"] < d0]
            l5 = sum((r["g"] or 0) + (r["a"] or 0) for r in past[-5:]) / 5
            dtoi = (sum(r["toi_min"] for r in past[-3:]) / 3) - (sum(r["toi_min"] for r in past[:-3]) / max(1, len(past) - 3))
            rows.append({"proj": p["G"] + p["A"], "l5": l5, "dtoi": dtoi, "out": o["G"] + o["A"], "n": o["n"]})

    def line(label, L):
        if not L:
            return f"| {label} | 0 | | | |"
        n = sum(r["n"] for r in L)
        pj = sum(r["proj"] * r["n"] for r in L) / n
        ot = sum(r["out"] * r["n"] for r in L) / n
        return f"| {label} | {len(L)} | {pj:.2f} | {ot:.2f} | {ot - pj:+.2f} |"
    print(f"\n# Signal backtest — forwards, next {WIN} days vs base projection (no role term)\n")
    print("| Signal | n | Projected P/GP | Actual P/GP | Actual - projected |\n|---|---|---|---|---|")
    groups = {
        "all": rows,
        "ice time up 2+ min (last 3 vs before)": [r for r in rows if r["dtoi"] >= 2],
        "ice time down 2+ min": [r for r in rows if r["dtoi"] <= -2],
        "hot: last 5 >= projection + 0.5": [r for r in rows if r["l5"] - r["proj"] >= 0.5],
        "cold: last 5 <= projection - 0.4": [r for r in rows if r["l5"] - r["proj"] <= -0.4],
        "cold and ice time down 1.5+": [r for r in rows if r["l5"] - r["proj"] <= -0.4 and r["dtoi"] <= -1.5],
    }
    out = {}
    for k, L in groups.items():
        print(line(k, L))
        if L:
            n = sum(r["n"] for r in L)
            out[k] = {"n": len(L), "resid": sum((r["out"] - r["proj"]) * r["n"] for r in L) / n}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["models", "rules", "signals", "all"])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    res = {}
    if a.what in ("models", "all"):
        res["models"] = run_models()
    if a.what in ("rules", "all"):
        res["rules"] = run_rules()
    if a.what in ("signals", "all"):
        res["signals"] = run_signals()
    if a.write:
        os.makedirs(OUTDIR, exist_ok=True)
        p = os.path.join(OUTDIR, "rules_ledger.json")
        hist = json.load(open(p)) if os.path.exists(p) else []
        hist.append({"run_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **res})
        json.dump(hist[-26:], open(p, "w"), indent=1)
        print(f"\nWrote {p}")


if __name__ == "__main__":
    main()
