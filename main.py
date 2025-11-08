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
from database import Gambler, Round, Bet
import database
from marketplace import setup_marketplace, MARKET_CHANNEL_ID

ROULETTE_MSG:Message = None
ROULETTE_EMBED:Embed = None
BETS_TABLE_MSG_STR:str = None
TIMER_MSG_STR:str = None
GAME_BUTTONS:View = None
LEADERBOARD_MSG:Message = None
LEADERBOARD:Embed = None

# Bot setup
load_dotenv()
app_id = os.getenv("APP_ID")
token = os.getenv("DC_BOT_TOKEN")
public_key = os.getenv("PUBLIC_KEY")

# Initialize bot
intents = Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------- COMMANDS ---------------------------- #
@bot.tree.command(name="setup", description="Setup the roulette game.")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: Interaction):
    await setup_helper(interaction)
    
@bot.tree.command(name="start", description="Start the roulette game.")
@app_commands.default_permissions(administrator=True)
async def start(interaction: Interaction):
    await interaction.response.send_message("Starting the game..!", ephemeral=True, delete_after=1)
    bot.loop.create_task(start_roulette_loop())

@bot.tree.command(name="bet_amount", description="Start the roulette game.")
async def set_bet_amount(interaction: Interaction, bet_amount:float):
    try:
        database.set_gambler_bet_amount(interaction.user.id, bet_amount)
        await interaction.response.send_message(f"Your bet amount is: **${bet_amount}**", ephemeral=True)
    except NoGamblerException:
        await interaction.response.send_message("You are not registered as a gambler yet! Click on the `🆕 Register` button to start playing.", ephemeral=True)
        return
    except Exception as e:
        await interaction.response.send_message(f"Error while setting up your bet amount: {e}", ephemeral=True)

@bot.tree.command(name="set_bet_period", description="Set the betting time in seconds.")
@app_commands.default_permissions(administrator=True)
async def set_bet_time(interaction: Interaction, bet_duration: int):
    game.setBetDuration(bet_duration)
    await interaction.response.send_message(f"Betting period is set to {game.getBetDuration()} seconds.", ephemeral=True)

@bot.tree.command(name="trade_url", description="Update your trade url.")
async def set_trade_url(interaction: Interaction, trade_url:str):
    updated_url = database.set_trade_url(interaction.user.id, trade_url)
    await interaction.response.send_message(f"Your trade URL is set to: {updated_url}", ephemeral=True, delete_after=3)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"Bot is ready. Logged in as {bot.user}")
        current_round = database.get_last_round()
        if not current_round:
            database.create_round(game.getNewRoundID(), game.getNewRoundResult())
    except Exception as e:
        print(f"Error syncing commands: {e}")


