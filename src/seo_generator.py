import os
import re
import json
import hashlib
from openai import OpenAI

try:
    from .logger import logger
except ImportError:
    from logger import logger

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


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def clean_filename(filename):
    """Remove extension and replace underscores/hyphens with spaces."""
    name_without_ext = os.path.splitext(filename)[0]
    cleaned = re.sub(r'[-_]', ' ', name_without_ext)
    return cleaned.strip()


def _get_client():
    """Return an OpenAI-compatible client pointing at NVIDIA's API, or None."""
    api_key = os.environ.get('NVIDIA_API_KEY')
    if not api_key:
        return None
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )


# ──────────────────────────────────────────────────────────────────────
# Stage 1 – AI SEO Metadata (filename-based)
# ──────────────────────────────────────────────────────────────────────

def generate_seo_metadata(filename, media_type='reel'):
    """
    Stage 1: Generates SEO title, description, and hashtags based on the
    video filename.  Uses NVIDIA API with Llama 3.1 70B Instruct.

    Returns a dict with keys:
        title, description, facebook_caption, hashtags, tags
    """
    client = _get_client()
    if not client:
        logger.warning("NVIDIA_API_KEY not found. Using fallback metadata generator.")
        return generate_fallback_metadata(filename)

    topic = clean_filename(filename)
    topic_title = topic.title() if topic else "Hollywood Reel"

    content_type_str = "Facebook Reel" if media_type == 'reel' else "Facebook Photo Post"
    video_str = "short vertical video (Facebook Reel)" if media_type == 'reel' else "stunning photo/image"
    hashtag_str = "#Reels" if media_type == 'reel' else "#PhotoOfTheDay"

    system_prompt = (
        "You are an expert Hollywood entertainment social media manager "
        "and SEO specialist targeting a United States audience."
    )

    user_prompt = f"""
You are managing social media accounts for a Hollywood entertainment brand.
Generate viral SEO metadata for a {video_str} about: "{topic}".

IMPORTANT CONTEXT:
- Target audience: United States, entertainment & pop-culture fans
- Tone: Exciting, click-baity, celebrity-gossip style
- Every output field MUST be tailored to Hollywood / entertainment

Generate the following and return ONLY a valid JSON object:

1. "short_headline": A punchy headline (max 60 characters) with at least one
   emoji. It must feel like a tabloid headline or viral reel title.
   Example: "Beyoncé SHOCKS everyone at the Met Gala! 😱"

2. "story": A 2-3 sentence description that builds curiosity and drives
   clicks. Use emojis naturally. Example:
   "The internet is on fire after what happened at last night's premiere!
   Nobody saw this coming. Wait until you see the twist! 😱🔥"

3. "category": Pick exactly ONE from: Celebrity, RedCarpet, Movie, Scandal,
   Transformation.

4. "title": An SEO-optimized title (max 60 chars) for YouTube with the
   headline above.

5. "description": A 2-3 sentence YouTube/Facebook description with Hollywood
   keywords (celebrity, trending, viral, exclusive, etc.).

6. "facebook_caption": A short, punchy Facebook caption (1-2 sentences)
   with a call-to-action (CTA) like "Tag a friend!" or "Drop a 🔥 if you agree!".
   Do NOT include hashtags in this field.

7. "hashtags": A string of 7-8 trending Hollywood / entertainment hashtags
   (e.g., "#Hollywood #ViralReels #CelebNews #RedCarpet").

8. "tags": A JSON array of 6-8 SEO tags for YouTube
   (e.g., ["celebrity", "hollywood", "red carpet", "viral", "movie", "exclusive"]).

Return ONLY valid JSON, no markdown fences.
"""

    fallback = generate_fallback_metadata(filename)

    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=800,
            timeout=45,
        )

        content = completion.choices[0].message.content.strip()

        # Strip markdown fences if the model wraps them
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
            content = content.strip()

        data = json.loads(content)

        # Ensure all required keys exist; fill from fallback
        required_keys = ["title", "description", "facebook_caption", "hashtags", "tags"]
        for key in required_keys:
            if key not in data or not data[key]:
                data[key] = fallback[key]

        # Enforce headline length
        if len(data["title"]) > 60:
            data["title"] = data["title"][:57] + "..."

        # Ensure tags is a list
        if isinstance(data["tags"], str):
            data["tags"] = [t.strip().strip('#') for t in data["tags"].split(',') if t.strip()]

        return data

    except Exception as e:
        logger.error(f"Error calling NVIDIA API for SEO metadata: {e}")
        return generate_fallback_metadata(filename)


