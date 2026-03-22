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
            "Each manager pays a buy-in at the start of the season. The prize pool is distributed "
            "to the top finishers at season end. Payout structure and buy-in amounts have varied "
            "over the years — see the Finances tab for historical figures."
        ),
    },
    {
        "title": "President's Trophy",
        "content": (
            "Awarded to the manager with the best record at the end of the regular season "
            "(before playoffs begin). A separate recognition from the championship — you can "
            "win the President's Trophy and still lose in the playoffs."
        ),
    },
    {
        "title": "Tritty Tax",
        "content": (
            "The manager who finishes last in the regular season standings must pay the Tritty Tax. "
            "Amount and form of payment TBD / varies by season."
        ),
    },
    {
        "title": "Playoffs",
        "content": (
            "The top teams qualify for playoffs in the final weeks of the season. "
            "Playoff format and bracket details to be filled in."
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
            "Standard Yahoo waiver system. Details to be filled in."
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
