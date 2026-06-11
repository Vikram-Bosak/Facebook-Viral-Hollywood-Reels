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


OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

if OPENAI_API_KEY and openai:
    openai.api_key = OPENAI_API_KEY



def generate_headline(title):
    """Uses Nvidia AI (via OpenAI client) to generate a short headline and wrap keywords in brackets"""
    if not openai or not OPENAI_API_KEY:
        print("OpenAI/Nvidia API key not found. Using default headline format.")
        # Default simple parser if no AI
        words = title.split()
        if len(words) > 2:
            return {"hook": f"{words[0]} {words[1]} " + " ".join(words[2:]) + " VIRAL", "highlights": ["VIRAL"]}
        return {"hook": f"{title} VIRAL", "highlights": ["VIRAL"]}
        
    try:
        # Use Nvidia's base URL as requested
        client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=OPENAI_API_KEY,
            timeout=30.0
        )
        
        prompt = (
            f"Analyze this Hollywood news title: '{title}'.\n"
            "Create a viral, curiosity-inducing clickbait hook for a short video reel.\n"
            "RULES:\n"
            "1. It MUST create intense suspense so viewers stop scrolling immediately.\n"
            "2. Keep it VERY short and punchy (5 to 12 words max).\n"
            "3. Use powerful hook words (e.g., 'SHOCKING', 'FINALLY', 'THE TRUTH ABOUT', 'NOBODY EXPECTED').\n"
            "4. ALL CAPS.\n"
            "5. NO brackets, NO parentheses, NO special tags.\n"
            "6. Return EXACTLY a valid JSON object with one key: \"hook\" (the full text).\n"
            "Example response:\n"
            "{\"hook\": \"THE SHOCKING TRUTH THEY TRIED TO HIDE!\"}"
        )
        
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            top_p=0.9,
            max_tokens=150
        )
        raw_text = response.choices[0].message.content.strip()
        
        # Try extracting JSON
        headline = ""
        highlights = []
        import re
        json_match = re.search(r'\{.*?\}', raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                headline = data.get("hook", "")
                highlights = data.get("highlights", [])
            except:
                pass
                
        if not headline:
            # Fallback parsing
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            if lines:
                headline = lines[-1]
            
        # Clean up characters
        headline = headline.replace('"', '').replace("'", "")
        
        # 1. Ensure ALL CAPS
        headline = headline.upper()
        highlights = [h.upper().strip() for h in highlights]
        
        # 2. Limit words safely
        words = headline.split()
        if len(words) > 25:
            headline = " ".join(words[:25]) + "..."
                
        if not headline or "USER WANTS" in headline:
            return {"hook": title.upper(), "highlights": []}
            
        return {"hook": headline, "highlights": highlights}
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return {"hook": title.upper(), "highlights": []}

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

def create_overlay_image(headline_data, output_img_path):
    """Generates a 1080x1920 transparent image with borders, text, and logo"""
    width, height = 1080, 1920
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0)) # Transparent
    draw = ImageDraw.Draw(img)
    
    # Draw Yellow Border around the entire frame
    border_width = 15
    draw.rectangle([0, 0, width-1, height-1], outline=(255, 255, 0, 255), width=border_width)
    
    # 2. Parse Text
    font_path = download_font()
    text_font = ImageFont.truetype(font_path, 70)
    
    hook_text = headline_data.get("hook", "").replace('\n', ' ')
    highlights = headline_data.get("highlights", [])
    
    flat_words = [word for word in hook_text.split(' ') if word]
    
    lines = []
    current_line = []
    current_line_width = 0
    max_text_width = width - 150
    space_width = draw.textlength(" ", font=text_font)
                
    for word in flat_words:
        w = draw.textlength(word, font=text_font)
        if current_line_width + w + space_width > max_text_width:
            lines.append(current_line)
            current_line = [word]
            current_line_width = w
        else:
            current_line.append(word)
            current_line_width += w + (space_width if current_line_width > 0 else 0)
            
    if current_line:
        lines.append(current_line)
        
    if len(lines) > 6:
        lines = lines[:6]
        if lines[-1]:
            lines[-1][-1] = lines[-1][-1] + "..."
            
    # Calculate Y start so that text sits nicely at the top
    text_y_start = 120
        
    # Draw Text with tight black background
    for line in lines:
        line_str = " ".join(line)
        # Calculate bounding box for the black background
        bbox = draw.textbbox((0, 0), line_str, font=text_font)
        line_w = bbox[2] - bbox[0]
        
        x_pos = (width - line_w) / 2
        
        # Draw Black Background Box with padding
        padding_x = 20
        padding_y = 15
        box_y1 = text_y_start - padding_y
        box_y2 = text_y_start + 70 + padding_y # 70 is rough font height for Bebas
        
        draw.rectangle(
            [x_pos - padding_x, box_y1, x_pos + line_w + padding_x, box_y2],
            fill=(0, 0, 0, 255)
        )
        
        # Draw text with solid yellow color
        draw.text((x_pos, text_y_start), line_str, font=text_font, fill=(255, 255, 0, 255))
        
        text_y_start += 100
        
    # Add "NEWS" at the bottom center
    news_text = "NEWS"
    news_font = ImageFont.truetype(font_path, 90)
    news_bbox = draw.textbbox((0, 0), news_text, font=news_font)
    news_w = news_bbox[2] - news_bbox[0]
    
    news_x = (width - news_w) / 2
    news_y_start = height - 200
    
    # Draw Black Background Box for NEWS
    draw.rectangle(
        [news_x - 40, news_y_start - 20, news_x + news_w + 40, news_y_start + 100],
        fill=(0, 0, 0, 255)
    )
    # Draw "NEWS" in yellow
    draw.text((news_x, news_y_start), news_text, font=news_font, fill=(255, 255, 0, 255))
    
    # 3. Draw Logo Image at Top Right (Drawn last to sit on top)
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            # Scale logo to fit nicely in Top Right Corner
            scale_w = 160 / logo_img.width
            scale_h = 160 / logo_img.height
            scale = min(scale_w, scale_h)
            
            new_w = int(logo_img.width * scale)
            new_h = int(logo_img.height * scale)
            logo_img = logo_img.resize((new_w, new_h), Image.LANCZOS)
            
            # Position at Top Right Corner
            logo_y = 40
            start_x = width - new_w - 40
            
            img.paste(logo_img, (int(start_x), int(logo_y)), logo_img)
        except Exception as e:
            print(f"Error drawing logo: {e}")
            pass
        
    img.save(output_img_path)

