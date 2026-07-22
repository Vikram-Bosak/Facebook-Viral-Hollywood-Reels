import os
import requests
import random
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure we can import existing modules
try:
    from src.facebook_uploader import upload_reel
    from src.youtube_uploader import upload_to_youtube
    from src.tiktok_uploader import upload_tiktok
except ImportError:
    from facebook_uploader import upload_reel
    from youtube_uploader import upload_to_youtube
    from tiktok_uploader import upload_tiktok

load_dotenv()

def run_upload(video_data):
    logging.info("Starting Agent 3: Facebook + YouTube Uploader")
    
    edited_video_path = video_data.get('edited_path')
    title = video_data.get('title', 'Unknown Video')
    headline = video_data.get('seo_title', '')
    source_url = video_data.get('source_url', '')
    
    if not edited_video_path or not os.path.exists(edited_video_path):
        logging.warning("No edited video found to upload.")
        return video_data
        
    if video_data.get("editing_status") != "Success":
        logging.warning(f"Editing did not succeed (Status: {video_data.get('editing_status')}). Skipping upload.")
        if os.path.exists(edited_video_path):
            os.remove(edited_video_path)
        return video_data
        
    # Construct Facebook Caption dynamically and parse YouTube SEO metadata
    yt_title = title
    yt_desc = ""
    yt_tags = []
    
    try:
        from src.common.seo_generator import generate_upload_metadata
        task_id = video_data.get("id", "default")
        state_file = f"temp/state_upload_{task_id}.json"
        
        if os.path.exists(state_file):
            import json
            with open(state_file, "r") as f:
                context = json.load(f)
        else:
            context = video_data
            
        metadata = generate_upload_metadata(context)
        fb_caption = f"{metadata.get('facebook_caption', headline)}\n\n{metadata.get('hashtags', '#Hollywood #Viral')}"
        yt_title = metadata.get('title', title)
        yt_desc = f"{metadata.get('description', '')}"
        yt_tags = metadata.get('tags', [])
    except Exception as e:
        logging.error(f"Error generating dynamic SEO metadata: {e}")
        fb_caption = f"{headline}\n\n#hollywood #viral #entertainment"
        yt_title = title
        yt_desc = fb_caption
        yt_tags = ["hollywood", "viral", "entertainment"]
        
    video_data["description"] = fb_caption

    # Human simulation delay: 15s to 2 minutes
    delay_seconds = random.randint(15, 120)
    delay_minutes = delay_seconds / 60
    logging.info(f"Waiting for {delay_seconds} seconds ({delay_minutes:.1f} minutes) before uploading to appear human...")
    
    try:
        from src.common.discord import send_discord_message as send_message
        send_message(f"⏳ <b>Simulation Delay Initiated:</b> Waiting {delay_minutes:.1f} minutes before upload to simulate human behavior...")
    except Exception as e:
        logging.warning(f"Failed to send delay report: {e}")
        
    time.sleep(delay_seconds)

    fb_success = False
    yt_success = False

    # Facebook Upload (Disabled for TikTok testing)
    logging.info("Facebook upload disabled for TikTok-only testing.")
    video_data["fb_url"] = "https://facebook.com/disabled-for-testing"
    fb_success = True
        
    # YouTube Upload (Disabled for TikTok testing)
    logging.info("YouTube Shorts upload disabled for TikTok-only testing.")
    video_data["yt_url"] = "https://youtube.com/disabled-for-testing"
    yt_success = True

    # TikTok Upload
    tt_success = False
    try:
        logging.info("Waiting 2 seconds before uploading to TikTok...")
        time.sleep(2)
        
        logging.info("Starting TikTok upload...")
        tiktok_url = upload_tiktok(edited_video_path, fb_caption)
        logging.info(f"Successfully uploaded to TikTok: {tiktok_url}")
        video_data["tiktok_url"] = tiktok_url
        tt_success = True
    except Exception as e:
        logging.error(f"Failed to upload to TikTok: {e}")
        video_data["tiktok_err"] = str(e)
        
    # Set overall status based on whether at least one upload succeeded
    if fb_success or yt_success or tt_success:
        video_data["upload_status"] = "Success"
        status_parts = []
        if fb_success:
            status_parts.append("Facebook")
        if yt_success:
            status_parts.append("YouTube")
        if tt_success:
            status_parts.append("TikTok")
        logging.info(f"Upload completed successfully to: {', '.join(status_parts)}")
    else:
        video_data["upload_status"] = "Failed"
        logging.error("All uploads (Facebook, YouTube, TikTok) failed.")
        
    # Cleanup — always runs regardless of upload outcome
    try:
        if os.path.exists(edited_video_path):
            os.remove(edited_video_path)
            logging.info(f"Cleaned up video file: {edited_video_path}")
    except Exception as e:
        logging.warning(f"Failed to clean up video file {edited_video_path}: {e}")
        
    return video_data

if __name__ == "__main__":
    pass
