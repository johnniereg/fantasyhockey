"""
Yahoo Fantasy Hockey - Data Fetcher
=====================================
Fetches league data from Yahoo Fantasy Sports API and caches it locally.
Run:  python3 scripts/fetch_data.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import LEAGUE_IDS, CURRENT_SEASON, CACHE_FILE, DATA_DIR
from scripts.yahoo_auth import get_valid_token

BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"


def yahoo_get(path, token):
    """Make an authenticated GET to the Yahoo Fantasy API (JSON format)."""
    sep = "&" if "?" in path else "?"
    url = f"{BASE_URL}{path}{sep}format=json"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token['access_token']}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} for {url}: {body}")


# ── Key discovery ─────────────────────────────────────────────────────────────

def discover_league_keys(token):
    """
    Ask Yahoo for all NHL leagues the authenticated user has ever been in.
    Returns a dict mapping league_id (str) -> full league_key (e.g. "453.l.36483").
    """
    print("🔍 Discovering your league keys from Yahoo...")
    data = yahoo_get("/users;use_login=1/games;game_codes=nhl/leagues", token)

    id_to_key = {}
    try:
        users = data["fantasy_content"]["users"]
        user  = users["0"]["user"]
        games = user[1]["games"]

        for gi in range(games.get("count", 0)):
            game_data = games[str(gi)]["game"]
            # game_data is a list: [meta_dict, {"leagues": {...}}]
            leagues_block = None
            for item in game_data:
                if isinstance(item, dict) and "leagues" in item:
                    leagues_block = item["leagues"]
                    break
            if not leagues_block:
                continue

            for li in range(leagues_block.get("count", 0)):
                league_raw = leagues_block[str(li)]["league"]
                # league_raw is a list of dicts
                league_meta = {}
                for item in league_raw:
                    if isinstance(item, dict):
                        league_meta.update(item)
                lk = league_meta.get("league_key", "")
                # league_key looks like "453.l.36483" — extract the numeric id
                parts = lk.split(".l.")
                if len(parts) == 2:
                    id_to_key[parts[1]] = lk

    except Exception as e:
        print(f"   ⚠️  Could not parse league keys: {e}")

    print(f"   ✅ Found {len(id_to_key)} leagues in your account")
    return id_to_key


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _extract_meta_dict(meta_list):
    """Flatten a Yahoo API team/league meta list into a single dict."""
    result = {}
    for item in meta_list:
        if isinstance(item, dict):
            result.update(item)
        elif isinstance(item, list):
            for sub in item:
                if isinstance(sub, dict):
                    result.update(sub)
    return result


def _safe_get(obj, key, default=None):
    """Call .get() only if obj is a dict, else return default."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


# ── League-level fetchers ─────────────────────────────────────────────────────

def fetch_league_meta(league_key, token):
    data   = yahoo_get(f"/league/{league_key}/metadata", token)
    league = data["fantasy_content"]["league"]
    # league is a list; first dict-item is the metadata
    meta = {}
    for item in league:
        if isinstance(item, dict):
            meta.update(item)
    return {
        "league_key":   meta.get("league_key"),
        "name":         meta.get("name"),
        "season":       meta.get("season"),
        "num_teams":    meta.get("num_teams"),
        "current_week": meta.get("current_week"),
        "start_week":   meta.get("start_week"),
        "end_week":     meta.get("end_week"),
        "scoring_type": meta.get("scoring_type"),
        "url":          meta.get("url"),
    }


def fetch_standings(league_key, token):
    data        = yahoo_get(f"/league/{league_key}/standings", token)
    league_list = data["fantasy_content"]["league"]

    # Find the standings block
    standings_block = None
    for item in league_list:
        if isinstance(item, dict) and "standings" in item:
            standings_block = item["standings"]
            break
    if not standings_block:
        return []

    standings_raw = standings_block[0]["teams"]

    # "count" key tells us how many teams; fall back to counting numeric keys
    count = standings_raw.get("count", 0)
    if not count:
        count = sum(1 for k in standings_raw if k.isdigit())

    teams = []
    for i in range(count):
        t = standings_raw[str(i)]["team"]
        # t[0] = list of meta dicts
        # t[1] = dict with "team_stats" and "team_points"
        # t[2] = dict with "team_standings"
        meta_list       = t[0] if len(t) > 0 else []
        stats_and_pts   = t[1] if len(t) > 1 else {}
        standings_block2 = t[2] if len(t) > 2 else {}

        meta = _extract_meta_dict(meta_list)

        # Managers is a LIST: [{"manager": {...}}]
        manager_name = "Unknown"
        managers = meta.get("managers", [])
        if isinstance(managers, list) and len(managers) > 0:
            manager_name = managers[0].get("manager", {}).get("nickname", "Unknown")
        elif isinstance(managers, dict) and "0" in managers:
            manager_name = managers["0"].get("manager", {}).get("nickname", "Unknown")

        # Stats live in t[1]
        team_stats = _safe_get(stats_and_pts, "team_stats", {})
        team_points = _safe_get(stats_and_pts, "team_points", {})

        stat_list = []
        if isinstance(team_stats, dict):
            raw_stats = team_stats.get("stats", [])
            if isinstance(raw_stats, list):
                stat_list = [s["stat"] for s in raw_stats if isinstance(s, dict) and "stat" in s]

        # Standings (rank, W/L/T) live in t[2]
        team_standings = _safe_get(standings_block2, "team_standings", {})
        outcome = team_standings.get("outcome_totals", {}) if isinstance(team_standings, dict) else {}

        teams.append({
            "rank":         team_standings.get("rank", "?") if isinstance(team_standings, dict) else "?",
            "team_key":     meta.get("team_key", ""),
            "name":         meta.get("name", "Unknown"),
            "manager":      manager_name,
            "wins":         outcome.get("wins", 0),
            "losses":       outcome.get("losses", 0),
            "ties":         outcome.get("ties", 0),
            "stats":        stat_list,
            "total_points": team_points.get("total", "0") if isinstance(team_points, dict) else "0",
        })

    teams.sort(key=lambda t: int(t["rank"]) if str(t["rank"]).isdigit() else 999)
    return teams


