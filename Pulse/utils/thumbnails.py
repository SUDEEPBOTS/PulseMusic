import os
import aiohttp
from config import YOUTUBE_IMG_URL as FAILED

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

async def get_thumb(videoid: str, chat_id: int = None) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}.jpg")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        return cache_path

    thumb_url = f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 1000:
                        with open(cache_path, "wb") as f:
                            f.write(data)
                        return cache_path
    except Exception:
        pass

    return FAILED
