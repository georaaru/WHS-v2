
import os
import json
from datetime import date, timedelta
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ---------------------------------------------------------------
#  ENVIRONMENT VALUES
# ---------------------------------------------------------------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_IDS = os.environ.get("SLACK_CHANNEL_IDS", "")  # comma-separated

# ---------------------------------------------------------------
#  CONSTANTS
# ---------------------------------------------------------------
# Used only for rotating daily messages within each topic
ANCHOR_DATE = date(2025, 1, 1)

# Explicit mapping for WHS week numbers (within the CURRENT YEAR)
# Weeks start Sunday and end Saturday.
# Week 1 starts on the Sunday on or before Jan 1 of that year.
WHS_WEEK_TOPIC_CODES = {
    # STF Campaign weeks (week numbers for the year)
    10: "STAIR",
    11: "WET",
    12: "OCS",
    13: "POA",

    # Other mapped weeks (keep if you want control later in the year)
    48: "MSD",
    49: "SFM",
    50: "CONV",
    51: "COLD",
    52: "MSD",
    53: "EOP",
}

# STF Campaign header override (same weeks as above)
STF_CAMPAIGN_WEEKS = {
    10: (1, "Stair Safety"),
    11: (2, "Wet Floor Hazards"),
    12: (3, "Object & Cart Safety"),
    13: (4, "Path Obstacle Awareness"),
}

# ---------------------------------------------------------------
#  PER-TOPIC EMOJI SETS
# ---------------------------------------------------------------
TOPIC_EMOJIS = {
    "MSD": {"header": ":muscle:", "title": ":bulb:", "footer": "Safe-to-go :safetogo:"},
    "SFM": {"header": ":speech_balloon:", "title": ":busts_in_silhouette:", "footer": "Safe-to-go :safetogo:"},
    "CONV": {"header": ":package:", "title": ":warning:", "footer": "Safe-to-go :safetogo:"},
    "COLD": {"header": ":snowflake:", "title": ":gloves:", "footer": "Safe-to-go :safetogo:"},
    "EOP": {"header": ":eyes:", "title": ":broom:", "footer": "Safe-to-go :safetogo:"},

    # Campaign topics
    "STAIR": {"header": ":ladder:", "title": ":warning:", "footer": "Safe-to-go :safetogo:"},
    "WET": {"header": ":droplet:", "title": ":warning:", "footer": "Safe-to-go :safetogo:"},
    "OCS": {"header": ":shopping_trolley:", "title": ":package:", "footer": "Safe-to-go :safetogo:"},
    "POA": {"header": ":construction:", "title": ":eyes:", "footer": "Safe-to-go :safetogo:"},
}

# ---------------------------------------------------------------
#  WEEK NUMBER HELPERS (SUNDAY START, WEEK 1 CONTAINS JAN 1)
# ---------------------------------------------------------------
def week1_start_sunday(year: int) -> date:
    """
    Week 1 starts on the Sunday on or before Jan 1 of the given year.
    Weeks run Sunday -> Saturday.
    """
    jan1 = date(year, 1, 1)
    # weekday(): Mon=0 ... Sun=6
    days_to_prev_sunday = (jan1.weekday() + 1) % 7
    return jan1 - timedelta(days=days_to_prev_sunday)


