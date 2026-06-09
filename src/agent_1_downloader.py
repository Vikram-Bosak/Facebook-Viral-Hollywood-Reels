import os
import sys
import yt_dlp
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TELEGRAM_BOT_TOKEN_1 = os.environ.get('TELEGRAM_BOT_TOKEN_1')
TELEGRAM_QUEUE_1_CHAT_ID = os.environ.get('TELEGRAM_QUEUE_1_CHAT_ID')  # Raw Videos Queue
HISTORY_FILE = 'downloaded_history.txt'

def send_video_to_telegram(video_path, caption, source_url):
    """Send downloaded video to Telegram Queue 1"""
    if not TELEGRAM_BOT_TOKEN_1 or not TELEGRAM_QUEUE_1_CHAT_ID:
        print("Telegram Bot Token or Queue 1 Chat ID is missing.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_1}/sendVideo"
    
    full_caption = f"{caption}\n\n🔗 Source: {source_url}\n#raw_video"
    
    with open(video_path, 'rb') as video:
        files = {'video': video}
        data = {'chat_id': TELEGRAM_QUEUE_1_CHAT_ID, 'caption': full_caption}
        
        print(f"Sending {video_path} to Telegram...")
        response = requests.post(url, data=data, files=files)
        
    if response.status_code == 200:
        print("Successfully sent video to Telegram.")
        return True
    else:
        print(f"Failed to send video: {response.text}")
        return False

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(f.read().splitlines())
    return set()

def save_to_history(video_id):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def search_and_download_shorts():
    """Searches YouTube for today's Hollywood News shorts and downloads the top trending one"""
    search_query = "Hollywood News #shorts"
    history = load_history()
    
    # We fetch top 20 results to give us room to filter by shorts and views, and skip already downloaded ones.
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'extract_flat': True,  # First extract metadata only
        'quiet': False,
        'dateafter': 'today' # Strict Today filter
    }

    print(f"Searching YouTube for: {search_query} (Today filter)")
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Get up to 20 search results
            search_url = f"ytsearch20:{search_query}"
            info = ydl.extract_info(search_url, download=False)
            entries = info.get('entries', [])
            
            valid_shorts = []
            for entry in entries:
                # Need to filter for duration < 60s
                duration = entry.get('duration')
                if duration and duration < 60:
                    valid_shorts.append(entry)
                    
            if not valid_shorts:
                print("No shorts found today.")
                return None, None, None
                
            # Sort by view count descending
            valid_shorts.sort(key=lambda x: x.get('view_count', 0), reverse=True)
            
            best_entry = None
            for entry in valid_shorts:
                if entry['id'] not in history:
                    best_entry = entry
                    break
                    
            if not best_entry:
                print("All trending shorts found have already been downloaded.")
                return None, None, None
                
            video_id = best_entry['id']
            title = best_entry['title']
            source_url = best_entry['url']
            
            print(f"Selected video: {title} ({video_id}) with {best_entry.get('view_count', 0)} views.")
            
            # Now actually download the selected video
            os.makedirs('downloads', exist_ok=True)
            download_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': f'downloads/{video_id}.%(ext)s',
                'quiet': False
            }
            
            with yt_dlp.YoutubeDL(download_opts) as dl:
                dl.download([source_url])
                
            filename = f"downloads/{video_id}.mp4"
            if os.path.exists(filename):
                return filename, title, video_id
            else:
                print("Download failed, file not found.")
                return None, None, None
                
        except Exception as e:
            print(f"Error searching/downloading video: {e}")
            return None, None, None

def main():
    print("Starting Agent 1: YouTube Downloader")
    video_path, title, video_id = search_and_download_shorts()
    
    if video_path and os.path.exists(video_path):
        source_url = f"https://www.youtube.com/watch?v={video_id}"
        caption = f"🎬 {title}"
        
        success = send_video_to_telegram(video_path, caption, source_url)
        if success:
            save_to_history(video_id)
            # Clean up raw download
            os.remove(video_path)
    else:
        print("No video downloaded.")

if __name__ == "__main__":
    main()
