"""
YUKIMUSIC — platforms/Youtube.py
Maintainer : HellFireDevs / Kaito
Last fixed : 2026

Download tier order (fastest → fallback):
  1. Hellfire Vault  — local 45 GB pre-cached files, instant
  2. Local DOWNLOAD_DIR cache — previously downloaded files
  3. 3-Way Async Race (FIRST_COMPLETED wins):
       A. Kidnnper DB   — MongoDB Catbox URL lookup + aiohttp stream
       B. YUKI API      — primary, reliable, never fails
       C. yt-dlp Node   — tv_embedded/web client, cookies.txt, Node.js JS engine
"""

import asyncio
import os
import random
import re
import aiohttp
from collections import defaultdict
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Pulse.utils.database import is_on_off
from Pulse.utils.formatters import time_to_seconds

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
FALLBACK_API_URL   = "http://music.yukiapi.site"
YOUR_API_URL       = "http://music.yukiapi.site"
API_URL_PASTEBIN   = None

cookies_file       = "cookies/cookies.txt"
HELLFIRE_VAULT_DIR = "/home/ubuntu/Hellfire_Vault"
DOWNLOAD_DIR       = "downloads"

# ── Kidnnper DB (MongoDB) ─────────────────────────────────────────────────────
# Set MONGO_URI to your connection string (e.g. via env var or hardcoded).
# The bot will gracefully skip this race arm if the URI is not configured.
MONGO_URI          = os.environ.get("MONGO_URI", "")   # e.g. "mongodb://localhost:27017"
KIDNNPER_DB_NAME   = "MusicAPI_DB"                         # MongoDB database name
KIDNNPER_COL_NAME  = "songs_cache"                      # collection name
# Expected document schema:  { "video_id": "dQw4w9WgXcW", "url": "https://files.catbox.moe/abc.mp3" }
# Adjust field names below (_CATBOX_URL_FIELD) to match your actual schema.
_CATBOX_URL_FIELD  = "catbox_link"

# Desktop User-Agent — required to bypass Catbox 403 on direct links
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ═══════════════════════════════════════════════════════════════════════════════
# THUMBNAIL CACHE  (in-memory, max 500 entries)
# ═══════════════════════════════════════════════════════════════════════════════
_thumb_cache: dict[str, str] = {}
_THUMB_CACHE_MAX = 500


def _cache_thumb(vidid: str, url: str) -> str:
    if len(_thumb_cache) >= _THUMB_CACHE_MAX:
        del _thumb_cache[next(iter(_thumb_cache))]
    _thumb_cache[vidid] = url
    return url


# ═══════════════════════════════════════════════════════════════════════════════
# PER-CHAT AUTOPLAY STATE
# ═══════════════════════════════════════════════════════════════════════════════
_autoplay_enabled: dict[int, bool]         = defaultdict(lambda: False)
_autoplay_history: dict[int, set[str]]     = defaultdict(set)
_autoplay_lock:    dict[int, asyncio.Lock] = {}


def get_autoplay_lock(chat_id: int) -> asyncio.Lock:
    """One lock per chat — stops double trigger giving the same song."""
    if chat_id not in _autoplay_lock:
        _autoplay_lock[chat_id] = asyncio.Lock()
    return _autoplay_lock[chat_id]


def is_autoplay_on(chat_id: int) -> bool:
    return _autoplay_enabled[chat_id]


def set_autoplay(chat_id: int, state: bool) -> None:
    _autoplay_enabled[chat_id] = state
    if not state:
        _autoplay_history[chat_id].clear()


def mark_played(chat_id: int, vidid: str) -> None:
    hist = _autoplay_history[chat_id]
    hist.add(vidid)
    if len(hist) > 200:                    # keep bounded
        for v in list(hist)[:50]:
            hist.discard(v)


def was_played(chat_id: int, vidid: str) -> bool:
    return vidid in _autoplay_history[chat_id]


# ═══════════════════════════════════════════════════════════════════════════════
# YUKI API  — primary download engine
# ═══════════════════════════════════════════════════════════════════════════════
_api_init_lock = asyncio.Lock()


async def _resolve_api_url() -> str:
    """Fetch live API base-URL from pastebin; cache for the process lifetime."""
    global YOUR_API_URL
    if YOUR_API_URL:
        return YOUR_API_URL
    async with _api_init_lock:
        if YOUR_API_URL:
            return YOUR_API_URL
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    API_URL_PASTEBIN,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    YOUR_API_URL = (await r.text()).strip() if r.status == 200 else FALLBACK_API_URL
        except Exception:
            YOUR_API_URL = FALLBACK_API_URL
        return YOUR_API_URL


