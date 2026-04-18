"""
Yahoo Fantasy Hockey - Configuration
=====================================
Fill in your Yahoo Developer App credentials here after creating your app at:
https://developer.yahoo.com/apps/create/

Steps to get credentials:
1. Go to https://developer.yahoo.com/apps/create/
2. Sign in with your Yahoo account
3. Fill in:
   - App Name: anything (e.g. "My Hockey Dashboard")
   - Description: anything
   - Redirect URI(s): oob  (for command-line / desktop use)
   - API Permissions: Fantasy Sports (Read) -> fspt-r
4. Click Create App
5. Copy your Client ID and Client Secret below
"""

# ── Yahoo Developer App credentials ─────────────────────────────────────────
CLIENT_ID     = "dj0yJmk9YW1RanJGbnlOZ1IwJmQ9WVdrOWRGTjNXbWRNTmtJbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWQz"
CLIENT_SECRET = "d2d29f151397ef5036040617281e02eba4ae6ed6"

# ── Your Yahoo Fantasy league IDs ────────────────────────────────────────────
# Find your league ID in the Yahoo Fantasy URL:
#   https://hockey.fantasysports.yahoo.com/hockey/LEAGUE_ID
# You can add multiple season league IDs here (oldest → newest)
LEAGUE_IDS = {
    "2007-08": "35442",
    "2008-09": "57489",
    "2009-10": "163282",
    "2010-11": "49139",
    "2011-12": "36124",
    "2012-13": "42039",
    "2013-14": "49824",
    "2014-15": "34992",
    "2015-16": "23518",
    "2016-17": "33236",
    "2017-18": "6670",
    "2018-19": "16082",
    "2019-20": "13467",
    "2020-21": "27747",
    "2021-22": "32364",
    "2022-23": "17094",
    "2023-24": "15739",
    "2024-25": "18866",
    "2025-26": "36483",
}

# Season you want shown as "current" in the dashboard
# 2025-26 wrapped up Apr 2026 — bumped to 2026-27 so 2025-26 is treated as completed.
# Once the league ID for 2026-27 is known, add it to LEAGUE_IDS above and re-run fetch_data.
CURRENT_SEASON = "2026-27"

# ── File paths ───────────────────────────────────────────────────────────────
import os
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(BASE_DIR, "data")
TOKEN_FILE  = os.path.join(DATA_DIR, "yahoo_token.json")
CACHE_FILE  = os.path.join(DATA_DIR, "league_cache.json")
