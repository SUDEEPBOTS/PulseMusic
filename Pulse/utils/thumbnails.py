# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

import os
import re
import random
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL as FAILED
from Pulse import app
from Pulse.misc import db  # ✅ added for chat_id → user_id fetch

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ------------------- UI CONFIG -------------------
PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 230
INNER_OFFSET = 36
THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET
TITLE_X = 377
META_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45
BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480
ICON_WIDTH, ICON_HEIGHT = 517, 115
ICON_X = PANEL_X + (PANEL_W - ICON_WIDTH) // 2
ICON_Y = BAR_Y + 23
MAX_TITLE_WIDTH = 580
# -------------------------------------------------

GRADIENT_SETS = [
    # 🔥 Sunset blend
    [(255, 255, 224), (255, 239, 213), (255, 218, 185),
     (255, 182, 193), (255, 160, 122), (255, 140, 0),
     (255, 99, 71), (255, 69, 0), (178, 34, 34), (139, 0, 0)],

    # 🌊 Ocean waves
    [(0, 105, 148), (0, 191, 255), (70, 130, 180),
     (100, 149, 237), (65, 105, 225), (123, 104, 238),
     (138, 43, 226), (106, 90, 205), (72, 61, 139)],

    # 🍃 Forest tones
    [(0, 100, 0), (34, 139, 34), (46, 139, 87),
     (60, 179, 113), (107, 142, 35), (124, 252, 0),
     (127, 255, 0), (173, 255, 47), (144, 238, 144), (152, 251, 152)],

    # 🌸 Candy / pastel mix
    [(255, 192, 203), (255, 182, 193), (255, 160, 122),
     (221, 160, 221), (218, 112, 214), (238, 130, 238),
     (216, 191, 216), (186, 85, 211), (147, 112, 219)],

    # ⚡ Neon vibes
    [(57, 255, 20), (0, 255, 127), (0, 255, 255),
     (0, 191, 255), (30, 144, 255), (138, 43, 226),
     (255, 20, 147), (255, 0, 255), (255, 105, 180), (255, 255, 0)],

    # 🧊 Ice blue
    [(224, 255, 255), (175, 238, 238), (173, 216, 230),
     (135, 206, 250), (135, 206, 235), (176, 224, 230)],

    # ☕ Coffee tones
    [(111, 78, 55), (139, 69, 19), (160, 82, 45),
     (205, 133, 63), (222, 184, 135), (245, 222, 179)],

    # 🎨 Material Indigo
    [(26, 35, 126), (57, 73, 171), (92, 107, 192),
     (121, 134, 203), (159, 168, 218)],

    # 🍂 Autumn orange
    [(255, 228, 181), (255, 218, 185), (255, 160, 122),
     (244, 164, 96), (210, 105, 30), (139, 69, 19)],

    # 🌌 Dark purple
    [(48, 25, 52), (75, 0, 130), (106, 90, 205),
     (123, 104, 238), (147, 112, 219)],

    # 🧁 Pastel mint
    [(152, 251, 152), (144, 238, 144), (102, 205, 170),
     (127, 255, 212), (175, 238, 238)],

    # 🖤 Charcoal grey
    [(33, 33, 33), (55, 55, 55), (77, 77, 77),
     (99, 99, 99), (120, 120, 120)],

    # 💎 Sapphire blue
    [(0, 51, 102), (0, 76, 153), (0, 102, 204),
     (0, 128, 255), (51, 153, 255)],

    # 🌅 Peach sunrise
    [(255, 218, 185), (255, 182, 193), (255, 160, 122),
     (250, 128, 114), (233, 150, 122)],

    # 🌿 Sage green
    [(107, 142, 35), (85, 107, 47), (143, 188, 143),
     (189, 183, 107), (240, 230, 140)],

    # 🎀 Soft lavender
    [(230, 230, 250), (216, 191, 216), (221, 160, 221),
     (238, 130, 238), (218, 112, 214)],

    # 🏙️ Urban night
    [(0, 0, 0), (25, 25, 25), (50, 50, 50),
     (75, 75, 75), (100, 100, 100)],

    # 🍋 Lemon zest
    [(255, 250, 205), (255, 255, 153), (255, 255, 102),
     (255, 255, 0), (204, 204, 0)],

    # 🍇 Grape mix
    [(75, 0, 130), (138, 43, 226), (148, 0, 211),
     (186, 85, 211), (218, 112, 214)],

    # 🧡 Coral tones
    [(255, 127, 80), (240, 128, 128), (233, 150, 122),
     (205, 92, 92), (178, 34, 34)],

    # ❄️ Frost white
    [(245, 245, 245), (220, 220, 220), (211, 211, 211),
     (192, 192, 192), (169, 169, 169)],
]


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