async def _yuki_api_download(link: str, is_video: bool = False) -> str | None:
    """
    Download via YUKI API (2-step: get token → stream file).
    Returns local file path on success, None on any failure.
    """
    api_url  = await _resolve_api_url()
    video_id = _extract_video_id(link)
    if not video_id:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ext       = "mp4" if is_video else "mp3"
    out_path  = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    # Serve from local cache if already downloaded
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    req_type = "video" if is_video else "audio"

    try:
        timeout = aiohttp.ClientTimeout(total=600, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as s:

            # Step 1 — get download token
            async with s.get(
                f"{api_url}/download",
                params={"url": video_id, "type": req_type},
            ) as r:
                if r.status != 200:
                    print(f"[YUKI API] /download returned {r.status} for {video_id}")
                    return None
                token = (await r.json()).get("download_token")
                if not token:
                    print(f"[YUKI API] No token in response for {video_id}")
                    return None

            # Step 2 — stream file to disk (atomic write)
            tmp = out_path + ".tmp"
            async with s.get(
                f"{api_url}/stream/{video_id}",
                params={"type": req_type},
                headers={"X-Download-Token": token},
            ) as r:
                if r.status != 200:
                    print(f"[YUKI API] /stream returned {r.status} for {video_id}")
                    return None
                try:
                    with open(tmp, "wb") as f:
                        async for chunk in r.content.iter_chunked(16384):
                            f.write(chunk)
                    os.replace(tmp, out_path)          # atomic — no partial files
                except Exception:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    raise

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
        return None

    except asyncio.TimeoutError:
        print(f"[YUKI API] Timeout for {video_id}")
        return None
    except Exception as e:
        print(f"[YUKI API] Error for {video_id}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# YT-DLP CLIENT OPTIONS
#
#  Android client
#    ✅ No JS signature needed  →  fixes SignatureTimestampMismatch
#    ✅ Works for all public videos (90 %+ of requests)
#    ❌ cookiefile is IGNORED by yt-dlp for android client (documented limitation)
#    ❌ Cannot access age-restricted / login-required videos
#
#  Web client + cookies
#    ✅ cookiefile works fully
#    ✅ Accesses age-restricted / login-required content
#    ✅ web_creator gives 1080p+ quality
#    ❌ Fails if cookies.txt is stale / empty
#
#  Every yt-dlp call below tries android first, then web+cookies.
# ═══════════════════════════════════════════════════════════════════════════════
_COMMON_YDL = {
    "quiet":              True,
    "no_warnings":        True,
    "geo_bypass":         True,
    "nocheckcertificate": True,
    "retries":            5,
    "fragment_retries":   5,
}


def _android_opts(extra: dict | None = None) -> dict:
    opts = {
        **_COMMON_YDL,
        # cookiefile intentionally absent — android ignores it
        "extractor_args": {
            "youtube": {"player_client": ["android", "android_music"]}
        },
    }
    if extra:
        opts.update(extra)
    return opts


def _web_opts(extra: dict | None = None) -> dict:
    has_cookies = os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 10
    opts = {
        **_COMMON_YDL,
        "extractor_args": {
            "youtube": {"player_client": ["web_creator", "web"]}
        },
    }
    if has_cookies:
        opts["cookiefile"] = cookies_file
    if extra:
        opts.update(extra)
    return opts


def _ydl_clients(extra: dict | None = None) -> list[dict]:
    """Return [android_opts, web_opts] — callers iterate and try each."""
    return [_android_opts(extra), _web_opts(extra)]


def _ydl_node_opts(extra: dict | None = None) -> dict:
    """
    yt-dlp options for the async race arm.

    Constraints (per spec):
      • NO android client — uses tv_embedded / web instead
      • cookiefile — required for age-restricted / login-required content
      • js_runtime: node — bypasses YouTube JS signature errors (jsInterpProto)
    """
    has_cookies = os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 10
    opts = {
        **_COMMON_YDL,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "tv_embedded"],
                "js_runtime":    ["node"],          # forces Node.js for sig decryption
            }
        },
    }
    if has_cookies:
        opts["cookiefile"] = cookies_file
    if extra:
        opts.update(extra)
    return opts


