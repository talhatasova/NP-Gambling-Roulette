import random
import os
import asyncio

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from discord import ActionRow, Intents, Embed, Color, Interaction
from discord import app_commands
from discord.enums import ButtonStyle
from discord.ext import commands
from discord.ui import Button, View
from discord.reaction import Reaction
from discord.member import Member
from discord.message import Message

from emojis import Emoji
from exceptions import InsufficientBalanceException, NoGamblerException
import embed_messages
import game
from database import Gambler, Item
import database

MARKET_CHANNEL_ID = 1324163837880045739

# ---------------------------- BUTTON CLASSES ---------------------------- #
class MarketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BringMyInventoryButton())

class BringMyInventoryButton(Button):
    def __init__(self):
        super().__init__(label="Update My Inventory", style=ButtonStyle.primary, emoji="🧮")

    async def callback(self, interaction: Interaction):
        try:
            gambler:Gambler = database.get_gambler_by_id(interaction.user.id)
        except NoGamblerException:
            await interaction.response.send_message("You are not registered as a gambler yet! Click on the `🆕 Register` button in the #roulette channel to start playing.", ephemeral=True)
            return
        
        database.refresh_user_items(gambler.id)
        items = database.get_items_by_gambler(gambler)
        items_embed = embed_messages.show_items(interaction, items)
        if interaction.channel_id == MARKET_CHANNEL_ID:
            await interaction.channel.send(embed=items_embed)

def setup_marketplace():
    return MarketView()
