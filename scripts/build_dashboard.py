"""
Yahoo Fantasy Hockey - Dashboard Builder
=========================================
Reads cached data and generates a self-contained HTML dashboard.
Run:  python3 scripts/build_dashboard.py
"""

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import CACHE_FILE, BASE_DIR, CURRENT_SEASON
from scripts.corrections import (
    MANAGER_OVERRIDES, MANAGER_ALIASES, EXCLUDE_MANAGERS,
    SEASON_AWARDS, SEASON_FINANCES, TRITTY_TAX_AMOUNT,
)
from scripts.league_info import LEAGUE_DESCRIPTION, LEAGUE_RULES

OUTPUT_FILE = os.path.join(BASE_DIR, "index.html")

# Yahoo NHL stat ID → display name
STAT_NAMES = {
    "1": "G",   "2": "A",   "4": "+/-", "5": "PPP",
    "8": "SOG", "12": "PIM","19": "FW", "22": "W",
    "23": "GAA","24": "SV", "25": "SA", "26": "SV%",
    "27": "SO",
}
DISPLAY_STATS = ["1","2","5","8","22","23","26","27"]


def resolve_manager(year, team_name, raw_name):
    """Apply corrections to get the canonical manager name for a team."""
    override = MANAGER_OVERRIDES.get(str(year), {}).get(team_name)
    if override:
        name = override
    else:
        name = raw_name or "Unknown"
    return MANAGER_ALIASES.get(name, name)


def load_cache():
    if not os.path.exists(CACHE_FILE):
        print("❌  No cached data found. Run  python3 scripts/fetch_data.py  first.")
        sys.exit(1)
    with open(CACHE_FILE) as f:
        return json.load(f)


# ── Data computation ───────────────────────────────────────────────────────────

def get_playoff_cutoff(season_data):
    """
    Returns the number of teams that made the actual (non-consolation) playoffs.

    Strategy: sort teams by regular-season total_points and test candidate
    cutoffs (6 is standard; 2016-17 used 8).  A cutoff N is valid when every
    top-N-RS team has a playoff rank ≤ N AND every bottom team has rank > N.
    Falls back to 6 if nothing fits.
    """
    standings = season_data.get("standings", [])
    if not standings:
        return 6

    sorted_teams = sorted(
        standings,
        key=lambda x: float(x.get("total_points") or 0),
        reverse=True,
    )

    for cutoff in [6, 8, 4]:
        if cutoff >= len(sorted_teams):
            continue
        top_ranks = [int(t.get("rank", 99)) for t in sorted_teams[:cutoff]
                     if str(t.get("rank", "")).isdigit()]
        bot_ranks = [int(t.get("rank", 99)) for t in sorted_teams[cutoff:]
                     if str(t.get("rank", "")).isdigit()]
        if not top_ranks or not bot_ranks:
            continue
        if max(top_ranks) <= cutoff and min(bot_ranks) > cutoff:
            return cutoff

    return 6  # fallback


def compute_alltime(seasons):
    """
    Returns (champions, leaderboard, season_awards_list).
    leaderboard: list of (mgr_name, stats_dict) sorted by titles then wins.
    Each stats_dict includes season_history for the manager profile page.
    """
    managers = defaultdict(lambda: {
        "seasons": 0, "wins": 0, "losses": 0, "ties": 0,
        "points": 0.0, "titles": 0, "top3": 0,
        "playoffs": 0,
        "presidents": 0, "tritty": 0,
        "season_history": [],
    })
    champions = []
    awards_list = []   # [{year, champion, champion_team, president, president_team, tritty, tritty_team}]

    for year in sorted(seasons.keys()):
        s = seasons[year]
        standings = s.get("standings", [])
        year_awards = SEASON_AWARDS.get(str(year), {})
        pres_mgr   = year_awards.get("presidents_trophy", "")
        tritty_mgr = year_awards.get("tritty_tax", "")
        fin    = SEASON_FINANCES.get(str(year), {})
        buyin  = fin.get("buyin", 0)
        payouts = fin.get("payouts", {})

        champion_mgr  = ""
        champion_team = ""
        pres_team  = ""
        tritty_team = ""

        in_progress = (str(year) == str(CURRENT_SEASON))
        playoff_cutoff = get_playoff_cutoff(s) if not in_progress else 4

        for t in standings:
            team_name = t.get("name", "")
            mgr = resolve_manager(year, team_name, t.get("manager", "Unknown"))
            if not mgr or mgr == "Unknown" or mgr in EXCLUDE_MANAGERS:
                continue

            is_pres   = bool(not in_progress and pres_mgr   and mgr == pres_mgr)
            is_tritty = bool(not in_progress and tritty_mgr and mgr == tritty_mgr)
            prize = payouts.get(mgr, 0)

            managers[mgr]["seasons"] += 1
            managers[mgr]["wins"]    += int(t.get("wins")   or 0)
            managers[mgr]["losses"]  += int(t.get("losses") or 0)
            managers[mgr]["ties"]    += int(t.get("ties")   or 0)
            managers[mgr]["points"]  += float(t.get("total_points") or 0)
            if is_pres:
                managers[mgr]["presidents"] += 1
                pres_team = team_name
            if is_tritty:
                managers[mgr]["tritty"] += 1
                tritty_team = team_name

            rank = str(t.get("rank", ""))
            made_playoffs = bool(
                not in_progress and rank.isdigit() and int(rank) <= playoff_cutoff
            )
            if rank == "1" and not in_progress:
                managers[mgr]["titles"] += 1
                champion_mgr  = mgr
                champion_team = team_name
            if rank in ("1","2","3") and not in_progress:
                managers[mgr]["top3"] += 1
            if made_playoffs:
                managers[mgr]["playoffs"] += 1

            managers[mgr]["season_history"].append({
                "year":             year,
                "team":             team_name,
                "rank":             rank,
                "wins":             int(t.get("wins")   or 0),
                "losses":           int(t.get("losses") or 0),
                "ties":             int(t.get("ties")   or 0),
                "points":           float(t.get("total_points") or 0),
                "presidents_trophy": is_pres,
                "tritty_tax":        is_tritty,
                "made_playoffs":    made_playoffs,
                "buyin":            buyin,
                "prize":            prize,
            })

        # Champion record for history table
        champ_entry = None
        for t in standings:
            if str(t.get("rank","")) == "1":
                champ_entry = t
                break
        if champ_entry is None and standings:
            champ_entry = standings[0]
        if champ_entry:
            champions.append({
                "year":    year,
                "team":    champ_entry.get("name","?"),
                "manager": champion_mgr or "?",
                "wins":    champ_entry.get("wins", 0),
                "losses":  champ_entry.get("losses", 0),
                "ties":    champ_entry.get("ties", 0),
                "points":  champ_entry.get("total_points","?"),
            })

        in_progress = (str(year) == str(CURRENT_SEASON))
        awards_list.append({
            "year":           year,
            "champion":       "" if in_progress else champion_mgr,
            "champion_team":  "" if in_progress else champion_team,
            "president":      "" if in_progress else pres_mgr,
            "president_team": "" if in_progress else pres_team,
            "tritty":         "" if in_progress else tritty_mgr,
            "tritty_team":    "" if in_progress else tritty_team,
        })

    leaderboard = sorted(
        managers.items(),
        key=lambda x: (x[1]["titles"], x[1]["wins"]),
        reverse=True,
    )
    return champions, leaderboard, awards_list


