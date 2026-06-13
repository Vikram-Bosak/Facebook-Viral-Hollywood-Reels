import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent_1_downloader import run_downloader
from src.agent_2_editor import process_video
from src.agent_3_uploader import run_upload
from src.common.limits import can_download, can_upload, increment_download, increment_edit
from src.common.telegram import (
    report_final_summary, 
    report_download_start, 
    report_download_complete, 
    report_edit_start, 
    report_edit_complete, 
    send_message
)

def run_single_sequence():
    print("\n--- STARTING SEQUENTIAL PIPELINE (SINGLE RUN) ---")
    
    if not can_download() or not can_upload():
        print("Daily upload limit reached. Exiting.")
        return False

    # 1. Download
    report_download_start()
    video_data = run_downloader()
    if not video_data:
        print("No video found.")
        send_message("⚠️ <b>Download Skipped:</b> No new videos found in any of the X (Twitter) profiles in the last 4 hours.")
        return False
        
    task_id = video_data['id']
    print(f"Downloaded Video: {task_id}")
    report_download_complete(video_data['source_url'])
    send_message(f"🆔 <b>Unique ID generated:</b> {task_id}")
    increment_download()
    
    # 2. Edit
    report_edit_start()
    try:
        print(f"Editing Video {task_id}...")
        video_data = process_video(video_data)
        if video_data.get('editing_status') == 'Success':
            report_edit_complete()
            increment_edit()
        else:
            send_message(f"❌ <b>Editing Failed for {task_id}</b>")
            return False
    except Exception as e:
        print(f"Editing failed: {e}")
        send_message(f"❌ <b>Editing Failed for {task_id}:</b>\n{e}")
        return False
        
    # 3. Upload
    print(f"Uploading Video {task_id}...")
    video_data = run_upload(video_data)
    
    # Final Report
    report_final_summary(video_data)
    
    print("Pipeline run completed.")
    return True

if __name__ == "__main__":
    run_single_sequence()
