import os
import json
from datetime import date
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
#  ENVIRONMENT VALUES
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_IDS = os.environ.get("SLACK_CHANNEL_IDS", "")  # comma-separated
#  CONSTANTS
# Your weekly cycle starts on a Sunday.
# Week 48 = MSD, Week 49 = SFM, Week 50 = Conveyor, then repeats.
# Adjust the anchor Sunday only if you want to change what “week 1” is.
ANCHOR_WEEK_START = date(2024, 12, 1)  # This is a Sunday
# Daily rotation anchor – used only to pick different messages each day
ANCHOR_DATE = date(2025, 1, 1)
# ---------------------------------------------------------------
#  LOAD TOPICS FROM JSON
# ---------------------------------------------------------------
def load_topics(path: str | Path = "whs_topics.json") -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Topics file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
# ---------------------------------------------------------------
#  WEEKLY TOPIC SELECTION — SUNDAY TO SATURDAY
# ---------------------------------------------------------------
def pick_weekly_topic(topics_json: dict, today: date | None = None) -> dict:
    """
    Week starts Sunday, ends Saturday.
    Week number drives the topic:
       week 48 -> topic 0 (MSD)
       week 49 -> topic 1 (SFM)
       week 50 -> topic 2 (CONV)
       then repeats.
    """
    if today is None:
        today = date.today()
    weekly_topics = topics_json.get("weekly_topics", [])
    if not weekly_topics:
        raise ValueError("No weekly_topics defined in JSON")
    # Days since anchor Sunday
    days_since_anchor = (today - ANCHOR_WEEK_START).days
    week_offset = days_since_anchor // 7  # integer division
    # Custom week numbering (1-based)
    custom_week_number = week_offset + 1
    # Rotate through topics
    idx = custom_week_number % len(weekly_topics)
    return weekly_topics[idx]
# ---------------------------------------------------------------
#  DAILY MESSAGE SELECTION (ROTATION)
# ---------------------------------------------------------------
def pick_daily_message(topic: dict, today: date | None = None) -> dict:
    """
    Pick a different message every day within the selected topic.
    """
    if today is None:
        today = date.today()
    messages = topic.get("messages", [])
    if not messages:
        raise ValueError(f"No messages found for topic {topic.get('code')}")
    days_since_anchor = (today - ANCHOR_DATE).days
    idx = days_since_anchor % len(messages)
    return messages[idx]  # {id, title, text}
# ---------------------------------------------------------------
#  FORMAT SLACK MESSAGE
# ---------------------------------------------------------------
def build_slack_text(topic: dict, message: dict) -> str:
    """
    Builds formatted Slack text:
Weekly topic header
Bolded message title
Clean body
Closing line
    """
    topic_name = topic.get("name", "WHS Theme")
    title = message.get("title", "Safety Tip")
    body = message.get("text", "")
    return (
        f":helmet_with_white_cross: *This week's topic: {topic_name}*\n\n"
        f":bulb: *{title}*\n"
        f"{body}\n\n"
        f"Automated WHS Reminder safe-to-go."
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
#  MAIN ENTRY POINT
# ---------------------------------------------------------------
def main():
    text = pick_message_for_today()
    post_to_slack(text)
if __name__ == "__main__":
    main()
