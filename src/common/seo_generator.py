import os
import re
import json
import hashlib
import time
from openai import OpenAI

try:
    from .logger import logger
except ImportError:
    try:
        from logger import logger
    except ImportError:
        logger = None

# Try to import Google GenAI
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# ──────────────────────────────────────────────────────────────────────
# Hollywood / Entertainment Constants
# ──────────────────────────────────────────────────────────────────────

HOLLYWOOD_KEYWORDS = [
    "celebrity", "hollywood", "red carpet", "movie", "film", "premiere",
    "award show", "oscars", "grammy", "golden globes", "bollywood",
    "actor", "actress", "director", "star", "fame", "glamour",
    "movie review", "box office", "blockbuster", "trailers",
    "celebrity couple", "breakup", "scandal", "transformation",
    "plastic surgery", "weight loss", "met gala", "coachella",
    "reality tv", "netflix", "streaming", "tv show", "season finale",
    "behind the scenes", "exclusive", "breaking news", "viral",
    "trending", "instagram", "tiktok", "youtube", "pop culture",
    "entertainment", "tabloid", "paparazzi", "fan", "cosplay",
    "fashion", "style", "beauty", "makeup", "redcarpet look"
]

HOLLYWOOD_HASHTAGS = [
    "#Hollywood", "#CelebNews", "#RedCarpet", "#ViralReels",
    "#MovieMagic", "#CelebrityGossip", "#TrendingNow", "#Entertainment",
    "#PopCulture", "#FYP", "#MustWatch", "#ReelsViral",
    "#Famous", "#AwardsSeason", "#Showbiz", "#BreakingNews",
    "#HollywoodLife", "#CelebrityStyle", "#MetGala", "#Fashion",
    "#BoxOffice", "#Netflix", "#MovieNight", "#FanEdit",
    "#Exclusive", "#Tabloid", "#Gossip", "#InstaFamous"
]

def clean_filename(filename):
    """Remove extension and replace underscores/hyphens with spaces."""
    name_without_ext = os.path.splitext(filename)[0]
    cleaned = re.sub(r'[-_]', ' ', name_without_ext)
    return cleaned.strip()

