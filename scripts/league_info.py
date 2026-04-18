"""
League Info
===========
Static content for the League Info tab: description and rules.
Edit this file to update what appears on the dashboard.
"""

LEAGUE_DESCRIPTION = (
    "The Tim McCabe Memorial Cup has been running since 2007, making it one of the "
    "longest-running fantasy hockey leagues among its members. Named in honour of Tim McCabe, "
    "the league brings together the same core group of friends each season for head-to-head "
    "hockey competition. Over 19 seasons it has produced memorable champions, contentious trades, "
    "and plenty of trash talk."
)

# Each entry is a section on the rules page.
# title: section heading
# content: body text (plain text; newlines become line breaks in the dashboard)
LEAGUE_RULES = [
    {
        "title": "Format",
        "content": (
            "Head-to-head points league. Weekly matchups run throughout the NHL regular season. "
            "Teams are scored on a set of offensive and goaltending statistical categories each week."
        ),
    },
    {
        "title": "Buy-In & Payouts",
        "content": (
            "Each manager pays a buy-in at the start of the season. Buy-in has increased over the years: "
            "$50 (2017–2018), $100 (2019–2021), $125 (2022–2024), $150 (2025–2026).\n\n"
            "Payout structure (based on playoff finish, 10 teams):\n"
            "  1st place — collects the buy-in from every manager who finished 5th or worse\n"
            "  2nd place — collects the buy-in from the 4th-place finisher\n"
            "  3rd place — gets their own buy-in refunded (free season)\n"
            "  4th place — pays their buy-in to 2nd place\n"
            "  5th–10th  — each pays their buy-in to 1st place\n\n"
            "Net at $150 buy-in: 1st +$900, 2nd +$150, 3rd $0, 4th–10th −$150.\n"
            "See the Finances tab for historical buy-ins and full payout records."
        ),
    },
    {
        "title": "President's Trophy",
        "content": (
            "Awarded to the manager with the best record at the end of the regular season "
            "(before playoffs begin). A separate recognition from the championship — you can "
            "win the President's Trophy and still lose in the playoffs. "
            "The Tritty Tax payer sends $50 to the President's Trophy winner each season."
        ),
    },
    {
        "title": "Tritty Tax",
        "content": (
            "The manager who finishes last in the regular season standings — before playoffs begin — "
            "must pay the Tritty Tax: $50 sent to the President's Trophy winner. "
            "Playoff results do not affect who pays; it is determined solely by regular season record. "
            "Named after Tristan Melton, who paid it two years running (2018–2019). "
            "It has since been referred to as the Melton Tax in his honour."
        ),
    },
    {
        "title": "Playoffs",
        "content": (
            "The top 6 teams qualify for the championship bracket. Seeds 1 and 2 receive a first-round bye; "
            "seeds 3–6 play in the first round.\n\n"
            "The bottom 4 teams (7th–10th) compete in a consolation bracket for the 1st overall pick "
            "in the following season's draft. The first two teams eliminated from the championship bracket "
            "play each other for the 5th overall pick."
        ),
    },
    {
        "title": "Trade Deadline",
        "content": (
            "Trades close at the Yahoo-set trade deadline. No trades are permitted after that point. "
            "Specific deadline week varies by season."
        ),
    },
    {
        "title": "Waivers",
        "content": (
            "Waiver Type: Free Agent Acquisition Budget (FAB) with a continual rolling list tiebreak.\n"
            "Waiver Mode: Standard.\n"
            "Waiver Period: 2 days."
        ),
    },
    {
        "title": "Scoring Categories",
        "content": (
            "Skaters: Goals (G), Assists (A), Power Play Points (PPP), Shots on Goal (SOG), "
            "Plus/Minus (+/−), PIM, Faceoff Wins (FW).\n"
            "Goalies: Wins (W), GAA, Save % (SV%), Shutouts (SO)."
        ),
    },
]