def compute_headtohead(seasons):
    """Build a manager vs manager win/loss record from matchup data."""
    records = defaultdict(lambda: defaultdict(lambda: {"w": 0, "l": 0}))
    for year, s in seasons.items():
        matchups = s.get("scoreboard", {}).get("matchups", [])
        name_to_mgr = {}
        for t in s.get("standings", []):
            name_to_mgr[t.get("name","")] = resolve_manager(
                year, t.get("name",""), t.get("manager","Unknown")
            )
        for m in matchups:
            teams = m.get("teams", [])
            if len(teams) < 2:
                continue
            a, b = teams[0], teams[1]
            try:
                a_pts = float(a.get("points", 0) or 0)
                b_pts = float(b.get("points", 0) or 0)
            except (ValueError, TypeError):
                continue
            mgr_a = name_to_mgr.get(a.get("name",""), "")
            mgr_b = name_to_mgr.get(b.get("name",""), "")
            if not mgr_a or not mgr_b:
                continue
            if mgr_a in EXCLUDE_MANAGERS or mgr_b in EXCLUDE_MANAGERS:
                continue
            if mgr_a == "Unknown" or mgr_b == "Unknown":
                continue
            if a_pts > b_pts:
                records[mgr_a][mgr_b]["w"] += 1
                records[mgr_b][mgr_a]["l"] += 1
            elif b_pts > a_pts:
                records[mgr_b][mgr_a]["w"] += 1
                records[mgr_a][mgr_b]["l"] += 1
    return records


def compute_finances(leaderboard):
    """Derive financial totals from each manager's season_history.
    Tritty Tax is applied automatically from SEASON_AWARDS: the tax payer
    loses TRITTY_TAX_AMOUNT and the President's Trophy winner gains it."""
    result = {}
    for mgr, data in leaderboard:
        paid = sum(s["buyin"] for s in data["season_history"])
        won  = sum(s["prize"] for s in data["season_history"])
        result[mgr] = {"paid": paid, "won": won, "net": won - paid}

    # Apply Tritty Tax for every completed season that has both awards set
    for year, awards in SEASON_AWARDS.items():
        if str(year) == str(CURRENT_SEASON):
            continue
        pres_mgr   = awards.get("presidents_trophy", "")
        tritty_mgr = awards.get("tritty_tax", "")
        if pres_mgr and tritty_mgr:
            if pres_mgr in result:
                result[pres_mgr]["won"]  += TRITTY_TAX_AMOUNT
                result[pres_mgr]["net"]  += TRITTY_TAX_AMOUNT
            if tritty_mgr in result:
                result[tritty_mgr]["paid"] += TRITTY_TAX_AMOUNT
                result[tritty_mgr]["net"]  -= TRITTY_TAX_AMOUNT

    return result


# ── HTML builders ──────────────────────────────────────────────────────────────

def _esc(s):
    """Minimal HTML escaping for user-supplied strings."""
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')


