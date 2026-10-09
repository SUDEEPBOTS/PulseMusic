# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

import asyncio
from datetime import datetime
from pyrogram.enums import ChatType

import config
from Pulse import app
from Pulse.core.call import Sagar, autoend
from Pulse.utils.database import get_client, is_active_chat, is_autoend

# yaha ek tracker dict banayenge
vc_participants = {}  # {chat_id: set(user_ids)}

async def auto_leave():
    if config.AUTO_LEAVING_ASSISTANT:
        while not await asyncio.sleep(900):
            from Pulse.core.userbot import assistants

            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ]:
                            if (
                                i.chat.id != config.LOGGER_ID
                                and i.chat.id != -1001686672798
                                and i.chat.id != -1001549206010
                            ):
                                if left == 20:
                                    continue
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except:
                                        continue
                except:
                    pass


asyncio.create_task(auto_leave())


async def auto_end():
    while not await asyncio.sleep(5):
        ender = await is_autoend()
        if not ender:
            continue

        for chat_id in autoend:
            timer = autoend.get(chat_id)
            if not timer:
                continue

            # --- VC participants tracker ---
            try:
                call = await app.get_call(chat_id)
                current_users = set(call.participants.keys()) if call else set()
            except:
                current_users = set()

            old_users = vc_participants.get(chat_id, set())

            # naye users (join)
            joined = current_users - old_users
            for user_id in joined:
                try:
                    user = await app.get_users(user_id)
                    await app.send_message(
                        chat_id,
                        f"👤 {user.mention} joined the voice chat."
                    )
                except:
                    continue

            # chhod ke gaye users (leave)
            left = old_users - current_users
            for user_id in left:
                try:
                    user = await app.get_users(user_id)
                    await app.send_message(
                        chat_id,
                        f"👋 {user.mention} left the voice chat."
                    )
                except:
                    continue

            # update tracker
            vc_participants[chat_id] = current_users

            # --- Autoend ka purana system ---
            if datetime.now() > timer:
                if not await is_active_chat(chat_id):
                    autoend[chat_id] = {}
                    continue
                autoend[chat_id] = {}
                try:
                    await Sagar.stop_stream(chat_id)
                except:
                    continue
                try:
                    await app.send_message(
                        chat_id,
                        "» ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʟᴇғᴛ ᴠɪᴅᴇᴏᴄʜᴀᴛ ʙᴇᴄᴀᴜsᴇ ɴᴏ ᴏɴᴇ ᴡᴀs ʟɪsᴛᴇɴɪɴɢ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
                    )
                except:
                    continue


asyncio.create_task(auto_end())
