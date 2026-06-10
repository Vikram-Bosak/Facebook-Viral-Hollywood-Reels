import os
import requests
import ffmpeg
import json
import textwrap
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Attempt to import openai
try:
    import openai
except ImportError:
    openai = None

load_dotenv()

TELEGRAM_BOT_TOKEN_2 = os.environ.get('TELEGRAM_BOT_TOKEN_2')
TELEGRAM_QUEUE_2_CHAT_ID = os.environ.get('TELEGRAM_QUEUE_2_CHAT_ID')  # Edited Videos Queue
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

if OPENAI_API_KEY and openai:
    openai.api_key = OPENAI_API_KEY

def get_latest_video_from_telegram():
    """Polls Telegram getUpdates for the latest raw video"""
    if not TELEGRAM_BOT_TOKEN_2:
        print("Telegram Bot Token is missing.")
        return None, None, None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_2}/getUpdates"
    print(f"Polling Telegram getUpdates... (timeout=15)")
    try:
        response = requests.get(url, params={'timeout': 10}, timeout=15)
        print(f"Telegram response status: {response.status_code}")
        data = response.json()
        
        if not data.get('ok') or not data.get('result'):
            print("No updates found in Telegram.")
            return None, None, None

        # Iterate backwards to find the most recent #raw_video
        for update in reversed(data['result']):
            message = update.get('message') or update.get('channel_post')
            if message and 'video' in message:
                caption = message.get('caption', '')
                if '#raw_video' in caption:
                    file_id = message['video']['file_id']
                    # Extract direct download URL to bypass 20MB limit
                    import re
                    match = re.search(r"📥 Video URL: (https?://[^\s]+)", caption)
                    download_url = match.group(1) if match else None
                    
                    # Clean up caption
                    raw_title = caption.replace('#raw_video', '').strip()
                    update_id = update['update_id']
                    print(f"Found raw video: file_id={file_id}")
                    return file_id, download_url, raw_title, update_id
                
        print("No raw video found in recent Telegram updates.")
        return None, None, None, None
    except Exception as e:
        print(f"Error fetching updates from Telegram: {e}")
        return None, None, None, None

def download_telegram_file(file_id, direct_url, output_path):
    if direct_url:
        print(f"Downloading directly from source URL to bypass Telegram limits...")
        try:
            file_response = requests.get(direct_url, stream=True, timeout=60)
            if file_response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=1024*1024):
                        if chunk: f.write(chunk)
                print("Direct download complete.")
                return True
        except Exception as e:
            print(f"Direct download failed: {e}. Falling back to Telegram getFile.")
            
    print(f"Fetching file path from Telegram for {file_id}")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_2}/getFile?file_id={file_id}"
    response = requests.get(url, timeout=10).json()
    if not response.get('ok'):
        print("Failed to get file path")
        return False
        
    file_path = response['result']['file_path']
    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN_2}/{file_path}"
    
    print(f"Downloading file from {download_url}...")
    file_response = requests.get(download_url, timeout=30)
    with open(output_path, 'wb') as f:
        f.write(file_response.content)
    print("Download complete.")
    return True

def generate_headline(title):
    """Uses Nvidia AI (via OpenAI client) to generate a short headline and wrap keywords in brackets"""
    if not openai or not OPENAI_API_KEY:
        print("OpenAI/Nvidia API key not found. Using default headline format.")
        # Default simple parser if no AI
        words = title.split()
        if len(words) > 2:
            return f"[{words[0]} {words[1]}] " + " ".join(words[2:])
        return f"[{title}]"
        
    try:
        # Use Nvidia's base URL as requested
        client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=OPENAI_API_KEY,
            timeout=30.0
        )
        
        prompt = (
            f"Analyze the following Hollywood news title: '{title}'. "
            "Generate a short, punchy 1-2 sentence headline for a vertical video reel. "
            "Identify the names of celebrities, entities, or key subjects, and enclose those specific words in brackets like [THIS]. "
            "Make it exciting and ALL CAPS. Example: 'YIKES! [MARIE MINKSSS] RUNS UP ON [MIMI LOVE]...'\n\n"
            "Output ONLY the headline text."
        )
        
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            top_p=0.95,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return f"[{title.upper()}] VIRAL NEWS!"

def download_font():
    """Downloads a bold font if not exists"""
    font_path = "assets/BebasNeue-Regular.ttf"
    os.makedirs('assets', exist_ok=True)
    if not os.path.exists(font_path):
        print("Downloading font...")
        url = "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"
        r = requests.get(url, timeout=20)
        with open(font_path, 'wb') as f:
            f.write(r.content)
        print("Font downloaded.")
    return font_path

