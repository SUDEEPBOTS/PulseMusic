# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

import math

from pyrogram.types import InlineKeyboardButton
from pyrogram.enums import ButtonStyle
from config import SUPPORT_CHANNEL, SUPPORT_CHAT
from Pulse.utils.formatters import time_to_seconds

def stream_markup_timer(_, chat_id, played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100
    umm = math.floor(percentage)
    if 0 < umm <= 10:
        bar = "▰▱▱▱▱▱▱▱▱▱"
    elif 10 < umm < 20:
        bar = "▰▰▱▱▱▱▱▱▱▱"
    elif 20 <= umm < 30:
        bar = "▰▰▰▱▱▱▱▱▱▱"
    elif 30 <= umm < 40:
        bar = "▰▰▰▰▱▱▱▱▱▱"
    elif 40 <= umm < 50:
        bar = "▰▰▰▰▰▱▱▱▱▱"
    elif 50 <= umm < 60:
        bar = "▰▰▰▰▰▰▱▱▱▱"
    elif 60 <= umm < 70:
        bar = "▰▰▰▰▰▰▰▱▱▱"
    elif 70 <= umm < 80:
        bar = "▰▰▰▰▰▰▰▰▱▱"
    elif 80 <= umm < 95:
        bar = "▰▰▰▰▰▰▰▰▰▱"
    else:
        bar = "▰▰▰▰▰▰▰▰▰▰"

    buttons = [
        # Row 1: Progress bar with timing
        [
            InlineKeyboardButton(
                text=f"{played.lower()}  {bar}  {dur.lower()}",
                callback_data="GetTimer"
            )
        ],
        # Row 2: Three new buttons (Backward, Download, Forward)
        [
            InlineKeyboardButton(text="⪻  -30s", callback_data=f"SEEKBACKWARD|{chat_id}|30", style=ButtonStyle.DEFAULT),
            InlineKeyboardButton(text="📥", callback_data=f"DOWNLOAD|{chat_id}", style=ButtonStyle.DEFAULT),
            InlineKeyboardButton(text="+30s  ⪼", callback_data=f"SEEKFORWARD|{chat_id}|30", style=ButtonStyle.DEFAULT),
        ],
        # Row 3: Main control buttons
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id="5397733426654626788"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6255793039705377676"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6152069270269334526"),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}", style=ButtonStyle.DANGER),
        ],
        # Row 4: Autoplay toggle
        [
            InlineKeyboardButton(text="𝐀ᴜᴛᴏᴘʟᴀʏ ➜ " + ("𝐎ɴ" if getattr(__import__("Pulse").YouTube, "is_autoplay_on", lambda x: False)(chat_id) else "𝐎ғғ"), callback_data=f"Autoplay_Toggle|{chat_id}", style=ButtonStyle.DEFAULT)
        ],
        # Row 5: Support & Update
        [
            InlineKeyboardButton(text="✰ ᴜᴘᴅᴧᴛᴇ ✰", url=SUPPORT_CHANNEL, style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="✰ sᴜᴘᴘᴏꝛᴛ ✰", url=SUPPORT_CHAT, style=ButtonStyle.PRIMARY)
        ],
        # Row 6: Close button
        [
            InlineKeyboardButton(text=_["CLOSE_BUTTON"].lower(), callback_data="close", style=ButtonStyle.DANGER)
        ]
    ]
    return buttons


def stream_markup(_, chat_id):
    buttons = [
        # Row 1: Seek / Download
        [
            InlineKeyboardButton(text="⪻  -30s", callback_data=f"SEEKBACKWARD|{chat_id}|30", style=ButtonStyle.DEFAULT),
            InlineKeyboardButton(text="📥", callback_data=f"DOWNLOAD|{chat_id}", style=ButtonStyle.DEFAULT),
            InlineKeyboardButton(text="+30s  ⪼", callback_data=f"SEEKFORWARD|{chat_id}|30", style=ButtonStyle.DEFAULT),
        ],
        # Row 2: Controls
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}", style=ButtonStyle.SUCCESS, icon_custom_emoji_id="5397733426654626788"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6255793039705377676"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6152069270269334526"),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}", style=ButtonStyle.DANGER),
        ],
        # Row 3: Autoplay
        [
            InlineKeyboardButton(text="𝐀ᴜᴛᴏᴘʟᴀʏ ➜ " + ("𝐎ɴ" if getattr(__import__("Pulse").YouTube, "is_autoplay_on", lambda x: False)(chat_id) else "𝐎ғғ"), callback_data=f"Autoplay_Toggle|{chat_id}", style=ButtonStyle.DEFAULT)
        ],
        # Row 4: Support
        [
            InlineKeyboardButton(text="✰ ᴜᴘᴅᴧᴛᴇ ✰", url=SUPPORT_CHANNEL, style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="✰ sᴜᴘᴘᴏꝛᴛ ✰", url=SUPPORT_CHAT, style=ButtonStyle.PRIMARY)
        ],
        # Row 5: Close
        [
            InlineKeyboardButton(text=_["CLOSE_BUTTON"].lower(), callback_data="close", style=ButtonStyle.DANGER)
        ]
    ]
    return buttons


def track_markup(_, videoid, user_id, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            )
        ],
    ]
    return buttons
def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"EraPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"EraPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    query = f"{query[:20]}"
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {query}|{user_id}",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]
    return buttons
