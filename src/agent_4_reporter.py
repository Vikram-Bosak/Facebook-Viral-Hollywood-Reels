import os
import json
import requests
import shutil

def send_telegram_message(message):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Telegram bot configuration is missing. Skipping Telegram notification.")
        return False
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        print("Successfully sent unified Telegram report.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")
        return False

def main():
    print("Starting Agent 4: Unified Reporter")
    report_path = "workspace/report.json"
    
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            try:
                report = json.load(f)
            except json.JSONDecodeError:
                report = {}
    else:
        report = {}
        
    # Default values in case keys are missing
    video_name = report.get('video_name', 'N/A')
    download_status = report.get('download_status', 'Failed / Unknown')
    editing_status = report.get('editing_status', 'N/A')
    upload_status = report.get('upload_status', 'N/A')
    seo_title = report.get('seo_title', 'N/A')
    description = report.get('description', 'N/A')
    fb_url = report.get('facebook_url', 'N/A')
    
    # Determine YouTube Status
    yt_url = report.get('youtube_url', 'N/A')
    yt_status = "Success" if "youtube.com" in yt_url or "youtu.be" in yt_url else "Failed / N/A"
    
    # GitHub Action Variables
    repo = os.environ.get('GITHUB_REPOSITORY', 'Vikram-Bosak/Facebook-Viral-Hollywood-Reels')
    run_id = os.environ.get('GITHUB_RUN_ID', 'UNKNOWN')
    repo_url = f"https://github.com/{repo}"
    run_url = f"{repo_url}/actions/runs/{run_id}"
    
    emoji_status = "✅" if upload_status == "Success" else "❌"
    
    message = (
        f"{emoji_status} <b>Pipeline Run Completed</b>\n\n"
        f"🎬 <b>Video Name:</b>\n{video_name}\n\n"
        f"📥 <b>Download Status:</b> {download_status}\n"
        f"✂️ <b>Editing Status:</b> {editing_status}\n"
        f"📤 <b>Facebook Upload Status:</b> {upload_status}\n"
        f"📤 <b>YouTube Upload Status:</b> {yt_status}\n\n"
        f"🏷️ <b>SEO Title:</b>\n{seo_title}\n\n"
        f"📝 <b>Description:</b>\n{description}\n\n"
        f"🔗 <b>Facebook Reel URL:</b>\n{fb_url}\n\n"
        f"▶️ <b>YouTube Video URL:</b>\n{yt_url}\n\n"
        f"📦 <b>GitHub Repository:</b>\n{repo_url}\n\n"
        f"📄 <b>Workflow Run:</b>\n{run_url}"
    )
    
    if "No new video" in download_status:
        print("No new video to process. Skipping Telegram notification to avoid spam.")
    else:
        send_telegram_message(message)
    
    # Cleanup workspace completely
    if os.path.exists("workspace"):
        shutil.rmtree("workspace")
        print("Cleaned up workspace directory.")

if __name__ == "__main__":
    main()
