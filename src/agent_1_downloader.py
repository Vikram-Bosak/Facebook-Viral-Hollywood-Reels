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

HISTORY_FILE = 'downloaded_history.txt'



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
    """Searches People.com RSS feed for the latest video article and downloads it"""
    print("Fetching RSS feed for latest videos...")
    import xml.etree.ElementTree as ET
    scraper = cloudscraper.create_scraper()
    
    try:
        rss_url = "https://rss.app/feeds/TevFqDIlvlfHryLT.xml"
        xml_data = scraper.get(rss_url).text
        root = ET.fromstring(xml_data)
    except Exception as e:
        print(f"Failed to fetch RSS feed: {e}")
        return None, None, None, None
        
    history = load_history()
    
    # Find article links
    unique_links = []
    for item in root.findall('.//item'):
        link = item.find('link')
        if link is not None and link.text:
            href = link.text.strip()
            if 'people.com' in href and href not in unique_links:
                unique_links.append(href)
            
    print(f"Found {len(unique_links)} potential video articles from RSS.")
    
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
        os.makedirs('workspace', exist_ok=True)
        filename = f"workspace/raw_video.mp4"
        
        # Save metadata
        meta = {
            "title": title,
            "source_url": article_url,
            "video_id": video_id
        }
        with open("workspace/meta.json", "w") as f:
            json.dump(meta, f)
        
        try:
            print(f"Downloading {filename}...")
            response = requests.get(video_url, stream=True)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                print("Download complete.")
                return filename, title, video_id, article_url, video_url
            else:
                print(f"Failed to download video file. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error downloading video: {e}")
            
    print("No new valid videos found.")
    return None, None, None, None, None

def main():
    print("Starting Agent 1: People.com Downloader")
    
    os.makedirs('workspace', exist_ok=True)
    report = {
        "video_name": "N/A",
        "download_status": "Failed / No new video",
        "editing_status": "N/A",
        "upload_status": "N/A",
        "seo_title": "N/A",
        "description": "N/A",
        "facebook_url": "N/A"
    }
    with open('workspace/report.json', 'w') as f:
        json.dump(report, f)

    result = search_and_download_latest_video()
    if result and len(result) == 5:
        video_path, title, video_id, source_url, video_url = result
    else:
        video_path, title, video_id, source_url, video_url = None, None, None, None, None
    
    if video_path and os.path.exists(video_path):
        save_to_history(video_id)
        report["video_name"] = title
        report["download_status"] = "Success"
        with open('workspace/report.json', 'w') as f:
            json.dump(report, f)
        print("Agent 1 completed successfully.")
    else:
        print("No video downloaded.")

if __name__ == "__main__":
    main()
