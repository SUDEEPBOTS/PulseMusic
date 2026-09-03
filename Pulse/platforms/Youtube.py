import asyncio
import os
import random
import re
import urllib.parse
from collections import defaultdict
from typing import Union

import aiohttp
from py_yt import VideosSearch, Playlist

API_URL = os.environ.get("MEOW_API_URL", "https://music.yukiapi.site")

API_KEY = os.environ.get("MEOW_API_KEY", "YOUR_API_KEY") ## Get This API KEY FROM TELEGRAM BOT USERNAME: @MeowApiRobot
DOWNLOAD_DIR = "downloads"

_global_session: aiohttp.ClientSession | None = None
_session_lock = asyncio.Lock()


async def get_session() -> aiohttp.ClientSession:
    global _global_session
    if _global_session is not None and not _global_session.closed:
        return _global_session

    async with _session_lock:
        if _global_session is not None and not _global_session.closed:
            return _global_session

        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=50,
            ttl_dns_cache=600,
            keepalive_timeout=300,
            enable_cleanup_closed=True,
            force_close=False,
        )
        timeout = aiohttp.ClientTimeout(total=180, connect=10, sock_read=60)
        _global_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )
        return _global_session


_thumb_cache: dict[str, str] = {}
_THUMB_CACHE_MAX = 1000


def _cache_thumb(vidid: str, url: str) -> str:
    if len(_thumb_cache) >= _THUMB_CACHE_MAX:
        del _thumb_cache[next(iter(_thumb_cache))]
    _thumb_cache[vidid] = url
    return url


_autoplay_enabled: dict[int, bool] = defaultdict(lambda: False)
_autoplay_history: dict[int, set[str]] = defaultdict(set)
_autoplay_lock: dict[int, asyncio.Lock] = {}


def get_autoplay_lock(chat_id: int) -> asyncio.Lock:
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
    if len(hist) > 300:
        for v in list(hist)[:100]:
            hist.discard(v)


def was_played(chat_id: int, vidid: str) -> bool:
    return vidid in _autoplay_history[chat_id]


def _extract_video_id(link: str) -> str | None:
    if not link:
        return None
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
    return link.split("&")[0] if "&" in link else link


def time_to_seconds(time_str: str) -> int:
    if not time_str:
        return 0
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return int(parts[0]) if parts[0].isdigit() else 0


