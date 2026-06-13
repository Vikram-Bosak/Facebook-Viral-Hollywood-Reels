import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
import yt_dlp
from dotenv import load_dotenv

load_dotenv()
HISTORY_FILE = 'downloaded_history.txt'

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(f.read().splitlines())
    return set()

def save_to_history(video_id):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

async def search_and_download_latest_video():
    print("Searching Twitter (X) for new videos posted in the last 4 hours...")
    
    profiles = [
        "https://x.com/THR",
        "https://x.com/enews",
        "https://x.com/Variety",
        "https://x.com/FilmUpdates"
    ]
    
    history = load_history()
    
    ydl_opts_download = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'workspace/raw_video.mp4',
        'quiet': False
    }
    
    time_limit = datetime.now(timezone.utc) - timedelta(hours=4)
    print(f"Time limit is set to: {time_limit.isoformat()}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        for profile in profiles:
            print(f"--------------------------------------------------")
            print(f"Checking profile: {profile}")
            try:
                await page.goto(profile, timeout=30000)
                await page.wait_for_selector("article", timeout=15000)
                await page.wait_for_timeout(3000) # Wait for videos to load
                
                # Fetch articles
                articles = await page.query_selector_all("article")
                for article in articles:
                    html = await article.inner_html()
                    
                    # 1. Check if it's a video
                    if "<video" in html or "playback" in html:
                        # 2. Extract timestamp
                        time_element = await article.query_selector("time")
                        is_within_4_hours = False
                        
                        if time_element:
                            datetime_str = await time_element.get_attribute("datetime")
                            if datetime_str:
                                try:
                                    post_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                                    if post_time >= time_limit:
                                        is_within_4_hours = True
                                        print(f"Found video post at {post_time.isoformat()}")
                                except ValueError:
                                    pass
                        
                        if not is_within_4_hours:
                            # Fallback: check status link texts for relative times like "34m", "2h"
                            status_links = await article.query_selector_all("a[href*='/status/']")
                            for sl in status_links:
                                txt = await sl.inner_text()
                                txt = txt.strip()
                                if txt.endswith('m') and txt[:-1].isdigit():
                                    is_within_4_hours = True
                                    print(f"Found recent post via relative time: {txt}")
                                    break
                                elif txt.endswith('h') and txt[:-1].isdigit():
                                    if int(txt[:-1]) <= 4:
                                        is_within_4_hours = True
                                        print(f"Found recent post via relative time: {txt}")
                                        break
                                elif txt.endswith('s') and txt[:-1].isdigit():
                                    is_within_4_hours = True
                                    print(f"Found recent post via relative time: {txt}")
                                    break
                                    
                        # 3. Check 4-hour window
                        if not is_within_4_hours:
                            print("Post is older than 4 hours or timestamp unknown. Skipping.")
                            continue
                            
                        # 4. Extract link and download
                        links = await article.query_selector_all("a[href*='/status/']")
                        for link in links:
                            href = await link.get_attribute("href")
                            if href and "/status/" in href and "photo" not in href:
                                tweet_url = f"https://x.com{href}" if href.startswith("/") else href
                                tweet_id = tweet_url.split("/status/")[1].split("/")[0].split("?")[0]
                                
                                if tweet_id in history:
                                    print(f"Video {tweet_id} already in history, skipping...")
                                    break
                                    
                                print(f"Selected valid video within 4 hours: {tweet_url}")
                                
                                # Use yt-dlp to download it
                                try:
                                    os.makedirs('workspace', exist_ok=True)
                                    filename = "workspace/raw_video.mp4"
                                    if os.path.exists(filename):
                                        os.remove(filename)
                                        
                                    print(f"Downloading with yt-dlp...")
                                    with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                                        info = ydl.extract_info(tweet_url, download=True)
                                        title = info.get('title', f"Twitter Video {tweet_id}")
                                        
                                    meta = {
                                        "title": title,
                                        "source_url": tweet_url,
                                        "video_id": tweet_id
                                    }
                                    with open("workspace/meta.json", "w") as f:
                                        json.dump(meta, f)
                                        
                                    await browser.close()
                                    return filename, title, tweet_id, tweet_url, tweet_url
                                    
                                except Exception as e:
                                    print(f"Error downloading {tweet_url}: {e}")
                                    # Try next article
                                    pass
            except Exception as e:
                print(f"Error checking profile {profile}: {e}")
                
        await browser.close()
        
    print("--------------------------------------------------")
    print("No new valid videos found across all profiles within the last 4 hours.")
    return None, None, None, None, None

def run_downloader():
    print("Starting Agent 1: X (Twitter) Downloader")
    os.makedirs('workspace', exist_ok=True)
    
    result = asyncio.run(search_and_download_latest_video())
    if result and len(result) == 5:
        video_path, title, tweet_id, source_url, video_url = result
    else:
        video_path, title, tweet_id, source_url, video_url = None, None, None, None, None
        
    if video_path and os.path.exists(video_path):
        save_to_history(tweet_id)
        video_data = {
            "id": tweet_id,
            "tweet_id": tweet_id,
            "title": title,
            "source_url": source_url,
            "local_path": video_path,
            "status": "DOWNLOADED"
        }
        print("Agent 1 completed successfully.")
        return video_data
    
    print("No video downloaded.")
    return None

if __name__ == "__main__":
    run_downloader()
