import random
import os
import asyncio

from datetime import datetime, timezone, timedelta
import time
from dotenv import load_dotenv, set_key

from discord import ActionRow, Intents, Embed, Color, Interaction, SelectOption
from discord import app_commands
from discord.enums import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View, Select, button
from discord.reaction import Reaction
from discord.member import Member
from discord.message import Message
import requests
from math import ceil
from emojis import Emoji
from exceptions import InsufficientBalanceException, NoGamblerException
import embed_messages
import game
from database import Gambler, Item
import settings
import database

MARKET_CHANNEL_ID = 1324163837880045739

# ---------------------------- BUTTON CLASSES ---------------------------- #
class MarketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BringMyInventoryButton())

class BringMyInventoryButton(Button):
    def __init__(self):
        super().__init__(label="Bring My Inventory", style=ButtonStyle.primary, emoji="🧮")

    async def callback(self, interaction: Interaction):
        try:
            gambler: Gambler = database.get_gambler_by_id(interaction.user.id)
        except NoGamblerException:
            await interaction.response.send_message(
                "You are not registered as a gambler yet! Click on the `🆕 Register` button in the #roulette channel to start playing.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Refreshing...", delete_after=3)
        database.refresh_user_items(gambler.id)
        items = database.get_items_by_gambler(gambler)
        items = [item for item in items if item.buff_price]
        if not items:
            await interaction.followup.send("You have no items in your inventory.", ephemeral=True)
            return

        item_per_page = 10
        items.sort(reverse=True)
        embeds_list = embed_messages.show_items(interaction, items, item_per_page)
        pages = len(embeds_list)

        def get_select_options(page_num=0):
            return [
                SelectOption(
                    label=f"{item.name} (${item.buff_price})",
                    value=str(item.id),
                    description=f"${item.buff_price}"
                )
                for item in items[page_num*item_per_page:(page_num+1)*item_per_page]
            ]

        class ItemSelectMenu(Select):
            def __init__(self):
                super().__init__(
                    placeholder=f"Select an item to deposit... (Page 1/{pages})",
                    options=get_select_options(0),
                    min_values=1,
                    max_values=1,
                )

            def changePage(self, new_page_num:int):
                self.placeholder = f"Select an item to deposit... (Page {new_page_num+1}/{pages})"
                self.options = get_select_options(new_page_num)

            async def callback(self, select_interaction: Interaction):
                selected_item_id = int(self.values[0])
                selected_item = next(item for item in items if item.id == selected_item_id)
                await select_interaction.response.send_message(
                    f"You selected {selected_item.name} for deposit. You will get ${selected_item.buff_price}", ephemeral=True, delete_after=5)
                # Add deposit logic here

        class PaginatedView(View):
            def __init__(self):
                super().__init__(timeout=180)
                self.current_page = 0
                self.previous_button = Button(label="Previous", style=ButtonStyle.secondary)
                self.next_button = Button(label="Next", style=ButtonStyle.secondary)
                self.close_button = Button(label="Close", style=ButtonStyle.danger)
                self.dropdown = ItemSelectMenu()

                self.previous_button.callback = self.previous_button_callback
                self.next_button.callback = self.next_button_callback
                self.close_button.callback = self.close_button_callback

                self.update_buttons()
                self.add_item(self.previous_button)
                self.add_item(self.next_button)
                self.add_item(self.close_button)
                self.add_item(self.dropdown)

            def update_buttons(self):
                self.previous_button.disabled = self.current_page == 0
                self.next_button.disabled = self.current_page == pages - 1

            def update_dropdown(self):
                self.remove_item(self.dropdown)
                self.dropdown = ItemSelectMenu()
                self.dropdown.changePage(self.current_page)
                self.add_item(self.dropdown)

            async def previous_button_callback(self, interaction: Interaction):
                if self.current_page > 0:
                    self.current_page -= 1
                    self.update_buttons()
                    self.update_dropdown()
                    await interaction.response.edit_message(
                        embeds=embeds_list[self.current_page], view=self)

            async def next_button_callback(self, interaction: Interaction):
                if self.current_page < pages - 1:
                    self.current_page += 1
                    self.update_buttons()
                    self.update_dropdown()
                    await interaction.response.edit_message(
                        embeds=embeds_list[self.current_page], view=self)

            async def close_button_callback(self, interaction: Interaction):
                await interaction.response.edit_message(content="Inventory selection closed.", view=None, embeds=[], delete_after=3)


        view = PaginatedView()
        await interaction.followup.send(embeds=embeds_list[0], view=view, ephemeral=True)

def setup_marketplace():
    return MarketView()
