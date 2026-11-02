"""
AGM projections — per-game category rates that don't overreact to small samples
==============================================================================
    python3 scripts/agm_project.py                       # our roster
    python3 scripts/agm_project.py --players "Matt Coronato,J.T. Miller"
    python3 scripts/agm_project.py --top 40              # best projected skaters on no roster

Method (each piece is tested in agm_backtest.py; defaults are the tested winners):
  prior    = last 3 seasons' per-game rates (data/history), weighted 3:2:1 by recency x games.
             No NHL history: position average per minute of ice time x his ice time.
  blend    = (prior x K + this season's totals) / (K + this season's GP). K differs by category
             because categories stabilise at different speeds (goals slowly, PIM fast).
  role     = scoring categories scaled by (recent TOI / prior TOI) ^ BETA: ice time this season is
             real information early; finishing luck is not.
  age      = small multiplier on scoring (young up, old down), only if the backtest keeps it.
Skater categories: G, A, PPP, PIM, PM (+/-), GWG, plus SOG for reference.
Goalies: SV% blended toward the prior with K_SA shots; W% and start share from this season.

Import project(as_of) for other scripts. as_of=None uses everything (live); a date uses only
box scores before it (backtests). PPP and GWG for the current season come from the season summary
when live, and from the prior only in backtests (box scores carry no PP assists or GWG).
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import IN, load  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "data", "history")
CATS = ["G", "A", "PPP", "PIM", "PM", "GWG", "SOG"]
SCORING = {"G", "A", "PPP", "GWG", "SOG"}
# Games of current-season data worth as much as the prior. Chosen in agm_backtest.py on the same
# days it reports (no holdout yet); K x0.5..x2 and BETA 0.4..1 all land within ~1%.
K = {"G": 40, "A": 40, "PPP": 40, "PIM": 25, "PM": 80, "GWG": 80, "SOG": 15}
BETA = 0.7          # role (ice time) elasticity for scoring categories
USE_AGE = False     # backtest decides
K_SA = 1500         # shots against for goalie SV% prior
PRIOR_W = {0: 3, 1: 2, 2: 1}   # seasons back -> weight
SUMMARY_MAP = {"G": "goals", "A": "assists", "PPP": "ppPoints", "PIM": "penaltyMinutes",
               "PM": "plusMinus", "GWG": "gameWinningGoals", "SOG": "shots"}


def _hist(report, season):
    p = os.path.join(HIST, f"{report}_{season}.json")
    return json.load(open(p))["rows"] if os.path.exists(p) else []


def seasons():
    cur = (json.load(open(os.path.join(HIST, "manifest.json"))).get("current_season")
           if os.path.exists(os.path.join(HIST, "manifest.json")) else "20262027")
    y = int(cur[:4])
    return cur, [f"{y - i}{y - i + 1}" for i in (1, 2, 3)]


def age_factor(age):
    if age is None:
        return 1.0
    if age <= 22:
        return 1.06
    if age <= 25:
        return 1.02
    if age <= 29:
        return 1.0
    if age <= 32:
        return 0.97
    return 0.93


def _box_rows():
    rows = []
    for f in sorted(glob.glob(os.path.join(IN, "skater_games", "*.json"))):
        d = json.load(open(f))
        rows += [dict(zip(d["cols"], r)) for r in d["rows"]]
    return rows


_CACHE = {}


def priors():
    if "priors" in _CACHE:
        return _CACHE["priors"]
    cur, prev = seasons()
    acc = defaultdict(lambda: {"w": 0.0, "gpw": 0.0, **{c: 0.0 for c in CATS}, "toi": 0.0, "gp": 0})
    for i, s in enumerate(prev):
        for r in _hist("skater_summary", s):
            gp = r.get("gamesPlayed") or 0
            if not gp:
                continue
            a = acc[r["playerId"]]
            w = PRIOR_W[i] * gp
            a["w"] += w
            a["gp"] += gp
            for c, k in SUMMARY_MAP.items():
                a[c] += PRIOR_W[i] * (r.get(k) or 0)
            a["toi"] += w * (r.get("timeOnIcePerGame") or 0) / 60
            a["pos"] = r.get("positionCode")
    # a[c] = sum(weight x count), a["w"] = sum(weight x gp)  ->  per-game rate = a[c] / a["w"]
    out = {pid: {"gp": a["gp"], "toi": a["toi"] / a["w"], "pos": a.get("pos"),
                 **{c: a[c] / a["w"] for c in CATS}} for pid, a in acc.items() if a["w"]}
    # league per-minute baseline by position group, for players with no NHL history
    tot = defaultdict(lambda: defaultdict(float))
    for pid, p in out.items():
        if p["gp"] < 40:
            continue
        grp = "D" if p["pos"] == "D" else "F"
        for c in CATS:
            tot[grp][c] += p[c] * p["gp"]
        tot[grp]["min"] += p["toi"] * p["gp"]
    per_min = {g: {c: t[c] / t["min"] for c in CATS} for g, t in tot.items()}
    births = {}
    for s in [cur] + prev:
        for r in _hist("skater_bios", s):
            births.setdefault(r["playerId"], r.get("birthDate"))
    _CACHE["priors"] = (out, per_min, births)
    return _CACHE["priors"]


def project(as_of=None, k_scale=1.0, beta=None, use_age=None, prior_only=False, current_only=False):
    """pid -> projection dict. as_of: ISO date; only box scores before it are used."""
    beta = BETA if beta is None else beta
    use_age = USE_AGE if use_age is None else use_age
    pri, per_min, births = priors()
    cur, _ = seasons()
    rows = _CACHE.setdefault("box", _box_rows())
    by = defaultdict(list)
    for r in rows:
        if as_of is None or r["date"] < as_of:
            by[r["player_id"]].append(r)
    live = {}
    if as_of is None:
        live = {r["playerId"]: r for r in _hist("skater_summary", cur)}
    ref = dt.date.fromisoformat(as_of) if as_of else dt.date.today()
    out = {}
    for pid in set(by) | set(live):
        rs = sorted(by.get(pid, []), key=lambda r: r["date"])
        gp = len(rs)
        if as_of is None and pid in live:
            L = live[pid]
            gp = L["gamesPlayed"]
            tot = {c: L.get(SUMMARY_MAP[c]) or 0 for c in CATS}
            toi_season = (L.get("timeOnIcePerGame") or 0) / 60
            name, team, pos = L["skaterFullName"], (L.get("teamAbbrevs") or "").split(",")[-1], L.get("positionCode")
        else:
            if not rs:
                continue
            tot = {"G": sum(r["g"] or 0 for r in rs), "A": sum(r["a"] or 0 for r in rs),
                   "PIM": sum(r["pim"] or 0 for r in rs), "PM": sum(r["pm"] or 0 for r in rs),
                   "SOG": sum(r["sog"] or 0 for r in rs), "PPP": None, "GWG": None}
            toi_season = sum(r["toi_min"] or 0 for r in rs) / gp
            name, team, pos = rs[-1]["name"], rs[-1]["team"], rs[-1]["pos"]
        toi_recent = (sum(r["toi_min"] or 0 for r in rs[-5:]) / len(rs[-5:])) if rs else toi_season
        grp = "D" if pos == "D" else "F"
        p = pri.get(pid)
        if p and p["gp"] >= 10:
            prior = {c: p[c] for c in CATS}
            prior_toi = p["toi"]
            kmult = min(1.0, p["gp"] / 82)  # thin history counts for less
        else:
            base_toi = toi_season or 12
            prior = {c: per_min.get(grp, {}).get(c, 0) * base_toi for c in CATS}
            prior_toi = base_toi
            kmult = 0.35
        rate = {}
        for c in CATS:
            k = K[c] * k_scale * kmult
            if prior_only or tot.get(c) is None or gp == 0:
                rate[c] = prior[c]
            elif current_only:
                rate[c] = tot[c] / gp
            else:
                rate[c] = (prior[c] * k + tot[c]) / (k + gp)
        role = (toi_recent / prior_toi) if prior_toi and toi_recent else 1.0
        role = max(0.6, min(1.6, role))
        bd = births.get(pid)
        age = None
        if bd:
            b = dt.date.fromisoformat(bd)
            age = (ref - b).days / 365.25
        # GWG is mostly luck: project it as the league share of goals that win games x projected goals
        rate["GWG"] = rate["G"] * _gwg_share()
        for c in SCORING - {"GWG"}:
            if not prior_only and not current_only:
                rate[c] *= role ** beta
            if use_age:
                rate[c] *= age_factor(age)
        rate["GWG"] = rate["G"] * _gwg_share()
        out[pid] = {"pid": pid, "name": name, "team": team, "pos": pos, "grp": grp, "gp": gp,
                    "toi": round(toi_season, 1), "toi_recent": round(toi_recent, 1),
                    "prior_gp": p["gp"] if p else 0, "age": round(age, 1) if age else None,
                    **{c: rate[c] for c in CATS}}
    return out


def _gwg_share():
    if "gwg" not in _CACHE:
        _, prev = seasons()
        g = w = 0
        for s in prev:
            for r in _hist("skater_summary", s):
                g += r.get("goals") or 0
                w += r.get("gameWinningGoals") or 0
        _CACHE["gwg"] = w / g if g else 0.16
    return _CACHE["gwg"]


TEAM_ABBR = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF", "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR", "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL", "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN", "Montréal Canadiens": "MTL",
    "Nashville Predators": "NSH", "New Jersey Devils": "NJD", "New York Islanders": "NYI",
    "New York Rangers": "NYR", "Ottawa Senators": "OTT", "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT", "San Jose Sharks": "SJS", "Seattle Kraken": "SEA", "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR", "Utah Mammoth": "UTA", "Utah Hockey Club": "UTA",
    "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG"}


def team_context(k_games=20):
    """Team GA/GP, SA/GP and win% blended: last season (k_games worth) + this season.
    Tested: team shots against and GA carry over season to season (r 0.55-0.66 and 0.29-0.49);
    individual goalie SV% does not (r -0.12, 38 goalies with 800+ shots both periods)."""
    cur, prev = seasons()
    last = {TEAM_ABBR.get(r["teamFullName"]): r for r in _hist("team_summary", prev[0])}
    out = {}
    for r in _hist("team_summary", cur):
        L = last.get(TEAM_ABBR.get(r["teamFullName"]), r)
        gp = r.get("gamesPlayed") or 0
        def bl(key, per_game=True):
            lv = L.get(key) or 0
            cv = r.get(key) or 0
            return (lv * k_games + cv * gp) / (k_games + gp)
        winp_l = (L.get("wins") or 0) / max(1, L.get("gamesPlayed") or 1)
        winp_c = (r.get("wins") or 0) / max(1, gp)
        out[TEAM_ABBR.get(r["teamFullName"], r["teamFullName"])] = {"ga_pg": bl("goalsAgainstPerGame"), "sa_pg": bl("shotsAgainstPerGame"),
                                  "win_pct": (winp_l * k_games + winp_c * gp) / (k_games + gp), "gp": gp}
    return out


def goalie_projection():
    """Live goalie view: start share and the team in front of him; SV% shown but not trusted."""
    cur, _ = seasons()
    teams = team_context()
    out = {}
    for r in _hist("goalie_summary", cur):
        pid = r["playerId"]
        gs = r.get("gamesStarted") or 0
        out[pid] = {"pid": pid, "name": r["goalieFullName"], "team": (r.get("teamAbbrevs") or "").split(",")[-1],
                    "gs": gs, "w_rate": (r.get("wins") or 0) / gs if gs else 0, "sv_season": r.get("savePct"),
                    "gaa_season": r.get("goalsAgainstAverage")}
    return out, teams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players")
    ap.add_argument("--top", type=int)
    a = ap.parse_args()
    pr = project()
    if a.players:
        want = [s.strip().lower() for s in a.players.split(",")]
        sel = [p for p in pr.values() if p["name"].lower() in want]
    else:
        from agm_plan import players_in
        names = {p["name"].lower() for p in players_in(load("my_roster_today"))}
        sel = [p for p in pr.values() if p["name"].lower() in names]
        if a.top:
            sel = sorted(pr.values(), key=lambda p: -(p["G"] + p["A"]))[:a.top]
    print("| Player | Team | Age | GP | TOI (recent) | G | A | PPP | PIM | +/- | GWG | SOG |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for p in sorted(sel, key=lambda p: -(p["G"] + p["A"])):
        print(f"| {p['name']} | {p['team']} | {p['age'] or '?'} | {p['gp']} | {p['toi']} ({p['toi_recent']}) | "
              + " | ".join(f"{p[c]:.2f}" for c in CATS[:6]) + f" | {p['SOG']:.1f} |")
    print("\n_Per-game projections. Blend of last 3 seasons and this season; see module docstring._")


if __name__ == "__main__":
    main()
