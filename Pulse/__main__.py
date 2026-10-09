# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from Pulse import LOGGER, app, userbot
from Pulse.core.call import Sagar
from Pulse.misc import sudo
from Pulse.plugins import ALL_MODULES
from Pulse.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    if config.RENDER:
        try:
            import server
            server.keep_alive_ping()
            LOGGER(__name__).info("Web server started for Render keep-alive.")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to start web server: {e}")

    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("Pulse.plugins" + all_module)
    LOGGER("Pulse.plugins").info("sᴜᴄᴄᴇssғᴜʟʟʏ ɪᴍᴘᴏʀᴛᴇᴅ ᴀʟʟ ᴍᴏᴅᴜʟᴇs...")
    await userbot.start()
    await Sagar.start()
    try:
        await Sagar.stream_call("https://te.legra.ph/file/39b302c93da5c457a87e3.mp4")
    except NoActiveGroupCall:
        LOGGER("Pulse").error(
            "Please turn on the Voice Chat in your Logger Group/Channel.\n\nBot is shutting down..."
        )
        exit()
    except:
        pass
    await Sagar.decorators()
    LOGGER("Pulse").info(
        "Pulse Music Bot Started Successfully!"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("Pulse").info("Stopping Pulse Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
