"""
AGM weekly plan — offline analysis of data/inseason/ (no network needed)
========================================================================
Run after `git pull`:
    python3 scripts/agm_plan.py              # rest of current fantasy week, from today
    python3 scripts/agm_plan.py --week 2     # a specific fantasy week, all days
    python3 scripts/agm_plan.py --from 2026-10-05

Output: markdown to stdout. Everything is derived from the raw JSON saved by
fetch_inseason.py; nothing here calls Yahoo or NHL.
"""

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN   = os.environ.get("AGM_DATA") or os.path.join(BASE, "data", "inseason")

# Yahoo editorial_team_abbr (upper-cased) -> NHL API abbrev, where they differ
YAHOO_TO_NHL = {"CLS": "CBJ", "MON": "MTL", "NJ": "NJD", "LA": "LAK", "SJ": "SJS",
                "TB": "TBL", "WAS": "WSH", "VEG": "VGK", "VGS": "VGK", "ARI": "UTA"}
SLOTS_DEFAULT = {"C": 2, "LW": 2, "RW": 2, "D": 4, "G": 2}
OUT_STATUSES  = {"IR", "IR-LT", "IR-NR", "O", "NA", "SUSP", "IR+"}
# 2026-27 keepers (vault: 30 Areas/Fantasy Hockey/2026-27-season). Yahoo's is_keeper flag is empty in-season.
KEEPERS = ["Matt Boldy", "Cutter Gauthier", "Will Smith", "Ivan Demidov", "Miro Heiskanen",
           "Cole Hutson", "Brock Nelson", "Karel Vejmelka"]
LIGHT_MAX_GAMES = 7            # a night with <= 7 games (<= 14 teams) is a light night
ET = dt.timezone(dt.timedelta(hours=-4))


# ── Generic Yahoo JSON helpers ────────────────────────────────────────────────