# ---------------------------- HELPER FUNCTIONS ---------------------------- #
def update_bets_table(bets: list[Bet] = None, isRoundEnd: bool = False) -> str:
    if not bets:
        bets = []

    current_round = database.get_last_round()
    round_result = current_round.result_color
    bets_table = {game.Results.GREEN: [], game.Results.RED: [], game.Results.BLACK: []}

    # Define headers based on round end or not
    if not isRoundEnd:
        headers = [
            "🟥 Red 2x", 
            "🟩 Green 14x", 
            "⬛ Black 2x"
        ]
        table_header = (f" {headers[0].center(16)} {headers[1].center(16)} {headers[2].center(16)}")
    else:
        headers = (
            ["🟥 Red 2x 💲", "🟩 Green 14x ❌", "⬛ Black 2x ❌"] if round_result == game.Results.RED else
            ["🟥 Red 2x ❌", "🟩 Green 14x 💲", "⬛ Black 2x ❌"] if round_result == game.Results.GREEN else
            ["🟥 Red 2x ❌", "🟩 Green 14x ❌", "⬛ Black 2x 💲"] if round_result == game.Results.BLACK else None
        )
        table_header = (f"{headers[0].center(15)} {headers[1].center(15)}{headers[2].center(15)}")

    # Process bets and fill bets_table
    for bet in bets:
        gambler: Gambler = database.get_gambler_by_id(bet.gambler_id)
        bet_on = bet.bet_on
        if isRoundEnd:
            reward = (
                bet.amount * game.RED_MULTIPLIER if bet_on == game.Results.RED else
                bet.amount * game.GREEN_MULTIPLIER if bet_on == game.Results.GREEN else
                bet.amount * game.BLACK_MULTIPLIER if bet_on == game.Results.BLACK else None
            )
            reward = round(reward, 2)

            name = f"{gambler.name}".ljust(8)
            bet_val = f"+{reward}".center(6) if round_result==bet.bet_on else f"-{bet.amount}".center(6)
            
        else:
            name = f"{gambler.name}".ljust(9)
            bet_val = f"{bet.amount}".center(5)

        bets_table[bet_on].append(f"{name[:8]} {bet_val}")

    # Generate the table header
    table_divider = f"+{'-' * 17}+{'-' * 17}+{'-' * 17}+"

    # Generate table rows
    table_rows = []
    max_rows = max(5,
        len(bets_table[game.Results.GREEN]),
        len(bets_table[game.Results.RED]),
        len(bets_table[game.Results.BLACK])
    )
    min_rows = min(max_rows, 8)  # Limit rows for display

    for i in range(min_rows):
        green = bets_table[game.Results.GREEN][i] if i < len(bets_table[game.Results.GREEN]) else ""
        red = bets_table[game.Results.RED][i] if i < len(bets_table[game.Results.RED]) else ""
        black = bets_table[game.Results.BLACK][i] if i < len(bets_table[game.Results.BLACK]) else ""
        table_rows.append(
            f"| {red.center(15)} | {green.center(15)} | {black.center(15)} |"
        )

    # Combine all parts into the final table
    table = f"{table_divider}\n{table_header}\n{table_divider}\n" + "\n".join(table_rows) + f"\n{table_divider}"
    content = f"```diff\n{table}\n```"
    return content

async def setup_helper(interaction:Interaction=None):
    global ROULETTE_MSG
    global ROULETTE_EMBED
    global GAME_BUTTONS
    global BETS_TABLE_MSG_STR
    global LEADERBOARD
    global LEADERBOARD_MSG

    LEADERBOARD = embed_messages.leaderboard()
    ROULETTE_EMBED = embed_messages.setup_roulette()
    TIMER_MSG_STR = f"Place your bets! ⏳ **{game.BETTING_DURATION}s** remaining\n{Emoji.PROGRESS_BAR.START}{game.PROGRESS_BAR}{Emoji.PROGRESS_BAR.BEFORE_END}"
    BETS_TABLE_MSG_STR = update_bets_table()
    GAME_BUTTONS = GameView()
    
    ROULETTE_EMBED.add_field(name="Time", value=TIMER_MSG_STR, inline=False)
    ROULETTE_EMBED.add_field(name="Bets", value=BETS_TABLE_MSG_STR, inline=False)

    if interaction:
        LEADERBOARD_MSG = await interaction.channel.send(embed=LEADERBOARD)
        ROULETTE_MSG = await interaction.channel.send(embed=ROULETTE_EMBED, view=GAME_BUTTONS)
        await set_button_states(False)
        await interaction.response.send_message("Success", delete_after=1)
    else:
        channel_id = 1323057839782101002
        channel = await bot.fetch_channel(channel_id)
        LEADERBOARD_MSG = await channel.send(embed=LEADERBOARD)
        ROULETTE_MSG = await channel.send(embed=ROULETTE_EMBED, view=GAME_BUTTONS)
        await set_button_states(False)

    marketplace_view = setup_marketplace()
    MARKET_CHANNEL = await bot.fetch_channel(MARKET_CHANNEL_ID)
    await MARKET_CHANNEL.send(view=marketplace_view)
    