def _get_client():
    """Return an OpenAI client pointing at NVIDIA's API, or None."""
    api_key = os.environ.get('NVIDIA_API_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

def _extract_gemini_video_context(video_path: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not HAS_GEMINI or not gemini_key or not video_path or not os.path.exists(video_path):
        return ""
        
    print(f"Deep Video Analysis: Uploading {video_path} to Gemini...")
    try:
        client = genai.Client(api_key=gemini_key)
        video_file = client.files.upload(file=video_path)
        
        while video_file.state.name == "PROCESSING":
            print("Waiting for video processing...")
            time.sleep(5)
            video_file = client.files.get(name=video_file.name)
            
        if video_file.state.name == "FAILED":
            print("Gemini Video processing failed.")
            return ""
            
        prompt = "Analyze this entertainment/Hollywood video. Describe what is happening visually, read any OCR text, transcribe spoken words, and note if there are broadcaster watermarks or sensitive issues."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[video_file, prompt]
        )
        
        client.files.delete(name=video_file.name)
        return response.text
    except Exception as e:
        print(f"Error extracting deep video context: {e}")
        return ""

# ──────────────────────────────────────────────────────────────────────
# Stage 1 – Analyze video for editing
# ──────────────────────────────────────────────────────────────────────

def analyze_video_for_editing(context: dict) -> dict:
    """
    Stage 1: Analyzes video context and generates Hook Line, Short Headline, Overlay Text, and Category.
    """
    client = _get_client()
    original_title = context.get('title', '')
    fallback = {
        "category": "Celebrity",
        "short_headline": (
            original_title[:35] + "..."
            if len(original_title) > 35
            else (original_title if original_title else "HOLLYWOOD EXCLUSIVE 🎬🔥")
        ),
        "story": (
            original_title
            if original_title
            else "You won't believe what happened in Hollywood today! Watch until the end to get the full scoop. 😱"
        ),
        "overlay_text": "🎬 HOLLYWOOD NEWS",
        "safety_flags": [],
        "safety_actions": []
    }
    
    if not client:
        print("Warning: API Key not found. Using fallback analysis.")
        return fallback
        
    deep_context = ""
    local_path = context.get('local_path')
    if local_path and os.getenv("GEMINI_API_KEY"):
        deep_context = _extract_gemini_video_context(local_path)
        if deep_context:
            context['deep_context'] = deep_context
            
    prompt = f"""You are a world-class Hollywood celebrity news editor and content safety auditor.
Analyze the video context and metadata carefully to ensure compliance with Facebook's Community Standards and Copyright/Rights Manager policies.

=== SOURCE OF TRUTH ===
Original Title/Text: {context.get('title', 'Unknown')}
Source Profile: {context.get('source', 'Unknown')}
{f"Deep AI Video Context: {context.get('deep_context', '')[:800]}" if context.get('deep_context') else ""}

=== YOUR TASK ===
Analyze the "Original Title/Text" and any visual context. Identify:
1. Exact celebrities, movies, or shows.
2. The emotional hook.
3. The content safety risks:
   - Does this show physical violence, fights, or medical emergencies?
   - Is it a highly sensitive personal scandal?
   - Does it use official broadcaster footage (e.g. HBO, Netflix, Disney, TMZ) that might trigger Rights Manager?

Then generate:
1. **short_headline** – 3-6 words max, ALL CAPS, punchy, in ENGLISH. Include 1 relevant emoji.
2. **story** – A 2-3 sentence conversational paragraph hyping the video.
3. **category** – "Celebrity", "RedCarpet", "Movie", "Scandal", "Transformation".
4. **safety_flags** – List containing flags if present: "violence" (fights/blood), "sensitive_scandal" (extreme sensitive issues), "copyright_audio" (heavy commentator/music), "broadcaster_watermark" (visible tv logos). Empty list if clean.
5. **safety_actions** – Actions required to make the video safe: "mute_audio" (if audio risk), "flip_horizontal" (to avoid visual match), "trim_video" (if ends in fight). Empty list if clean.

Return ONLY a valid JSON object with these exact keys:
{{
  "category": "...",
  "short_headline": "...",
  "story": "...",
  "safety_flags": [],
  "safety_actions": []
}}"""
    
    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
            timeout=45,
        )
        content = completion.choices[0].message.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        data = json.loads(content.strip())
        
        for key in fallback.keys():
            if key not in data:
                data[key] = fallback[key]
                
        return data
    except Exception as e:
        print(f"Error calling NVIDIA LLM API for editing analysis: {e}")
        return fallback

# ──────────────────────────────────────────────────────────────────────
# Stage 2 – Generate upload metadata
# ──────────────────────────────────────────────────────────────────────

def generate_seo_metadata(filename, media_type='reel'):
    """
    Backward compatible helper for filename-based Stage 1 SEO.
    """
    return generate_fallback_metadata(filename)

def generate_upload_metadata(context: dict) -> dict:
    """
    Stage 2: Generates SEO metadata based on the full editing context.
    Platform-specific: YouTube (title <60 chars, description, tags) + Facebook (caption, hashtags).
    """
    client = _get_client()
    if not client:
        print("Warning: API Key not found. Using fallback SEO data.")
        return _get_fallback_upload_metadata(context)
    
    title_clean = clean_filename(context.get('title', 'Unknown'))
    headline_clean = clean_filename(context.get('short_headline', ''))
    story_clean = clean_filename(context.get('story', ''))

    prompt = f"""You are a top-tier Hollywood entertainment SEO specialist. Generate platform-specific upload metadata for a viral video.

=== FULL VIDEO CONTEXT ===
Original Title/Text: {title_clean}
Source Profile: {context.get('source', 'Unknown')}
Determined Category: {context.get('category', 'Celebrity')}
Headline Used in Video: {headline_clean}
Story Used in Video: {story_clean}

=== YOUR TASK ===
Generate SEO metadata tailored for YouTube AND Facebook.

**1. "title" (YouTube SEO Title)**
• STRICTLY under 60 characters.
• Include the most relevant celebrity or movie name.
• Use a power word (SHOCKING, REVEALED, TRUTH, SPOTTED).
• Example: "Zendaya SHOCKS Fans At Dune 3 Premiere! 😱"

**2. "description" (YouTube Description)**
• 2-3 sentences. First sentence must hook the viewer.
• Naturally include 3-5 entertainment keywords.
• End with a call to action (Like, Subscribe, Comment).
• Include relevant hashtags at the end. Do NOT request source URLs.

**3. "facebook_caption" (Facebook Reels Caption)**
• Short, punchy, MAX 2 sentences. Do NOT include hashtags here.
• Must include a clear call-to-action (e.g. "Tag someone who needs to see this!", "Who is your favorite actor?").

**4. "hashtags" (Facebook Hashtags – string)**
• A single string of 7-8 highly relevant hashtags (e.g., "#Hollywood #CelebNews #RedCarpet").

**5. "tags" (YouTube Tags – list of strings)**
• A list of 8-10 SEO tags for YouTube.

Return ONLY a valid JSON object with these exact keys:
{{
  "title": "...",
  "description": "...",
  "facebook_caption": "...",
  "hashtags": "...",
  "tags": ["...", "...", "..."]
}}"""
    
    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
        )
        
        content = completion.choices[0].message.content
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
            
        data = json.loads(content.strip())
        
        if "title" in data and len(data["title"]) > 60:
            data["title"] = data["title"][:57] + "..."
        
        required_keys = ["title", "description", "facebook_caption", "hashtags", "tags"]
        for key in required_keys:
            if key not in data:
                data[key] = _get_fallback_upload_metadata(context)[key]
                
        return data

    except Exception as e:
        print(f"Error calling LLM API for SEO: {e}")
        return _get_fallback_upload_metadata(context)

