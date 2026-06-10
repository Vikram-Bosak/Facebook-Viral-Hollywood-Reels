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

def main():
    print("Starting Agent 3: Facebook Uploader")
    
    edited_video_path = "workspace/edited_video.mp4"
    meta_path = "workspace/meta.json"
    
    if not os.path.exists(edited_video_path) or not os.path.exists(meta_path):
        print("No edited video or meta.json found in workspace.")
        return
        
    import json
    with open(meta_path, 'r') as f:
        meta = json.load(f)
        
    title = meta.get('title', 'Unknown Video')
    headline = meta.get('headline', '')
    source_url = meta.get('source_url', '')
    
    # Construct Facebook Caption
    fb_caption = f"{headline}\n\n#hollywood #viral #entertainment\n\nOriginal Title: {title}\nSource: {source_url}"
    
    try:
        print(f"Uploading to Facebook with caption: {fb_caption}")
        fb_url = upload_reel(edited_video_path, fb_caption)
        print(f"Successfully uploaded: {fb_url}")
        report_success("edited_video.mp4", fb_caption, fb_url, 0, "reel")
    except Exception as e:
        print(f"Failed to upload to Facebook: {e}")
        report_failure("edited_video.mp4", str(e), 0, "reel")
        
    # Cleanup
    if os.path.exists(edited_video_path):
        os.remove(edited_video_path)
    if os.path.exists(meta_path):
        os.remove(meta_path)

if __name__ == "__main__":
    main()
