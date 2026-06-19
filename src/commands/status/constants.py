"""Constants shared across /status subcommands."""

POLL_MINUTES = 5
STATUS_COLOR = 0xE03B3B
MAX_SUMMARY = 600
MAX_ISSUE_MESSAGE = 400

SUBSCRIPTIONS_KEY = "status_subscriptions"
SEEN_KEY = "status_seen"
SYSTEMS_KEY = "status_systems"

STATUS_LABEL = {
    "operational": "Operational",
    "degraded": "Degraded",
    "partial": "Partial Outage",
    "major": "Major Outage",
    "maintenance": "Maintenance",
}
OVERVIEW_COLOR = {
    "operational": 0x51AE7A,
    "degraded": 0x969AE8,
    "partial": 0xE8944A,
    "major": 0xFF6666,
    "maintenance": 0xAAB5BB,
}