# ──────────────────────────────────────────────────────────────────────
# Fallback functions
# ──────────────────────────────────────────────────────────────────────

def generate_fallback_metadata(filename):
    def get_deterministic_choice(fn, lst):
        h = int(hashlib.md5(fn.encode('utf-8')).hexdigest(), 16)
        return lst[h % len(lst)]
        
    topic = clean_filename(filename)
    topic_title = topic.title() if topic else "Hollywood News"
    
    titles = [
        "Unbelievable {topic} moment! 😱🔥",
        "Nobody expected this from {topic}! 🤯",
        "POV: Witnessing {topic} history. ✨",
        "Is this the best of {topic} ever? 👀",
        "This {topic} clip is breaking the internet! 🚨"
    ]
    descriptions = [
        "The whole Hollywood is talking about {topic} right now! Make sure to watch until the end and share your thoughts! 💫",
        "Up close and personal with {topic}! An exclusive look behind the scenes. Drop a comment below! 👇",
        "Just when you think you've seen it all in show business, this happens. Absolute magic! ✨"
    ]
    
    title_template = get_deterministic_choice(filename, titles)
    desc_template = get_deterministic_choice(filename, descriptions)
    
    title = title_template.format(topic=topic_title)
    if len(title) > 60:
        title = title[:57] + "..."
        
    description = desc_template.format(topic=topic_title)
    
    hash_tags_set = {'#hollywood', '#celebnews', '#redcarpet', '#reels'}
    ordered_tags = ['#hollywood', '#celebnews', '#redcarpet', '#reels']
    
    final_tags = ordered_tags[:8]
    hashtags_str = " ".join([t.title() for t in final_tags])
    
    return {
        'title': title,
        'description': description,
        'facebook_caption': f"{title}\n\nTag a friend who needs to see this! 👇",
        'hashtags': hashtags_str,
        'tags': [t.strip('#') for t in final_tags]
    }

def _get_fallback_upload_metadata(seo_metadata: dict) -> dict:
    title = seo_metadata.get("title", "Hollywood Reel")
    description = seo_metadata.get("description", "Exclusive Hollywood celebrity update.")
    
    return {
        "title": title[:60],
        "description": f"{description}\n\nSubscribe for daily Hollywood updates! 🔔",
        "facebook_caption": f"{title}\n\nDrop a comment and tag a friend! 👇",
        "hashtags": "#Hollywood #CelebNews #RedCarpet #Viral #Trending",
        "tags": ["celebrity", "hollywood", "movie", "viral"]
    }

def format_caption(seo_metadata):
    parts = []
    if seo_metadata.get('title'):
        parts.append(seo_metadata['title'])
    if seo_metadata.get('description'):
        parts.append(seo_metadata['description'])
    if seo_metadata.get('hashtags'):
        parts.append(seo_metadata['hashtags'])
    return "\n\n".join(parts)