def load(name):
    p = os.path.join(IN, f"{name}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def flat(o):
    """Merge Yahoo's list-of-dicts (possibly nested lists) into one dict."""
    out = {}
    if isinstance(o, dict):
        return dict(o)
    for item in o or []:
        if isinstance(item, dict):
            out.update(item)
        elif isinstance(item, list):
            out.update(flat(item))
    return out


def walk(o, key):
    """Yield every value stored under `key` anywhere in o."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v, key)


def parse_player(raw):
    d = flat(raw)
    elig = list(walk(d.get("eligible_positions", []), "position"))
    sel = [p for p in walk(d.get("selected_position", []), "position")]
    own = next(walk(d.get("percent_owned", {}), "value"), None)
    abbr = str(d.get("editorial_team_abbr", "")).upper()
    stats = {}
    for s in walk(d.get("player_stats", {}), "stat"):
        if isinstance(s, dict):
            stats[str(s.get("stat_id"))] = s.get("value")
    return {
        "key": d.get("player_key"),
        "name": (d.get("name") or {}).get("full", "?"),
        "team": YAHOO_TO_NHL.get(abbr, abbr),
        "pos": d.get("display_position", ""),
        "elig": [p for p in elig if p in SLOTS_DEFAULT],
        "status": d.get("status", "") or "",
        "slot": sel[0] if sel else "",
        "owned": own,
        "stats": stats,
    }


def players_in(o):
    return [parse_player(p) for p in walk(o, "player") if isinstance(p, list)]


# ── Data assembly ─────────────────────────────────────────────────────────────

def nhl_games_by_date():
    by_date = {}
    for fn in sorted(os.listdir(IN)):
        if not fn.startswith("nhl_schedule_"):
            continue
        for day in json.load(open(os.path.join(IN, fn))).get("gameWeek", []):
            teams = set()
            for g in day.get("games", []):
                if g.get("gameType", 2) not in (2, 3):     # regular season / playoffs only
                    continue
                teams.add(g["awayTeam"]["abbrev"]); teams.add(g["homeTeam"]["abbrev"])
            by_date[day["date"]] = teams
    return by_date


def roster_slots(settings):
    slots = {}
    for rp in walk(settings, "roster_position"):
        if isinstance(rp, dict) and rp.get("position") in SLOTS_DEFAULT:
            slots[rp["position"]] = int(rp.get("count", 0))
    return slots or dict(SLOTS_DEFAULT)


def stat_names(settings):
    names = {}
    for s in walk(settings, "stat"):
        if isinstance(s, dict) and "stat_id" in s and "display_name" in s:
            names[str(s["stat_id"])] = s["display_name"]
    return names


# ── Lineup simulation (max bipartite matching per day) ────────────────────────

def best_lineup(players, slots):
    """Max number of players placed into slots. Earlier players win ties."""
    seats = [pos for pos, n in slots.items() for _ in range(n)]
    owner = [None] * len(seats)

    def place(i, seen):
        for s, pos in enumerate(seats):
            if pos in players[i]["elig"] and s not in seen:
                seen.add(s)
                if owner[s] is None or place(owner[s], seen):
                    owner[s] = i
                    return True
        return False

    for i in range(len(players)):
        place(i, set())
    return {players[o]["key"]: seats[s] for s, o in enumerate(owner) if o is not None}, \
           sum(1 for o in owner if o is None)


def simulate(roster, dates, games, slots):
    starts, benched, empty = defaultdict(int), defaultdict(int), {}
    for d in dates:
        playing = [p for p in roster if p["team"] in games.get(d, set())
                   and p["status"] not in OUT_STATUSES and p["slot"] not in ("IR", "IR+")]
        # Only one goalie per NHL team can start on a night; keep the first listed, bench the rest
        g_teams, dup = set(), []
        for p in playing:
            if "G" in p["elig"]:
                if p["team"] in g_teams:
                    dup.append(p)
                g_teams.add(p["team"])
        playing_eff = [p for p in playing if p not in dup]
        placed, n_empty = best_lineup(playing_eff, slots)
        for p in playing:
            (starts if p["key"] in placed else benched)[p["key"]] += 1
        empty[d] = n_empty
    return starts, benched, empty


# ── Report ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int)
    ap.add_argument("--from", dest="start")
    ap.add_argument("--fa", type=int, default=8, help="FA rows per position")
    ap.add_argument("--keepers", help="comma-separated names never treated as droppable")
    a = ap.parse_args()
    keepers = set(k.strip() for k in (a.keepers.split(",") if a.keepers else KEEPERS))

    m = load("manifest") or {}
    settings = load("league_settings")
    slots = roster_slots(settings)
    names = stat_names(settings)
    games = nhl_games_by_date()

    week = a.week or m.get("current_week")
    wk = (m.get("week_dates") or {}).get(str(week))
    today = dt.datetime.now(ET).date()
    if wk:
        w0, w1 = dt.date.fromisoformat(wk[0]), dt.date.fromisoformat(wk[1])
    else:
        w0, w1 = today, today + dt.timedelta(days=6)
    start = dt.date.fromisoformat(a.start) if a.start else (max(w0, today) if not a.week else w0)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range((w1 - start).days + 1)]
    missing = [d for d in dates if d not in games]

    fetched = m.get("fetched_at_utc", "?")
    try:
        age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(fetched)).total_seconds() / 3600
        age = f"{age_h:.1f} h old"
    except Exception:
        age = "age unknown"

    print(f"# AGM plan — week {week}: {dates[0]} → {dates[-1]}\n")
    print(f"_Data fetched {fetched} UTC ({age}). Failed endpoints: "
          f"{', '.join(m.get('errors', {})) or 'none'}._\n")
    if missing:
        print(f"> ⚠️ No NHL schedule for {', '.join(missing)} — counts below undercount.\n")

    # Nights
    print("## Nights\n\n| Date | Day | Games | Light |\n|---|---|---|---|")
    for d in dates:
        n = len(games.get(d, set())) // 2
        print(f"| {d} | {dt.date.fromisoformat(d):%a} | {n} | {'✅' if n <= LIGHT_MAX_GAMES else ''} |")
    light = {d for d in dates if len(games.get(d, set())) // 2 <= LIGHT_MAX_GAMES}

    # Adds used
    adds = next((v for v in walk(load("my_team"), "roster_adds")), None)
    if isinstance(adds, dict):
        print(f"\n**Adds used this week:** {adds.get('value', '?')} of 4 "
              f"(coverage {adds.get('coverage_type')} {adds.get('coverage_value')})")

    # Roster
    roster = players_in(load("my_roster_today"))
    if not roster:
        print("\n❌ No roster parsed from my_roster_today.json — check the raw file.")
        return
    unmapped = sorted({p["team"] for p in roster if p["team"] and not any(p["team"] in t for t in games.values())})
    if unmapped and games:
        print(f"\n> ⚠️ Team codes with no games found (mapping?): {', '.join(unmapped)}")

    starts, benched, empty = simulate(roster, dates, games, slots)
    print(f"\n## Roster — games and projected starts ({len(dates)} days)\n")
    print("| Player | Pos | Team | Status | Slot | Games | Light-night | Starts | Benched |")
    print("|---|---|---|---|---|---|---|---|---|")
    for p in sorted(roster, key=lambda p: (p["elig"][:1] == ["G"], -starts[p["key"]])):
        g = sum(1 for d in dates if p["team"] in games.get(d, set()))
        lg = sum(1 for d in light if p["team"] in games.get(d, set()))
        print(f"| {p['name']} | {p['pos']} | {p['team']} | {p['status'] or '—'} | {p['slot']} | "
              f"{g} | {lg} | {starts[p['key']]} | {benched[p['key']]} |")
    total_empty = sum(empty.values())
    print(f"\n**Empty skater/goalie slot-days:** {total_empty} "
          f"({', '.join(f'{d[5:]}: {n}' for d, n in empty.items() if n)})")
    print("_Goalie 'starts' = team games; actual starts depend on the crease — confirm daily._")

    base_total = sum(starts.values())

    # Free agents: marginal starts if added (no drop) and if added dropping the lowest-starts skater
    droppable = [p for p in roster if p["slot"] not in ("IR", "IR+") and p["name"] not in keepers]
    print(f"\n## Free agents — marginal starts over the window\n")
    print("_+Starts = lineup starts gained if added with an open roster spot. Net = best case after dropping "
          "one non-keeper (named); goalies only swap for goalies. Starts are games filled, not value — "
          "weigh deployment and category fit on top._\n")
    for pos in ["C", "LW", "RW", "D", "G"]:
        fas, seen = [], set()
        for page in range(4):
            for p in players_in(load(f"fa_{pos}_{page}")):
                if p["key"] not in seen:
                    seen.add(p["key"]); fas.append(p)
        lw = {p["key"]: p["stats"] for p in players_in(load(f"fa_{pos}_lastweek"))}
        if not fas:
            print(f"### {pos}\n\n_no data_\n"); continue
        rows = []
        for p in fas:
            if p["status"] in OUT_STATUSES:
                continue
            g = sum(1 for d in dates if p["team"] in games.get(d, set()))
            lg = sum(1 for d in light if p["team"] in games.get(d, set()))
            s_add, _, _ = simulate(roster + [p], dates, games, slots)
            gain = sum(s_add.values()) - base_total
            net, drop_name = None, "—"
            for dp in droppable:
                if ("G" in dp["elig"]) != ("G" in p["elig"]):
                    continue
                s_sw, _, _ = simulate([r for r in roster if r["key"] != dp["key"]] + [p], dates, games, slots)
                n = sum(s_sw.values()) - base_total
                if net is None or n > net:
                    net, drop_name = n, dp["name"]
            rows.append((net if net is not None else gain, gain, g, lg, p, lw.get(p["key"], {}), drop_name))
        rows.sort(key=lambda r: (-r[0], -r[1], -r[3]))
        print(f"### {pos}\n\n| Player | Pos | Team | Own% | Games | Light | +Starts | Net | Drop | Last wk |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for net, gain, g, lg, p, st, drop_name in rows[:a.fa]:
            lwtxt = " ".join(f"{names.get(k, k)}:{v}" for k, v in st.items() if v not in ("", "-", "0", None))[:60]
            print(f"| {p['name']} | {p['pos']} | {p['team']} | {p['owned'] or '?'} | {g} | {lg} | "
                  f"{gain} | {net} | {drop_name} | {lwtxt or '—'} |")
        print()

    # Matchup
    mu = load("my_matchup")
    if mu:
        mblk = next(walk(mu, "matchup"), {})
        teams = list(walk(mblk, "team"))
        if len(teams) >= 2:
            print("## Matchup — category totals so far\n")
            cols = []
            for t in teams[:2]:
                meta = flat(t[0]) if isinstance(t, list) and t else {}
                st = {str(s.get("stat_id")): s.get("value")
                      for s in walk(t, "stat") if isinstance(s, dict)}
                cols.append((meta.get("name", "?"), st))
            ids = [i for i in names if any(i in c[1] for c in cols)]
            print(f"| Cat | {cols[0][0]} | {cols[1][0]} |\n|---|---|---|")
            for i in ids:
                print(f"| {names[i]} | {cols[0][1].get(i, '')} | {cols[1][1].get(i, '')} |")
            print()


if __name__ == "__main__":
    main()