# ──────────────────────────────────────────────────────────────────────
# Stage 2 – Upload / Platform Metadata (context-based)
# ──────────────────────────────────────────────────────────────────────

def generate_upload_metadata(seo_metadata: dict) -> dict:
    """
    Stage 2: Generates platform-specific upload metadata (YouTube SEO,
    Facebook caption) based on the Stage 1 SEO output.

    Args:
        seo_metadata: dict with at least title, description, hashtags, tags.

    Returns:
        dict with keys: title, description, facebook_caption, hashtags, tags
    """
    client = _get_client()

    title = seo_metadata.get("title", "Hollywood Reel")
    description = seo_metadata.get("description", "")
    short_headline = seo_metadata.get("short_headline", title)
    category = seo_metadata.get("category", "Celebrity")

    if not client:
        logger.warning("NVIDIA_API_KEY not found. Using fallback upload metadata.")
        return _get_fallback_upload_metadata(seo_metadata)

    prompt = f"""
You are an expert Hollywood entertainment social media manager. Generate
platform-specific upload metadata based on the following Hollywood reel info.

REEL INFO:
- Title: {title}
- Description: {description}
- Short Headline: {short_headline}
- Category: {category}

Generate the following and return ONLY a valid JSON object:

1. "title": An SEO-optimized YouTube title (max 60 chars) with a Hollywood
   hook. Include an emoji.

2. "description": A 3-5 sentence YouTube description packed with Hollywood
   entertainment keywords (celebrity, movie, red carpet, trending, viral,
   exclusive, premiere, blockbuster). End with a CTA like "Subscribe for
   daily Hollywood updates!" and a placeholder for social links.

3. "facebook_caption": A punchy 1-2 sentence Facebook Reels caption with
   a strong call-to-action (e.g., "Tag someone who needs to see this! 👇"
   or "Drop a 🔥 if you agree!"). Do NOT include hashtags here.

4. "hashtags": A string of 7-8 trending Hollywood / entertainment hashtags
   (e.g., "#Hollywood #CelebNews #RedCarpet #Viral #Movie").

5. "tags": A JSON array of 8-10 YouTube SEO tags relevant to the Hollywood
   entertainment niche (e.g., ["celebrity", "hollywood", "red carpet",
   "movie", "viral", "trending", "entertainment", "exclusive"]).

Return ONLY valid JSON, no markdown fences.
"""

    fallback = _get_fallback_upload_metadata(seo_metadata)

    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
            timeout=45,
        )

        content = completion.choices[0].message.content.strip()

        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
            content = content.strip()

        data = json.loads(content)

        required_keys = ["title", "description", "facebook_caption", "hashtags", "tags"]
        for key in required_keys:
            if key not in data or not data[key]:
                data[key] = fallback[key]

        if isinstance(data["tags"], str):
            data["tags"] = [t.strip().strip('#') for t in data["tags"].split(',') if t.strip()]

        return data

    except Exception as e:
        logger.error(f"Error calling NVIDIA API for upload metadata: {e}")
        return fallback


# ──────────────────────────────────────────────────────────────────────
# Fallback Metadata (Hollywood / Entertainment templates)
# ──────────────────────────────────────────────────────────────────────

