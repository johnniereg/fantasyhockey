"""
League Corrections
==================
Handles manager name overrides, aliases, exclusions, season awards, and finances.

MANAGER_OVERRIDES  — fix hidden managers or mid-history team transfers
MANAGER_ALIASES    — normalize Yahoo nicknames to canonical display names
EXCLUDE_MANAGERS   — remove one-season guests / inactive former members
SEASON_AWARDS      — manually record President's Trophy and Tritty Tax winners
SEASON_FINANCES    — buy-in amounts and prize payouts per season
"""

# ── Per-season team → manager overrides ──────────────────────────────────────
# Use this to fix hidden managers or team transfers.
MANAGER_OVERRIDES = {
    # Alex took over Justin's team starting in 2020-21
    "2020-21": { "Bruiser Brigade":     "Alex" },
    "2021-22": { "Bruiser Brigade":     "Alex" },
    "2022-23": { "Last Dance Energy":   "Alex" },
    "2023-24": { "Last Dance Energy":   "Alex" },
    "2024-25": { "Last Dance Energy":   "Alex" },
    "2025-26": { "Last Dance Energy":   "Alex" },

    # Tom's hidden seasons — confirm which of these are his:
    # "2007-08": { "Children Of Tim":       "Tom" },
    # "2008-09": { "Cranky Cockatoos":      "Tom" },
    # "2009-10": { "Sim Sim Salabimster":   "Tom" },
    # "2010-11": { "Braggarttaggart!":      "Tom" },
    # "2012-13": { "PuppetMaster":          "Tom" },
    # "2013-14": { "Gloryholes":            "Tom" },
    # "2014-15": { "Letme Take a Shelfie":  "Tom" },
}

# ── Manager name aliases ──────────────────────────────────────────────────────
# Maps Yahoo nickname → the canonical name to display everywhere.
MANAGER_ALIASES = {
    "johnnie":    "Johnnie",
    "justin":     "Justin",
    "graham":     "Graham",
    "derek":      "Derek",
    "byron":      "Byron",
    "TMeltron":   "Tristan",
    "jordan":     "Jordan",
}

# ── Managers to exclude from all-time stats ───────────────────────────────────
# Former league members who are no longer relevant to the leaderboard.
EXCLUDE_MANAGERS = {
    "--hidden--",
    "keloniusmonk",  # 1 season guest (2015)
    "Tyler Wowchuk", # 1 season guest (2008)
    "Dylan",         # 1 season guest (2013)
    "Nick",          # 4 seasons (2007–2010), no longer active
}

# ── Season awards ─────────────────────────────────────────────────────────────
# presidents_trophy: manager with best regular-season record (before playoffs)
# tritty_tax:        manager who finished last in the regular season
# Use canonical manager names (after MANAGER_ALIASES are applied).
SEASON_AWARDS = {
    # President's Trophy and Tritty Tax introduced in 2018-19.
    # Keys use NHL season format (e.g. "2018-19" = NHL season starting Oct 2018).
    # Confirmed from Facebook message archive (end-of-season payment discussions).
    "2018-19": { "presidents_trophy": "Jordan",  "tritty_tax": "Tristan"  },  # Apr 2019: "last place is Chaz" (Tristan), "Tristan pays Jordan $100"
    "2019-20": { "presidents_trophy": "Braeden", "tritty_tax": "Tristan"  },  # COVID season; Braeden rank 1, Tristan rank 10
    "2020-21": { "presidents_trophy": "Pete",    "tritty_tax": "Tom"      },  # Pete rank 4 (reg season best), Tom tanked
    "2021-22": { "presidents_trophy": "Jordan",  "tritty_tax": "Graham"   },  # Apr 2022: "Gmelt pays tax to JLaw"
    "2022-23": { "presidents_trophy": "Derek",   "tritty_tax": "Pete"     },  # Apr 2023: "Papa johns pays tax to Hughes" + "$50 tax for pete"
    "2023-24": { "presidents_trophy": "Derek",   "tritty_tax": "Alex"     },  # Apr 2024: "That's your tax @Alexandre Desrochers - paying to Hughes Yo Daddy"
    "2024-25": { "presidents_trophy": "Jordan",  "tritty_tax": "Johnnie"  },  # Apr 2025: Jordan collecting; Johnnie rank 10 / "big fat loser paying $175"
    # 2025-26 is in progress — awards added once season ends
}

# ── Tritty Tax amount ─────────────────────────────────────────────────────────
# The Tritty Tax payer sends this amount to the President's Trophy winner.
# Applied automatically for any season that has both awards set in SEASON_AWARDS.
TRITTY_TAX_AMOUNT = 50

