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
CHANNEL_IDS = os.environ.get("SLACK_CHANNEL_IDS", "")  # comma-separated string
# ---------------------------------------------------------------
#  CONSTANTS
# ---------------------------------------------------------------
# Weekly cycle: Sunday → Saturday
# Custom week numbering starts from this Sunday.
# With this anchor, the week that contains 26 Nov 2025 is week 48.
ANCHOR_WEEK_START = date(2024, 12, 29)  # Sunday
# Daily rotation anchor (used to rotate messages within a topic)
ANCHOR_DATE = date(2025, 1, 1)
# ---------------------------------------------------------------
#  PER-TOPIC EMOJI SETS
# ---------------------------------------------------------------
TOPIC_EMOJIS = {
    "MSD": {  # MSD Prevention
        "header": ":muscle:",                     # before "This week's topic"
        "title": ":bulb:",                     # before title
        "footer": "Safe-To-Go :safetogo:",
    },
    "SFM": {  # Safety Feedback Mechanism
        "header": ":speech_balloon:",                    # emphasises communication
        "title": ":busts_in_silhouette:",                     # people/feedback
        "footer": "Safe-To-Go :safetogo:",
    },
    "CONV": {  # Conveyor Safety
        "header": ":package:",                    # conveyors & parcels
        "title": ":warning:",                    # hazard awareness
        "footer": "Safe-To-Go :safetogo:",
    },
    "COLD": {  # Cold Stress Prevention
        "header": ":snowflake:",                    # cold
        "title": ":gloves:",                     # PPE for cold
        "footer": "Safe-To-Go :safetogo:",
    },
}
# ---------------------------------------------------------------
#  PREFIX CLEANER
# ---------------------------------------------------------------
def strip_prefix(text: str, prefix: str) -> str:
    """
    Remove the prefix (topic or title) from the body if repeated.
    Makes Slack message cleaner and avoids duplicate bold text.
    """
    if not prefix:
        return text
    t = text.lstrip()
    if t.lower().startswith(prefix.lower()):
        t = t[len(prefix):]           # remove prefix
        t = t.lstrip(" :–-")          # remove punctuation and spaces
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
    Week starts Sunday, ends Saturday.
    Weekly topic rotates based on a custom week number derived from
    ANCHOR_WEEK_START.
    custom_week_number = weeks since anchor (0-based) + 1
    topic index = custom_week_number % len(weekly_topics)
    With ANCHOR_WEEK_START = 2024-12-29 and 4 topics ordered as:
      0: MSD, 1: SFM, 2: CONV, 3: COLD
    You get:
      week 48 -> MSD
      week 49 -> SFM
      week 50 -> CONV
      week 51 -> COLD
      ... then repeats every 4 weeks.
    """
    if today is None:
        today = date.today()
    weekly_topics = topics_json.get("weekly_topics", [])
    if not weekly_topics:
        raise ValueError("weekly_topics missing in JSON")
    days_since_anchor = (today - ANCHOR_WEEK_START).days
    week_offset = days_since_anchor // 7  # integer weeks since anchor
    custom_week_number = week_offset + 1
    idx = custom_week_number % len(weekly_topics)
    return weekly_topics[idx]
# ---------------------------------------------------------------
#  SELECT DAILY MESSAGE
# ---------------------------------------------------------------
def pick_daily_message(topic: dict, today: date | None = None) -> dict:
    """
    Pick a different message each day inside the topic.
    """
    if today is None:
        today = date.today()
    messages = topic.get("messages", [])
    if not messages:
        raise ValueError(f"No messages in topic {topic.get('code')}")
    days_since_anchor = (today - ANCHOR_DATE).days
    idx = days_since_anchor % len(messages)
    return messages[idx]  # returns dict
# ---------------------------------------------------------------
#  BUILD SLACK FORMATTED MESSAGE
# ---------------------------------------------------------------
def build_slack_text(topic: dict, message: dict) -> str:
    topic_name = topic.get("name", "WHS Theme")
    title = message.get("title", "Safety Tip")
    raw_body = message.get("text", "")
    code = topic.get("code", "").upper()
    # Remove repeated topic/title from body
    body = strip_prefix(raw_body, topic_name)
    body = strip_prefix(body, title)
    # Pick emoji set for this topic (fallback if missing)
    emoji_set = TOPIC_EMOJIS.get(code, {
        "header": ":helmet_with_white_cross:",
        "title": ":bulb:",
        "footer": "Safe-To-Go :safetogo:",
    })
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
#  MAIN MESSAGE PICKER
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
    channel_list = [c.strip() for c in CHANNEL_IDS.split(",") if c.strip()]
    for channel_id in channel_list:
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
