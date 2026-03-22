"""
Yahoo OAuth2 Authentication (PKCE / Out-of-Band flow)
======================================================
Handles getting and refreshing Yahoo API tokens.
Run this script directly to authenticate:  python3 scripts/yahoo_auth.py
"""

import json
import os
import time
import hashlib
import base64
import secrets
import urllib.parse
import urllib.request
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import CLIENT_ID, CLIENT_SECRET, TOKEN_FILE, DATA_DIR

AUTH_URL    = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL   = "https://api.login.yahoo.com/oauth2/get_token"
REDIRECT_URI = "https://localhost"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _save_token(token: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    token["saved_at"] = time.time()
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)
    print(f"✅ Token saved to {TOKEN_FILE}")


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        return json.load(f)


def is_token_expired(token: dict) -> bool:
    saved_at   = token.get("saved_at", 0)
    expires_in = token.get("expires_in", 3600)
    return time.time() > saved_at + expires_in - 60  # 60s buffer


def refresh_token(token: dict) -> dict:
    print("🔄 Refreshing Yahoo token...")
    data = {
        "grant_type":    "refresh_token",
        "refresh_token": token["refresh_token"],
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    new_token = _post_token(data)
    # preserve refresh_token if not returned
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = token["refresh_token"]
    _save_token(new_token)
    return new_token


def _post_token(data: dict) -> dict:
    creds  = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    body   = urllib.parse.urlencode(data).encode()
    req    = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Authorization", f"Basic {creds}")
    req.add_header("Content-Type",  "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_valid_token() -> dict:
    """Return a valid (non-expired) token, refreshing or re-authing as needed.

    In CI environments (GitHub Actions etc.) set the YAHOO_REFRESH_TOKEN
    environment variable instead of relying on a saved token file.
    The refresh token will be exchanged silently — no browser required.
    """
    # CI / headless mode: bootstrap from environment variable
    env_refresh = os.environ.get("YAHOO_REFRESH_TOKEN", "").strip()
    if env_refresh:
        print("🤖 CI mode: refreshing token from YAHOO_REFRESH_TOKEN env var...")
        synthetic = {
            "refresh_token": env_refresh,
            "saved_at":      0,       # force an immediate refresh
            "expires_in":    3600,
        }
        return refresh_token(synthetic)

    # Normal local flow
    token = load_token()
    if token is None:
        print("⚠️  No token found. Starting first-time authentication...")
        return authenticate()
    if is_token_expired(token):
        try:
            return refresh_token(token)
        except Exception as e:
            print(f"⚠️  Token refresh failed ({e}). Re-authenticating...")
            return authenticate()
    return token


def authenticate() -> dict:
    """Full OAuth2 authorization_code flow (out-of-band / copy-paste)."""
    if CLIENT_ID == "YOUR_CLIENT_ID_HERE":
        print("\n❌  Please set CLIENT_ID and CLIENT_SECRET in scripts/config.py first!")
        print("   See: https://developer.yahoo.com/apps/create/\n")
        sys.exit(1)

    # PKCE
    verifier  = secrets.token_urlsafe(64)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())

    params = {
        "client_id":             CLIENT_ID,
        "redirect_uri":          REDIRECT_URI,
        "response_type":         "code",
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)

    print("\n" + "="*60)
    print("STEP 1 — Open this URL in your browser:")
    print("="*60)
    print(url)
    print("="*60)
    print("\nSTEP 2 — Sign in with your Yahoo account and authorize the app.")
    print("STEP 3 — Your browser will try to redirect to https://localhost")
    print("         and show a 'connection refused' error — that's expected!")
    print("STEP 4 — Copy the full URL from your browser's address bar.")
    print("         It will look like: https://localhost?code=XXXX&...")
    raw = input("\nPaste the full redirect URL here: ").strip()
    # Extract code from URL or accept bare code
    if "code=" in raw:
        import urllib.parse as _up
        code = _up.parse_qs(_up.urlparse(raw).query).get("code", [raw])[0]
    else:
        code = raw

    data = {
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code_verifier": verifier,
    }
    token = _post_token(data)
    _save_token(token)
    print("🎉 Authentication successful!")
    return token


if __name__ == "__main__":
    token = get_valid_token()
    print(f"\n✅ Access token ready (expires in ~{token.get('expires_in', '?')}s)")