# ═══════════════════════════════════════════════════════════════════════════════
# SHELL HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if err:
        err_s = err.decode("utf-8", errors="replace")
        if "unavailable videos are hidden" in err_s.lower():
            return out.decode("utf-8", errors="replace")
        return err_s
    return out.decode("utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════════════════════
# SMALL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_video_id(link: str) -> str | None:
    for pat in [
        r"(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?]|$)",
        r"youtu\.be/([0-9A-Za-z_-]{11})",
        r"embed/([0-9A-Za-z_-]{11})",
        r"shorts/([0-9A-Za-z_-]{11})",
    ]:
        m = re.search(pat, link)
        if m:
            return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", link.strip()):
        return link.strip()
    return None


def _clean_link(link: str) -> str:
    """Strip playlist params — keep clean watch URL."""
    return link.split("&")[0] if "&" in link else link


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH RACE — 3-way async race (single result)
#
#   Arm A: youtube-search-python  (VideosSearch)
#   Arm B: yt-music-api vercel    (fastest, own deployment)
#   Arm C: yt-dlp                 (most reliable fallback)
#
#   asyncio.wait(FIRST_COMPLETED) — same pattern as _run_race().
#   First arm to return a valid result wins; losers are cancelled.
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_arm_ytsp(query: str) -> dict | None:
    """Search arm A: youtube-search-python."""
    try:
        s     = VideosSearch(query, limit=1)
        items = (await s.next()).get("result", [])
        if not items:
            return None
        r = items[0]
        if not r.get("id") or not r.get("duration"):
            return None
        thumb = (
            r["thumbnails"][0]["url"].split("?")[0]
            if r.get("thumbnails")
            else f"https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg"
        )
        return {
            "id": r["id"], "title": r["title"],
            "link": r["link"], "duration": r["duration"],
            "thumbnails": [{"url": thumb}],
        }
    except Exception as e:
        print(f"[search/ytsp] failed for {query!r}: {e}")
        return None


async def _search_arm_vercel(query: str) -> dict | None:
    """Search arm B: yt-music-api vercel (fastest — own deployment)."""
    try:
        import urllib.parse
        url = (
            f"https://yt-music-api-seven.vercel.app/search/musics"
            f"?query={urllib.parse.quote(query)}"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
        for item in data.get("content", []):
            vid_id   = item.get("youtubeId")
            duration = item.get("duration", {}).get("duration")
            title    = item.get("name")
            if not vid_id or not duration or not title:
                continue
            thumb      = item.get("thumbnails", [{}])[-1].get("url", "")
            mins, secs = int(duration // 60), int(duration % 60)
            return {
                "id": vid_id, "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "duration": f"{mins}:{secs:02d}",
                "thumbnails": [{"url": thumb}],
            }
        return None
    except Exception as e:
        print(f"[search/vercel] failed for {query!r}: {e}")
        return None


async def _search_arm_ytdlp(query: str) -> dict | None:
    """Search arm C: yt-dlp ytsearch."""
    try:
        loop = asyncio.get_running_loop()

        def _search():
            opts = {
                "quiet": True, "no_warnings": True,
                "extract_flat": True, "skip_download": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                r = ydl.extract_info(f"ytsearch5:{query}", download=False)
                for e in (r.get("entries", []) if r else []):
                    if e and e.get("duration") and e.get("id"):
                        return e
            return None

        e = await loop.run_in_executor(None, _search)
        if not e:
            return None
        vid_id     = e["id"]
        mins, secs = int(e["duration"] // 60), int(e["duration"] % 60)
        return {
            "id": vid_id, "title": e.get("title", query),
            "link": f"https://www.youtube.com/watch?v={vid_id}",
            "duration": f"{mins}:{secs:02d}",
            "thumbnails": [{"url": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"}],
        }
    except Exception as e:
        print(f"[search/ytdlp] failed for {query!r}: {e}")
        return None


async def _race_search_one(query: str) -> dict | None:
    """
    3-way async race — single best search result.
    Arms: youtube-search-python | vercel API | yt-dlp
    First valid result wins; losers are cancelled.
    Used by: track(), details(), title(), thumbnail(), duration()
    """
    coros  = [
        _search_arm_ytsp(query),
        _search_arm_vercel(query),
        _search_arm_ytdlp(query),
    ]
    labels = ["ytsp", "vercel", "yt-dlp"]

    pending: set[asyncio.Task] = {asyncio.ensure_future(c) for c in coros}
    task_labels = {t: labels[i] for i, t in enumerate(pending)}
    winner: dict | None = None

    while pending and winner is None:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            label = task_labels.get(fut, "?")
            try:
                result = fut.result()
            except Exception as e:
                print(f"[search race] ❌ {label} raised: {e}")
                continue
            if result:
                print(f"[search race] 🏆 {label} → {result.get('title', '?')!r}")
                winner = result
                break
            else:
                print(f"[search race] ⚠️  {label} returned None")

    for fut in pending:
        fut.cancel()
        try:
            await fut
        except (asyncio.CancelledError, Exception):
            pass

    return winner


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH RACE — 3-way async race (multiple results, for slider/addplaylist)
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_arm_ytsp_many(query: str, limit: int = 10) -> list[dict]:
    """Arm A (many): youtube-search-python."""
    try:
        s     = VideosSearch(query, limit=limit)
        items = (await s.next()).get("result", [])
        out   = []
        for r in items:
            if not r.get("id") or not r.get("duration"):
                continue
            thumb = (
                r["thumbnails"][0]["url"].split("?")[0]
                if r.get("thumbnails")
                else f"https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg"
            )
            out.append({
                "id": r["id"], "title": r["title"],
                "link": r["link"], "duration": r["duration"],
                "thumbnails": [{"url": thumb}],
            })
        return out
    except Exception as e:
        print(f"[search_many/ytsp] failed for {query!r}: {e}")
        return []


async def _search_arm_vercel_many(query: str, limit: int = 10) -> list[dict]:
    """Arm B (many): vercel API."""
    try:
        import urllib.parse
        url = (
            f"https://yt-music-api-seven.vercel.app/search/musics"
            f"?query={urllib.parse.quote(query)}"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
        out = []
        for item in data.get("content", []):
            vid_id   = item.get("youtubeId")
            duration = item.get("duration", {}).get("duration")
            title    = item.get("name")
            if not vid_id or not duration or not title:
                continue
            thumb      = item.get("thumbnails", [{}])[-1].get("url", "")
            mins, secs = int(duration // 60), int(duration % 60)
            out.append({
                "id": vid_id, "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "duration": f"{mins}:{secs:02d}",
                "thumbnails": [{"url": thumb}],
            })
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        print(f"[search_many/vercel] failed for {query!r}: {e}")
        return []


async def _search_arm_ytdlp_many(query: str, limit: int = 10) -> list[dict]:
    """Arm C (many): yt-dlp ytsearch."""
    try:
        loop = asyncio.get_running_loop()

        def _search():
            opts = {
                "quiet": True, "no_warnings": True,
                "extract_flat": True, "skip_download": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                r = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                return [
                    e for e in (r.get("entries", []) if r else [])
                    if e and e.get("id") and e.get("duration")
                ]

        entries = await loop.run_in_executor(None, _search)
        out = []
        for e in entries:
            vid_id     = e["id"]
            mins, secs = int(e["duration"] // 60), int(e["duration"] % 60)
            out.append({
                "id": vid_id, "title": e.get("title", query),
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "duration": f"{mins}:{secs:02d}",
                "thumbnails": [{"url": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"}],
            })
        return out
    except Exception as e:
        print(f"[search_many/ytdlp] failed for {query!r}: {e}")
        return []


async def _race_search_many(query: str, limit: int = 10) -> list[dict]:
    """
    3-way async race — multiple search results.
    First arm to return a non-empty list wins; losers are cancelled.
    Used by: slider() (addplaylist Next/Prev navigation)
    """
    coros  = [
        _search_arm_ytsp_many(query, limit),
        _search_arm_vercel_many(query, limit),
        _search_arm_ytdlp_many(query, limit),
    ]
    labels = ["ytsp", "vercel", "yt-dlp"]

    pending: set[asyncio.Task] = {asyncio.ensure_future(c) for c in coros}
    task_labels = {t: labels[i] for i, t in enumerate(pending)}
    winner: list[dict] = []

    while pending and not winner:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            label = task_labels.get(fut, "?")
            try:
                result = fut.result()
            except Exception as e:
                print(f"[search_many race] ❌ {label} raised: {e}")
                continue
            if result:
                print(f"[search_many race] 🏆 {label} → {len(result)} results")
                winner = result
                break
            else:
                print(f"[search_many race] ⚠️  {label} returned empty")

    for fut in pending:
        fut.cancel()
        try:
            await fut
        except (asyncio.CancelledError, Exception):
            pass

    return winner


def _build_search_queries(title: str) -> list[str]:
    """
    Multiple varied search queries from one song title.
    Prevents autoplay always returning the same top-2 YouTube results.
    """
    clean = re.sub(r"\s*[\(\[].{0,40}[\)\]]", "", title, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s*(feat\.?|ft\.?|x |×).+$", "", clean, flags=re.IGNORECASE).strip()

    artist = ""
    if " - " in clean:
        artist, clean = [x.strip() for x in clean.split(" - ", 1)]

    seen, out = set(), []
    for q in [
        f"{artist} songs"          if artist else None,
        f"{artist} best hits"      if artist else None,
        f"songs like {clean}",
        f"{clean} similar songs",
        f"{artist} {clean} mix"    if artist else None,
        clean,
    ]:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# RACE ARM 1 — Kidnnper DB (MongoDB → Catbox Downloader)
# ═══════════════════════════════════════════════════════════════════════════════

async def _catbox_db_download(video_id: str, is_video: bool) -> str | None:
    """
    Race arm 1: look up video_id in MongoDB (Kidnnper DB).
    If a Catbox URL exists, stream it to disk using a desktop User-Agent
    to bypass Catbox's 403 block on bot/headless requests.

    Returns local file path on success, None on any failure (so the race
    continues without crashing).
    """
    if not MONGO_URI:
        # MongoDB not configured — skip this arm silently
        return None

    try:
        # Import lazily so the bot starts even without motor installed
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError:
        print("[Kidnnper DB] motor not installed — skipping arm (pip install motor)")
        return None

    try:
        client  = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        col     = client[KIDNNPER_DB_NAME][KIDNNPER_COL_NAME]
        doc     = await col.find_one({"video_id": video_id})
        client.close()
    except Exception as e:
        print(f"[Kidnnper DB] MongoDB lookup failed for {video_id}: {e}")
        return None

    if not doc:
        print(f"[Kidnnper DB] No record found for {video_id}")
        return None

    catbox_url: str | None = doc.get(_CATBOX_URL_FIELD)
    if not catbox_url:
        print(f"[Kidnnper DB] Record exists but URL field '{_CATBOX_URL_FIELD}' is empty for {video_id}")
        return None

    # Determine output path from the Catbox URL extension
    url_ext = catbox_url.rsplit(".", 1)[-1].lower() if "." in catbox_url else ("mp4" if is_video else "mp3")
    
    # If a video is requested but the Catbox link is just an audio file, SKIP this DB cache.
    if is_video and url_ext in ["mp3", "m4a", "opus", "wav", "flac"]:
        print(f"[Kidnnper DB] Skipping audio-only DB cache for video request: {video_id}")
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    out_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{url_ext}")

    # Return immediately if already on disk
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print(f"[Kidnnper DB] ✅ already cached: {out_path}")
        return out_path

    try:
        timeout = aiohttp.ClientTimeout(total=600, connect=10)
        headers = {
            "User-Agent": _DESKTOP_UA,   # MUST — bypasses Catbox 403
            "Referer":    "https://catbox.moe/",
        }
        tmp = out_path + ".tmp"
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
            async with s.get(catbox_url) as r:
                if r.status != 200:
                    print(f"[Kidnnper DB] Catbox returned HTTP {r.status} for {video_id} ({catbox_url})")
                    return None
                try:
                    with open(tmp, "wb") as f:
                        async for chunk in r.content.iter_chunked(16384):
                            f.write(chunk)
                    os.replace(tmp, out_path)   # atomic write — no partial files on disk
                except Exception:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    raise

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[Kidnnper DB] ✅ {out_path}")
            return out_path
        return None

    except asyncio.TimeoutError:
        print(f"[Kidnnper DB] Timeout while downloading {catbox_url}")
        return None
    except Exception as e:
        print(f"[Kidnnper DB] Download error for {video_id}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# RACE ARM 3 — yt-dlp (Node.js runtime, tv_embedded/web, cookies.txt)
# ═══════════════════════════════════════════════════════════════════════════════

async def _ydl_node_download(link: str, is_video: bool) -> str | None:
    """
    Race arm 3: yt-dlp via run_in_executor.

    Constraints enforced:
      • NO android client  — uses tv_embedded / web
      • cookiefile         — always passed when cookies.txt exists
      • js_runtime: node   — forces Node.js to resolve YouTube JS sig errors
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    loop = asyncio.get_running_loop()

    _AUDIO_FMT = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
    _VIDEO_FMT = "bestvideo[height<=?720]+bestaudio/best"
    fmt_str  = _VIDEO_FMT if is_video else _AUDIO_FMT
    dl_extra = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        **({"merge_output_format": "mp4"} if is_video else {}),
    }
    opts = _ydl_node_opts({**dl_extra, "format": fmt_str})

    def _run() -> str | None:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                ext  = "mp4" if is_video else info["ext"]
                path = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{ext}")
                if not (os.path.exists(path) and os.path.getsize(path) > 0):
                    ydl.download([link])
                return path if os.path.exists(path) and os.path.getsize(path) > 0 else None
        except Exception as e:
            print(f"[yt-dlp/node] Error: {e}")
            return None

    try:
        path = await loop.run_in_executor(None, _run)
        if path:
            print(f"[yt-dlp/node] ✅ {path}")
        return path
    except Exception as e:
        print(f"[yt-dlp/node] Executor error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# THE RACE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_race(
    link:     str,
    video_id: str,
    is_video: bool,
) -> str | None:
    """
    Fire all 3 download arms simultaneously.
    Uses asyncio.wait(FIRST_COMPLETED) in a loop so that:
      • The first arm to return a valid path WINS immediately.
      • A failed arm (returns None / raises) is skipped — the race continues.
      • All losing/pending futures are cancelled once a winner is found.

    Returns the winning file path, or None if every arm failed.
    """
    # Build coroutines for the three arms
    coros = [
        _catbox_db_download(video_id, is_video),        # Arm A: Kidnnper DB
        _yuki_api_download(link, is_video),              # Arm B: YUKI API
        _ydl_node_download(link, is_video),              # Arm C: yt-dlp Node
    ]
    labels = ["Kidnnper DB", "YUKI API", "yt-dlp/node"]

    # Wrap each coroutine in a Task so asyncio.wait can track them
    pending: set[asyncio.Task] = {
        asyncio.ensure_future(c) for c in coros
    }
    # Map task → label for logging
    task_labels: dict[asyncio.Task, str] = {
        t: labels[i] for i, t in enumerate(pending)
    }

    winner: str | None = None

    while pending and winner is None:
        done, pending = await asyncio.wait(
            pending,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for fut in done:
            label = task_labels.get(fut, "?")
            try:
                result = fut.result()
            except Exception as e:
                print(f"[Race] ❌ {label} raised: {e} — race continues")
                continue

            if result:
                print(f"[Race] 🏆 Winner: {label} → {result}")
                winner = result
                break
            else:
                print(f"[Race] ⚠️  {label} returned None — race continues")

    # Cancel all tasks still running (losers)
    for fut in pending:
        label = task_labels.get(fut, "?")
        fut.cancel()
        try:
            await fut            # let the cancellation propagate cleanly
        except (asyncio.CancelledError, Exception):
            pass
        print(f"[Race] ✖  Cancelled: {label}")

    return winner


# ═══════════════════════════════════════════════════════════════════════════════
# YouTubeAPI CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class YouTubeAPI:

    def __init__(self):
        self.base     = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.regex    = re.compile(r"(?:youtube\.com|youtu\.be)")
        self.ansi_re  = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    # ── exists ────────────────────────────────────────────────────────────────

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(self.regex.search(link))

    # ── url ───────────────────────────────────────────────────────────────────

    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)
        for msg in messages:
            for ents in (msg.entities, msg.caption_entities):
                if not ents:
                    continue
                for e in ents:
                    if e.type == MessageEntityType.TEXT_LINK:
                        return e.url
                    if e.type == MessageEntityType.URL:
                        text = msg.text or msg.caption or ""
                        return text[e.offset : e.offset + e.length]
        return None

    # ── details ───────────────────────────────────────────────────────────────

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        r = await _race_search_one(_clean_link(link))
        if not r:
            raise Exception(f"No results: {link}")
        thumb = r["thumbnails"][0]["url"].split("?")[0]
        dur_s = int(time_to_seconds(r["duration"])) if r["duration"] else 0
        _cache_thumb(r["id"], thumb)
        return r["title"], r["duration"], dur_s, thumb, r["id"]

    # ── title ─────────────────────────────────────────────────────────────────

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        r = await _race_search_one(_clean_link(link))
        return r["title"] if r else ""

    # ── duration ──────────────────────────────────────────────────────────────

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        r = await _race_search_one(_clean_link(link))
        return r["duration"] if r else "0:00"

    # ── thumbnail ─────────────────────────────────────────────────────────────

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        vid = _extract_video_id(link)
        if vid and vid in _thumb_cache:
            return _thumb_cache[vid]
        r = await _race_search_one(_clean_link(link))
        if not r:
            return ""
        url = r["thumbnails"][0]["url"].split("?")[0]
        if vid:
            _cache_thumb(vid, url)
        return url

    # ── playlist ──────────────────────────────────────────────────────────────

    async def playlist(
        self, link: str, limit: int, user_id: int,
        videoid: Union[bool, str] = None,
    ) -> list[str]:
        if videoid:
            link = self.listbase + link
        raw = await shell_cmd(
            f"yt-dlp --cookies {cookies_file} -i --get-id "
            f"--flat-playlist --playlist-end {limit} --skip-download {_clean_link(link)}"
        )
        return [self.ansi_re.sub("", v).strip() for v in raw.split("\n") if v.strip()]

    # ── track ─────────────────────────────────────────────────────────────────

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        r = await _race_search_one(_clean_link(link))
        if not r:
            raise Exception(f"No track found: {link}")
        thumb = r["thumbnails"][0]["url"].split("?")[0]
        _cache_thumb(r["id"], thumb)
        return {
            "title": r["title"], "link": r["link"], "vidid": r["id"],
            "duration_min": r["duration"], "thumb": thumb,
        }, r["id"]

    # ── formats ───────────────────────────────────────────────────────────────

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = _clean_link(link)
        loop = asyncio.get_running_loop()

        def _extract():
            for opts in _ydl_clients():
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(link, download=False)
                except Exception as e:
                    print(f"[formats] client attempt failed: {e}")
            raise Exception("formats: all clients failed")

        try:
            info = await loop.run_in_executor(None, _extract)
        except Exception as e:
            print(f"[formats] yt-dlp extract failed: {e}")
            return [], link

        out = []
        for fmt in info.get("formats", []):
            try:
                if "dash" not in str(fmt.get("format", "")).lower():
                    out.append({
                        "format":      fmt["format"],
                        "filesize":    fmt.get("filesize"),
                        "format_id":   fmt["format_id"],
                        "ext":         fmt["ext"],
                        "format_note": fmt.get("format_note", ""),
                        "yturl":       link,
                    })
            except Exception:
                continue
        return out, link

    # ── slider ────────────────────────────────────────────────────────────────

    async def slider(
        self, link: str, query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        link  = _clean_link(link)
        items = await _race_search_many(link, limit=10)
        if not items:
            raise Exception(f"No search results: {link}")
        if query_type >= len(items):
            query_type = 0
        r     = items[query_type]
        thumb = r["thumbnails"][0]["url"].split("?")[0] if r.get("thumbnails") else ""
        _cache_thumb(r["id"], thumb)
        return r["title"], r["duration"], thumb, r["id"]

    # ── video  (live stream direct URL) ───────────────────────────────────────

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = _clean_link(link)
        loop = asyncio.get_running_loop()

        def _get_url():
            for opts in _ydl_clients({"format": "best", "noplaylist": True}):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(link, download=False)
                        url  = info.get("url") or info.get("manifest_url")
                        if url:
                            return url
                except Exception as e:
                    print(f"[video/live] client attempt failed: {e}")
            return None

        try:
            url = await loop.run_in_executor(None, _get_url)
            return (1, url) if url else (0, None)
        except Exception as e:
            print(f"[video/live] failed: {e}")
            return 0, None

    # ── is_live ───────────────────────────────────────────────────────────────

    async def is_live(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        link = _clean_link(link)
        loop = asyncio.get_running_loop()

        def _check():
            for opts in _ydl_clients({"skip_download": True}):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(link, download=False)
                        return bool(
                            info.get("is_live") or
                            info.get("live_status") == "is_live"
                        )
                except Exception:
                    pass
            return False

        try:
            return await loop.run_in_executor(None, _check)
        except Exception:
            return False

    # ── search ────────────────────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        try:
            r     = VideosSearch(query, limit=limit)
            items = (await r.next()).get("result", [])
        except Exception as e:
            print(f"[search] failed: {e}")
            return []
        out = []
        for item in items:
            thumb = item["thumbnails"][0]["url"].split("?")[0] if item.get("thumbnails") else ""
            _cache_thumb(item["id"], thumb)
            out.append({
                "title":     item["title"],
                "duration":  item.get("duration", "N/A"),
                "vidid":     item["id"],
                "thumbnail": thumb,
                "link":      item["link"],
                "channel":   item.get("channel", {}).get("name", ""),
                "views":     item.get("viewCount", {}).get("short", ""),
            })
        return out

    # ── related ───────────────────────────────────────────────────────────────

    async def related(
        self,
        vidid:   str,
        limit:   int = 10,
        chat_id: int = None,
    ) -> list[dict]:
        """
        Related tracks for autoplay.

        FIX vs old code:
          • Old used extract_flat on single video → entries always [] → same 2 songs
          • Now uses YouTube Mix URL (RD{vidid}) — YouTube's own radio engine
          • Shuffled results → different order each call
          • Per-chat deduplication → different songs across GCs
        """
        loop    = asyncio.get_running_loop()
        mix_url = f"https://www.youtube.com/watch?v={vidid}&list=RD{vidid}"

        # ── Step 1: YouTube Mix playlist ─────────────────────────────────────
        def _get_mix():
            extra = {
                "extract_flat":  "in_playlist",
                "playlistend":   limit + 15,
                "skip_download": True,
                "ignoreerrors":  True,
            }
            for opts in _ydl_clients(extra):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info    = ydl.extract_info(mix_url, download=False) or {}
                        entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
                        if not entries:
                            continue
                        src_title = next(
                            (e.get("title", "") for e in entries if e.get("id") == vidid),
                            entries[0].get("title", ""),
                        )
                        return src_title, [
                            {
                                "vidid":     e["id"],
                                "title":     e.get("title", ""),
                                "duration":  e.get("duration_string", e.get("duration", "")),
                                "link":      f"https://www.youtube.com/watch?v={e['id']}",
                                "thumbnail": _thumb_cache.get(e["id"], ""),
                                "channel":   e.get("channel", ""),
                            }
                            for e in entries if e["id"] != vidid
                        ]
                except Exception as e:
                    print(f"[related/_get_mix] attempt failed: {e}")
            return "", []

        source_title = ""
        candidates: list[dict] = []

        try:
            source_title, candidates = await loop.run_in_executor(None, _get_mix)
            print(f"[related] Mix → {len(candidates)} tracks for {vidid}")
        except Exception as e:
            print(f"[related] Mix fetch error: {e}")

        # ── Step 2: Search supplement if mix gave too few ─────────────────────
        if len(candidates) < 5:
            if not source_title:
                r = await _race_search_one(self.base + vidid)
                source_title = r["title"] if r else ""

            if source_title:
                seen_ids = {c["vidid"] for c in candidates} | {vidid}
                for q in _build_search_queries(source_title):
                    if len(candidates) >= limit + 5:
                        break
                    try:
                        sr    = VideosSearch(q, limit=8)
                        items = (await sr.next()).get("result", [])
                        for item in items:
                            if item["id"] in seen_ids:
                                continue
                            thumb = (
                                item["thumbnails"][0]["url"].split("?")[0]
                                if item.get("thumbnails") else ""
                            )
                            _cache_thumb(item["id"], thumb)
                            candidates.append({
                                "vidid":     item["id"],
                                "title":     item["title"],
                                "duration":  item.get("duration", ""),
                                "link":      item["link"],
                                "thumbnail": thumb,
                                "channel":   item.get("channel", {}).get("name", ""),
                            })
                            seen_ids.add(item["id"])
                    except Exception as e:
                        print(f"[related] search fallback {q!r} failed: {e}")

        if not candidates:
            print(f"[related] No related tracks found for {vidid}")
            return []

        # ── Step 3: Shuffle for variety ───────────────────────────────────────
        random.shuffle(candidates)

        # ── Step 4: Per-chat deduplication ────────────────────────────────────
        if chat_id is not None:
            fresh = [c for c in candidates if not was_played(chat_id, c["vidid"])]
            if not fresh:
                print(f"[related] All tracks played in chat {chat_id} — resetting history")
                _autoplay_history[chat_id].clear()
                fresh = candidates
            candidates = fresh

        return candidates[:limit]

    # ── autoplay_next ─────────────────────────────────────────────────────────

    async def autoplay_next(self, vidid: str, chat_id: int) -> dict | None:
        """
        Thread-safe wrapper for autoplay.py.

        Usage in autoplay.py:
        ──────────────────────────────────────────────────────────────────
        from Pulse.platforms.Youtube import (
            YouTubeAPI, is_autoplay_on, set_autoplay
        )
        yt = YouTubeAPI()

        # /autoplay command:
        async def cmd_autoplay(client, message):
            chat_id = message.chat.id
            new_state = not is_autoplay_on(chat_id)
            set_autoplay(chat_id, new_state)
            await message.reply("✅ Autoplay ON" if new_state else "❌ Autoplay OFF")

        # Called when a track ends:
        async def on_stream_end(chat_id, finished_vidid):
            if not is_autoplay_on(chat_id):
                return
            nxt = await yt.autoplay_next(finished_vidid, chat_id)
            if nxt:
                # play nxt["link"] using your existing play flow
        ──────────────────────────────────────────────────────────────────
        """
        lock = get_autoplay_lock(chat_id)
        if lock.locked():
            # Double trigger — first one already handling it
            return None

        async with lock:
            tracks = await self.related(vidid, limit=10, chat_id=chat_id)
            if not tracks:
                return None
            nxt = tracks[0]
            mark_played(chat_id, nxt["vidid"])

            # Warm the YUKI API cache in background (non-blocking)
            asyncio.create_task(_yuki_api_download(nxt["link"], is_video=False))
            return nxt

    # ── download  (MAIN — Vault → local cache → 3-way async race) ─────────────

    async def download(
        self,
        link:      str,
        mystic,
        video:     Union[bool, str] = None,
        videoid:   Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title:     Union[bool, str] = None,
    ) -> tuple[str, bool]:

        is_video = bool(video or songvideo)
        vid      = _extract_video_id(link) or link

        if videoid:
            link = self.base + link
        link = _clean_link(link)

        # ── TIER 1: Hellfire Vault  (local 45 GB cache, instant) ─────────────
        if os.path.exists(HELLFIRE_VAULT_DIR):
            exts = ["mp4", "mkv", "webm"] if is_video else ["mp3", "m4a", "opus", "webm"]
            for ext in exts:
                path = os.path.join(HELLFIRE_VAULT_DIR, f"{vid}.{ext}")
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    print(f"[Vault] ✅ {path}")
                    return path, True

        # ── TIER 2: Local DOWNLOAD_DIR cache  (already downloaded this session) ──
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        exts = ["mp4", "mkv", "webm"] if is_video else ["mp3", "m4a", "opus", "webm"]
        for ext in exts:
            path = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
            if os.path.exists(path) and os.path.getsize(path) > 0:
                print(f"[Cache] ✅ {path}")
                return path, True

        # ── TIER 3: 3-Way Async Race ──────────────────────────────────────────
        #
        #   ARM A — Kidnnper DB  : MongoDB → Catbox URL → aiohttp stream
        #                          (with desktop User-Agent to bypass 403)
        #   ARM B — YUKI API     : token-based 2-step stream, always reliable
        #   ARM C — yt-dlp/Node  : tv_embedded/web client + cookies.txt
        #                          + js_runtime:node (no android client)
        #
        #   asyncio.wait(FIRST_COMPLETED) loops until one arm wins or all fail.
        #   Failing arms return None silently — they never crash the race.
        # ─────────────────────────────────────────────────────────────────────
        print(f"[Race] 🚀 Launching 3-way race for {vid} (video={is_video})")
        path = await _run_race(link=link, video_id=vid, is_video=is_video)

        if path:
            return path, True

        # ── All arms exhausted ────────────────────────────────────────────────
        raise Exception(
            f"All download tiers failed for: {link}\n"
            f"  Checked: Hellfire Vault, local cache, "
            f"Kidnnper DB (Catbox), YUKI API, yt-dlp (Node/tv_embedded/web)"
          )
