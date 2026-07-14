import os
import random
import textwrap
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

def generate_ui_frame(output_path: str, source_name: str, headline: str, story: str, width=1080, height=1920):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    fb_blue = (59, 89, 152, 255)
    white = (255, 255, 255, 255)
    yellow = (255, 215, 0, 255)
    
    # 1. Outer yellow border (5px)
    draw.rectangle([0, 0, width, height], outline=yellow, width=5)
    
    # 2. Draw Top Banner
    top_banner_path = os.path.join(os.path.dirname(__file__), "../../assets/top_banner_extracted.png")
    top_bar_height = 90
    if os.path.exists(top_banner_path):
        try:
            top_banner_img = Image.open(top_banner_path).convert("RGBA")
            top_banner_resized = top_banner_img.resize((width - 10, top_bar_height), Image.LANCZOS)
            img.paste(top_banner_resized, (5, 5), top_banner_resized)
        except Exception:
            draw.rectangle([5, 5, width-5, top_bar_height+5], fill=fb_blue)
    else:
        draw.rectangle([5, 5, width-5, top_bar_height+5], fill=fb_blue)
        
    # 3. Draw Bottom Banner
    bottom_bar_height = 340
    draw.rectangle([5, height - bottom_bar_height - 5, width - 5, height - 5], fill=fb_blue)
    
    # Fonts
    font_bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    font_reg = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    
    try:
        f_head = ImageFont.truetype(font_bold, 40)
        f_story = ImageFont.truetype(font_reg, 32)
    except IOError:
        f_head = f_story = ImageFont.load_default()
        
    def draw_all(renderer, is_pilmoji):
        start_y = height - bottom_bar_height + 25
        
        # --- Main Headline ---
        try:
            f_sub = ImageFont.truetype(font_bold, 38)
        except IOError:
            f_sub = ImageFont.load_default()
            
        headline_text = headline.strip() if headline else ""
        renderer.text((30, start_y), headline_text, fill=white, font=f_sub)
        
        start_y += 60
        
        # --- Description and Hashtags ---
        story_text = story if story else "Unbelievable news from Hollywood today! Watch until the end to get the full story."
        
        words = story_text.split()
        hashtags = [w for w in words if w.startswith('#')]
        clean_story = " ".join([w for w in words if not w.startswith('#')])
        
        story_lines = textwrap.wrap(clean_story, width=72)
        
        try:
            f_story = ImageFont.truetype(font_reg, 30)
        except IOError:
            f_story = ImageFont.load_default()
            
        for line in story_lines[:3]: # Max 3 lines for description
            renderer.text((30, start_y), line, fill=white, font=f_story)
            start_y += 42
            
        if hashtags:
            hashtag_text = " ".join(hashtags)
            renderer.text((30, start_y), hashtag_text, fill=(160, 176, 192, 255), font=f_story)
            start_y += 45
            
        # --- VIDEO CREDIT OVERLAY ---
        credit_text = "Video Credit: Hollywood News"
        try:
            f_credit = ImageFont.truetype(font_bold, 35)
        except IOError:
            f_credit = ImageFont.load_default()
            
        if is_pilmoji:
            credit_w = renderer.getsize(credit_text, font=f_credit)[0]
        else:
            try:
                credit_w = int(draw.textlength(credit_text, font=f_credit))
            except AttributeError:
                bbox = draw.textbbox((0, 0), credit_text, font=f_credit)
                credit_w = bbox[2] - bbox[0]
                
        credit_x = width - credit_w - 30
        credit_y = height - bottom_bar_height - 50
        
        shadow_color = (0, 0, 0, 200)
        for offset in [(2,2), (-2,-2), (2,-2), (-2,2), (0,2), (2,0), (-2,0), (0,-2)]:
            renderer.text((credit_x + offset[0], credit_y + offset[1]), credit_text, fill=shadow_color, font=f_credit)
        renderer.text((credit_x, credit_y), credit_text, fill=(230, 230, 230, 255), font=f_credit)

    try:
        with Pilmoji(img) as pilmoji:
            draw_all(pilmoji, is_pilmoji=True)
    except Exception as e:
        print(f"Pilmoji failed: {e}. Falling back to standard ImageDraw.")
        draw_all(draw, is_pilmoji=False)
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    return output_path