def standings_table(standings, year):
    if not standings:
        return "<p class='empty'>No standings data.</p>"

    year_awards = SEASON_AWARDS.get(str(year), {})
    pres_mgr   = year_awards.get("presidents_trophy", "")
    tritty_mgr = year_awards.get("tritty_tax", "")

    sample_stats = standings[0].get("stats", [])
    stat_ids = [s.get("stat_id") for s in sample_stats if s.get("stat_id") in DISPLAY_STATS]
    stat_headers = "".join(f"<th class='num'>{STAT_NAMES.get(sid,sid)}</th>" for sid in stat_ids)

    rows = ""
    for t in standings:
        team_name = t.get("name","?")
        raw_mgr   = t.get("manager","?")
        mgr       = resolve_manager(year, team_name, raw_mgr)
        rank      = str(t.get("rank","?"))
        stat_map  = {s["stat_id"]: s["value"] for s in t.get("stats",[]) if "stat_id" in s}
        stat_cells = "".join(f"<td>{stat_map.get(sid,'—')}</td>" for sid in stat_ids)
        w, l, ti  = t.get("wins",0), t.get("losses",0), t.get("ties",0)
        pts       = t.get("total_points","—")

        badges = ""
        if pres_mgr and mgr == pres_mgr:
            badges += "<span class='badge badge-pres' title='President\\'s Trophy'>P</span>"
        if tritty_mgr and mgr == tritty_mgr:
            badges += "<span class='badge badge-tritty' title='Tritty Tax'>T</span>"

        rows += f"""<tr>
          <td class="rank-cell">{rank}</td>
          <td class="name-cell">{_esc(team_name)} {badges}<span class="mgr">{_esc(mgr)}</span></td>
          <td class="num">{w}–{l}–{ti}</td>
          <td class="num">{pts}</td>
          {stat_cells}
        </tr>"""

    return f"""<div class="table-wrap"><table>
  <thead><tr>
    <th class="num" style="width:40px">#</th><th>Team</th><th class="num">W–L–T</th><th class="num">Pts</th>
    {stat_headers}
  </tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


def matchup_section(matchups, current_week):
    if not matchups:
        return ""
    cards = ""
    for m in matchups:
        teams = m.get("teams",[])
        if len(teams) < 2:
            continue
        a, b = teams[0], teams[1]
        try:
            a_pts = float(a.get("points",0) or 0)
            b_pts = float(b.get("points",0) or 0)
        except (ValueError, TypeError):
            a_pts = b_pts = 0
        a_win = " winner" if a_pts > b_pts else ""
        b_win = " winner" if b_pts > a_pts else ""
        cards += f"""<div class="matchup">
          <div class="mu-row{a_win}">
            <span class="mu-name">{_esc(a.get("name","?"))}</span>
            <span class="mu-pts">{a.get("points","—")}</span>
          </div>
          <div class="mu-row{b_win}">
            <span class="mu-name">{_esc(b.get("name","?"))}</span>
            <span class="mu-pts">{b.get("points","—")}</span>
          </div>
        </div>"""
    return f"""<section>
  <h2>Week {current_week} Matchups</h2>
  <div class="matchup-grid">{cards}</div>
</section>"""


def leaderboard_table(leaderboard, finance_summary):
    rows = ""
    for i, (mgr, s) in enumerate(leaderboard, 1):
        pct = s["wins"] / max(s["wins"] + s["losses"] + s["ties"], 1)
        fin = finance_summary.get(mgr, {"paid": 0, "won": 0, "net": 0})
        net = fin["net"]
        if fin["paid"] > 0:
            net_str = ("+$" if net >= 0 else "-$") + str(abs(int(net)))
            net_cls = "pos-money" if net > 0 else ("neg-money" if net < 0 else "")
            net_val = net
        else:
            net_str = "—"
            net_cls = ""
            net_val = -999999   # sort no-buy-in managers to bottom
        pres_ct     = s.get("presidents", 0)
        tritty_ct   = s.get("tritty", 0)
        playoffs_ct = s.get("playoffs", 0)

        rows += f"""<tr>
          <td class="num" data-val="{i}">{i}</td>
          <td class="mgr-link" data-val="{_esc(mgr)}" onclick="showManager('{_esc(mgr)}')">{_esc(mgr)}</td>
          <td class="num" data-val="{s['seasons']}">{s["seasons"]}</td>
          <td class="num bold" data-val="{s['titles']}">{s["titles"]}</td>
          <td class="num" data-val="{playoffs_ct}">{playoffs_ct}</td>
          <td class="num" data-val="{pres_ct}">{pres_ct}</td>
          <td class="num" data-val="{tritty_ct}">{tritty_ct}</td>
          <td class="num" data-val="{s['top3']}">{s["top3"]}</td>
          <td class="num" data-val="{s['wins']}">{s["wins"]}–{s["losses"]}–{s["ties"]}</td>
          <td class="num" data-val="{pct:.4f}">{pct:.3f}</td>
          <td class="num" data-val="{s['points']:.0f}">{s["points"]:.0f}</td>
          <td class="num {net_cls}" data-val="{net_val}">{net_str}</td>
        </tr>"""

    return f"""<div class="table-wrap"><table class="sortable-table" id="leaderboard-table">
  <thead><tr>
    <th class="num sortable-col" onclick="sortTable(this)">#<span class="sort-arrow"> ↕</span></th>
    <th class="sortable-col" onclick="sortTable(this)">Manager<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Seasons<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Titles<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)" title="Playoff appearances (non-consolation)">Playoffs<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Pres.<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Tax<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Top 3<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">W–L–T<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Win%<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Total Pts<span class="sort-arrow"> ↕</span></th>
    <th class="num sortable-col" onclick="sortTable(this)">Net $<span class="sort-arrow"> ↕</span></th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


