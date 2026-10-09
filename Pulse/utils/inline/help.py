# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

# Email: sudeepgithub@gmail.com

# Importing important modules & bot

from Pulse import app
from typing import Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

#------------------------------------------------------------------------#



from pyrogram.enums import ButtonStyle

# creating first partition of menu

def first_page(_):
    controll_button = [InlineKeyboardButton(text="ʙᴀᴄᴋ ⤶", callback_data="settingsback_helper", style=ButtonStyle.DANGER, icon_custom_emoji_id="6152069270269334526")]
    first_page_menu = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=_["H_B_1"], callback_data="help_callback hb1", style=ButtonStyle.PRIMARY), InlineKeyboardButton(text=_["H_B_2"], callback_data="help_callback hb2", style=ButtonStyle.PRIMARY), InlineKeyboardButton(text=_["H_B_3"], callback_data="help_callback hb3", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text=_["H_B_4"], callback_data="help_callback hb4", style=ButtonStyle.SUCCESS), InlineKeyboardButton(text=_["H_B_5"], callback_data="help_callback hb5", style=ButtonStyle.SUCCESS), InlineKeyboardButton(text=_["H_B_6"], callback_data="help_callback hb6", style=ButtonStyle.SUCCESS)],
            [InlineKeyboardButton(text=_["H_B_7"], callback_data="help_callback hb7", style=ButtonStyle.PRIMARY), InlineKeyboardButton(text=_["H_B_8"], callback_data="help_callback hb8", style=ButtonStyle.PRIMARY), InlineKeyboardButton(text=_["H_B_9"], callback_data="help_callback hb9", style=ButtonStyle.PRIMARY)],
            controll_button,
        ]
    )
    return first_page_menu




# creating second partition of menu

def second_page(_):
	controll_button = [InlineKeyboardButton(text="◁", callback_data=f"settings_back_helper_fixed", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6255793039705377676"), InlineKeyboardButton(text="HOME", callback_data=f"settingsback_helper", style=ButtonStyle.SUCCESS, icon_custom_emoji_id="5397733426654626788"), InlineKeyboardButton(text="▷", callback_data=f"settings_back_helper", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6255793039705377676")]
	second_page_menu = InlineKeyboardMarkup(
		[
			[InlineKeyboardButton(text=_["H_B_10"], callback_data="help_callback hb10", style=ButtonStyle.PRIMARY), InlineKeyboardButton(text=_["H_B_11"], callback_data="help_callback hb11", style=ButtonStyle.PRIMARY), InlineKeyboardButton(text=_["H_B_12"], callback_data="help_callback hb12", style=ButtonStyle.PRIMARY)],
			[InlineKeyboardButton(text=_["H_B_13"], callback_data="help_callback hb13", style=ButtonStyle.SUCCESS), InlineKeyboardButton(text=_["H_B_14"], callback_data="help_callback hb14", style=ButtonStyle.SUCCESS), InlineKeyboardButton(text=_["H_B_15"], callback_data="help_callback hb15", style=ButtonStyle.SUCCESS)],
			[InlineKeyboardButton(text=_["H_B_16"], callback_data="help_callback hb16", style=ButtonStyle.PRIMARY)],
			controll_button,
		]
	)
	return second_page_menu


# Just an common button
def help_back_markup(_):
	upl = InlineKeyboardMarkup([[InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data=f"settings_back_helper", style=ButtonStyle.DANGER, icon_custom_emoji_id="6152069270269334526")]])
	return upl


# Ease of access 
def private_help_panel(_):
	buttons = [[InlineKeyboardButton(text=_["S_B_4"], url=f"https://t.me/{app.username}?start=help", style=ButtonStyle.PRIMARY, icon_custom_emoji_id="6152069270269334526")]]
	return buttons



#----------------------------> NOTE <-----------------------------#
"""
Written By Dil.
"""
