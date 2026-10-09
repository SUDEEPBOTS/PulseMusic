# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

import config
from Pulse.misc import db
from typing import Union
from config import OWNER_ID
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ButtonStyle


def queue_markup(
    _,
    DURATION,
    CPLAY,
    videoid,
    played: Union[bool, int] = None,
    dur: Union[bool, int] = None,
):
    not_dur = [
        [
            InlineKeyboardButton(
                text=_["QU_B_1"],
                callback_data=f"GetQueued {CPLAY}|{videoid}",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
        ]
    ]
    dur = [
        [
            InlineKeyboardButton(
                text=_["QU_B_2"].format(played, dur),
                callback_data="GetTimer",
                style=ButtonStyle.PRIMARY,
                icon_custom_emoji_id="5397733426654626788"
            )
        ],
        [
            InlineKeyboardButton(
                text=_["QU_B_1"],
                callback_data=f"GetQueued {CPLAY}|{videoid}",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
        ],
    ]
    upl = InlineKeyboardMarkup(not_dur if DURATION == "Unknown" else dur)
    return upl


def queue_back_markup(_, CPLAY):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"],
                    callback_data=f"queue_back_timer {CPLAY}",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close",
                    style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788"),
            ]
        ]
    )
    return upl



def aq_markup(_, chat_id):
    queue_text = "No song in queue"

    # Agar queue me ek se jyada song hai (0 = current, baaki = queue)
    if chat_id in db and len(db[chat_id]) > 1:
        last_index = len(db[chat_id]) - 1   # last added song ka index
        track = db[chat_id][last_index]
        title = track["title"]
        queue_text = f"Next :- {last_index}. {title[:15]}"

    buttons = [
        [
            InlineKeyboardButton(
                text=queue_text,
                callback_data=f"ADMIN Skip|{chat_id}"
            , style=ButtonStyle.PRIMARY, icon_custom_emoji_id="5397733426654626788")
        ]
    ]
    return buttons