async def restart():
    global ROULETTE_MSG
    global LEADERBOARD_MSG

    await ROULETTE_MSG.delete(delay=1)
    await LEADERBOARD_MSG.delete(delay=1)

    await setup_helper()


async def set_button_states(state:bool=True):
    global GAME_BUTTONS
    if GAME_BUTTONS:
        for item in GAME_BUTTONS.children:
            if isinstance(item, BetButton):
                item.disabled = not(state)  # Disable the button
        await ROULETTE_MSG.edit(view=GAME_BUTTONS)  # Update the message with the disabled buttons

async def start_roulette_loop():
    while True:
        # ----------------- CONSTANTS
        global ROULETTE_MSG
        global TIMER_MSG_STR
        global BETS_TABLE_MSG_STR
        global LEADERBOARD_MSG
        global LEADERBOARD

        # ----------------- NEED TO RESTART ?
        round_count = database.get_round_count()
        if round_count % 50 == 49:
            await restart()
        # ----------------- UPDATE THE LEADERBOARD
        LEADERBOARD = embed_messages.leaderboard()
        await  LEADERBOARD_MSG.edit(embed=LEADERBOARD)
        
        # ----------------- CREATE A NEW ROUND
        last_round: Round = database.get_last_round()
        current_round: Round = database.create_round(game.getNewRoundID(), game.getNewRoundResult())

        # ----------------- EMBED COLOUR TO DEFAULT
        ROULETTE_EMBED.color = Color.gold()
        await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)

        # ----------------- CLEAR THE BETS TABLE
        BETS_TABLE_MSG_STR = update_bets_table()
        ROULETTE_EMBED.set_field_at(index=4, name="Bets", value=BETS_TABLE_MSG_STR, inline=False)
        await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)

        # ----------------- ENABLE BET GAME_BUTTONS
        await set_button_states(True)

        # ----------------- START THE TIMER FOR BETTING
        TIMER_MSG_STR = f"Place your bets! ⏳ **{game.BETTING_DURATION}s** remaining\n{Emoji.PROGRESS_BAR.START}{game.PROGRESS_BAR}{Emoji.PROGRESS_BAR.BEFORE_END}"
        ROULETTE_EMBED.set_field_at(index=3, name="Time", value=TIMER_MSG_STR, inline=False)
        await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)
        for elapsed in range(1, game.BETTING_DURATION+1):
            await asyncio.sleep(1)
            progress = int((elapsed / game.BETTING_DURATION) * game.PROGRESS_BAR_LENGTH)
            remaining_time = game.BETTING_DURATION - elapsed
            game.PROGRESS_BAR = Emoji.PROGRESS_BAR.BEHIND_EDGE*progress + Emoji.PROGRESS_BAR.EDGE + Emoji.PROGRESS_BAR.FRONT_EDGE*(game.PROGRESS_BAR_LENGTH - progress)

            TIMER_MSG_STR = f"Place your bets! ⏳ **{remaining_time}s** remaining\n{Emoji.PROGRESS_BAR.START}{game.PROGRESS_BAR}{Emoji.PROGRESS_BAR.BEFORE_END}"
            ROULETTE_EMBED.set_field_at(index=3, name="Time", value=TIMER_MSG_STR, inline=False)
            await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)
            
        # ----------------- BETS OVER! DISABLE BET GAME_BUTTONS
        await set_button_states(False)

        TIMER_MSG_STR = f"Betting is now closed! 🚫\n{Emoji.PROGRESS_BAR.START}{Emoji.PROGRESS_BAR.BEHIND_EDGE * game.PROGRESS_BAR_LENGTH}{Emoji.PROGRESS_BAR.AFTER_END}"
        ROULETTE_EMBED.set_field_at(index=3, name="Time", value=TIMER_MSG_STR, inline=False)
        await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)
        
        # ----------------- BETS OVER! ANIMATE THE ROULETTE
        await animate_roulette(last_round.result_num, current_round.result_num)

        # ----------------- PREVIOUS ROLLS AND EMBED COLOR
        last_rounds:list[Round] = database.get_last_x_rounds(8)
        last_rolls = [Emoji.roulette_values.get(round.result_num) for round in last_rounds]
        ROULETTE_EMBED.set_field_at(index=0, name="Previous Rolls", value=" ".join(last_rolls), inline=False)
        color = (Color.red() if current_round.result_color == game.Results.RED else
            Color.green() if current_round.result_color == game.Results.GREEN else
            Color.darker_grey() if current_round.result_color == game.Results.BLACK else Color.gold())
        ROULETTE_EMBED.color = color
        await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)

        # ----------------- SHOW THE RESULTS ON THE BET TABLE
        bets = database.get_all_bets_by_round_id(current_round.id)
        BETS_TABLE_MSG_STR = update_bets_table(bets, isRoundEnd=True)
        ROULETTE_EMBED.set_field_at(index=4, name="Bets", value=BETS_TABLE_MSG_STR, inline=False)
        await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)

        # ----------------- PROCESS RESULTS TO DATABASE
        database.process_bets()

        # ----------------- PAUSE BETWEEN THE ROUNDS
        await asyncio.sleep(5)

