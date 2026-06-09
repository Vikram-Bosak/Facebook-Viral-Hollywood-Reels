import os
import requests
from dotenv import load_dotenv

# Ensure we can import existing modules
try:
    from src.facebook_uploader import upload_reel
    from src.telegram_reporter import report_success, report_failure
except ImportError:
    from facebook_uploader import upload_reel
    from telegram_reporter import report_success, report_failure

load_dotenv()

TELEGRAM_BOT_TOKEN_3 = os.environ.get('TELEGRAM_BOT_TOKEN_3')

def get_latest_edited_video_from_telegram():
    """Polls Telegram getUpdates for the latest edited video message"""
    if not TELEGRAM_BOT_TOKEN_3:
        print("Telegram Bot Token is missing.")
        return None, None, None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_3}/getUpdates"
    try:
        response = requests.get(url, params={'timeout': 10})
        data = response.json()
        
        if not data.get('ok') or not data.get('result'):
            print("No updates found in Telegram.")
            return None, None, None

        # Iterate forwards to find the oldest #edited_video (FIFO Queue)
        for update in data['result']:
            message = update.get('message') or update.get('channel_post')
            if message and 'video' in message:
                caption = message.get('caption', '')
                if '#edited_video' in caption:
                    file_id = message['video']['file_id']
                    # Clean up the caption for Facebook
                    fb_caption = caption.replace('#edited_video', '').strip()
                    update_id = update['update_id']
                    return file_id, fb_caption, update_id
                
        print("No edited video found in recent Telegram updates.")
        return None, None, None
    except Exception as e:
        print(f"Error fetching updates from Telegram: {e}")
        return None, None, None

def download_telegram_file(file_id, output_path):
    """Downloads a file from Telegram by file_id"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_3}/getFile?file_id={file_id}"
    response = requests.get(url).json()
    
    if not response.get('ok'):
        print("Failed to get file path from Telegram.")
        return False
        
    file_path = response['result']['file_path']
    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN_3}/{file_path}"
    
    print(f"Downloading edited video from Telegram: {file_path}")
    file_response = requests.get(download_url)
    with open(output_path, 'wb') as f:
        f.write(file_response.content)
        
    return True

def acknowledge_update(update_id):
    """Acknowledges the update so it's not processed again"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_3}/getUpdates"
    requests.get(url, params={'offset': update_id + 1})

def main():
    print("Starting Agent 3: Facebook Uploader")
    os.makedirs('workspace', exist_ok=True)
    
    file_id, fb_caption, update_id = get_latest_edited_video_from_telegram()
    
    if file_id:
        video_path = "workspace/final_upload_video.mp4"
        
        if download_telegram_file(file_id, video_path):
            try:
                print(f"Uploading to Facebook with caption: {fb_caption}")
                fb_url = upload_reel(video_path, fb_caption)
                print(f"Successfully uploaded: {fb_url}")
                report_success("final_upload_video.mp4", fb_caption, fb_url, 0, "reel")
                acknowledge_update(update_id)
            except Exception as e:
                print(f"Failed to upload to Facebook: {e}")
                report_failure("final_upload_video.mp4", str(e), 0, "reel")
            
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
    else:
        print("No edited video to process.")

if __name__ == "__main__":
    main()