def fetch_scoreboard(league_key, token, week=None):
    path = f"/league/{league_key}/scoreboard"
    if week:
        path += f";week={week}"
    data        = yahoo_get(path, token)
    league_list = data["fantasy_content"]["league"]

    board = {}
    for item in league_list:
        if isinstance(item, dict) and "scoreboard" in item:
            board = _safe_get(item["scoreboard"].get("0", {}), "matchups", {})
            break

    matchups = []
    for i in range(board.get("count", 0) if isinstance(board, dict) else 0):
        m        = board[str(i)]["matchup"]
        week_val = m.get("week", "?")
        teams_in = _safe_get(m.get("0", {}), "teams", {})
        pair = []
        for j in range(teams_in.get("count", 0) if isinstance(teams_in, dict) else 0):
            team_raw = teams_in[str(j)]["team"]
            t_meta   = _extract_meta_dict(team_raw[0])
            t_pts    = _safe_get(team_raw[1], "team_points", {}) if len(team_raw) > 1 else {}
            pair.append({
                "name":   t_meta.get("name", "?"),
                "points": t_pts.get("total", "0") if isinstance(t_pts, dict) else "0",
            })
        matchups.append({"week": week_val, "teams": pair})
    return {"matchups": matchups}


def fetch_stat_categories(league_key, token):
    data        = yahoo_get(f"/league/{league_key}/settings", token)
    league_list = data["fantasy_content"]["league"]

    settings = {}
    for item in league_list:
        if isinstance(item, dict) and "settings" in item:
            settings = item["settings"]
            break

    cats_raw = {}
    if isinstance(settings, dict):
        cats_raw = settings.get("stat_categories", {}).get("stats", {}).get("stat", [])
    if not isinstance(cats_raw, list):
        cats_raw = [cats_raw] if cats_raw else []

    return [
        {"id": str(c.get("stat_id", "")), "name": c.get("display_name", c.get("name", "?"))}
        for c in cats_raw if isinstance(c, dict)
    ]


# ── Main fetch + cache ────────────────────────────────────────────────────────

def fetch_all(seasons=None):
    """
    Fetch data for all (or specified) seasons and return a combined dict.
    Also saves to CACHE_FILE for offline/dashboard use.
    """
    token   = get_valid_token()
    seasons = seasons or list(LEAGUE_IDS.keys())
    result  = {"fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"), "seasons": {}}

    # Discover correct league keys from Yahoo API
    id_to_key = discover_league_keys(token)

    for season in seasons:
        league_id = LEAGUE_IDS.get(season)
        if not league_id:
            print(f"⚠️  No league ID configured for season {season}, skipping.")
            continue

        # Use discovered key, fall back to nhl.l.ID if not found
        league_key = id_to_key.get(str(league_id), f"nhl.l.{league_id}")
        print(f"\n📡 Fetching season {season} (league key: {league_key})...")

        try:
            meta       = fetch_league_meta(league_key, token)
            cats       = fetch_stat_categories(league_key, token)
            standings  = fetch_standings(league_key, token)
            scoreboard = fetch_scoreboard(league_key, token)

            result["seasons"][season] = {
                "meta":       meta,
                "categories": cats,
                "standings":  standings,
                "scoreboard": scoreboard,
            }
            print(f"   ✅ {meta.get('name')} — {len(standings)} teams fetched")

        except Exception as e:
            print(f"   ❌ Error fetching {season}: {e}")
            result["seasons"][season] = {"error": str(e)}

    # Save cache
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 Data cached to {CACHE_FILE}")
    return result


if __name__ == "__main__":
    seasons = sys.argv[1:] or None
    data = fetch_all(seasons)
    print(f"\n✅ Done! Seasons fetched: {list(data['seasons'].keys())}")