async def animate_roulette(last_round_result: int, current_round_result: int):
    global ROULETTE_MSG
    global ROULETTE_EMBED

    extra_rotations = random.randint(1, 2)
    sequence = game.ROULETTE_SEQUENCE
    sequence_length = len(sequence)
    start_index = sequence.index(last_round_result)
    final_index = sequence.index(current_round_result)

    # Calculate the total distance with extra rotations
    forward_distance = (final_index - start_index) % sequence_length
    total_distance = forward_distance + (sequence_length * extra_rotations)

    def easing(t, total_frames):
        t /= total_frames
        return 1 - (1 - t) ** 2

    positions = []
    for frame in range(game.TOTAL_FRAMES):
        progress = easing(frame, game.TOTAL_FRAMES)
        current_position = round(start_index + progress * total_distance) % sequence_length
        positions.append(current_position)

    # Ensure the final position matches the target
    positions[-1] = final_index

    # Animation
    for frame, start_index in enumerate(positions):
        if frame % game.FRAME_RATE == 0 or frame == len(positions) - 1:
            window = game.set_sequence(sequence[start_index])
            roulette_sequence = [Emoji.roulette_values.get(num) for num in window]
            ROULETTE_EMBED.set_field_at(index=1, name="Roulette", value=" ".join(roulette_sequence), inline=False)
            await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)
        await asyncio.sleep(game.SLEEP_DURATION)


# ---------------------------- BUTTON CLASSES ---------------------------- #
class GameView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BetButton(label="RED", bet_on=game.Results.RED, style=ButtonStyle.red))
        self.add_item(BetButton(label="GREEN", bet_on=game.Results.GREEN, style=ButtonStyle.green))
        self.add_item(BetButton(label="BLACK", bet_on=game.Results.BLACK, style=ButtonStyle.grey))
        self.add_item(MyStatsButton())
        self.add_item(RegisterButton())
        self.add_item(DailyRewardButton())


