import os
import sys
import time
import json
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent_1_downloader import run_downloader_batch, save_to_history
from src.agent_2_editor import process_video
from src.agent_3_uploader import run_upload
from src.common.limits import can_download, can_upload, increment_download, increment_edit, increment_upload
from src.common.discord import (
    report_download_start, 
    report_download_complete, 
    report_edit_start, 
    report_edit_complete, 
    send_discord_message as send_message
)

# ─── Config ───
VIDEOS_PER_RUN = 1  # 1 video per run to avoid Facebook rate limits

def write_report(report_data):
    os.makedirs("workspace", exist_ok=True)
    try:
        with open("workspace/report.json", "w") as f:
            json.dump(report_data, f, indent=4)
        print("Report written to workspace/report.json")
    except Exception as e:
        print(f"Warning: Failed to write report: {e}")

def push_history_mid_run():
    print("Pushing history to GitHub immediately to prevent race conditions...")
    try:
        subprocess.run("git config --global user.name 'github-actions[bot]'", shell=True)
        subprocess.run("git config --global user.email 'github-actions[bot]@users.noreply.github.com'", shell=True)
        subprocess.run("git add downloaded_history.txt", shell=True, check=True)
        subprocess.run("git add temp/daily_limits.json", shell=True, check=True)
        subprocess.run("git commit -m 'Update history (mid-run)'", shell=True, check=True)
        subprocess.run("git pull origin main --rebase --strategy-option=ours", shell=True, check=True)
        subprocess.run("git push origin HEAD:main", shell=True, check=True)
        print("History pushed successfully.")
    except Exception as e:
        print(f"Warning: Mid-run history push failed: {e}")

def run_single_video(video_data, video_number, total, report_data):
    """Process a single video through edit + upload. Returns True on success."""
    task_id = video_data['id']
    title = video_data.get('title', '')
    source_url = video_data.get('source_url', '')

    print(f"\n{'='*50}")
    print(f"  Processing video {video_number}/{total}: {task_id}")
    print(f"{'='*50}")

    report_data["video_name"] = title if title else task_id
    report_data["download_status"] = "Success"
    write_report(report_data)

    # Pre-screening text metadata safety check
    from src.common.safety_filter import check_metadata_safety
    safety_check = check_metadata_safety(title, source_url)
    if not safety_check["is_safe"]:
        reasons = ", ".join(safety_check["reasons"])
        print(f"Video {task_id} rejected by safety filter: {reasons}")
        send_message(f"⚠️ <b>Video {task_id} Rejected by Safety Filter:</b>\n{reasons}")
        report_data["download_status"] = f"Rejected (Safety: {reasons})"
        write_report(report_data)
        save_to_history(task_id)
        push_history_mid_run()
        return False

    report_download_complete(source_url)
    send_message(f"🆔 <b>Video {video_number}/{total} — ID:</b> {task_id}")
    increment_download()
    
    # Save to history immediately to prevent parallel execution conflicts
    save_to_history(task_id)
    push_history_mid_run()

    # 2. Edit
    report_edit_start()
    report_data["editing_status"] = "Pending"
    write_report(report_data)
    try:
        print(f"Editing Video {task_id}...")
        video_data = process_video(video_data)
        if video_data.get('editing_status') == 'Success':
            report_edit_complete()
            increment_edit()
            report_data["editing_status"] = "Success"
            write_report(report_data)
        else:
            send_message(f"❌ <b>Editing Failed for {task_id}</b>")
            report_data["editing_status"] = "Failed"
            write_report(report_data)
            return False
    except Exception as e:
        print(f"Editing failed: {e}")
        send_message(f"❌ <b>Editing Failed for {task_id}:</b>\n{e}")
        report_data["editing_status"] = f"Failed ({str(e)})"
        write_report(report_data)
        return False

    # 3. Upload
    print(f"Uploading Video {task_id}...")
    report_data["upload_status"] = "Pending"
    write_report(report_data)
    
    video_data = run_upload(video_data)

    if video_data.get('upload_status') == 'Success':
        increment_upload()

    report_data["upload_status"] = video_data.get('upload_status', 'Failed')
    report_data["facebook_url"] = video_data.get('fb_url', 'N/A')
    report_data["youtube_url"] = video_data.get('yt_url', 'N/A')
    report_data["tiktok_url"] = video_data.get('tiktok_url', 'N/A')
    report_data["seo_title"] = video_data.get('seo_title', 'N/A')
    report_data["description"] = video_data.get('description', 'N/A')
    write_report(report_data)
    
    return True

def run_multi_sequence():
    """
    Main pipeline: download videos and process each one.
    Target: VIDEOS_PER_RUN videos per GitHub Actions run.
    """
    print(f"\n{'#'*60}")
    print(f"  STARTING PIPELINE (target: {VIDEOS_PER_RUN} video per run)")
    print(f"{'#'*60}\n")

    report_data = {
        "video_name": "N/A",
        "download_status": "Failed / Unknown",
        "editing_status": "N/A",
        "upload_status": "N/A",
        "seo_title": "N/A",
        "description": "N/A",
        "facebook_url": "N/A",
        "youtube_url": "N/A"
    }

    if not can_download() or not can_upload():
        print("Daily upload limit reached. Exiting.")
        report_data["download_status"] = "Skipped (Daily limit reached)"
        write_report(report_data)
        return False

    # Step 1: Batch download
    report_download_start()
    downloaded_videos = run_downloader_batch(count=VIDEOS_PER_RUN)

    if not downloaded_videos:
        send_message("⚠️ <b>Batch Download:</b> No new videos found across all X profiles.")
        print("No videos downloaded. Exiting pipeline.")
        report_data["download_status"] = "No new video found"
        write_report(report_data)
        return False

    print(f"\n✅ Downloaded {len(downloaded_videos)} videos. Starting processing...\n")

    # Step 2: Process each video
    success_count = 0
    fail_count = 0
    for idx, video_data in enumerate(downloaded_videos, 1):
        try:
            ok = run_single_video(video_data, idx, len(downloaded_videos), report_data)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"Unexpected error processing video {idx}: {e}")
            send_message(f"❌ <b>Unexpected error on video {idx}/{len(downloaded_videos)}:</b>\n{e}")
            fail_count += 1

    summary = (
        f"📊 <b>Pipeline Batch Complete</b>\n\n"
        f"✅ Successful: <b>{success_count}</b>\n"
        f"❌ Failed: <b>{fail_count}</b>\n"
        f"📥 Total Downloaded: <b>{len(downloaded_videos)}</b>"
    )
    send_message(summary)
    print(f"\n{'#'*60}")
    print(f"  PIPELINE FINISHED — {success_count} success, {fail_count} failed")
    print(f"{'#'*60}\n")

    return success_count > 0

if __name__ == "__main__":
    run_multi_sequence()