def generate_fallback_metadata(filename):
    """
    Generates deterministic Hollywood/entertainment fallback metadata when
    the AI API is unavailable.
    """
    def get_deterministic_choice(fn, lst):
        h = int(hashlib.md5(fn.encode('utf-8')).hexdigest(), 16)
        return lst[h % len(lst)]

    topic = clean_filename(filename)
    topic_title = topic.title() if topic else "This Moment"

    words = [w.lower() for w in re.findall(r'\w+', topic) if len(w) > 2]

    stopwords = {
        'the', 'and', 'for', 'you', 'with', 'from', 'this', 'that',
        'are', 'was', 'were', 'has', 'have', 'had', 'its', 'their',
        'our', 'your', 'his', 'her', 'she', 'him', 'them', 'who',
        'whom', 'which', 'been', 'not', 'but', 'what', 'all', 'can',
    }

    keywords = [w for w in words if w not in stopwords]

    # ── Hollywood keyword classification ──────────────────────────────

    celebrity_keywords = {
        'celebrity', 'star', 'famous', 'actor', 'actress', 'singer',
        'model', 'influencer', 'beyonce', 'taylor', 'kim', 'kanye',
        'kardashian', 'drake', 'justin', 'ariana', 'lizzo', 'doja',
    }

    redcarpet_keywords = {
        'carpet', 'redcarpet', 'red', 'gala', 'met', 'oscars', 'grammy',
        'golden', 'globes', 'awards', 'premiere', 'fashion', 'style',
        'vogue', 'couture', 'gown', 'tuxedo',
    }

    movie_keywords = {
        'movie', 'film', 'cinema', 'blockbuster', 'trailer', 'marvel',
        'dc', 'disney', 'netflix', 'series', 'season', 'episode',
        'studio', 'director', 'cast', 'sequel', 'prequel',
    }

    scandal_keywords = {
        'scandal', 'cheating', 'affair', 'arrest', 'drama', 'feud',
        'beef', 'shade', 'exposed', 'leaked', 'fired', 'cancelled',
        'divorce', 'breakup', 'controversy',
    }

    transformation_keywords = {
        'transformation', 'glow', 'glowup', 'weight', 'loss', 'gain',
        'plastic', 'surgery', 'botox', 'makeover', 'before', 'after',
        'fit', 'fitness', 'gym', 'diet',
    }

    is_celebrity = any(k in celebrity_keywords for k in keywords)
    is_redcarpet = any(k in redcarpet_keywords for k in keywords)
    is_movie = any(k in movie_keywords for k in keywords)
    is_scandal = any(k in scandal_keywords for k in keywords)
    is_transformation = any(k in transformation_keywords for k in keywords)

    # ── Category-specific templates ──────────────────────────────────

    if is_celebrity:
        titles = [
            "{topic} just broke the internet! 😱",
            "Nobody expected THIS from {topic}! 🤯",
            "POV: You see {topic} in real life! ✨",
            "{topic} is giving us EVERYTHING right now! 🔥",
            "Wait for it… {topic} does NOT disappoint! 🚨",
        ]
        descriptions = [
            "The whole world is talking about {topic} right now and we get it! This is the moment everyone's been waiting for. 💫",
            "Just when you thought {topic} couldn't surprise us anymore… this happens! You NEED to see this. 👀",
            "The celebrity world just got a whole lot more interesting. {topic} is making headlines everywhere! 🌟",
        ]
        cat_tags = ['#Celebrity', '#Famous', '#Hollywood', '#Viral', '#PopCulture', '#Trending']
    elif is_redcarpet:
        titles = [
            "The {topic} look that stopped everything! 😍",
            "{topic} just OWNED the red carpet! 🔴",
            "This {topic} moment is UNREAL! 💎",
            "Everyone is talking about {topic} tonight! ✨",
            "{topic} just set the internet on fire! 🔥",
        ]
        descriptions = [
            "The red carpet has never looked this good! {topic} just delivered a moment for the ages. Absolutely stunning. 🌟",
            "Fashion critics are losing their minds over {topic} and honestly we are too! This look is everything. 👗",
            "From theMet Gala to the Oscars, {topic} knows how to make an entrance. Pure glamour! 💎",
        ]
        cat_tags = ['#RedCarpet', '#Fashion', '#Glamour', '#Style', '#Hollywood', '#MetGala']
    elif is_movie:
        titles = [
            "The {topic} trailer just dropped and WE ARE NOT OKAY! 😱",
            "This {topic} scene gave us chills! 🎬",
            "{topic} is about to be the BIGGEST movie of the year! 🔥",
            "OMG! You won't believe what happens in {topic}! 🤯",
            "{topic} just changed EVERYTHING! No spoilers! 🚨",
        ]
        descriptions = [
            "The movie world just got a major shakeup! {topic} is delivering scenes we never thought we'd see. Buckle up! 🎬",
            "Hollywood is buzzing about {topic} and for good reason! This is going to break every record. 🍿",
            "If you haven't heard about {topic} yet, you will! This movie moment is going absolutely viral. 🎥",
        ]
        cat_tags = ['#Movie', '#Blockbuster', '#Film', '#Cinema', '#Hollywood', '#MovieNight']
    elif is_scandal:
        titles = [
            "The {topic} drama just got WORSE! 😱",
            "Everyone is SHOOK by {topic}! 🤯",
            "{topic} just exposed EVERYTHING! 👀",
            "The internet can't stop talking about {topic}! 🔥",
            "Wait until you hear about {topic}… 😳",
        ]
        descriptions = [
            "The drama around {topic} just escalated to a whole new level and we are here for every second of it! 👀",
            "You thought it was over? Think again! {topic} just dropped a BOMBSHELL and the internet is losing it! 💣",
            "Breaking: The {topic} situation just took an unexpected turn. Nobody saw this coming! 😱",
        ]
        cat_tags = ['#Scandal', '#Drama', '#Breaking', '#Hollywood', '#Gossip', '#Exposed']
    elif is_transformation:
        titles = [
            "The {topic} transformation is INSANE! 😱",
            "You won't recognize {topic} after this! 🤯",
            "The {topic} glow-up is UNREAL! ✨",
            "{topic} just showed us the ultimate transformation! 🔥",
            "Wait for the before & after of {topic}! 😍",
        ]
        descriptions = [
            "The glow-up is real! {topic} just dropped a transformation that has everyone speechless. You HAVE to see this! 💫",
            "From before to after, the {topic} transformation is absolutely jaw-dropping. What a journey! 🌟",
            "We've never seen a transformation quite like {topic}. The internet is calling this the glow-up of the year! 🔥",
        ]
        cat_tags = ['#Transformation', '#GlowUp', '#BeforeAfter', '#Hollywood', '#Makeover', '#Fitness']
    else:
        # General Hollywood / entertainment fallback
        titles = [
            "You won't believe this {topic} moment! 😱",
            "The internet is SCREAMING about {topic}! 🤯",
            "Wait for it… {topic} just happened! 🔥",
            "This {topic} clip is breaking the internet! 🚨",
            "Everyone is talking about {topic} right now! ✨",
        ]
        descriptions = [
            "Hollywood is on fire right now and {topic} is at the center of it all! You NEED to see this moment. 💫",
            "Just when you think you've seen it all, {topic} comes along and changes everything! This is absolutely wild. 🌟",
            "The entertainment world can't stop buzzing about {topic}. Watch this before it breaks the internet! 👀",
        ]
        cat_tags = ['#Hollywood', '#Viral', '#Trending', '#Entertainment', '#MustWatch', '#Reels']

    # ── Pick deterministic templates ──────────────────────────────────

    title_template = get_deterministic_choice(filename, titles)
    desc_template = get_deterministic_choice(filename, descriptions)

    title = title_template.format(topic=topic_title)
    if len(title) > 60:
        title = title[:57] + "..."

    base_desc = desc_template.format(topic=topic_title)

    ctas = [
        "Double tap if you agree! ❤️",
        "Tag a friend who NEEDS to see this! 👇",
        "Drop a 🔥 if this blew your mind!",
        "Follow for daily Hollywood updates! 📲",
        "What do you think? Comment below! 💬",
        "Share this with someone who would love it! ✈️",
    ]
    cta = get_deterministic_choice(filename + "_cta", ctas)
    description = f"{base_desc}\n\n{cta}"

    # ── Build hashtags ────────────────────────────────────────────────

    # Start with universal Hollywood tags + category tags
    hashtag_set = set()
    hashtag_set.update(cat_tags)
    hashtag_set.add('#Reels')
    hashtag_set.add('#Viral')

    # Add matching Hollywood keywords
    hollywood_map = {
        'celebrity': ['#CelebNews', '#Famous', '#PopCulture'],
        'movie': ['#Movie', '#Film', '#Blockbuster', '#Cinema'],
        'star': ['#StarPower', '#Famous'],
        'premiere': ['#Premiere', '#RedCarpet'],
        'fashion': ['#Fashion', '#Style', '#OOTD'],
        'trend': ['#Trending', '#FYP', '#Viral'],
        'music': ['#Music', '#Grammy', '#Concert'],
        'tv': ['#TVShow', '#Netflix', '#Streaming'],
        'love': ['#CelebrityCouple', '#Love'],
        'drama': ['#Drama', '#Gossip', '#Scandal'],
    }

    for k in keywords:
        if k in hollywood_map:
            for tag in hollywood_map[k]:
                hashtag_set.add(tag)
        if len(k) > 2:
            hashtag_set.add(f"#{k.title()}")

    ordered = ['#Reels', '#Viral', '#Hollywood']
    for tag in sorted(hashtag_set):
        if tag not in ordered:
            ordered.append(tag)

    final_tags = ordered[:10]
    hashtags_str = " ".join(final_tags)

    return {
        'title': title,
        'description': description,
        'facebook_caption': cta,
        'hashtags': hashtags_str,
        'tags': [t.strip('#') for t in final_tags],
    }


