"""
Debug script — saves raw Yahoo API responses so we can fix the parser.
Run:  python3 scripts/debug_raw.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.yahoo_auth import get_valid_token
from scripts.fetch_data import yahoo_get, discover_league_keys
from scripts.config import LEAGUE_IDS, DATA_DIR

token = get_valid_token()
id_to_key = discover_league_keys(token)

# Use 2025 season
league_id  = LEAGUE_IDS["2025"]
league_key = id_to_key.get(str(league_id), f"nhl.l.{league_id}")
print(f"Using league key: {league_key}")

raw_standings = yahoo_get(f"/league/{league_key}/standings", token)

out = os.path.join(DATA_DIR, "debug_standings.json")
os.makedirs(DATA_DIR, exist_ok=True)
with open(out, "w") as f:
    json.dump(raw_standings, f, indent=2)
print(f"✅ Raw standings saved to: {out}")