def awards_table(awards_list):
    rows = ""
    for a in reversed(awards_list):
        yr = a["year"]
        is_current = yr == str(CURRENT_SEASON)
        suffix = "<span class='in-progress'> in progress</span>" if is_current else ""

        champ = _esc(a["champion"]) if a["champion"] else "—"
        champ_team = _esc(a["champion_team"]) if a["champion_team"] else ""
        pres  = _esc(a["president"]) if a["president"] else "—"
        pres_team = _esc(a["president_team"]) if a["president_team"] else ""
        trit  = _esc(a["tritty"]) if a["tritty"] else "—"
        trit_team = _esc(a["tritty_team"]) if a["tritty_team"] else ""

        def cell(name, team):
            if name == "—":
                return "<td class='empty-cell'>—</td>"
            sub = f"<span class='mgr'>{team}</span>" if team else ""
            return f"<td class='name-cell'>{name}{sub}</td>"

        rows += f"""<tr>
          <td class="num">{yr}{suffix}</td>
          {cell(champ, champ_team)}
          {cell(pres, pres_team)}
          {cell(trit, trit_team)}
        </tr>"""

    return f"""<div class="table-wrap"><table>
  <thead><tr>
    <th class="num">Year</th>
    <th><span class="badge badge-champ">★</span> Champion</th>
    <th><span class="badge badge-pres">P</span> President's Trophy</th>
    <th><span class="badge badge-tritty">T</span> Tritty Tax</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


def headtohead_table(records, leaderboard):
    managers = [mgr for mgr, _ in leaderboard if mgr in records]
    if not managers:
        return "<p class='empty'>Not enough matchup data across seasons.</p>"

    header = "<th></th>" + "".join(
        f"<th class='hth-hdr' title='{_esc(m)}'>{_esc(m[:6])}</th>" for m in managers
    )
    rows = ""
    for mgr in managers:
        cells = f"<td class='hth-name'>{_esc(mgr)}</td>"
        for opp in managers:
            if mgr == opp:
                cells += "<td class='hth-self'>—</td>"
            else:
                r = records[mgr][opp]
                w, l = r["w"], r["l"]
                cls = " hth-pos" if w > l else (" hth-neg" if l > w else "")
                cells += f"<td class='hth-cell{cls}'>{w}–{l}</td>"
        rows += f"<tr>{cells}</tr>"

    return f"""<div class="table-wrap hth-wrap"><table class="hth-table">
  <thead><tr>{header}</tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


