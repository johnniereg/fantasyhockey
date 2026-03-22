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
    # Alex took over Justin's team starting in 2020
    "2020": { "Bruiser Brigade":     "Alex" },
    "2021": { "Bruiser Brigade":     "Alex" },
    "2022": { "Last Dance Energy":   "Alex" },
    "2023": { "Last Dance Energy":   "Alex" },
    "2024": { "Last Dance Energy":   "Alex" },
    "2025": { "Last Dance Energy":   "Alex" },

    # Tom's hidden seasons — confirm which of these are his:
    # "2007": { "Children Of Tim":       "Tom" },
    # "2008": { "Cranky Cockatoos":      "Tom" },
    # "2009": { "Sim Sim Salabimster":   "Tom" },
    # "2010": { "Braggarttaggart!":      "Tom" },
    # "2012": { "PuppetMaster":          "Tom" },
    # "2013": { "Gloryholes":            "Tom" },
    # "2014": { "Letme Take a Shelfie":  "Tom" },
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
    # President's Trophy and Tritty Tax introduced in 2018.
    "2018": { "presidents_trophy": "Jordan",  "tritty_tax": "Byron"    },
    "2019": { "presidents_trophy": "Braeden", "tritty_tax": "Tristan"  },
    "2020": { "presidents_trophy": "Pete",    "tritty_tax": "Tom"      },
    "2021": { "presidents_trophy": "Jordan",  "tritty_tax": "Graham"   },
    "2022": { "presidents_trophy": "Derek",   "tritty_tax": "Pete"     },
    "2023": { "presidents_trophy": "Derek",   "tritty_tax": "Alex"     },
    "2024": { "presidents_trophy": "Jordan",  "tritty_tax": "Johnnie"  },
    # 2025 is in progress — awards added once season ends
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
    # "2025": {
    #     "buyin": 40,
    #     "payouts": {
    #         "Johnnie": 200,   # 1st place
    #         "Graham":   80,   # 2nd place
    #         "Derek":    40,   # 3rd place
    #     }
    # },
    # … fill in for each season
}
