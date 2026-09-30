"""
AGM week view — offline summary of data/inseason/ for the weekly matchup doc
============================================================================
Run after `git pull`:
    python3 scripts/agm_week.py                 # from today (ET) to end of the fantasy week
    python3 scripts/agm_week.py --from 2026-10-01

Reads the per-date lineups saved by fetch_inseason.py (my_roster_<date>, opp_roster_<date>),
so every lineup statement is about the lineup actually set for that date. If a date has no
saved lineup, it says so and makes no lineup call for that date. Nothing here calls Yahoo/NHL.

Sections: data freshness · scoreboard · lineup check per night (us) · starts remaining
(us vs opponent) · goalies · opponent moves this week.
"""

import argparse
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agm_plan import (load, flat, walk, players_in, nhl_games_by_date, roster_slots,
                      stat_names, best_lineup, OUT_STATUSES)

ET = ZoneInfo("America/Toronto")
LOWER_IS_BETTER = {"GAA"}
ACTIVE_SKIP = {"BN", "IR", "IR+", "IL", "IL+", "NA"}


def is_active(p):
    return p["slot"] and p["slot"] not in ACTIVE_SKIP


def night(roster, games, d, slots):
    """What the saved lineup for date d does, vs the best lineup possible from that roster."""
    playing = [p for p in roster if p["team"] in games.get(d, set())]
    set_starts = [p for p in playing if is_active(p) and p["status"] not in OUT_STATUSES]
    benched_playing = [p for p in playing if p["slot"] == "BN" and p["status"] not in OUT_STATUSES]
    hurt_active = [p for p in roster if is_active(p) and p["status"] in OUT_STATUSES]
    # Best case: one goalie per NHL team; injured/out excluded
    eligible, g_teams = [], set()
    for p in playing:
        if p["status"] in OUT_STATUSES or p["slot"] in ("IR", "IR+"):
            continue
        if "G" in p["elig"]:
            if p["team"] in g_teams:
                continue
            g_teams.add(p["team"])
        eligible.append(p)
    placed, _ = best_lineup(eligible, slots)
    return set_starts, benched_playing, hurt_active, len(placed)