class BetButton(Button):
    def __init__(self, label, bet_on, style, emoji=None):
        if emoji:
            super().__init__(label=label, style=style, emoji=emoji)
        else:
            super().__init__(label=label, style=style)
        self.bet_on = bet_on

    async def callback(self, interaction: Interaction):
        global ROULETTE_MSG
        global BETS_TABLE_MSG_STR

        # Fetch the current round
        current_round:Round = database.get_last_round()
        if not current_round:
            await interaction.response.send_message("No active round found.", ephemeral=True)
            return

        # Fetch or create the gambler
        try:
            gambler:Gambler = database.get_gambler_by_id(interaction.user.id)
        except NoGamblerException:
            await interaction.response.send_message("You are not registered as a gambler yet! Click on the `🆕 Register` button to start playing.", ephemeral=True)
            return

        # Place the bet
        bet_amount = gambler.default_bet_amount
        try:
            bets = database.get_all_bets_by_round_id(current_round.id)
            for bet in bets:
                if gambler.id == bet.gambler_id:
                    await interaction.response.send_message(
                        f"You have already made your bet on **{bet.bet_on}** with **${bet.amount}**", ephemeral=True, delete_after=2)
                    return

            new_bet:Bet = database.create_bet(gambler, current_round, bet_amount, self.bet_on)
            bets.append(new_bet)
            BETS_TABLE_MSG_STR = update_bets_table(bets, isRoundEnd=False)
            ROULETTE_EMBED.set_field_at(index=4, name="Bets", value=BETS_TABLE_MSG_STR, inline=False)
            await ROULETTE_MSG.edit(embed=ROULETTE_EMBED)
            database.update_gambler_balance(gambler.id, -bet_amount)
            await interaction.response.send_message(f"Bet placed on **{self.bet_on}** for **${bet_amount}**!\nYour updated balance: **${gambler.balance}**", ephemeral=True, delete_after=2)
        except InsufficientBalanceException as e:
            await interaction.response.send_message(f"{e}", ephemeral=True)
        except Exception as e:
            print(f"Error processing bet: {e}")
            await interaction.response.send_message("There was an error placing your bet.", ephemeral=True, delete_after=2)

class MyStatsButton(Button):
    def __init__(self):
        super().__init__(label="My Stats", style=ButtonStyle.primary, emoji="🧮")

    async def callback(self, interaction: Interaction):
        try:
            gambler = database.get_gambler_by_id(interaction.user.id)
        except NoGamblerException:
            await interaction.response.send_message("You are not registered as a gambler yet! Click on the `🆕 Register` button to start playing.", ephemeral=True)
            return
        
        stats_embed = embed_messages.gambler_statistics(interaction, gambler)
        await interaction.response.send_message(embed=stats_embed, ephemeral=True)

class RegisterButton(Button):
    def __init__(self):
        super().__init__(label="Register", style=ButtonStyle.primary, emoji="🆕")

    async def callback(self, interaction: Interaction):
        try:
            gambler = database.get_gambler_by_id(interaction.user.id)
            await interaction.response.send_message(f"You are already registered as **{gambler.name}** with **${gambler.balance:.2f}** credit.", ephemeral=True)
        except NoGamblerException:
            created_gambler: Gambler = database.create_gambler(interaction.user.id, interaction.user.global_name)
            if not created_gambler:
                await interaction.response.send_message("Error during registration. Please try again later.", ephemeral=True)
                return
            # ----------------- UPDATE THE LEADERBOARD
            LEADERBOARD = embed_messages.leaderboard()
            await  LEADERBOARD_MSG.edit(embed=LEADERBOARD)
            await interaction.response.send_message(f"You have been registered as **{interaction.user.global_name}** with **${created_gambler.balance:.2f}** credit.", ephemeral=True)

class DailyRewardButton(Button):
    def __init__(self):
        super().__init__(label="Claim Daily Reward", style=ButtonStyle.primary, emoji="🎁")

    async def callback(self, interaction: Interaction):
        try:
            gambler = database.get_gambler_by_id(interaction.user.id)
        except NoGamblerException as e:
            await interaction.response.send_message("You are not registered as a gambler yet! Click on the `🆕 Register` button to start playing.", ephemeral=True)
            return

        cooldown:datetime = gambler.daily_cooldown
        if datetime.now(timezone.utc) > cooldown.astimezone(timezone.utc):
            database.update_gambler_balance(interaction.user.id, gambler.daily)
            database.update_daily_cooldown(interaction.user.id)
            await interaction.response.send_message(embed=embed_messages.daily_claimed_success(interaction, gambler), ephemeral=True, delete_after=3)
        else:
            await interaction.response.send_message(embed=embed_messages.daily_claimed_fail(interaction, gambler), ephemeral=True, delete_after=3)


bot.run(token)