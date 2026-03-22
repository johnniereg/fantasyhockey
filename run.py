#!/usr/bin/env python3
"""
Fantasy Hockey Dashboard — Main Runner
========================================
Usage:
  python3 run.py              # Fetch latest data + rebuild dashboard
  python3 run.py --build-only # Rebuild dashboard from cached data only
  python3 run.py --auth       # Re-authenticate with Yahoo
  python3 run.py 2024 2025    # Fetch specific seasons only
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    args = sys.argv[1:]

    if "--auth" in args:
        from scripts.yahoo_auth import authenticate
        authenticate()
        return

    if "--build-only" in args:
        from scripts.build_dashboard import load_cache, build_html, OUTPUT_FILE
        print("📊 Building dashboard from cache...")
        data = load_cache()
        html = build_html(data)
        with open(OUTPUT_FILE, "w") as f:
            f.write(html)
        print(f"✅ Dashboard ready: {OUTPUT_FILE}")
        return

    # Filter out flags, treat remaining args as season years
    seasons = [a for a in args if a.isdigit() and len(a) == 4] or None

    print("🏒 Fantasy Hockey Dashboard")
    print("=" * 40)

    # Step 1: Fetch data
    from scripts.fetch_data import fetch_all
    fetch_all(seasons)

    # Step 2: Build dashboard
    from scripts.build_dashboard import load_cache, build_html, OUTPUT_FILE
    print("\n📊 Building dashboard...")
    data = load_cache()
    html = build_html(data)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"✅ Dashboard ready: {OUTPUT_FILE}")
    print(f"\n👉 Open index.html in your browser to view your pool!\n")


if __name__ == "__main__":
    main()