def managers_panel(leaderboard, h2h_records, finance_summary):
    """Build the Managers tab: selector + JS-rendered manager profiles."""
    mgr_data = {}
    for mgr, s in leaderboard:
        fin = finance_summary.get(mgr, {"paid": 0, "won": 0, "net": 0})
        h2h = {}
        for opp, rec in h2h_records.get(mgr, {}).items():
            h2h[opp] = {"w": rec["w"], "l": rec["l"]}
        mgr_data[mgr] = {
            "totals": {
                "seasons":   s["seasons"],
                "wins":      s["wins"],
                "losses":    s["losses"],
                "ties":      s["ties"],
                "titles":    s["titles"],
                "presidents": s.get("presidents", 0),
                "tritty":    s.get("tritty", 0),
                "top3":      s["top3"],
                "points":    round(s["points"], 1),
                "paid":      fin["paid"],
                "won":       fin["won"],
                "net":       fin["net"],
            },
            "seasons": sorted(
                s["season_history"], key=lambda x: x["year"], reverse=True
            ),
            "h2h": h2h,
        }

    mgr_json = json.dumps(mgr_data, ensure_ascii=False)

    manager_names = [mgr for mgr, _ in leaderboard]
    btns = "".join(
        f'<button class="mgr-btn" id="mgrbtn-{_esc(m).replace(" ","-")}" '
        f'onclick="selectManager(\'{_esc(m)}\')">{_esc(m)}</button>'
        for m in manager_names
    )
    first = _esc(manager_names[0]) if manager_names else ""

    # JS is a plain string (not f-string) to avoid brace escaping headaches
    js = (
        "var MGR_DATA = " + mgr_json + ";\n"
        "\n"
        "function selectManager(name) {\n"
        "  document.querySelectorAll('.mgr-btn').forEach(function(b){ b.classList.remove('active'); });\n"
        "  var btn = document.getElementById('mgrbtn-' + name.replace(/ /g,'-'));\n"
        "  if (btn) btn.classList.add('active');\n"
        "  var d = MGR_DATA[name];\n"
        "  if (!d) return;\n"
        "  var t = d.totals;\n"
        "  var pct = t.wins / Math.max(t.wins + t.losses + t.ties, 1);\n"
        "\n"
        "  // Finance card\n"
        "  var netStr = '—', netCls = '';\n"
        "  if (t.paid > 0) {\n"
        "    netStr = (t.net >= 0 ? '+$' : '-$') + Math.abs(t.net).toFixed(0);\n"
        "    netCls = t.net > 0 ? 'pos-money' : (t.net < 0 ? 'neg-money' : '');\n"
        "  }\n"
        "\n"
        "  // Season history rows\n"
        "  var histRows = d.seasons.map(function(s) {\n"
        "    var badges = '';\n"
        "    if (s.presidents_trophy) badges += '<span class=\"badge badge-pres\">P</span> ';\n"
        "    if (s.tritty_tax)        badges += '<span class=\"badge badge-tritty\">T</span> ';\n"
        "    var buyinStr = s.buyin > 0 ? '$' + s.buyin : '—';\n"
        "    var prizeStr = s.prize > 0 ? '+$' + s.prize : '—';\n"
        "    var netVal   = s.prize - s.buyin;\n"
        "    var netStr2  = s.buyin > 0 ? (netVal >= 0 ? '+$' : '-$') + Math.abs(netVal) : '—';\n"
        "    var netCls2  = s.buyin > 0 ? (netVal > 0 ? 'pos-money' : (netVal < 0 ? 'neg-money' : '')) : '';\n"
        "    var rankBadge = s.rank == '1' ? '<span class=\"badge badge-champ\">★</span> ' : '';\n"
        "    return '<tr>' +\n"
        "      '<td class=\"num\">' + s.year + '</td>' +\n"
        "      '<td>' + rankBadge + s.team + ' ' + badges + '</td>' +\n"
        "      '<td class=\"num\">' + (s.rank || '?') + '</td>' +\n"
        "      '<td class=\"num\">' + s.wins + '\\u2013' + s.losses + '\\u2013' + s.ties + '</td>' +\n"
        "      '<td class=\"num\">' + s.points.toFixed(1) + '</td>' +\n"
        "      '<td class=\"num\">' + buyinStr + '</td>' +\n"
        "      '<td class=\"num\">' + prizeStr + '</td>' +\n"
        "      '<td class=\"num ' + netCls2 + '\">' + netStr2 + '</td>' +\n"
        "      '</tr>';\n"
        "  }).join('');\n"
        "\n"
        "  // H2H rows (sorted by W-L diff)\n"
        "  var h2hEntries = Object.entries(d.h2h).sort(function(a,b) {\n"
        "    return (b[1].w - b[1].l) - (a[1].w - a[1].l);\n"
        "  });\n"
        "  var h2hRows = h2hEntries.map(function(entry) {\n"
        "    var opp = entry[0], r = entry[1];\n"
        "    var total = r.w + r.l;\n"
        "    var wpct = total > 0 ? (r.w / total * 100).toFixed(0) + '%' : '—';\n"
        "    var cls = r.w > r.l ? 'hth-pos' : (r.l > r.w ? 'hth-neg' : '');\n"
        "    return '<tr>' +\n"
        "      '<td>' + opp + '</td>' +\n"
        "      '<td class=\"num ' + cls + '\">' + r.w + '\\u2013' + r.l + '</td>' +\n"
        "      '<td class=\"num\">' + wpct + '</td>' +\n"
        "      '</tr>';\n"
        "  }).join('');\n"
        "\n"
        "  var html = '';\n"
        "  html += '<div class=\"mgr-stats-grid\">';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val\">' + t.seasons + '</div><div class=\"stat-lbl\">Seasons</div></div>';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val\">' + t.wins + '\\u2013' + t.losses + '\\u2013' + t.ties + '</div><div class=\"stat-lbl\">W\\u2013L\\u2013T</div></div>';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val\">' + pct.toFixed(3) + '</div><div class=\"stat-lbl\">Win %</div></div>';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val bold\">' + t.titles + '</div><div class=\"stat-lbl\">Titles</div></div>';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val\">' + t.presidents + '</div><div class=\"stat-lbl\">Pres. Trophy</div></div>';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val\">' + t.tritty + '</div><div class=\"stat-lbl\">Tritty Tax</div></div>';\n"
        "  html += '<div class=\"stat-card\"><div class=\"stat-val ' + netCls + '\">' + netStr + '</div><div class=\"stat-lbl\">Net $</div></div>';\n"
        "  html += '</div>';\n"
        "\n"
        "  html += '<section><h2>Season History</h2>';\n"
        "  html += '<div class=\"table-wrap\"><table>';\n"
        "  html += '<thead><tr><th class=\"num\">Year</th><th>Team</th><th class=\"num\">#</th><th class=\"num\">W\\u2013L\\u2013T</th><th class=\"num\">Pts</th><th class=\"num\">Buy-in</th><th class=\"num\">Prize</th><th class=\"num\">Net</th></tr></thead>';\n"
        "  html += '<tbody>' + (histRows || '<tr><td colspan=\"8\" class=\"empty\">No history</td></tr>') + '</tbody>';\n"
        "  html += '</table></div></section>';\n"
        "\n"
        "  if (h2hRows) {\n"
        "    html += '<section><h2>Head-to-Head vs Others</h2>';\n"
        "    html += '<div class=\"table-wrap\"><table>';\n"
        "    html += '<thead><tr><th>Opponent</th><th class=\"num\">W\\u2013L</th><th class=\"num\">Win%</th></tr></thead>';\n"
        "    html += '<tbody>' + h2hRows + '</tbody>';\n"
        "    html += '</table></div></section>';\n"
        "  }\n"
        "\n"
        "  document.getElementById('mgr-profile').innerHTML = html;\n"
        "}\n"
        "\n"
        "function showManager(name) {\n"
        "  showTab('managers');\n"
        "  selectManager(name);\n"
        "}\n"
        "\n"
        "// Auto-select first manager on load\n"
        "if (Object.keys(MGR_DATA).length > 0) selectManager('" + first + "');\n"
    )

    return f"""<div class="tab-panel" id="panel-managers">
  <div class="mgr-selector">{btns}</div>
  <div class="content-inner" id="mgr-profile"></div>
  <script>{js}</script>
</div>"""


