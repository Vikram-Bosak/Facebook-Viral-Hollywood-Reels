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
            f"Analyze the following Hollywood news title: '{title}'. "
            "Generate an EXTREMELY SHORT, punchy, SINGLE-LINE hook for a vertical video reel. "
            "It must be under 8 words. "
            "Identify the names of celebrities, entities, or key subjects, and enclose those specific words in brackets like [THIS]. "
            "Make it exciting and ALL CAPS. Example: '[MARIE] RUNS UP ON [MIMI]!'\n\n"
            "Output ONLY the single line headline text."
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
    """Generates a 1080x1920 transparent image with borders, text, and logo"""
    width, height = 1080, 1920
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0)) # Transparent
    draw = ImageDraw.Draw(img)
    
    # 1. Draw double borders (Yellow outer, White inner)
    draw.rectangle([10, 10, 1070, 1910], outline="yellow", width=10)
    draw.rectangle([25, 25, 1055, 1895], outline="white", width=5)

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
        
    # 3. Draw Logo below the video area
    logo_path = "assets/logo.png"
    
    logo_w, logo_h = 0, 0
    logo_img = None
    logo_y = 1250 # Default if no logo
    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            # Scale logo to fit nicely (max width 600 or max height 180)
            scale_w = 600 / logo_img.width
            scale_h = 180 / logo_img.height
            scale = min(scale_w, scale_h)
            
            new_w = int(logo_img.width * scale)
            new_h = int(logo_img.height * scale)
            logo_img = logo_img.resize((new_w, new_h), Image.LANCZOS)
            logo_w, logo_h = logo_img.size
            
            # Center it so it overlaps the boundary of the video (y=1280)
            logo_y = 1280 - (logo_h // 2)
            
            start_x = (width - logo_w) / 2
            img.paste(logo_img, (int(start_x), int(logo_y)), logo_img)
        except Exception as e:
            print(f"Error drawing logo: {e}")
            pass
            
    # Calculate layout Y positions for text
    if logo_img:
        available_start = logo_y + logo_h
    else:
        available_start = 1280
        
    available_space = height - available_start
    total_text_height = len(lines) * 120
    text_y_start = available_start + (available_space - total_text_height) // 2
        
    # Draw Text
    for line in lines:
        line_w = sum(draw.textlength(w, font=text_font) for w, h in line) + space_width * (len(line) - 1)
        x_pos = (width - line_w) / 2
        
        for word, is_highlight in line:
            color = (255, 255, 0, 255) if is_highlight else (255, 255, 255, 255) # Yellow highlight
            # Draw text without shadow as background is black
            draw.text((x_pos, text_y_start), word, font=text_font, fill=color)
            x_pos += draw.textlength(word, font=text_font) + space_width
            
        text_y_start += 120
        
    img.save(output_img_path)

def edit_video(input_vid_path, overlay_img_path, output_vid_path):
    """Composites the raw video onto a 1080x1920 black background and applies the transparent overlay"""
    print("Compositing video...")
    try:
        # Base black canvas
        base = ffmpeg.input('color=c=black:s=1080x1920', f='lavfi', t=1) # Temporary dummy length, shorter than video
        
        # Raw video
        vid = ffmpeg.input(input_vid_path)
        
        # Overlay image
        overlay = ffmpeg.input(overlay_img_path)
        
        # Scale and crop the video to 1020x1250 to fit exactly inside the white border
        scaled_vid = vid.video.filter('scale', 1020, 1250, force_original_aspect_ratio='increase').filter('crop', 1020, 1250)
        
        # First overlay the scaled video onto the black base at x=30, y=30
        vid_on_base = ffmpeg.overlay(base, scaled_vid, x=30, y=30, shortest=1)
        
        # Then overlay the transparent Pillow image (borders, logo, text) on top
        final = ffmpeg.overlay(vid_on_base, overlay, x=0, y=0)
        
        # Output with audio (limited to 20 seconds for Reels)
        out = ffmpeg.output(final, vid.audio, output_vid_path, vcodec='libx264', acodec='aac', t=20, shortest=None, crf=28, preset='fast')
        
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        print("Video editing completed.")
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
