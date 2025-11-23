import os
import random
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
# --- Environment variables ---
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise SystemExit("Missing SLACK_BOT_TOKEN or SLACK_SIGNING_SECRET")
# --- WHS tips (reuse same style as daily bot) ---
WHS_TIPS = [
    "*Safe to Go Tip:* :safety_vest::muscle: Use your powerzone: Keeping items in your powerzone — mid-thigh to mid-chest — helps you stay safe when lifting, lowering, and turning.",
    "*Safe to Go Tip:* :gloves::warning: The right equipment for the job: Using correct PPE, like gloves for proper grasping, reduces the risk of MSDs such as sprains and strains.",
    "*Safe to Go Tip:* :arrows_counterclockwise::scales: Switch sides: Alternating between your left and right sides helps your body maintain balance and reduces strain.",
    "*Safe to Go Tip:* :handshake::package: Practise the team lift: Test the weight before lifting and use both hands. Ask for help if an item is too heavy or awkward.",
    "*Safe to Go Tip:* :man-cartwheeling::person_in_lotus_position: Stretch it out: Stretch before and after work to reduce fatigue and improve range of motion.",
    "*Safe to Go Tip:* :toolbox::wrench: Select the right tool: Use the correct equipment in the proper way to reduce effort and avoid unnecessary strain.",
]
def random_tip() -> str:
    return random.choice(WHS_TIPS)
# --- Slack Bolt app ---
bolt_app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
)
# Respond when someone @mentions the bot
@bolt_app.event("app_mention")
def handle_app_mention(body, say, event, logger):
    text = event.get("text", "").lower()
    user = event.get("user")
    if "help" in text:
        say(
            f"Hi <@{user}> :wave:\n"
            "*I’m your WHS Safety Bot.*\n"
            "• I post daily Safe to Go tips.\n"
            "• Mention me with `tip` to get an extra WHS reminder.\n"
            "• Mention me with `help` to see this message again."
        )
    elif "tip" in text:
        say(random_tip())
    else:
        say(
            f"Hi <@{user}> :construction_worker:\n"
            "You can say `tip` for a WHS tip or `help` for more info."
        )
# Optional: a slash command /whs-tip
@bolt_app.command("/whs-tip")
def handle_whs_tip(ack, respond):
    ack()
    respond(random_tip())
# --- Flask app wrapper for Bolt ---
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)
if __name__ == "__main__":
    # Run locally on port 3000
    flask_app.run(host="0.0.0.0", port=3000)
