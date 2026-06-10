import os
import requests
import random
import time
from dotenv import load_dotenv

# Ensure we can import existing modules
try:
    from src.facebook_uploader import upload_reel
except ImportError:
    from facebook_uploader import upload_reel

load_dotenv()

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
    
    report_path = "workspace/report.json"
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            report = json.load(f)
    else:
        print("No report.json found. Cannot verify editing status.")
        return

    if report.get("editing_status") != "Success":
        print(f"Editing did not succeed (Status: {report.get('editing_status')}). Skipping upload.")
        # Cleanup
        if os.path.exists(edited_video_path):
            os.remove(edited_video_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return
        
    report["description"] = fb_caption

    # Add a random delay between 1 and 20 minutes (60 to 1200 seconds) to seem more human-like
    delay_seconds = random.randint(60, 1200)
    delay_minutes = delay_seconds // 60
    print(f"Waiting for {delay_minutes} minutes and {delay_seconds % 60} seconds before uploading to appear human...")
    time.sleep(delay_seconds)

    try:
        print(f"Uploading to Facebook with caption: {fb_caption}")
        fb_url = upload_reel(edited_video_path, fb_caption)
        print(f"Successfully uploaded: {fb_url}")
        
        report["upload_status"] = "Success"
        report["facebook_url"] = fb_url
    except Exception as e:
        print(f"Failed to upload to Facebook: {e}")
        report["upload_status"] = "Failed"
        report["facebook_url"] = str(e)
        
    with open(report_path, 'w') as f:
        json.dump(report, f)
        
    # Cleanup
    if os.path.exists(edited_video_path):
        os.remove(edited_video_path)
    if os.path.exists(meta_path):
        os.remove(meta_path)

if __name__ == "__main__":
    main()
