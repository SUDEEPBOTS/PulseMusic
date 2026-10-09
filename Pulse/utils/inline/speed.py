# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ButtonStyle


def speed_markup(_, chat_id):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🕒 0.5x",
                    callback_data=f"SpeedUP {chat_id}|0.5",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
                InlineKeyboardButton(
                    text="🕓 0.75x",
                    callback_data=f"SpeedUP {chat_id}|0.75",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            ],
            [
                InlineKeyboardButton(
                    text=_["P_B_4"],
                    callback_data=f"SpeedUP {chat_id}|1.0",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            ],
            [
                InlineKeyboardButton(
                    text="🕤 1.5x",
                    callback_data=f"SpeedUP {chat_id}|1.5",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
                InlineKeyboardButton(
                    text="🕛 2.0x",
                    callback_data=f"SpeedUP {chat_id}|2.0",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            ],
            [
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            ],
        ]
    )
    return upl