def whs_week_number(today: date) -> int:
    """
    Returns WHS week number for the given date, where:
Weeks start Sunday
Week 1 is the week containing Jan 1
    """
    start = week1_start_sunday(today.year)
    return ((today - start).days // 7) + 1


# ---------------------------------------------------------------
#  PREFIX CLEANER
# ---------------------------------------------------------------
def strip_prefix(text: str, prefix: str) -> str:
    """
    Remove the prefix (topic or title) from the body if repeated.
    Keeps Slack message cleaner and avoids duplicate bold text.
    """
    if not prefix:
        return text
    t = text.lstrip()
    if t.lower().startswith(prefix.lower()):
        t = t[len(prefix):]
        t = t.lstrip(" :–-")
        return t.lstrip()
    return text


# ---------------------------------------------------------------
#  LOAD TOPICS JSON
# ---------------------------------------------------------------
def load_topics(path: str | Path = "whs_topics.json") -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Topics file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------
#  SELECT WEEKLY TOPIC
# ---------------------------------------------------------------
def pick_weekly_topic(topics_json: dict, today: date | None = None) -> dict:
    """
    Choose this week's topic based on:
Sunday-start weeks
Week 1 contains Jan 1
Explicit mapping (WHS_WEEK_TOPIC_CODES) overrides rotation
Otherwise rotate through topics in JSON
    """
    if today is None:
        today = date.today()

    weekly_topics = topics_json.get("weekly_topics", [])
    if not weekly_topics:
        raise ValueError("weekly_topics missing in JSON")

    week_num = whs_week_number(today)

    mapped_code = WHS_WEEK_TOPIC_CODES.get(week_num)
    if mapped_code:
        for topic in weekly_topics:
            if topic.get("code") == mapped_code:
                return topic
        print(
            f"Warning: week {week_num} mapped to '{mapped_code}' "
            f"but no such code found in JSON. Falling back to rotation."
        )

    idx = week_num % len(weekly_topics)
    return weekly_topics[idx]


# ---------------------------------------------------------------
#  SELECT DAILY MESSAGE
# ---------------------------------------------------------------
def pick_daily_message(topic: dict, today: date | None = None) -> dict:
    """
    Pick a different message each day within the chosen topic.
    Daily rotation is anchored to ANCHOR_DATE.
    """
    if today is None:
        today = date.today()

    messages = topic.get("messages", [])
    if not messages:
        raise ValueError(f"No messages in topic {topic.get('code')}")

    days_since_anchor = (today - ANCHOR_DATE).days
    idx = days_since_anchor % len(messages)
    return messages[idx]


# ---------------------------------------------------------------
#  BUILD SLACK MESSAGE TEXT (WITH STF CAMPAIGN HEADER OVERRIDE)
# ---------------------------------------------------------------
def build_slack_text(topic: dict, message: dict, today: date) -> str:
    topic_name = topic.get("name", "WHS Theme")
    title = message.get("title", "Safety Tip")
    raw_body = message.get("text", "")
    code = topic.get("code", "").upper()

    # Clean up repeats of topic name or title at the start of body
    body = strip_prefix(raw_body, topic_name)
    body = strip_prefix(body, title)

    emoji_set = TOPIC_EMOJIS.get(
        code,
        {"header": ":helmet_with_white_cross:", "title": ":bulb:", "footer": "Safe-to-go :safetogo:"},
    )

    header_emoji = emoji_set["header"]
    title_emoji = emoji_set["title"]
    footer_text = emoji_set["footer"]

    week_num = whs_week_number(today)

    # STF Campaign header override (Weeks 10-13)
    if week_num in STF_CAMPAIGN_WEEKS:
        campaign_week, campaign_focus = STF_CAMPAIGN_WEEKS[week_num]
        header_text = (
            f"{header_emoji} *Slips, Trips, and Falls (STF) Prevention Campaign Implementation*\n"
            f"Week {campaign_week} – {campaign_focus}"
        )
    else:
        header_text = f"{header_emoji} *This week's topic: {topic_name}*"

    return (
        f"{header_text}\n\n"
        f"{title_emoji} *{title}*\n"
        f"{body}\n\n"
        f"{footer_text}"
    )


# ---------------------------------------------------------------
#  PICK MESSAGE FOR TODAY
# ---------------------------------------------------------------
def pick_message_for_today() -> str:
    topics_json = load_topics()
    today = date.today()
    topic = pick_weekly_topic(topics_json, today)
    message = pick_daily_message(topic, today)
    return build_slack_text(topic, message, today)


# ---------------------------------------------------------------
#  SEND TO SLACK
# ---------------------------------------------------------------
def post_to_slack(text: str) -> None:
    if not SLACK_BOT_TOKEN:
        raise SystemExit("Missing SLACK_BOT_TOKEN.")
    if not CHANNEL_IDS:
        raise SystemExit("Missing SLACK_CHANNEL_IDS.")

    client = WebClient(token=SLACK_BOT_TOKEN)
    channels = [c.strip() for c in CHANNEL_IDS.split(",") if c.strip()]

    for channel_id in channels:
        try:
            client.chat_postMessage(channel=channel_id, text=text)
            print(f"Sent message to {channel_id}")
        except SlackApiError as e:
            print(f"Slack error for {channel_id}: {e.response.get('error')}")


# ---------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------
def main():
    text = pick_message_for_today()
    post_to_slack(text)


if __name__ == "__main__":
    main()