def finances_panel(leaderboard, finance_summary):
    """Build the Finances tab."""
    has_data = any(v["paid"] > 0 for v in finance_summary.values())

    if not has_data:
        return """<div class="tab-panel" id="panel-finances">
  <div class="content-inner">
    <section>
      <h2>Financial Tracking</h2>
      <p class="empty">No financial data yet. Add buy-in amounts and prize payouts to
        <code>scripts/corrections.py</code> under <code>SEASON_FINANCES</code>,
        then rebuild the dashboard.</p>
    </section>
  </div>
</div>"""

    # Net leaderboard sorted by net
    net_sorted = sorted(
        finance_summary.items(),
        key=lambda x: x[1]["net"],
        reverse=True
    )
    net_rows = ""
    for i, (mgr, f) in enumerate(net_sorted, 1):
        if f["paid"] == 0 and f["won"] == 0:
            continue
        net = f["net"]
        net_str = ("+$" if net >= 0 else "-$") + str(abs(int(net)))
        net_cls = "pos-money" if net > 0 else ("neg-money" if net < 0 else "")
        net_rows += f"""<tr>
          <td class="num">{i}</td>
          <td class="mgr-link" onclick="showManager('{_esc(mgr)}')">{_esc(mgr)}</td>
          <td class="num">${int(f['paid'])}</td>
          <td class="num">${int(f['won'])}</td>
          <td class="num {net_cls}">{net_str}</td>
        </tr>"""

    net_table = f"""<div class="table-wrap"><table>
  <thead><tr>
    <th class="num">#</th><th>Manager</th><th class="num">Total Paid</th><th class="num">Total Won</th><th class="num">Net</th>
  </tr></thead>
  <tbody>{net_rows}</tbody>
</table></div>"""

    # Season-by-season history
    season_rows = ""
    for year in sorted(SEASON_FINANCES.keys(), reverse=True):
        fin = SEASON_FINANCES[year]
        buyin   = fin.get("buyin", 0)
        payouts = fin.get("payouts", {})
        payout_parts = ", ".join(
            f"<span class='fw'>{_esc(m)}</span> +${amt}"
            for m, amt in sorted(payouts.items(), key=lambda x: -x[1])
        )
        season_rows += f"""<tr>
          <td class="num">{year}</td>
          <td class="num">${buyin}</td>
          <td>{payout_parts if payout_parts else "<span class='empty-cell'>—</span>"}</td>
        </tr>"""

    season_table = f"""<div class="table-wrap"><table>
  <thead><tr>
    <th class="num">Year</th><th class="num">Buy-in</th><th>Payouts</th>
  </tr></thead>
  <tbody>{season_rows}</tbody>
</table></div>"""

    return f"""<div class="tab-panel" id="panel-finances">
  <div class="content-inner">
    <section>
      <h2>All-Time Net</h2>
      <p class="section-note">Total prize money received minus total buy-ins paid.</p>
      {net_table}
    </section>
    <section>
      <h2>Season Breakdown</h2>
      {season_table}
    </section>
  </div>
</div>"""


def league_info_panel():
    """Build the League Info tab from league_info.py."""
    rules_html = ""
    for rule in LEAGUE_RULES:
        title   = _esc(rule.get("title",""))
        content = rule.get("content","")
        # Preserve newlines as <br>
        content_html = _esc(content).replace("\n", "<br>")
        rules_html += f"""<div class="rule-block">
  <h3>{title}</h3>
  <p>{content_html}</p>
</div>"""

    return f"""<div class="tab-panel" id="panel-league">
  <div class="content-inner">
    <section>
      <h2>About the League</h2>
      <p class="league-desc">{_esc(LEAGUE_DESCRIPTION)}</p>
    </section>
    <section>
      <h2>Rules</h2>
      <div class="rules-grid">{rules_html}</div>
    </section>
  </div>
</div>"""


# ── Full page ──────────────────────────────────────────────────────────────────

