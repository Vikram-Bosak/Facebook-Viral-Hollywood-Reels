import os
import sys
import time
import shutil

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent_1_downloader import run_downloader_batch
from src.agent_2_editor import process_video
from src.agent_3_uploader import run_upload
from src.common.telegram import (
    report_final_summary, 
    report_download_start, 
    report_download_complete, 
    report_edit_start, 
    report_edit_complete, 
    send_message
)

# ─── Config ───
VIDEOS_PER_RUN = 1  # 1 video per run to avoid Facebook rate limits


def run_single_video(video_data, video_number, total):
    """Process a single video through edit + upload. Returns True on success."""
    task_id = video_data['id']
    print(f"\n{'='*50}")
    print(f"  Processing video {video_number}/{total}: {task_id}")
    print(f"{'='*50}")

    report_download_complete(video_data['source_url'])
    send_message(f"🆔 <b>Video {video_number}/{total} — ID:</b> {task_id}")

    # 2. Edit
    report_edit_start()
    try:
        print(f"Editing Video {task_id}...")
        video_data = process_video(video_data)
        if video_data.get('editing_status') == 'Success':
            report_edit_complete()
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
    return True


def run_multi_sequence():
    """
    Main pipeline: download videos and process each one.
    Target: VIDEOS_PER_RUN videos per GitHub Actions run.
    """
    print(f"\n{'#'*60}")
    print(f"  STARTING PIPELINE (target: {VIDEOS_PER_RUN} video per run)")
    print(f"{'#'*60}\n")

    # Step 1: Batch download — get up to VIDEOS_PER_RUN videos at once
    report_download_start()
    downloaded_videos = run_downloader_batch(count=VIDEOS_PER_RUN)

    if not downloaded_videos:
        send_message("⚠️ <b>Batch Download:</b> No new videos found across all Twitter profiles.")
        print("No videos downloaded. Exiting pipeline.")
        return False

    print(f"\n✅ Downloaded {len(downloaded_videos)} videos. Starting processing...\n")

    # Step 2: Process each video (edit + upload)
    success_count = 0
    fail_count = 0
    for idx, video_data in enumerate(downloaded_videos, 1):
        try:
            ok = run_single_video(video_data, idx, len(downloaded_videos))
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"Unexpected error processing video {idx}: {e}")
            send_message(f"❌ <b>Unexpected error on video {idx}/{len(downloaded_videos)}:</b>\n{e}")
            fail_count += 1

    # Step 3: Send summary
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


# ─── Legacy single-video mode (kept for backward compatibility) ───
def run_single_sequence():
    """Process just 1 video. Used for testing."""
    from src.agent_1_downloader import run_downloader
    from src.common.limits import can_download, can_upload, increment_download, increment_edit

    print("\n--- STARTING SEQUENTIAL PIPELINE (SINGLE RUN) ---")

    if not can_download() or not can_upload():
        print("Daily upload limit reached. Exiting.")
        return False

    # 1. Download
    report_download_start()
    video_data = run_downloader()
    if not video_data:
        print("No video found.")
        send_message("⚠️ <b>Download Skipped:</b> No new videos found.")
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
    run_multi_sequence()