async def _fetch_oembed(video_id: str) -> dict | None:
    session = await get_session()
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
            if resp.status == 200:
                data = await resp.json()
                title = data.get("title", "")
                thumb = data.get("thumbnail_url", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
                return {
                    "id": video_id,
                    "title": title,
                    "link": f"https://www.youtube.com/watch?v={video_id}",
                    "duration": "0:00",
                    "thumbnails": [{"url": thumb}],
                }
    except Exception:
        pass
    return None


async def _search_vercel(query: str, limit: int = 1) -> list[dict]:
    session = await get_session()
    url = f"https://yt-music-api-seven.vercel.app/search/musics?query={urllib.parse.quote(query)}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
            if resp.status == 200:
                data = await resp.json()
                out = []
                for item in data.get("content", []):
                    vid_id = item.get("id")
                    title = item.get("title")
                    if not vid_id or not title:
                        continue
                    dur_obj = item.get("duration", {})
                    dur_str = dur_obj.get("formatted") if isinstance(dur_obj, dict) else "0:00"
                    thumbs = item.get("thumbnails", [])
                    thumb = thumbs[-1].get("url") if thumbs else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
                    out.append({
                        "id": vid_id,
                        "title": title,
                        "link": f"https://www.youtube.com/watch?v={vid_id}",
                        "duration": dur_str or "0:00",
                        "thumbnails": [{"url": thumb}],
                    })
                    if len(out) >= limit:
                        break
                return out
    except Exception:
        pass
    return []


async def _search_one(query: str) -> dict | None:
    vid = _extract_video_id(query)
    if vid:
        oembed = await _fetch_oembed(vid)
        if oembed:
            return oembed

    try:
        s = VideosSearch(query, limit=1)
        res = await s.next()
        items = res.get("result", [])
        if items and items[0].get("id"):
            r = items[0]
            thumb = (
                r["thumbnails"][0]["url"].split("?")[0]
                if r.get("thumbnails")
                else f"https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg"
            )
            return {
                "id": r["id"],
                "title": r.get("title", query),
                "link": r.get("link", f"https://www.youtube.com/watch?v={r['id']}"),
                "duration": r.get("duration", "0:00"),
                "thumbnails": [{"url": thumb}],
            }
    except Exception:
        pass

    vercel_results = await _search_vercel(query, limit=1)
    if vercel_results:
        return vercel_results[0]

    try:
        import yt_dlp
        loop = asyncio.get_running_loop()

        def _ytdlp_flat():
            opts = {"extract_flat": True, "quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                target = query if vid else f"ytsearch1:{query}"
                info = ydl.extract_info(target, download=False)
                if "entries" in info and info["entries"]:
                    return info["entries"][0]
                return info

        info = await loop.run_in_executor(None, _ytdlp_flat)
        if info and info.get("id"):
            v_id = info["id"]
            dur_s = int(info.get("duration") or 0)
            dur_str = f"{dur_s//60}:{dur_s%60:02d}" if dur_s else "0:00"
            thumb = f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg"
            return {
                "id": v_id,
                "title": info.get("title", query),
                "link": f"https://www.youtube.com/watch?v={v_id}",
                "duration": dur_str,
                "thumbnails": [{"url": thumb}],
            }
    except Exception:
        pass

    if vid:
        return {
            "id": vid,
            "title": f"YouTube Video ({vid})",
            "link": f"https://www.youtube.com/watch?v={vid}",
            "duration": "0:00",
            "thumbnails": [{"url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}],
        }
    return None


async def _search_many(query: str, limit: int = 10) -> list[dict]:
    try:
        s = VideosSearch(query, limit=limit)
        res = await s.next()
        items = res.get("result", [])
        out = []
        for r in items:
            if not r.get("id"):
                continue
            thumb = (
                r["thumbnails"][0]["url"].split("?")[0]
                if r.get("thumbnails")
                else f"https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg"
            )
            out.append({
                "id": r["id"],
                "title": r.get("title", ""),
                "link": r.get("link", f"https://www.youtube.com/watch?v={r['id']}"),
                "duration": r.get("duration", "0:00"),
                "thumbnails": [{"url": thumb}],
            })
        if out:
            return out
    except Exception:
        pass

    vercel_results = await _search_vercel(query, limit=limit)
    if vercel_results:
        return vercel_results

    return []


async def download_media(video_id: str, is_video: bool = False) -> str:
    if not API_KEY or API_KEY == "YOUR_API_KEY":
        print("[Yuki API] Error: API_KEY is not set in environment or config.")
        raise RuntimeError("API_KEY missing. Please set MEOW_API_KEY in .env or get from @MeowApiRobot")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ext = "mp4" if is_video else "mp3"
    req_type = "video" if is_video else "audio"
    out_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        return out_path

    session = await get_session()
    stream_url = f"{API_URL}/stream/{video_id}?key={API_KEY}&type={req_type}&quality=360"

    tmp_path = f"{out_path}.tmp.{random.randint(1000, 9999)}"
    try:
        async with session.get(stream_url) as resp:
            if resp.status == 200:
                with open(tmp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        f.write(chunk)

                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 10000:
                    os.replace(tmp_path, out_path)
                    return out_path
            elif resp.status == 401:
                raise RuntimeError("Invalid API_KEY. Please get a valid key from @MeowApiRobot")
    except Exception as e:
        print(f"[Yuki API] Stream error for {video_id}: {e}")
        raise
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        return out_path
    raise RuntimeError(f"Yuki API download failed for {video_id}")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://www.youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        vid = _extract_video_id(link) if not videoid else link
        return bool(vid)

    async def url(self, message_or_text) -> str | None:
        text = message_or_text.text if hasattr(message_or_text, "text") else str(message_or_text)
        vid = _extract_video_id(text)
        return f"https://www.youtube.com/watch?v={vid}" if vid else None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        clean = _clean_link(link)
        r = await _search_one(clean)
        if not r:
            raise RuntimeError(f"No track details found for: {link}")

        title = r["title"]
        dur_str = r["duration"]
        dur_sec = time_to_seconds(dur_str)
        thumb = r["thumbnails"][0]["url"]
        vid = r["id"]
        _cache_thumb(vid, thumb)
        return title, dur_str, dur_sec, thumb, vid

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        r = await _search_one(_clean_link(link))
        return r["title"] if r else ""

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        r = await _search_one(_clean_link(link))
        return r["duration"] if r else "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        if videoid:
            link = self.base + link
        vid = _extract_video_id(link)
        if vid and vid in _thumb_cache:
            return _thumb_cache[vid]
        r = await _search_one(_clean_link(link))
        if r:
            thumb = r["thumbnails"][0]["url"]
            if vid:
                _cache_thumb(vid, thumb)
            return thumb
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        r = await _search_one(_clean_link(link))
        if not r:
            raise RuntimeError(f"No track found for: {link}")
        thumb = r["thumbnails"][0]["url"]
        _cache_thumb(r["id"], thumb)
        return {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r["duration"],
            "thumb": thumb,
        }, r["id"]

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None) -> list[str]:
        if videoid:
            link = self.listbase + link
        clean = _clean_link(link)

        list_id = None
        if "list=" in link:
            m = re.search(r"[?&]list=([0-9A-Za-z_-]+)", link)
            if m:
                list_id = m.group(1)

        targets = [clean]
        if list_id and list_id.startswith("RD"):
            seed_vid = list_id[2:]
            if "_" in seed_vid:
                seed_vid = seed_vid.split("_")[-1]
            elif len(seed_vid) >= 11:
                seed_vid = seed_vid[:11]
            if seed_vid:
                targets.insert(0, f"https://www.youtube.com/watch?v={seed_vid}&list={list_id}")

        try:
            import yt_dlp
            for tgt in targets:
                try:
                    loop = asyncio.get_running_loop()

                    def _extract_pl(url_to_extract):
                        opts = {"extract_flat": True, "quiet": True, "no_warnings": True, "playlistend": limit}
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(url_to_extract, download=False) or {}
                            entries = info.get("entries") or []
                            return [
                                f"https://www.youtube.com/watch?v={e['id']}"
                                for e in entries
                                if e and e.get("id")
                            ]

                    res = await loop.run_in_executor(None, _extract_pl, tgt)
                    if res:
                        return res[:limit]
                except Exception:
                    pass
        except ImportError:
            pass

        try:
            plist = Playlist(clean)
            while plist.hasMore():
                await plist.getNext()
                if len(plist.videos) >= limit:
                    break
            if plist.videos:
                return [v["link"] for v in plist.videos[:limit]]
        except Exception:
            pass
        return []

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        items = await _search_many(_clean_link(link), limit=10)
        if not items:
            raise RuntimeError(f"No search results for: {link}")
        if query_type >= len(items):
            query_type = 0
        r = items[query_type]
        thumb = r["thumbnails"][0]["url"]
        _cache_thumb(r["id"], thumb)
        return r["title"], r["duration"], thumb, r["id"]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        vid = _extract_video_id(link) or (link if videoid else None)
        if not vid:
            return 0, None
        try:
            path = await download_media(vid, is_video=True)
            return 1, path
        except Exception as e:
            print(f"[video] Error: {e}")
            return 0, None

    async def is_live(self, link: str, videoid: Union[bool, str] = None) -> bool:
        return False

    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> tuple[str, bool]:
        is_vid = bool(video or songvideo)
        vid = _extract_video_id(link) or link
        path = await download_media(vid, is_video=is_vid)
        return path, True

    async def related(self, vidid: str, limit: int = 10, chat_id: int = None) -> list[dict]:
        mix_url = f"https://www.youtube.com/watch?v={vidid}&list=RD{vidid}"
        candidates = []
        try:
            import yt_dlp
            loop = asyncio.get_running_loop()

            def _get_mix():
                opts = {"extract_flat": True, "quiet": True, "no_warnings": True, "playlistend": limit + 5}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(mix_url, download=False) or {}
                    return [
                        {
                            "vidid": e["id"],
                            "title": e.get("title", ""),
                            "duration": str(e.get("duration", "")),
                            "link": f"https://www.youtube.com/watch?v={e['id']}",
                            "thumbnail": f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg",
                        }
                        for e in (info.get("entries") or [])
                        if e and e.get("id") and e.get("id") != vidid
                    ]

            candidates = await loop.run_in_executor(None, _get_mix)
        except Exception:
            pass

        if not candidates:
            candidates = await _search_many(f"songs like {vidid}", limit=limit)

        random.shuffle(candidates)
        if chat_id is not None:
            fresh = [c for c in candidates if not was_played(chat_id, c["vidid"])]
            if fresh:
                candidates = fresh
        return candidates[:limit]

    async def autoplay_next(self, vidid: str, chat_id: int) -> dict | None:
        lock = get_autoplay_lock(chat_id)
        if lock.locked():
            return None
        async with lock:
            tracks = await self.related(vidid, limit=10, chat_id=chat_id)
            if not tracks:
                return None
            nxt = tracks[0]
            mark_played(chat_id, nxt["vidid"])
            asyncio.create_task(download_media(nxt["vidid"], is_video=False))
            return nxt


YouTube = YouTubeAPI()


async def download_song(link: str) -> str:
    vid = _extract_video_id(link) or link
    return await download_media(vid, is_video=False)


async def download_video(link: str) -> str:
    vid = _extract_video_id(link) or link
    return await download_media(vid, is_video=True)