def build_html(data):
    seasons     = data.get("seasons", {})
    fetched_at  = data.get("fetched_at", "unknown")
    season_list = sorted(seasons.keys(), reverse=True)

    champions, leaderboard, awards_list = compute_alltime(seasons)
    h2h_records  = compute_headtohead(seasons)
    fin_summary  = compute_finances(leaderboard)

    # ── Tab bar ───────────────────────────────────────────────────────────────
    fixed_tabs = (
        '<button class="tab-btn active" onclick="showTab(\'alltime\')" id="tab-alltime">All-Time</button>\n'
        '<button class="tab-btn" onclick="showTab(\'managers\')" id="tab-managers">Managers</button>\n'
        '<button class="tab-btn" onclick="showTab(\'finances\')" id="tab-finances">Finances</button>\n'
        '<button class="tab-btn" onclick="showTab(\'league\')" id="tab-league">League Info</button>\n'
    )
    season_tabs = "".join(
        f'<button class="tab-btn" onclick="showTab(\'{y}\')" id="tab-{y}">{y}</button>\n'
        for y in season_list
    )
    tab_btns = fixed_tabs + season_tabs

    # ── All-Time panel ────────────────────────────────────────────────────────
    alltime_panel = f"""<div class="tab-panel active" id="panel-alltime">
  <section>
    <h2>All-Time Leaderboard</h2>
    <p class="section-note">Ranked by championships, then total wins. Click a name to view their profile.</p>
    {leaderboard_table(leaderboard, fin_summary)}
  </section>
  <section>
    <h2>Season Awards</h2>
    <p class="section-note">
      <span class="badge badge-champ">★</span> Champion &nbsp;
      <span class="badge badge-pres">P</span> President's Trophy (best regular-season record) &nbsp;
      <span class="badge badge-tritty">T</span> Tritty Tax (last in regular season)
    </p>
    {awards_table(awards_list)}
  </section>
  <section>
    <h2>Head-to-Head Records</h2>
    <p class="section-note">Weekly matchup results across all seasons on record.</p>
    {headtohead_table(h2h_records, leaderboard)}
  </section>
</div>"""

    # ── Managers panel ────────────────────────────────────────────────────────
    mgr_panel = managers_panel(leaderboard, h2h_records, fin_summary)

    # ── Finances panel ────────────────────────────────────────────────────────
    fin_panel = finances_panel(leaderboard, fin_summary)

    # ── League info panel ─────────────────────────────────────────────────────
    league_panel = league_info_panel()

    # ── Season panels ─────────────────────────────────────────────────────────
    season_panels = ""
    for year in season_list:
        s = seasons[year]
        meta        = s.get("meta", {})
        league_name = meta.get("name", f"Season {year}")
        cur_week    = meta.get("current_week","?")
        num_teams   = meta.get("num_teams","?")
        scoring     = meta.get("scoring_type","?")
        start_week  = meta.get("start_week","?")
        end_week    = meta.get("end_week","?")

        # Awards banner for this season
        year_awards = SEASON_AWARDS.get(str(year), {})
        pres_mgr   = year_awards.get("presidents_trophy","")
        tritty_mgr = year_awards.get("tritty_tax","")
        awards_banner = ""
        if pres_mgr or tritty_mgr:
            parts = []
            if pres_mgr:
                parts.append(f"<span class='badge badge-pres'>P</span> <strong>President's Trophy:</strong> {_esc(pres_mgr)}")
            if tritty_mgr:
                parts.append(f"<span class='badge badge-tritty'>T</span> <strong>Tritty Tax:</strong> {_esc(tritty_mgr)}")
            awards_banner = "<div class='awards-banner'>" + " &nbsp;·&nbsp; ".join(parts) + "</div>"

        if "error" in s:
            body = f"<p class='empty'>Error loading season: {s['error']}</p>"
        else:
            matchups = s.get("scoreboard",{}).get("matchups",[])
            mu_html  = matchup_section(matchups, cur_week) if str(year) == str(CURRENT_SEASON) else ""
            body = f"""{mu_html}
<section>
  <h2>Standings</h2>
  {standings_table(s.get("standings",[]), year)}
</section>"""

        season_panels += f"""<div class="tab-panel" id="panel-{year}">
  <div class="season-meta">
    <span class="season-name">{_esc(league_name)}</span>
    <span class="season-detail">{year} &nbsp;·&nbsp; {num_teams} teams &nbsp;·&nbsp; {scoring} &nbsp;·&nbsp; weeks {start_week}–{end_week}</span>
  </div>
  {awards_banner}
  {body}
</div>"""

    # ── CSS ───────────────────────────────────────────────────────────────────
    css = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      font-size: 14px;
      color: #111;
      background: #fff;
      line-height: 1.5;
    }

    /* Header */
    .site-header {
      border-bottom: 1px solid #111;
      padding: 20px 32px 16px;
      display: flex;
      align-items: baseline;
      gap: 16px;
    }
    .site-header h1 { font-size: 1.1rem; font-weight: 700; letter-spacing: -0.01em; }
    .site-header .updated { color: #888; font-size: 0.78rem; margin-left: auto; }

    /* Tabs */
    .tab-bar {
      display: flex;
      border-bottom: 1px solid #e0e0e0;
      padding: 0 32px;
      overflow-x: auto;
      overflow-y: hidden;
    }
    .tab-btn {
      background: none; border: none;
      border-bottom: 2px solid transparent;
      padding: 10px 14px;
      font-size: 0.82rem; font-weight: 500; color: #888;
      cursor: pointer; white-space: nowrap; margin-bottom: -1px;
    }
    .tab-btn:hover { color: #111; }
    .tab-btn.active { color: #111; border-bottom-color: #111; }

    /* Content */
    .content { max-width: 1100px; margin: 0 auto; padding: 0 32px 64px; }
    .content-inner { }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    .season-meta { padding: 24px 0 16px; border-bottom: 1px solid #e0e0e0; margin-bottom: 24px; }
    .season-name { display: block; font-size: 1.15rem; font-weight: 700; }
    .season-detail { font-size: 0.8rem; color: #888; margin-top: 2px; display: block; }

    section { margin-top: 36px; }
    section h2 {
      font-size: 0.72rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.08em;
      color: #888; margin-bottom: 12px;
    }
    .section-note { font-size: 0.78rem; color: #aaa; margin-bottom: 12px; margin-top: -8px; }
    code { font-family: monospace; font-size: 0.85em; background: #f5f5f5; padding: 1px 4px; border-radius: 3px; }

    /* Badges */
    .badge {
      display: inline-block;
      font-size: 0.65rem; font-weight: 700;
      padding: 1px 5px; border-radius: 3px;
      line-height: 1.4; vertical-align: middle;
      margin-right: 2px;
    }
    .badge-pres   { background: #e8f0fe; color: #1a56db; }
    .badge-tritty { background: #fef3c7; color: #92400e; }
    .badge-champ  { background: #fef9c3; color: #854d0e; }

    /* Awards banner */
    .awards-banner {
      font-size: 0.85rem;
      padding: 10px 0 20px;
      color: #444;
      border-bottom: 1px solid #f0f0f0;
      margin-bottom: 8px;
    }

    /* Tables */
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    thead th {
      text-align: left;
      font-size: 0.72rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.06em;
      color: #888; padding: 6px 12px 6px 0;
      border-bottom: 1px solid #e0e0e0; white-space: nowrap;
    }
    tbody tr { border-bottom: 1px solid #f0f0f0; }
    tbody tr:hover { background: #fafafa; }
    tbody td { padding: 9px 12px 9px 0; color: #111; vertical-align: middle; }
    .num { text-align: right; padding-right: 16px; color: #444; font-variant-numeric: tabular-nums; }
    thead th.num { color: #888; }
    .bold { font-weight: 700; color: #111 !important; }
    .rank-cell { color: #aaa; font-size: 0.78rem; width: 32px; }
    .name-cell { font-weight: 600; }
    .mgr { display: block; font-weight: 400; font-size: 0.78rem; color: #888; margin-top: 1px; }
    .mgr-col { color: #666; }
    .empty-cell { color: #ccc; }
    .in-progress { font-size: 0.72rem; color: #aaa; font-weight: 400; }
    .empty { color: #aaa; font-size: 0.85rem; padding: 12px 0; }
    .fw { font-weight: 600; }
    .pos-money { color: #16a34a !important; font-weight: 600; }
    .neg-money { color: #dc2626 !important; }
    .mgr-link { cursor: pointer; text-decoration: underline; text-underline-offset: 2px; text-decoration-color: #ccc; }
    .mgr-link:hover { text-decoration-color: #111; }

    /* Sortable table */
    .sortable-col { cursor: pointer; user-select: none; white-space: nowrap; }
    .sortable-col:hover { background: #f0f0f0; }
    .sort-arrow { font-size: 0.7rem; color: #bbb; margin-left: 2px; }
    .sortable-col.sort-asc .sort-arrow::after  { content: " ▲"; color: #333; }
    .sortable-col.sort-desc .sort-arrow::after { content: " ▼"; color: #333; }
    .sortable-col.sort-asc .sort-arrow,
    .sortable-col.sort-desc .sort-arrow { display: none; }

    /* Matchups */
    .matchup-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1px; background: #e0e0e0; border: 1px solid #e0e0e0;
    }
    .matchup { background: #fff; padding: 12px 14px; }
    .mu-row {
      display: flex; justify-content: space-between; align-items: center;
      padding: 3px 0; font-size: 0.85rem; color: #888;
    }
    .mu-row.winner { color: #111; font-weight: 600; }
    .mu-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px; }
    .mu-pts { font-variant-numeric: tabular-nums; font-size: 0.9rem; }

    /* Head-to-Head */
    .hth-wrap { max-width: 100%; }
    .hth-table { font-size: 0.78rem; }
    .hth-table thead th { text-align: center; }
    .hth-hdr { max-width: 52px; overflow: hidden; text-overflow: ellipsis; text-align: center; }
    .hth-name { font-weight: 600; color: #111; white-space: nowrap; padding-right: 16px !important; }
    .hth-cell { text-align: center; color: #666; }
    .hth-pos { color: #111; font-weight: 600; }
    .hth-neg { color: #aaa; }
    .hth-self { text-align: center; color: #ddd; }

    /* Manager selector */
    .mgr-selector {
      display: flex; flex-wrap: wrap; gap: 6px;
      padding: 24px 0 20px;
      border-bottom: 1px solid #e0e0e0; margin-bottom: 4px;
    }
    .mgr-btn {
      background: none; border: 1px solid #ddd;
      padding: 5px 12px; border-radius: 4px;
      font-size: 0.82rem; cursor: pointer; color: #444;
    }
    .mgr-btn:hover { border-color: #aaa; color: #111; }
    .mgr-btn.active { border-color: #111; color: #111; font-weight: 600; background: #f5f5f5; }

    /* Manager stat cards */
    .mgr-stats-grid {
      display: flex; flex-wrap: wrap; gap: 12px;
      padding: 24px 0 8px;
    }
    .stat-card {
      border: 1px solid #e0e0e0; border-radius: 6px;
      padding: 12px 18px; min-width: 90px; text-align: center;
    }
    .stat-val { font-size: 1.25rem; font-weight: 700; color: #111; line-height: 1.2; }
    .stat-lbl { font-size: 0.7rem; color: #888; margin-top: 3px; }

    /* League info */
    .league-desc { font-size: 0.9rem; line-height: 1.7; color: #333; max-width: 700px; }
    .rules-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin-top: 12px; }
    .rule-block { border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px 18px; }
    .rule-block h3 { font-size: 0.8rem; font-weight: 700; color: #111; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.04em; }
    .rule-block p { font-size: 0.84rem; color: #444; line-height: 1.6; }

    @media (max-width: 600px) {
      .site-header, .tab-bar, .content { padding-left: 16px; padding-right: 16px; }
    }
    """

    # ── JavaScript ────────────────────────────────────────────────────────────
    js_main = """
function showTab(id) {
  document.querySelectorAll('.tab-panel').forEach(function(p){ p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
  document.getElementById('panel-' + id).classList.add('active');
  document.getElementById('tab-' + id).classList.add('active');
}

function sortTable(th) {
  var table = th.closest('table');
  var tbody = table.querySelector('tbody');
  var ths   = Array.from(th.closest('tr').querySelectorAll('th'));
  var col   = ths.indexOf(th);
  var asc   = !th.classList.contains('sort-asc');

  // Clear sort state on all headers
  ths.forEach(function(h) { h.classList.remove('sort-asc', 'sort-desc'); });
  th.classList.add(asc ? 'sort-asc' : 'sort-desc');

  // Collect and sort rows
  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {
    var aCell = a.querySelectorAll('td')[col];
    var bCell = b.querySelectorAll('td')[col];
    var aVal  = aCell ? aCell.getAttribute('data-val') : '';
    var bVal  = bCell ? bCell.getAttribute('data-val') : '';
    // Try numeric comparison first
    var aNum = parseFloat(aVal);
    var bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return asc ? aNum - bNum : bNum - aNum;
    }
    // Fall back to string
    return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
}
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tim McCabe Memorial Cup</title>
  <style>{css}</style>
</head>
<body>

<header class="site-header">
  <h1>Tim McCabe Memorial Cup</h1>
  <span class="updated">Updated {fetched_at}</span>
</header>

<nav class="tab-bar">
  {tab_btns}
</nav>

<div class="content">
  {alltime_panel}
  {mgr_panel}
  {fin_panel}
  {league_panel}
  {season_panels}
</div>

<script>{js_main}</script>
</body>
</html>"""


if __name__ == "__main__":
    print("📊 Building dashboard...")
    data = load_cache()
    html = build_html(data)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"✅ Dashboard written to: {OUTPUT_FILE}")
