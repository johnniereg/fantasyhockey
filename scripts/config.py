"""
Yahoo Fantasy Hockey - Configuration
=====================================
Create your Yahoo Developer App at https://developer.yahoo.com/apps/create/
  - Redirect URI(s):   oob  (for command-line / desktop use)
  - API Permissions:   Fantasy Sports (Read) -> fspt-r

This file is tracked in a PUBLIC repo, so credentials must never be written
here. Supply them one of two ways:

  Local:  create data/yahoo_app.json (gitignored) containing
            {"client_id": "...", "client_secret": "..."}
  CI:     set the YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET env vars
          (GitHub Actions reads them from repository secrets)
"""

import json
import os

# ── File paths ───────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(BASE_DIR, "data")
TOKEN_FILE  = os.path.join(DATA_DIR, "yahoo_token.json")
CACHE_FILE  = os.path.join(DATA_DIR, "league_cache.json")
APP_FILE    = os.path.join(DATA_DIR, "yahoo_app.json")


# ── Yahoo Developer App credentials ─────────────────────────────────────────
def _load_app_credentials():
    """Return (client_id, client_secret) from the environment or APP_FILE."""
    cid  = os.environ.get("YAHOO_CLIENT_ID", "").strip()
    csec = os.environ.get("YAHOO_CLIENT_SECRET", "").strip()
    if cid and csec:
        return cid, csec

    if os.path.exists(APP_FILE):
        with open(APP_FILE) as f:
            creds = json.load(f)
        return (str(creds.get("client_id", "")).strip(),
                str(creds.get("client_secret", "")).strip())

    return "", ""


CLIENT_ID, CLIENT_SECRET = _load_app_credentials()

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
    "2026-27": "12088",
}

# Season you want shown as "current" in the dashboard
# 2025-26 wrapped up Apr 2026. The 2026-27 league (477.l.12088) is in predraft
# until the season starts 2026-09-29; standings stay empty until games are played.
CURRENT_SEASON = "2026-27"