def rosters_for(prefix, dates):
    """{date: roster or None} from <prefix>_roster_<date>.json."""
    return {d: (players_in(load(f"{prefix}_roster_{d}")) or None) for d in dates}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start")
    a = ap.parse_args()

    m = load("manifest") or {}
    settings = load("league_settings")
    slots, names = roster_slots(settings), stat_names(settings)
    g_min = int(next(walk(settings, "min_games_played"), 3) or 3)
    games = nhl_games_by_date()
    now_et = dt.datetime.now(ET)
    today = now_et.date()

    week = m.get("current_week")
    wk = (m.get("week_dates") or {}).get(str(week))
    w0, w1 = (dt.date.fromisoformat(wk[0]), dt.date.fromisoformat(wk[1])) if wk else (today, today + dt.timedelta(days=6))
    start = dt.date.fromisoformat(a.start) if a.start else max(w0, today)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range((w1 - start).days + 1)]

    # ── Freshness ────────────────────────────────────────────────────────
    fetched = m.get("fetched_at_utc")
    try:
        age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(fetched)).total_seconds() / 3600
    except Exception:
        age_h = None
    print(f"# AGM week {week} — {w0} → {w1} (view from {dates[0] if dates else '?'})\n")
    print(f"- Data fetched: {fetched} UTC ({f'{age_h:.1f} h old' if age_h is not None else 'age unknown'})")
    print(f"- Fetch date (ET): {m.get('date_et')} · lineups saved for: {', '.join(m.get('roster_dates', [])) or 'NONE (old fetch script)'}")
    print(f"- Failed endpoints: {', '.join(m.get('errors', {})) or 'none'}")
    if not m.get("roster_dates"):
        print("- ⚠️ No per-date lineups in this fetch. Do NOT make lineup calls from my_roster_today "
              f"(it is the lineup for {m.get('date_et')} only).")
    print()

    # ── Scoreboard ───────────────────────────────────────────────────────
    mu = load("my_matchup")
    my_tk, opp_tk = m.get("team_key"), m.get("opp_team_key")
    opp_name = "Opponent"
    if mu:
        mblk = next(walk(mu, "matchup"), {})
        teams = [t for t in walk(mblk, "team") if isinstance(t, list) and t]
        cols = []
        for t in teams[:2]:
            meta = flat(t[0])
            st = {str(s.get("stat_id")): s.get("value") for s in walk(t, "stat") if isinstance(s, dict)}
            rem = next(walk(t, "team_remaining_games"), {}) or {}
            cols.append((meta.get("team_key"), meta.get("name", "?"), st, (rem.get("total") or {})))
        cols.sort(key=lambda c: c[0] != my_tk)
        if len(cols) == 2:
            opp_tk = opp_tk or cols[1][0]
            opp_name = cols[1][1]
            print(f"## Scoreboard — {cols[0][1]} vs {cols[1][1]}\n")
            print(f"| Cat | Us | Them | Lead |\n|---|---|---|---|")
            score = [0, 0, 0]
            for sid, nm in names.items():
                if sid not in cols[0][2] and sid not in cols[1][2]:
                    continue
                if nm in ("GA", "SV", "SA"):
                    continue
                u, t = cols[0][2].get(sid, ""), cols[1][2].get(sid, "")
                if u in (None, "") and t in (None, ""):
                    print(f"| {nm} | — | — | no games yet |"); score[2] += 1
                    continue
                try:
                    fu, ft = float(u or 0), float(t or 0)
                    if fu == ft:
                        lead = "tied"; score[2] += 1
                    elif (fu < ft) == (nm in LOWER_IS_BETTER):
                        lead = "us"; score[0] += 1
                    else:
                        lead = "them"; score[1] += 1
                except ValueError:
                    lead = "?"
                print(f"| {nm} | {u} | {t} | {lead} |")
            print(f"\n**Category score:** {score[0]}-{score[1]}-{score[2]} (W-L-T). "
                  "Ratio cats (GAA, SV%) with few goalie games are volatile.")
            for _, nm, _, rem in cols:
                if rem:
                    print(f"- Yahoo games: {nm} — completed {rem.get('completed_games')}, live {rem.get('live_games')}, "
                          f"remaining {rem.get('remaining_games')}")
            print()

    # ── Our lineup, night by night ──────────────────────────────────────
    mine = rosters_for("my", dates)
    theirs = rosters_for("opp", dates)
    print("## Our lineup by night (from the lineup saved for each date)\n")
    print("| Date | NHL games | Set starts | Best possible | Playing on BN | Injured in active slot |")
    print("|---|---|---|---|---|---|")
    my_set = my_best = 0
    for d in dates:
        r = mine.get(d)
        n = len(games.get(d, set())) // 2
        if not r:
            print(f"| {d} {dt.date.fromisoformat(d):%a} | {n} | — no saved lineup, no call — | | | |")
            continue
        s, bn, hurt, best = night(r, games, d, slots)
        my_set += len(s); my_best += best
        fix = f"⚠️ {', '.join(p['name'] for p in bn)}" if bn and best > len(s) else \
              (", ".join(p["name"] for p in bn) + " (no open slot)" if bn else "—")
        print(f"| {d} {dt.date.fromisoformat(d):%a} | {n} | {len(s)} | {best} | {fix} | "
              f"{', '.join(p['name'] + ' (' + p['status'] + ')' for p in hurt) or '—'} |")
    print("\n_⚠️ in 'Playing on BN' = a start is being left on the bench for that date. "
          "Later dates may simply not be set yet; Yahoo lineups for future days default to the current one._\n")

    # ── Starts remaining, us vs them ─────────────────────────────────────
    opp_set = opp_best = 0
    have_opp = any(theirs.values())
    for d in dates:
        r = theirs.get(d)
        if r:
            s, _, _, best = night(r, games, d, slots)
            opp_set += len(s); opp_best += best
    print("## Starts remaining this week (skaters + goalies)\n")
    print(f"| | Set in lineup | Best possible |\n|---|---|---|")
    print(f"| Us | {my_set} | {my_best} |")
    print(f"| {opp_name} | {opp_set if have_opp else 'no data'} | {opp_best if have_opp else 'no data'} |\n")

    # ── Goalies ─────────────────────────────────────────────────────────
    latest = next((mine[d] for d in dates if mine.get(d)), None) or players_in(load("my_roster_today"))
    print(f"## Goalies — floor {g_min} appearances/week\n")
    for p in [p for p in latest if "G" in p["elig"]]:
        gd = [d[5:] for d in dates if p["team"] in games.get(d, set())]
        print(f"- {p['name']} ({p['team']}, {p['status'] or 'healthy'}): team games left {len(gd)} — {', '.join(gd) or 'none'}")
    if have_opp:
        opp_latest = next(r for r in theirs.values() if r)
        for p in [p for p in opp_latest if "G" in p["elig"]]:
            gd = [d[5:] for d in dates if p["team"] in games.get(d, set())]
            print(f"- Opp: {p['name']} ({p['team']}): team games left {len(gd)} — {', '.join(gd) or 'none'}")
    print("\n_Team games are an upper bound; appearances so far come from the matchup/box scores, not this table._\n")

    # ── Opponent moves ──────────────────────────────────────────────────
    print(f"## Opponent moves — {opp_name}\n")
    log = [e for e in (load("roster_moves_log") or []) if e.get("team_key") == opp_tk
           and e.get("date_et", "") >= w0.isoformat()]
    tx = []
    for t in walk(load("transactions") or {}, "transaction"):
        if not isinstance(t, list):
            continue
        meta = flat(t[0]) if isinstance(t[0], dict) else flat(t)
        ts = dt.datetime.fromtimestamp(int(meta.get("timestamp", 0)), ET)
        if ts.date() < w0 - dt.timedelta(days=1):
            continue
        for p in walk(t, "player"):
            if not isinstance(p, list):
                continue
            info = flat(p[0])
            td = flat(next(walk(p, "transaction_data"), []))
            if opp_tk in (td.get("destination_team_key"), td.get("source_team_key")):
                tx.append((ts, td.get("type"), (info.get("name") or {}).get("full"),
                           info.get("display_position"), info.get("editorial_team_abbr")))
    if tx:
        print("From Yahoo transactions:")
        for ts, typ, nm, pos, team in sorted(tx):
            print(f"- {ts:%a %m-%d %H:%M} ET — {typ}: {nm} ({pos}, {team})")
    if log:
        print("From roster diffs between fetches:")
        for e in log:
            add = ", ".join(f"{p['name']} ({p['pos']}, {p['team']})" for p in e["added"]) or "—"
            drop = ", ".join(f"{p['name']} ({p['pos']}, {p['team']})" for p in e["dropped"]) or "—"
            print(f"- detected {e['detected_at_utc']} (since {e.get('since_utc')}): +{add} / −{drop}")
    if not tx and not log:
        print("- No opponent adds/drops found this week"
              + ("" if load("roster_moves_log") is not None else " (roster diff log not started yet)") + ".")


if __name__ == "__main__":
    main()
