import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
import yt_dlp
from dotenv import load_dotenv

load_dotenv()
HISTORY_FILE = 'downloaded_history.txt'

# Expanded profiles — more Hollywood news sources = more videos
PROFILES = [
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
]

# Time window: 12 hours instead of 4 — catches more videos per run
TIME_WINDOW_HOURS = 12

# Max videos to find per batch call (used by main_agent loop)
MAX_VIDEOS_PER_BATCH = 5

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(f.read().splitlines())
    return set()

def save_to_history(video_id):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def download_video_with_retry(tweet_url, tweet_id, max_retries=2):
    """Download a single video with retry logic."""
    ydl_opts_download = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'workspace/raw_video.mp4',
        'quiet': False,
        'no_warnings': True,
        'socket_timeout': 30,
        'retries': 3,
    }

    for attempt in range(max_retries + 1):
        try:
            os.makedirs('workspace', exist_ok=True)
            filename = "workspace/raw_video.mp4"
            if os.path.exists(filename):
                os.remove(filename)

            print(f"  Downloading with yt-dlp (attempt {attempt + 1}/{max_retries + 1})...")
            with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                info = ydl.extract_info(tweet_url, download=True)
                title = info.get('title', f"Twitter Video {tweet_id}")

            if os.path.exists(filename) and os.path.getsize(filename) > 10000:
                return filename, title
            else:
                print(f"  Downloaded file too small or missing, retrying...")
        except Exception as e:
            print(f"  Download attempt {attempt + 1} failed: {e}")
            if os.path.exists("workspace/raw_video.mp4"):
                os.remove("workspace/raw_video.mp4")

    return None, None

async def scrape_videos_from_profile(page, profile, time_limit, history):
    """Scrape video tweet URLs from a single profile. Returns list of (tweet_url, tweet_id)."""
    found_videos = []
    try:
        await page.goto(profile, timeout=30000)
        await page.wait_for_selector("article", timeout=15000)
        await page.wait_for_timeout(3000)

        articles = await page.query_selector_all("article")
        for article in articles:
            html = await article.inner_html()

            # Check if it's a video
            if "<video" not in html and "playback" not in html:
                continue

            # Extract timestamp
            time_element = await article.query_selector("time")
            is_within_window = False

            if time_element:
                datetime_str = await time_element.get_attribute("datetime")
                if datetime_str:
                    try:
                        post_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        if post_time >= time_limit:
                            is_within_window = True
                            print(f"  Found video post at {post_time.isoformat()}")
                    except ValueError:
                        pass

            # Fallback: relative time check
            if not is_within_window:
                status_links = await article.query_selector_all("a[href*='/status/']")
                for sl in status_links:
                    txt = (await sl.inner_text()).strip()
                    # Parse "34m", "2h", "5s" etc.
                    if txt and txt[-1].isdigit():
                        continue  # pure number, skip
                    if len(txt) >= 2 and txt[-1] in ('m', 'h', 's') and txt[:-1].isdigit():
                        val = int(txt[:-1])
                        unit = txt[-1]
                        if unit == 's' or (unit == 'm') or (unit == 'h' and val <= 12):
                            is_within_window = True
                            print(f"  Found recent post via relative time: {txt}")
                            break

            if not is_within_window:
                continue

            # Extract tweet link
            links = await article.query_selector_all("a[href*='/status/']")
            for link in links:
                href = await link.get_attribute("href")
                if href and "/status/" in href and "photo" not in href:
                    tweet_url = f"https://x.com{href}" if href.startswith("/") else href
                    tweet_id = tweet_url.split("/status/")[1].split("/")[0].split("?")[0]

                    if tweet_id in history:
                        print(f"  Video {tweet_id} already in history, skipping.")
                        break

                    found_videos.append((tweet_url, tweet_id))
                    break  # One video per article

    except Exception as e:
        print(f"  Error checking profile {profile}: {e}")

    return found_videos

async def search_and_download_latest_videos(count=1):
    """
    Search Twitter for new videos and download up to `count` videos.
    Returns list of video_data dicts.
    """
    print(f"Searching Twitter (X) for new videos (last {TIME_WINDOW_HOURS} hours, need {count})...")

    history = load_history()
    time_limit = datetime.now(timezone.utc) - timedelta(hours=TIME_WINDOW_HOURS)
    print(f"Time limit is set to: {time_limit.isoformat()}")

    # First pass: collect candidate video URLs from all profiles
    all_candidates = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        for profile in PROFILES:
            print(f"\n--- Checking profile: {profile} ---")
            candidates = await scrape_videos_from_profile(page, profile, time_limit, history)
            all_candidates.extend(candidates)
            print(f"  Total candidates so far: {len(all_candidates)}")
            # Early exit if we have enough candidates
            if len(all_candidates) >= count * 2:
                break

        await browser.close()

    if not all_candidates:
        print("\nNo new valid videos found across all profiles.")
        return []

    print(f"\n=== Found {len(all_candidates)} candidate videos. Downloading up to {count} ===\n")

    # Download videos one by one
    downloaded_videos = []
    for tweet_url, tweet_id in all_candidates:
        if len(downloaded_videos) >= count:
            break

        print(f"Trying: {tweet_url}")
        filename, title = download_video_with_retry(tweet_url, tweet_id)

        if filename and os.path.exists(filename):
            save_to_history(tweet_id)

            # Move downloaded file to a unique name so next download doesn't overwrite
            unique_path = f"workspace/raw_video_{tweet_id}.mp4"
            if os.path.exists(unique_path):
                os.remove(unique_path)
            os.rename(filename, unique_path)

            meta = {
                "title": title,
                "source_url": tweet_url,
                "video_id": tweet_id
            }
            with open(f"workspace/meta_{tweet_id}.json", "w") as f:
                json.dump(meta, f)

            video_data = {
                "id": tweet_id,
                "tweet_id": tweet_id,
                "title": title,
                "source_url": tweet_url,
                "local_path": unique_path,
                "status": "DOWNLOADED"
            }
            downloaded_videos.append(video_data)
            print(f"✅ Downloaded: {tweet_id} ({title})")
        else:
            print(f"❌ Failed to download: {tweet_url}")

    print(f"\n=== Download complete: {len(downloaded_videos)}/{count} videos ===")
    return downloaded_videos


# ─── Legacy single-video interface (used by old main_agent flow) ───

def run_downloader():
    """Download a single video. Used by the original pipeline."""
    print("Starting Agent 1: X (Twitter) Downloader")
    os.makedirs('workspace', exist_ok=True)

    results = asyncio.run(search_and_download_latest_videos(count=1))
    if results:
        print("Agent 1 completed successfully.")
        return results[0]

    print("No video downloaded.")
    return None


def run_downloader_batch(count=3):
    """Download multiple videos in one call. Used by the new multi-video pipeline."""
    print(f"Starting Agent 1: X (Twitter) Downloader — batch of {count}")
    os.makedirs('workspace', exist_ok=True)

    results = asyncio.run(search_and_download_latest_videos(count=count))
    if results:
        print(f"Agent 1 completed: {len(results)} videos downloaded.")
    else:
        print("No videos downloaded in batch.")

    return results


if __name__ == "__main__":
    run_downloader()
