import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1527242487272439869/9_p2AXyQ-ER5nJrKoLmC4WG3C9ADRjeMNFfsN6jTDDcG2oAI31i4WaiXRUnthC2x7J4U")

def send_discord_message(content: str, embeds: list = None) -> bool:
    """
    Sends a message (with optional embeds) to the Discord Webhook.
    """
    if not DISCORD_WEBHOOK_URL:
        print("Discord configuration is missing (DISCORD_WEBHOOK_URL). Skipping notification.")
        print(f"Content: {content}")
        return False

    formatted_content = content
    html_to_md = {
        "<b>": "**", "</b>": "**",
        "<i>": "*", "</i>": "*",
        "🔴": "🔴", "🟢": "🟢", "🟡": "🟡", "✅": "✅", "❌": "❌", "⏳": "⏳", "🆔": "🆔"
    }
    for html_tag, md_tag in html_to_md.items():
        formatted_content = formatted_content.replace(html_tag, md_tag)

    payload = {
        "content": formatted_content if not embeds else None
    }
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")
        return False

def get_run_details() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "Unknown")
    workflow = os.environ.get("GITHUB_WORKFLOW", "Unknown")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"**Run ID:** {run_id} | **Workflow:** {workflow} | **Time:** {current_time}"

def report_download_start():
    embed = {
        "title": "🟢 Hollywood Download Started",
        "description": get_run_details(),
        "color": 3066993
    }
    send_discord_message("", embeds=[embed])

def report_download_complete(source_url: str):
    embed = {
        "title": "✅ Hollywood Download Completed",
        "description": f"**Source:** {source_url}\n{get_run_details()}",
        "color": 3066993
    }
    send_discord_message("", embeds=[embed])

def report_edit_start():
    embed = {
        "title": "🟡 Video Editing Started",
        "description": get_run_details(),
        "color": 16776960
    }
    send_discord_message("", embeds=[embed])

def report_edit_complete():
    embed = {
        "title": "✅ Video Editing Completed",
        "description": get_run_details(),
        "color": 3066993
    }
    send_discord_message("", embeds=[embed])