def draw_gradient_bar(draw, x, y, length, height, colors):
    num_colors = len(colors) - 1
    for i in range(length):
        rel_pos = i / (length - 1)
        segment = min(int(rel_pos * num_colors), num_colors - 1)
        local_pos = (rel_pos - segment / num_colors) * num_colors
        start_color, end_color = colors[segment], colors[segment + 1]
        r = int(start_color[0] + (end_color[0] - start_color[0]) * local_pos)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * local_pos)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * local_pos)
        draw.line([(x + i, y), (x + i, y + height)], fill=(r, g, b), width=1)


def create_gradient_overlay(width, height, colors, alpha=150):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    num_colors = len(colors) - 1
    for x in range(width):
        rel_pos = x / (width - 1)
        segment = min(int(rel_pos * num_colors), num_colors - 1)
        local_pos = (rel_pos - segment / num_colors) * num_colors
        start_color, end_color = colors[segment], colors[segment + 1]
        r = int(start_color[0] + (end_color[0] - start_color[0]) * local_pos)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * local_pos)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * local_pos)
        draw.line([(x, 0), (x, height)], fill=(r, g, b, alpha))
    return overlay


async def download_and_process_profile_pic(user_id: int, size=96):
    try:
        photos = await app.get_profile_photos(user_id, limit=1)
        if not photos:
            print(f"[thumb] No profile photo for {user_id}")
            return None
        path = await app.download_media(photos[0].file_id, file_name=f"{CACHE_DIR}/{user_id}.jpg")
        with Image.open(path).convert("RGBA") as im:
            im = ImageOps.fit(im, (size, size))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            im.putalpha(mask)
            return im
    except Exception as e:
        print(f"[thumb] Profile error {user_id}: {e}")
        return None


def get_user_id_from_chat(chat_id: int):
    """Fetch current user's ID from DB for given chat."""
    try:
        if chat_id in db and db[chat_id]:
            user_id = db[chat_id][0].get("user_id")
            print(f"[thumb] Found user_id={user_id} for chat_id={chat_id}")
            return user_id
    except Exception as e:
        print(f"[thumb] DB lookup error: {e}")
    return None


async def get_thumb(videoid: str, chat_id: int = None) -> str:
    """Generate styled thumbnail; auto fetch user_id from chat_id"""
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v5.png")
    if os.path.exists(cache_path):
        return cache_path

    # 🧠 fetch user_id from DB using chat_id
    user_id = get_user_id_from_chat(chat_id) if chat_id else None

    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        data = (await results.next()).get("result", [])[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        thumb_url = data.get("thumbnails", [{}])[0].get("url", FAILED)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumb_url, duration, views = "Unsupported Title", FAILED, None, "Unknown Views"

    thumb_dl = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    async with aiohttp.ClientSession() as session:
        async with session.get(thumb_url) as resp:
            if resp.status == 200:
                async with aiofiles.open(thumb_dl, "wb") as f:
                    await f.write(await resp.read())

    base = Image.open(thumb_dl).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)
    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    gradient_colors = random.choice(GRADIENT_SETS)
    overlay = create_gradient_overlay(PANEL_W, PANEL_H, gradient_colors, TRANSPARENCY)
    frosted = Image.alpha_composite(panel_area, overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    draw = ImageDraw.Draw(bg)
    try:
        title_font = ImageFont.truetype("Pulse/assets/FIGHTBACK.ttf", 32)
        regular_font = ImageFont.truetype("Pulse/assets/font2.ttf", 18)
    except OSError:
        title_font = regular_font = ImageFont.load_default()

    thumb = base.resize((THUMB_W, THUMB_H))
    tmask = Image.new("L", thumb.size, 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)
    draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)
    draw_gradient_bar(draw, BAR_X, BAR_Y - 3, BAR_RED_LEN, 6, gradient_colors)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7), (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)],
                 fill=gradient_colors[-1])
    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
    draw.text((BAR_X + BAR_TOTAL_LEN - 60, BAR_Y + 15), duration or "Live", fill="black", font=regular_font)

    # 🎵 Play icon
    icons_path = "Pulse/assets/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICON_WIDTH, ICON_HEIGHT)).convert("RGBA")
        bg.paste(ic, (ICON_X, ICON_Y), ic)

    # 👤 Add user DP (if found)
    if user_id:
        profile_img = await download_and_process_profile_pic(user_id, 96)
        if profile_img:
            bg.paste(profile_img, (50, 600), profile_img)
            print(f"[thumb] DP pasted for user_id={user_id}")

    os.remove(thumb_dl)
    bg.save(cache_path)
    return cache_path
