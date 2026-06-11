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
            f"Analyze the following Hollywood news title: '{title}'.\n"
            "Create an irresistible, suspenseful clickbait hook for a vertical video reel.\n"
            "RULES:\n"
            "1. Length MUST be between 12 to 20 words (to fill the screen nicely).\n"
            "2. Make it highly engaging so viewers can't scroll past.\n"
            "3. ALL CAPS.\n"
            "4. Names of celebrities/entities MUST be in brackets. Example: [BRAD PITT] MOVES ON!\n"
            "5. Return ONLY a valid JSON object with the key \"hook\". No markdown, no conversational text.\n"
            "Example response:\n"
            "{\"hook\": \"[TOM HANKS] MAKES A SHOCKING REVEAL ABOUT HIS PAST THAT NOBODY SAW COMING!\"}"
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
        import re
        json_match = re.search(r'\{.*?\}', raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                headline = data.get("hook", "")
            except:
                pass
                
        if not headline:
            # Fallback parsing
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            for line in lines:
                if '[' in line and ']' in line:
                    headline = line
                    break
            if not headline and lines:
                headline = lines[-1]
            
        # Clean up characters
        headline = headline.replace('"', '').replace("'", "")
        
        # 1. Ensure ALL CAPS
        headline = headline.upper()
        
        # 2. Limit words safely
        words = headline.split()
        if len(words) > 25:
            headline = " ".join(words[:25]) + "..."
                
        # Clean up dangling brackets if we cut them off
        if headline.count('[') > headline.count(']'):
            if not headline.endswith(']'):
                headline += ']'
                
        if not headline or "USER WANTS" in headline:
            return f"[{title.upper()[:40]}] VIRAL NEWS!"
            
        return headline
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return f"[{title.upper()[:40]}] VIRAL NEWS!"

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
    """Generates a 1080x1920 transparent image with borders, text, and logo"""
    width, height = 1080, 1920
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0)) # Transparent
    draw = ImageDraw.Draw(img)
    
    # 2. Parse Text
    font_path = download_font()
    text_font = ImageFont.truetype(font_path, 110)
    
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

    lines = []
    current_line = []
    current_line_width = 0
    max_text_width = width - 100
    space_width = draw.textlength(" ", font=text_font)
    
    flat_words = []
    for text, is_highlight in tokens:
        text = text.replace('\n', ' ')
        for word in text.split(' '):
            if word: flat_words.append((word, is_highlight))
                
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
        
    if len(lines) > 5:
        lines = lines[:5]
        if lines[-1]:
            last_word, highlight = lines[-1][-1]
            lines[-1][-1] = (last_word + "...", highlight)
            
    total_text_height = len(lines) * 120
    
    # 3. Draw Logo below the text
    logo_text = "CELEBRITY BUZZ USA"
    logo_font = ImageFont.truetype(font_path, 50)
    logo_w = draw.textlength(logo_text, font=logo_font)
    
    # Calculate Y start so that text + logo sit nicely at the bottom
    # Bottom margin ~ 200px
    total_content_height = total_text_height + 80 # 80 is logo height + gap
    text_y_start = height - 200 - total_content_height
        
    # Draw Text
    for line in lines:
        line_w = sum(draw.textlength(w, font=text_font) for w, h in line) + space_width * (len(line) - 1)
        x_pos = (width - line_w) / 2
        
        for word, is_highlight in line:
            # Cyan for highlight, White for normal
            color = (0, 255, 255, 255) if is_highlight else (255, 255, 255, 255)
            # Draw text with black stroke
            draw.text((x_pos, text_y_start), word, font=text_font, fill=color, stroke_width=6, stroke_fill=(0, 0, 0, 255))
            x_pos += draw.textlength(word, font=text_font) + space_width
            
        text_y_start += 120
        
    # Draw Logo Text centered below main text
    logo_x = (width - logo_w) / 2
    logo_y = text_y_start + 20
    draw.text((logo_x, logo_y), logo_text, font=logo_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
        
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
    
    headline = generate_headline(title)
    print(f"Generated Headline: {headline}")
    
    # Save headline to meta for Uploader
    meta['headline'] = headline
    with open(meta_path, 'w') as f:
        json.dump(meta, f)
        
    create_overlay_image(headline, overlay_path)
    
    report_path = "workspace/report.json"
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            report = json.load(f)
    else:
        report = {}
        
    report["seo_title"] = headline
    
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
