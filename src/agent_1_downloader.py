import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import yt_dlp
from dotenv import load_dotenv

load_dotenv()
HISTORY_FILE = 'downloaded_history.txt'

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_to_history(video_id):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def search_and_download_latest_videos(count=1):
    print(f"Searching Twitter (via Nitter RSS) for new Hollywood videos (need {count})...")
    
    profiles = [
        "https://x.com/THR",
        "https://x.com/enews",
        "https://x.com/Variety",
        "https://x.com/FilmUpdates",
        "https://x.com/DEADLINE",
        "https://x.com/PopCrave",
        "https://x.com/JustJared",
        "https://x.com/etnow",
        "https://x.com/people",
        "https://x.com/MTVNEWS",
        "https://x.com/PopBase",
        "https://x.com/HollywoodHandle",
        "https://x.com/culturecrave",
        "https://x.com/extratv",
        "https://x.com/DailyLoud",
        "https://x.com/IMDb",
        "https://x.com/DiscussingFilm",
        "https://x.com/etalkCTV",
        "https://x.com/BuzzFeed",
        "https://x.com/Complex"
    ]
        
    usernames = []
    for p in profiles:
        if "x.com/" in p:
            usernames.append(p.split("x.com/")[-1].strip("/"))
        elif "twitter.com/" in p:
            usernames.append(p.split("twitter.com/")[-1].strip("/"))
        else:
            usernames.append(p)
            
    history = load_history()
    
    ydl_opts_download = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'workspace/raw_video.mp4',
        'quiet': False
    }
    
    # 12 hours lookback
    time_limit = datetime.now(timezone.utc) - timedelta(hours=12)
    print(f"Time limit is set to: {time_limit.isoformat()}")
    
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.privacydev.net",
        "https://nitter.poast.org"
    ]
    
    valid_videos = []
    
    for username in usernames:
        print(f"--------------------------------------------------")
        print(f"Checking profile: {username}")
        
        rss_fetched = False
        items = []
        for instance in nitter_instances:
            url = f"{instance}/{username}/rss"
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    xml_data = response.read()
                    root = ET.fromstring(xml_data)
                    items = root.findall('.//item')
                    rss_fetched = True
                    break
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")
                
        if not rss_fetched:
            print(f"Could not fetch RSS for {username} on any Nitter instance.")
            continue
            
        for item in items:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            pubDate_str = item.find('pubDate').text if item.find('pubDate') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            
            if not link or not pubDate_str:
                continue
                
            # Check if it's a video
            if ">Video<" not in desc and "Video" not in desc:
                continue
                
            # Extract tweet ID and check history
            try:
                tweet_id = link.split("/status/")[1].split("#")[0].split("?")[0]
            except Exception:
                continue
                
            # Check exact post time
            try:
                post_time = parsedate_to_datetime(pubDate_str)
                if post_time.tzinfo is None:
                    post_time = post_time.replace(tzinfo=timezone.utc)
            except Exception as e:
                print(f"Error parsing date {pubDate_str}: {e}")
                continue
                
            if post_time < time_limit:
                print(f"Post {tweet_id} is older than 12 hours. Moving to next profile.")
                break
                
            if tweet_id in history:
                print(f"Video {tweet_id} already in history, skipping...")
                continue
                
            original_tweet_url = f"https://x.com/{username}/status/{tweet_id}"
            valid_videos.append({
                "tweet_id": tweet_id,
                "url": original_tweet_url,
                "post_time": post_time,
                "title": title
            })
            
    print("--------------------------------------------------")
    if not valid_videos:
        print("No new valid videos found across all profiles.")
        return []
        
    # Sort valid videos by post_time (oldest first)
    valid_videos.sort(key=lambda x: x["post_time"])
    
    downloaded_videos = []
    for video in valid_videos:
        if len(downloaded_videos) >= count:
            break
            
        tweet_id = video["tweet_id"]
        original_tweet_url = video["url"]
        clean_title = video["title"]
        
        print(f"Selected valid NEW video: {original_tweet_url}")
        
        try:
            os.makedirs('workspace', exist_ok=True)
            temp_path = "workspace/raw_video.mp4"
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            print(f"Downloading with yt-dlp...")
            # Use unique path for batch downloads
            unique_path = f"workspace/raw_video_{tweet_id}.mp4"
            if os.path.exists(unique_path):
                os.remove(unique_path)
                
            ydl_opts_download['outtmpl'] = unique_path
            with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                info = ydl.extract_info(original_tweet_url, download=True)
                download_title = info.get('title', clean_title)
                
            meta = {
                "title": download_title,
                "source_url": original_tweet_url,
                "video_id": tweet_id
            }
            with open(f"workspace/meta_{tweet_id}.json", "w") as f:
                json.dump(meta, f)
                
            video_data = {
                "id": tweet_id,
                "tweet_id": tweet_id,
                "title": download_title,
                "source_url": original_tweet_url,
                "local_path": unique_path,
                "status": "DOWNLOADED"
            }
            downloaded_videos.append(video_data)
            print(f"✅ Downloaded: {tweet_id} ({download_title})")
            
        except Exception as e:
            print(f"Error downloading {original_tweet_url}: {e}")
            continue
            
    return downloaded_videos

def run_downloader():
    print("Starting Agent 1: X (Twitter) Downloader")
    os.makedirs('workspace', exist_ok=True)
    results = search_and_download_latest_videos(count=1)
    if results:
        return results[0]
    return None

def run_downloader_batch(count=3):
    print(f"Starting Agent 1: X (Twitter) Downloader — batch of {count}")
    os.makedirs('workspace', exist_ok=True)
    return search_and_download_latest_videos(count=count)

if __name__ == "__main__":
    run_downloader()