# ── Season finances ───────────────────────────────────────────────────────────
# buyin:   amount each active manager paid to enter that season
# payouts: dict of  canonical_manager_name → prize amount received
#          (only include managers who received a payout — do NOT include
#           the Tritty Tax here, that is handled automatically above)
SEASON_FINANCES = {
    # Payouts confirmed from Facebook message archive end-of-season payment posts.
    # Keys use NHL season format (e.g. "2017-18" = NHL season starting Oct 2017).
    # Formula (10 teams, post-2017): 1st = 7×buyin, 2nd = 2×buyin, 3rd = 1×buyin (buy-in refunded).
    # Pre-2017: winner-take-all (full pool = n_teams × buyin to 1st place).
    # Tritty Tax ($50) is handled separately above — do NOT include it here.
    # NOTE: 2013-14 was the first season with a buy-in (Johnnie won back-to-back in 2013-14 and 2014-15).
    # Seasons before 2013-14 had no buy-in.

    "2013-14": {  # First money season. 12 teams × $50 = $600, winner-take-all → Johnnie
        "buyin": 50,
        "payouts": {
            "Johnnie": 600,   # 1st place — winner-take-all (12 teams)
        },
    },
    "2014-15": {  # 12 teams × $50 = $600, winner-take-all → Johnnie (back-to-back)
        "buyin": 50,
        "payouts": {
            "Johnnie": 600,   # 1st place — winner-take-all (12 teams)
        },
    },
    "2015-16": {  # 10 teams × $50 = $500, winner-take-all → Justin
        "buyin": 50,
        "payouts": {
            "Justin": 500,    # 1st place — winner-take-all (10 teams)
        },
    },
    "2016-17": {  # 10 teams × $50 = $500, winner-take-all → Braeden
        "buyin": 50,
        "payouts": {
            "Braeden": 500,   # 1st place — winner-take-all (10 teams)
        },
    },

    "2017-18": {  # Apr 2018: "Everyone else pays $50 to Tom" — first season with 2nd/3rd payouts
        "buyin": 50,
        "payouts": {
            "Tom":     350,   # 1st place — playoff champion
            "Braeden": 100,   # 2nd place
            "Graham":   50,   # 3rd place
        },
    },
    "2018-19": {  # Apr 2019: "1st $350, 2nd $100, 3rd $50 (incl. own $50 back)"
        "buyin": 50,
        "payouts": {
            "Tom":    350,   # 1st place — playoff champion
            "Jordan": 100,   # 2nd place
            "Pete":    50,   # 3rd place
        },
    },
    "2019-20": {  # Jun 2020: "$100 buy-in; 1st $700, 2nd $200, 3rd $100" (COVID season)
        "buyin": 100,
        "payouts": {
            "Braeden": 700,   # 1st place — playoff champion
            "Graham":  200,   # 2nd place
            "Pete":    100,   # 3rd place
        },
    },
    "2020-21": {  # May 2021: "Pay outs at $100 per person as agreed at the start"
        "buyin": 100,
        "payouts": {
            "David":   700,   # 1st place — playoff champion (David Scott)
            "Braeden": 200,   # 2nd place
            "Jeremy":  100,   # 3rd place
        },
    },
    "2021-22": {  # Apr 2022: "Everyone else pays Pete"; "4th place pays $100 to second"
        "buyin": 100,
        "payouts": {
            "Pete":  700,   # 1st place — playoff champion
            "Derek": 200,   # 2nd place
            "Tom":   100,   # 3rd place
        },
    },
    "2022-23": {  # Apr 2023: "$125 buy in"; "1st $875, 2nd $250, 3rd $125"
        "buyin": 125,
        "payouts": {
            "Braeden": 875,   # 1st place — playoff champion
            "Derek":   250,   # 2nd place
            "Graham":  125,   # 3rd place
        },
    },
    "2023-24": {  # Apr 2024: "Buy-in was $125"; "1st Monsieur J-Baby, 2nd Hughes Yo Daddy, 3rd Hugh Jasule"
        "buyin": 125,
        "payouts": {
            "Jeremy": 875,   # 1st place — playoff champion
            "Derek":  250,   # 2nd place
            "Jordan": 125,   # 3rd place
        },
    },
    "2024-25": {  # Apr 2025: "$125 buy in"; "4th place Derek pays 2nd place Jeremy $125"
        "buyin": 125,
        "payouts": {
            "Jordan":  875,   # 1st place — playoff champion
            "Jeremy":  250,   # 2nd place
            "Braeden": 125,   # 3rd place
        },
    },
}
