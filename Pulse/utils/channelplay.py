# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

from Pulse import app
from Pulse.utils.database import get_cmode


async def get_channeplayCB(_, command, CallbackQuery):
    if command == "c":
        chat_id = await get_cmode(CallbackQuery.message.chat.id)
        if chat_id is None:
            try:
                return await CallbackQuery.answer(_["setting_7"], show_alert=True)
            except:
                return
        try:
            channel = (await app.get_chat(chat_id)).title
        except:
            try:
                return await CallbackQuery.answer(_["cplay_4"], show_alert=True)
            except:
                return
    else:
        chat_id = CallbackQuery.message.chat.id
        channel = None
    return chat_id, channel