def get_video_duration(video_path):
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0

def edit_video(input_vid_path, overlay_img_path, output_vid_path):
    """Composites the raw video onto a 1080x1920 black background and applies the transparent overlay"""
    print("Compositing video...")
    try:
        # Base black canvas (optional now since we are full screen, but good for safety)
        base = ffmpeg.input('color=c=black:s=1080x1920', f='lavfi')
        
        # Raw video
        vid = ffmpeg.input(input_vid_path)
        
        # Overlay image
        overlay = ffmpeg.input(overlay_img_path)
        
        # Scale and crop the video to 1080x1920 to fit exactly inside full screen
        scaled_vid = vid.video.filter('scale', 1080, 1920, force_original_aspect_ratio='increase').filter('crop', 1080, 1920)
        
        # Overlay the scaled video onto the base
        vid_on_base = ffmpeg.overlay(base, scaled_vid, x=0, y=0, shortest=1)
        
        # Then overlay the transparent Pillow image (text) on top
        final = ffmpeg.overlay(vid_on_base, overlay, x=0, y=0)
        
        # Output with audio (limited to 58 seconds for Reels)
        out = ffmpeg.output(final, vid.audio, output_vid_path, vcodec='libx264', acodec='aac', t=58, shortest=None, crf=28, preset='fast')
        
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        print("Video editing completed.")
        
        duration = get_video_duration(output_vid_path)
        print(f"Final video duration: {duration:.2f} seconds")
        
        if duration < 20:
            print("Validation Failed: Video is under 20 seconds.")
            if os.path.exists(output_vid_path): os.remove(output_vid_path)
            return False
        if duration > 59:
            print("Validation Failed: Video is over 59 seconds.")
            if os.path.exists(output_vid_path): os.remove(output_vid_path)
            return False
            
        return True
    except Exception as e:
        print(f"Error during video editing: {e}")
        return False

def main():
    print("Starting Agent 2: Video Editor")
    
    raw_video_path = "workspace/raw_video.mp4"
    meta_path = "workspace/meta.json"
    overlay_path = "workspace/overlay.png"
    edited_video_path = "workspace/edited_video.mp4"
    
    if not os.path.exists(raw_video_path) or not os.path.exists(meta_path):
        print("No raw video or meta.json found in workspace.")
        return
        
    with open(meta_path, 'r') as f:
        meta = json.load(f)
        
    title = meta.get('title', 'Unknown Video')
    print(f"Processing video: {title}")
    
    headline_data = generate_headline(title)
    headline_text = headline_data.get("hook", "")
    print(f"Generated Headline: {headline_text}")
    
    # Save headline to meta for Uploader
    meta['headline'] = headline_text
    with open(meta_path, 'w') as f:
        json.dump(meta, f)
        
    create_overlay_image(headline_data, overlay_path)
    
    report_path = "workspace/report.json"
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            report = json.load(f)
    else:
        report = {}
        
    report["seo_title"] = headline_text
    
    if edit_video(raw_video_path, overlay_path, edited_video_path):
        report["editing_status"] = "Success"
        with open(report_path, 'w') as f:
            json.dump(report, f)
        
        # Cleanup intermediate files
        if os.path.exists(raw_video_path): os.remove(raw_video_path)
        if os.path.exists(overlay_path): os.remove(overlay_path)
    else:
        report["editing_status"] = "Failed"
        with open(report_path, 'w') as f:
            json.dump(report, f)
        print("Editing failed.")

if __name__ == "__main__":
    main()
