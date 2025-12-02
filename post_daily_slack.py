import os
import json
from datetime import date
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
# Weeks run Sunday → Saturday, grouped from this anchor Sunday.
ANCHOR_WEEK_START = date(2024, 12, 29)  # Sunday
# Used only for rotating daily messages within each topic
ANCHOR_DATE = date(2025, 1, 1)
# Explicit mapping for WHS custom week numbers
# After Cold Stress (week 51), we repeat MSD (week 52),
# and then Eyes on Path (week 53).
WHS_WEEK_TOPIC_CODES = {
    48: "MSD",   # week starting 23 Nov 2025
    49: "SFM",   # week starting 30 Nov 2025
    50: "CONV",  # week starting 07 Dec 2025
    51: "COLD",  # week starting 14 Dec 2025
    52: "MSD",   # week starting 21 Dec 2025 (repeat MSD)
    53: "EOP",   # week starting 28 Dec 2025 (Eyes on Path)
}
# ---------------------------------------------------------------
#  PER-TOPIC EMOJI SETS
# ---------------------------------------------------------------
TOPIC_EMOJIS = {
    "MSD": {   # MSD Prevention
        "header": ":muscle:",
        "title": ":bulb:",
        "footer": "Safe-to-go :safetogo:",
    },
    "SFM": {   # Safety Feedback Mechanism
        "header": ":speech_balloon:",
        "title": ":busts_in_silhouette:",
        "footer": "Safe-to-go :safetogo:",
    },
    "CONV": {  # Conveyor Safety
        "header": ":package:",
        "title": ":warning:",
        "footer": "Safe-to-go :safetogo:",
    },
    "COLD": {  # Cold Stress Prevention
        "header": ":snowflake:",
        "title": ":gloves:",
        "footer": "Safe-to-go :safetogo:",
    },
    "EOP": {   # Eyes on Path & Housekeeping
        "header": ":eyes:",
        "title": ":broom:",
        "footer": "Safe-to-go :safetogo:",
    },
}
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
#  SELECT WEEKLY TOPIC (SUNDAY–SATURDAY)
# ---------------------------------------------------------------
def pick_weekly_topic(topics_json: dict, today: date | None = None) -> dict:
    """
    Choose this week's topic.
Compute a custom week number based on ANCHOR_WEEK_START with
       Sunday–Saturday weeks.
If the custom week number is in WHS_WEEK_TOPIC_CODES, use that
       topic code (e.g., week 48 -> MSD, 49 -> SFM, etc.).
Otherwise, fall back to simple rotation by modulo across all
       defined topics.
    """
    if today is None:
        today = date.today()
    weekly_topics = topics_json.get("weekly_topics", [])
    if not weekly_topics:
        raise ValueError("weekly_topics missing in JSON")
    # 1) Work out week number (Sunday–Saturday) relative to anchor
    days_since_anchor = (today - ANCHOR_WEEK_START).days
    week_offset = days_since_anchor // 7
    custom_week_number = week_offset + 1
    # 2) Try explicit mapping first
    mapped_code = WHS_WEEK_TOPIC_CODES.get(custom_week_number)
    if mapped_code:
        # Find first topic with that code
        for topic in weekly_topics:
            if topic.get("code") == mapped_code:
                return topic
        # If mapping code is missing from JSON, fall back to rotation
        print(
            f"Warning: week {custom_week_number} mapped to '{mapped_code}' "
            f"but no such code found in JSON. Falling back to rotation."
        )
    # 3) Fallback: simple rotation by modulo
    idx = custom_week_number % len(weekly_topics)
    return weekly_topics[idx]
# ---------------------------------------------------------------
#  SELECT DAILY MESSAGE
# ---------------------------------------------------------------
def pick_daily_message(topic: dict, today: date | None = None) -> dict:
    """
    Pick a different message each day within the chosen topic.
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
#  BUILD SLACK MESSAGE TEXT
# ---------------------------------------------------------------
def build_slack_text(topic: dict, message: dict) -> str:
    topic_name = topic.get("name", "WHS Theme")
    title = message.get("title", "Safety Tip")
    raw_body = message.get("text", "")
    code = topic.get("code", "").upper()
    # Clean up repeats of topic name or title at the start of body
    body = strip_prefix(raw_body, topic_name)
    body = strip_prefix(body, title)
    emoji_set = TOPIC_EMOJIS.get(
        code,
        {
            "header": ":helmet_with_white_cross:",
            "title": ":bulb:",
            "footer": "Safe-to-go :safetogo:",
        },
    )
    header_emoji = emoji_set["header"]
    title_emoji = emoji_set["title"]
    footer_text = emoji_set["footer"]
    return (
        f"{header_emoji} *This week's topic: {topic_name}*\n\n"
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
    formatted = build_slack_text(topic, message)
    return formatted
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
