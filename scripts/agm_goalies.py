"""
AGM goalie market — offline view of data/inseason/goalie_starts.json (no network)
==================================================================================
    python3 scripts/agm_goalies.py            # last 5 team games
    python3 scripts/agm_goalies.py --last 7

Sections: our goalies · trigger 1 (an available goalie started 3+ of his team's last 5 with
SV% .910+) · trigger 2 hints (a team's season-leading starter has missed its last 3 games) ·
every goalie who started in his team's window, with owner and ownership %.
Starter flags come from NHL box scores; Yahoo ownership from the fa_G / waivers / all_rosters files.
"""

import argparse
import collections
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import load, players_in, walk, flat

TRIGGER_STARTS, TRIGGER_SV = 3, 0.910


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return s.replace(".", "").replace("-", " ").strip()


def last_name(full):
    return norm(full).split(" ")[-1] if full else ""


def yahoo_goalies():
    """{(nhl_team, last): {name, owner, owned, status, key}} for every goalie Yahoo shows us."""
    out = {}
    for t in walk(load("all_rosters") or {}, "team"):
        if not (isinstance(t, list) and len(t) > 1):
            continue
        meta = flat(t[0])
        for p in players_in(t[1]):
            if "G" in p["elig"]:
                out[(p["team"], last_name(p["name"]))] = dict(name=p["name"], owner=meta.get("name", "?"),
                                                               owned=None, status=p["status"], key=p["key"])
    waiver_keys = {p["key"] for pg in range(2) for p in players_in(load(f"waivers_{pg}"))}
    for pg in range(4):
        for p in players_in(load(f"fa_G_{pg}")):
            out[(p["team"], last_name(p["name"]))] = dict(
                name=p["name"], owner="W" if p["key"] in waiver_keys else "FA",
                owned=p["owned"], status=p["status"], key=p["key"])
    return out


def ratios(rows):
    sa = sum(r["sa"] or 0 for r in rows)
    sv = sum(r["sv"] or 0 for r in rows)
    ga = sum(r["ga"] or 0 for r in rows)
    mins = sum(r.get("toi_min") or 0 for r in rows)
    return (sv / sa if sa else None), (ga * 60 / mins if mins else None), sa


def fmt_sv(x):
    return f"{x:.3f}".lstrip("0") if x is not None else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=5, help="team games in the window")
    a = ap.parse_args()

    log = load("goalie_starts")
    if not log or not log.get("rows"):
        print("❌ No goalie_starts.json yet — the fetch builds it from NHL box scores.")
        return
    m = load("manifest") or {}
    rows = log["rows"]
    print(f"# AGM goalie market — last {a.last} team games\n")
    print(f"_Box scores through {max(r['date'] for r in rows)} ({len(log['games_done'])} games). "
          f"Yahoo data fetched {m.get('fetched_at_utc', '?')} UTC._\n")

    by_team = collections.defaultdict(list)            # team -> [game rows for that team]
    for r in rows:
        by_team[r["team"]].append(r)
    games_by_team = {t: sorted({(r["date"], r["game_id"]) for r in rs}) for t, rs in by_team.items()}
    window = {t: set(g for _, g in gs[-a.last:]) for t, gs in games_by_team.items()}
    last3 = {t: set(g for _, g in gs[-3:]) for t, gs in games_by_team.items()}

    yg = yahoo_goalies()
    per_goalie = collections.defaultdict(list)          # (team, last) -> starter rows in window
    season_starts = collections.Counter()
    for r in rows:
        if r["starter"]:
            key = (r["team"], norm(r["last"]))
            season_starts[key] += 1
            if r["game_id"] in window.get(r["team"], ()):
                per_goalie[key].append(r)

    table = []
    for key, rs in per_goalie.items():
        team, ln = key
        info = yg.get(key, {"name": rs[0]["goalie"], "owner": "?", "owned": None, "status": ""})
        sv, gaa, sa = ratios(rs)
        n_win = len(window[team])
        w = sum(1 for r in rs if r["decision"] == "W")
        so = sum(1 for r in rs if (r["ga"] == 0 and (r.get("toi_min") or 0) >= 55))
        table.append(dict(team=team, name=info["name"], owner=info["owner"], owned=info["owned"],
                          status=info["status"], starts=len(rs), of=n_win, sv=sv, gaa=gaa, w=w, so=so,
                          season=season_starts[key], dates=[r["date"][5:] for r in rs]))
    table.sort(key=lambda x: (x["team"], -x["starts"]))

    ours = [x for x in table if x["owner"] == "Flow Riders"]
    print("## Our goalies\n")
    for x in ours:
        gaa = f"{x['gaa']:.2f}" if x["gaa"] is not None else "—"
        print(f"- **{x['name']}** ({x['team']}): {x['starts']} of {x['team']}'s last {x['of']} "
              f"({', '.join(x['dates'])}), SV% {fmt_sv(x['sv'])}, GAA {gaa}")
    if not ours:
        print("- none matched (check names/teams)")

    print(f"\n## Trigger 1 — available goalie, {TRIGGER_STARTS}+ of last {a.last}, SV% {fmt_sv(TRIGGER_SV)}+\n")
    hits = [x for x in table if x["owner"] in ("FA", "W") and x["starts"] >= TRIGGER_STARTS
            and (x["sv"] or 0) >= TRIGGER_SV]
    for x in hits:
        gaa = f"{x['gaa']:.2f}" if x["gaa"] is not None else "—"
        print(f"- 🔔 **{x['name']}** ({x['team']}, {x['owner']}, {x['owned'] or '?'}% owned): "
              f"{x['starts']} of {x['of']}, SV% {fmt_sv(x['sv'])}, GAA {gaa}")
    if not hits:
        print("- none")

    print("\n## Trigger 2 hints — season-leading starter hasn't started any of the team's last 3\n")
    hints = []
    for team, gs in games_by_team.items():
        leaders = [(k, n) for k, n in season_starts.items() if k[0] == team]
        if not leaders or len(gs) < 4:
            continue
        top, n = max(leaders, key=lambda kv: kv[1])
        recent = [r for r in by_team[team] if r["starter"] and r["game_id"] in last3[team]]
        if not any(norm(r["last"]) == top[1] for r in recent):
            now = ", ".join(sorted({r["goalie"] for r in recent}))
            info = yg.get(top, {"name": top[1].title(), "owner": "?"})
            hints.append(f"- {team}: **{info['name']}** ({n} season starts, owner {info['owner']}) — "
                         f"last 3 started by {now}. Check injury/demotion news.")
    print("\n".join(hints) or "- none")

    print(f"\n## All goalies who started in their team's last {a.last}\n")
    print("| Team | Goalie | Owner | Own% | Starts | SV% | GAA | W | SO | Season starts |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for x in table:
        gaa = f"{x['gaa']:.2f}" if x["gaa"] is not None else "—"
        print(f"| {x['team']} | {x['name']} | {x['owner']} | {x['owned'] or '—'} | {x['starts']}/{x['of']} | "
              f"{fmt_sv(x['sv'])} | {gaa} | {x['w']} | {x['so']} | {x['season']} |")


if __name__ == "__main__":
    main()
