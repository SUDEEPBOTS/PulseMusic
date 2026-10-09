# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMember
import logging
from Pulse import app

logging.basicConfig(level=logging.INFO)

@app.on_message(filters.video_chat_started)
async def video_chat_started(client, message: Message):
    chat = message.chat
    await message.reply(
        f"🎥 Video chat has started in {chat.title}!\n\nJoin us now for a fun time together! 😄"
    )

@app.on_message(filters.video_chat_ended)
async def video_chat_ended(client, message: Message):
    chat = message.chat
    await message.reply(
        f"🚫 Video chat has ended in {chat.title}.\n\nThank you for joining! See you next time! 👋"
    )