def _get_fallback_upload_metadata(seo_metadata: dict) -> dict:
    """
    Deterministic Hollywood fallback for Stage 2 upload metadata.
    """
    title = seo_metadata.get("title", "Hollywood Reel")
    description = seo_metadata.get("description", "")
    category = seo_metadata.get("category", "Celebrity")

    fb_caption_templates = [
        f"{title}\n\nTag someone who needs to see this! 👇",
        f"{title}\n\nDrop a 🔥 if you agree!",
        f"{title}\n\nThe internet is NOT okay right now 😱",
        f"{title}\n\nFollow for more daily Hollywood tea! ☕",
    ]
    h = int(hashlib.md5(title.encode()).hexdigest(), 16)
    fb_caption = fb_caption_templates[h % len(fb_caption_templates)]

    yt_description = (
        f"{title}\n\n"
        f"{description}\n\n"
        "Subscribe for daily Hollywood updates, celebrity news, and "
        "exclusive behind-the-scenes content! 🔔\n\n"
        "📱 Follow us:\n"
        "Instagram: @hollywoodreels\n"
        "TikTok: @hollywoodreels\n\n"
        "#Hollywood #Celebrity #Viral #Entertainment"
    )

    tags = ["celebrity", "hollywood", "red carpet", "movie", "viral",
            "trending", "entertainment", "exclusive", "pop culture", "reels"]

    return {
        "title": title[:60],
        "description": yt_description,
        "facebook_caption": fb_caption,
        "hashtags": "#Hollywood #CelebNews #RedCarpet #Viral #Trending #Entertainment #Reels #MustWatch",
        "tags": tags,
    }


# ──────────────────────────────────────────────────────────────────────
# Caption Formatter
# ──────────────────────────────────────────────────────────────────────

def format_caption(seo_metadata):
    """
    Combines the title, description, and hashtags into the final
    Facebook caption format.
    """
    parts = []
    if seo_metadata.get('title'):
        parts.append(seo_metadata['title'])
    if seo_metadata.get('description'):
        parts.append(seo_metadata['description'])
    if seo_metadata.get('hashtags'):
        parts.append(seo_metadata['hashtags'])
    return "\n\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# CLI quick-test
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_files = [
        "met_gala_2025_best_dresses.mp4",
        "taylor_swift_eras_tour_finale.mp4",
        "beyonce_movie_role_reveal.mp4",
        "celebrity_couple_breakup_scandal.mp4",
        "oscar_winner_transformation.mp4",
        "random_funny_reel.mp4",
    ]

    for f in test_files:
        print(f"\n{'='*60}")
        print(f"FILE: {f}")
        print('='*60)
        result = generate_seo_metadata(f)
        for k, v in result.items():
            print(f"  {k}: {v}")
