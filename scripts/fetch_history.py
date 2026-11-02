"""
Fetch season-level NHL stats for projections: prior seasons (once) + current season (every run)
==============================================================================================
    python3 scripts/fetch_history.py            # current season + any missing prior season
    python3 scripts/fetch_history.py --force    # refetch everything

Source: the NHL stats REST API (api.nhle.com/stats/rest/en), regular season only.
Writes data/history/<report>_<seasonId>.json as {"season", "report", "fetched_at_utc", "rows": [...]}.

Reports:
  skater_summary   GP, G, A, PPP, PIM, +/-, GWG, shots, TOI/GP
  skater_powerplay PP TOI per game and PP TOI share
  skater_bios      birth date (age), position
  goalie_summary   GS, W, SV%, GAA, SHO, shots against
  team_summary     team GA/GP, shots against/GP (goalie context)

Called from .github/workflows/update.yml. The NHL API is not reachable from Claude's sandbox;
only the GitHub Action fetches it.
"""
import argparse
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request

BASE = "https://api.nhle.com/stats/rest/en"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "history")
REPORTS = {
    "skater_summary": "skater/summary",
    "skater_powerplay": "skater/powerplay",
    "skater_bios": "skater/bios",
    "goalie_summary": "goalie/summary",
    "team_summary": "team/summary",
}
PRIOR = ["20232024", "20242025", "20252026"]


def current_season(today=None):
    t = today or dt.date.today()
    y = t.year if t.month >= 9 else t.year - 1
    return f"{y}{y + 1}"


def get(path, params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "agm-fetch"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)


def fetch_report(report, season):
    rows, start = [], 0
    exp = f"seasonId={season} and gameTypeId=2"
    while True:
        params = {"limit": 100, "start": start, "cayenneExp": exp}
        if report != "team_summary":
            params["isAggregate"] = "false"
            params["isGame"] = "false"
        d = get(REPORTS[report], params)
        page = d.get("data", [])
        rows += page
        start += len(page)
        if not page or start >= d.get("total", 0):
            break
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    cur = current_season()
    errors = {}
    for season in PRIOR + [cur]:
        for report in REPORTS:
            fn = os.path.join(OUT, f"{report}_{season}.json")
            if season != cur and os.path.exists(fn) and not a.force:
                continue
            try:
                rows = fetch_report(report, season)
                json.dump({"season": season, "report": report,
                           "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                           "rows": rows}, open(fn, "w"), separators=(",", ":"))
                print(f"{report} {season}: {len(rows)} rows")
            except Exception as e:  # keep going; one failed report shouldn't sink the fetch
                errors[f"{report}_{season}"] = str(e)[:200]
                print(f"FAILED {report} {season}: {e}")
    json.dump({"fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "current_season": cur, "errors": errors},
              open(os.path.join(OUT, "manifest.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