def create_overlay_image(headline, output_img_path):
    """Generates a 1080x1920 transparent image with border, logo, and formatted text"""
    width, height = 1080, 1920
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0)) # Transparent
    draw = ImageDraw.Draw(img)
    
    # 1. Draw border
    border_color = (0, 255, 255, 255) # Cyan outer frame, or just White
    border_width = 15
    draw.rectangle([0, 0, width, height], outline=border_color, width=border_width)
    draw.rectangle([border_width, border_width, width-border_width, height-border_width], outline=(255, 255, 255, 255), width=5)
    
    # 2. Draw Logo (Placeholder if file doesn't exist)
    logo_y = int(height * 0.65) # Position below the video
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            # Scale logo width to max 600px
            lw, lh = logo.size
            if lw > 600:
                scale = 600 / lw
                logo = logo.resize((600, int(lh * scale)), Image.LANCZOS)
                lw, lh = logo.size
            img.paste(logo, ((width - lw) // 2, logo_y), logo)
            logo_bottom = logo_y + lh
        except Exception as e:
            print(f"Error loading logo: {e}")
            logo_bottom = logo_y
    else:
        # Draw placeholder text for Logo
        font_path = download_font()
        logo_font = ImageFont.truetype(font_path, 80)
        logo_text = "CELEBRITY BUZZ USA"
        bbox = draw.textbbox((0, 0), logo_text, font=logo_font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        draw.text(((width - lw) // 2, logo_y), logo_text, font=logo_font, fill=(0, 255, 255, 255))
        logo_bottom = logo_y + lh

    # 3. Draw formatted Text
    font_path = download_font()
    text_font = ImageFont.truetype(font_path, 90)
    
    # Simple word wrapping logic that supports color segments
    # We parse the brackets [WORD] into a list of (word, is_highlighted)
    tokens = []
    current_word = ""
    in_bracket = False
    for char in headline:
        if char == '[':
            if current_word:
                tokens.append((current_word, in_bracket))
                current_word = ""
            in_bracket = True
        elif char == ']':
            if current_word:
                tokens.append((current_word, in_bracket))
                current_word = ""
            in_bracket = False
        else:
            current_word += char
    if current_word:
        tokens.append((current_word, in_bracket))

    # Split into lines
    lines = []
    current_line = []
    current_line_width = 0
    max_text_width = width - 100 # 50px padding on sides
    
    space_width = draw.textlength(" ", font=text_font)
    
    # This is a basic wrapper. It assumes tokens don't contain spaces internally that need breaking.
    # We will split tokens by space first for safer wrapping.
    flat_words = []
    for text, is_highlight in tokens:
        for word in text.split(' '):
            if word:
                flat_words.append((word, is_highlight))
                
    for word, is_highlight in flat_words:
        w = draw.textlength(word, font=text_font)
        if current_line_width + w + space_width > max_text_width:
            lines.append(current_line)
            current_line = [(word, is_highlight)]
            current_line_width = w
        else:
            current_line.append((word, is_highlight))
            current_line_width += w + (space_width if current_line_width > 0 else 0)
            
    if current_line:
        lines.append(current_line)
        
    text_y_start = logo_bottom + 80
    
    for line in lines:
        # Calculate total line width to center it
        line_w = sum(draw.textlength(w, font=text_font) for w, h in line) + space_width * (len(line) - 1)
        x_pos = (width - line_w) / 2
        
        for word, is_highlight in line:
            color = (0, 255, 255, 255) if is_highlight else (255, 255, 255, 255)
            draw.text((x_pos, text_y_start), word, font=text_font, fill=color)
            x_pos += draw.textlength(word, font=text_font) + space_width
            
        text_y_start += 100 # Line height

    img.save(output_img_path)

def edit_video(input_vid_path, overlay_img_path, output_vid_path):
    """Composites the raw video onto a 1080x1920 black background and applies the transparent overlay"""
    print("Compositing video...")
    try:
        # Base black canvas
        base = ffmpeg.input('color=c=black:s=1080x1920', f='lavfi', t=1) # Temporary dummy
        
        # Raw video
        vid = ffmpeg.input(input_vid_path)
        
        # Overlay image
        overlay = ffmpeg.input(overlay_img_path)
        
        # Scale video to fit 1080 width, maintaining aspect ratio. 
        # Then pad to 1080x1920 to create the full canvas.
        scaled_vid = vid.video.filter('scale', 1080, -1).filter('pad', 1080, 1920, 0, 150, color='black')
        
        # Now overlay the transparent Pillow image on top
        final = ffmpeg.overlay(scaled_vid, overlay, x=0, y=0)
        
        # Output with audio (limited to 59 seconds for Reels)
        out = ffmpeg.output(final, vid.audio, output_vid_path, vcodec='libx264', acodec='aac', t=59, shortest=None)
        
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        print("Video editing completed.")
        return True
    except Exception as e:
        print(f"Error during video editing: {e}")
        return False

def send_video_to_queue_2(video_path, caption):
    if not TELEGRAM_QUEUE_2_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_2}/sendVideo"
    with open(video_path, 'rb') as video:
        files = {'video': video}
        data = {'chat_id': TELEGRAM_QUEUE_2_CHAT_ID, 'caption': f"{caption}\n#edited_video"}
        print("Sending edited video to Queue 2...")
        response = requests.post(url, data=data, files=files)
    return response.status_code == 200

def acknowledge_update(update_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_2}/getUpdates"
    requests.get(url, params={'offset': update_id + 1})

def main():
    print("Starting Agent 2: Video Editor")
    os.makedirs('workspace', exist_ok=True)
    
    file_id, direct_url, raw_caption, update_id = get_latest_video_from_telegram()
    
    if file_id:
        raw_video_path = "workspace/raw_video.mp4"
        overlay_path = "workspace/overlay.png"
        edited_video_path = "workspace/edited_video.mp4"
        
        if download_telegram_file(file_id, direct_url, raw_video_path):
            headline = generate_headline(raw_caption)
            print(f"Generated Headline: {headline}")
            
            create_overlay_image(headline, overlay_path)
            
            if edit_video(raw_video_path, overlay_path, edited_video_path):
                if send_video_to_queue_2(edited_video_path, raw_caption):
                    acknowledge_update(update_id)
            
        # Cleanup
        if os.path.exists(raw_video_path): os.remove(raw_video_path)
        if os.path.exists(overlay_path): os.remove(overlay_path)
        if os.path.exists(edited_video_path): os.remove(edited_video_path)
    else:
        print("No video to process.")

if __name__ == "__main__":
    main()
