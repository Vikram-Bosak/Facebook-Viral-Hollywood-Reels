import os
import sys
import cloudscraper
import requests
import json
import uuid
import re
from bs4 import BeautifulSoup
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

def get_video_from_people_article(scraper, url):
    try:
        html = scraper.get(url).text
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')
        
        for s in scripts:
            try:
                data = json.loads(s.string)
                # Handle both list of schemas and single schema
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if item.get('@type') == 'VideoObject':
                        video_url = item.get('contentUrl')
                        title = item.get('name', 'People Video')
                        # generate a safe ID
                        video_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
                        if video_url:
                            return video_url, title, video_id
            except:
                pass
    except Exception as e:
        print(f"Error extracting video from {url}: {e}")
    return None, None, None

def search_and_download_latest_video():
    """Searches People.com/video for the latest video article and downloads it"""
    print("Scraping People.com/video for latest videos...")
    scraper = cloudscraper.create_scraper()
    
    try:
        html = scraper.get("https://people.com/video").text
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        print(f"Failed to scrape index page: {e}")
        return None, None, None, None
        
    history = load_history()
    
    # Find article links
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'people.com' in href and '/video/' not in href and len(href) > 40:
            links.append(href)
            
    # Remove duplicates while preserving order (first usually latest)
    seen = set()
    unique_links = []
    for l in links:
        if l not in seen:
            seen.add(l)
            unique_links.append(l)
            
    print(f"Found {len(unique_links)} potential video articles.")
    
    for article_url in unique_links:
        video_url, title, video_id = get_video_from_people_article(scraper, article_url)
        if not video_url:
            continue
            
        if video_id in history:
            print(f"Video {video_id} already downloaded. Skipping...")
            continue
            
        print(f"Selected video: {title} from {article_url}")
        print(f"Download URL: {video_url}")
        
        # Download the video
        os.makedirs('downloads', exist_ok=True)
        filename = f"downloads/{video_id}.mp4"
        
        try:
            print(f"Downloading {filename}...")
            response = requests.get(video_url, stream=True)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                print("Download complete.")
                return filename, title, video_id, article_url
            else:
                print(f"Failed to download video file. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error downloading video: {e}")
            
    print("No new valid videos found.")
    return None, None, None, None

def main():
    print("Starting Agent 1: People.com Downloader")
    video_path, title, video_id, source_url = search_and_download_latest_video()
    
    if video_path and os.path.exists(video_path):
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
