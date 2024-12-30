import random
import os
import asyncio

from datetime import datetime
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

ROULETTE_MSG:Message = None
BETS_MSG:Message = None
TIMER_MSG:Message = None
BUTTONS:View = None

# Bot setup
load_dotenv()
app_id = os.getenv("APP_ID")
token = os.getenv("DC_BOT_TOKEN")
public_key = os.getenv("PUBLIC_KEY")

# Initialize bot
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def animate_roulette(last_round_result: int, current_round_result: int):
    global ROULETTE_MSG
    extra_rotations = random.randint(1, 2)
    sequence = game.ROULETTE_SEQUENCE
    sequence_length = len(sequence)
    start_index = sequence.index(last_round_result)
    final_index = sequence.index(current_round_result)

    # Calculate the total distance with extra rotations
    forward_distance = (final_index - start_index) % sequence_length
    total_distance = forward_distance + (sequence_length * extra_rotations)

    # Easing function (quadratic ease-out)
    def easing(t, total_frames):
        t /= total_frames
        return 1 - (1 - t) ** 2

    # Generate positions using easing
    positions = []
    for frame in range(game.TOTAL_FRAMES):
        progress = easing(frame, game.TOTAL_FRAMES)
        current_position = round(start_index + progress * total_distance) % sequence_length
        positions.append(current_position)

    # Ensure the final position matches the target
    positions[-1] = final_index
    last_rounds:list[Round] = database.get_last_x_rounds(9)
    last_rolls = [Emoji.roulette_values.get(round.result_num) for round in last_rounds]
    # Animate through positions
    for frame, start_index in enumerate(positions):
        # Throttle updates to approximately 10 per second to avoid rate limit
        if frame % game.FRAME_RATE == 0 or frame == len(positions) - 1:
            window = game.set_sequence(sequence[start_index])
            roulette_sequence = [Emoji.roulette_values.get(num) for num in window]
            roulette_embed = embed_messages.setup_roulette(roulette_sequence, last_rolls[:-1])
            await ROULETTE_MSG.edit(embed=roulette_embed)
        await asyncio.sleep(game.SLEEP_DURATION)

    await asyncio.sleep(1)
    color = (Color.red() if current_round_result in game.RED_INTERVAL else
        Color.green() if current_round_result in game.GREEN_INTERVAL else
        Color.darker_grey() if current_round_result in game.BLACK_INTERVAL else Color.gold())
    result_embed = embed_messages.result_roulette(roulette_sequence, last_rolls[1:], color=color)
    await ROULETTE_MSG.edit(embed=result_embed)
    await asyncio.sleep(2)
    roulette_embed = embed_messages.setup_roulette(roulette_sequence, last_rolls[1:])
    await ROULETTE_MSG.edit(embed=roulette_embed)

async def start_roulette_loop():
    while True:
        # ----------------- CONSTANTS
        global ROULETTE_MSG
        global TIMER_MSG
        global BETS_MSG
        
        progress_bar_length = 30
        progress_bar = Emoji.PROGRESS_BAR.EDGE + Emoji.PROGRESS_BAR.FRONT_EDGE * (progress_bar_length-1)

        # ----------------- CREATE A NEW ROUND
        last_round: Round = database.get_last_round()
        current_round: Round = database.create_round(game.getNewRoundID(), game.getNewRoundResult())

        # ----------------- CLEAR THE BETS TABLE
        await update_bets_table()

        # ----------------- ENABLE BET BUTTONS
        await set_button_states(True)
        await ROULETTE_MSG.edit(view=BUTTONS)
        #for bet_type in Emoji.BET_TYPES.ALL:
        #    await ROULETTE_MSG.add_reaction(bet_type)

        # ----------------- START THE TIMER FOR BETTING
        if not TIMER_MSG:
            TIMER_MSG = await ROULETTE_MSG.channel.send(f"Place your bets! ⏳ **{game.BETTING_DURATION}s** remaining\n{Emoji.PROGRESS_BAR.START}{progress_bar}{Emoji.PROGRESS_BAR.BEFORE_END}")
        else:
            await TIMER_MSG.edit(content=f"Place your bets! ⏳ **{game.BETTING_DURATION}s** remaining\n{Emoji.PROGRESS_BAR.START}{progress_bar}{Emoji.PROGRESS_BAR.BEFORE_END}")
        
        await asyncio.sleep(1)
        for elapsed in range(1, game.BETTING_DURATION + 1):
            progress = int((elapsed / game.BETTING_DURATION) * progress_bar_length)
            remaining_time = game.BETTING_DURATION - elapsed
            progress_bar = Emoji.PROGRESS_BAR.BEHIND_EDGE * (progress-1) + Emoji.PROGRESS_BAR.EDGE + Emoji.PROGRESS_BAR.FRONT_EDGE * (progress_bar_length - progress)

            await TIMER_MSG.edit(content=f"Place your bets! ⏳ **{remaining_time}s** remaining\n{Emoji.PROGRESS_BAR.START}{progress_bar}{Emoji.PROGRESS_BAR.BEFORE_END}")
            await asyncio.sleep(1)

        # ----------------- BETS OVER! DISABLE BET BUTTONS
        await asyncio.sleep(1)
        await set_button_states(False)
        await ROULETTE_MSG.edit(view=BUTTONS)
        await TIMER_MSG.edit(content=f"Betting is now closed! 🚫\n{Emoji.PROGRESS_BAR.START}{Emoji.PROGRESS_BAR.BEHIND_EDGE * progress_bar_length}{Emoji.PROGRESS_BAR.AFTER_END}")

        # ----------------- BETS OVER! ANIMATE THE ROULETTE
        if last_round:
            await animate_roulette(last_round.result_num, current_round.result_num)
        else:
            await animate_roulette(0, current_round.result_num)

        # ----------------- SHOW THE RESULTS ON THE BET TABLE
        bets = database.get_all_bets_by_round_id(current_round.id)
        await update_bets_table(bets, isRoundEnd=True)

        # ----------------- PROCESS RESULTS TO DATABASE
        database.process_bets()

        # ----------------- PAUSE BETWEEN THE ROUNDS
        await asyncio.sleep(2)

@bot.tree.command(name="start", description="Start the roulette game.")
@app_commands.default_permissions(administrator=True)
async def start(interaction: Interaction):
    global ROULETTE_MSG
    global BUTTONS
    BUTTONS = BetView()
    roulette_embed = embed_messages.setup_roulette()
    ROULETTE_MSG = await interaction.channel.send(embed=roulette_embed, view=BUTTONS)
    if not ROULETTE_MSG:
        await interaction.response.send_message("Error!", ephemeral=True)
        return
    
    await interaction.response.send_message("Starting the roulette game!", ephemeral=True, delete_after=3)
    # Start the roulette game loop
    bot.loop.create_task(start_roulette_loop())


@bot.tree.command(name="bet_amount", description="Start the roulette game.")
async def set_bet_amount(interaction: Interaction, bet_amount:float):
    try:
        database.set_gambler_bet_amount(interaction.user.id, bet_amount)
        await interaction.response.send_message(f"Your bet amount is: **{bet_amount}**$", ephemeral=True)
    except NoGamblerException as e:
        database.create_gambler(interaction.user.id, interaction.user.global_name)
        await interaction.response.send_message(f"You have been registered as **{interaction.user.global_name}** with 100$ credit.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error while setting up your bet amount: {e}", ephemeral=True)


@bot.tree.command(name="me", description="Get your statistics.")
async def me(interaction: Interaction):
    # Fetch gambler information from the database
    gambler: Gambler = database.get_gambler_by_id(interaction.user.id)
    
    if not gambler:
        await interaction.response.send_message(
            "You are not registered as a gambler yet! Start playing to create your profile.",
            ephemeral=True
        )
        return

    # Generate the gambler's statistics embed
    stats_embed = embed_messages.gambler_statistics(interaction, gambler)
    await interaction.response.send_message(embed=stats_embed)


@bot.tree.command(name="set_bet_period", description="Set the betting time in seconds.")
@app_commands.default_permissions(administrator=True)
async def set_bet_time(interaction: Interaction, bet_duration: int):
    game.setBetDuration(bet_duration)
    await interaction.response.send_message(f"Betting period is set to {game.getBetDuration()} seconds.", ephemeral=True)


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"Bot is ready. Logged in as {bot.user}")
    except Exception as e:
        print(f"Error syncing commands: {e}")


@bot.event
async def on_reaction_add(reaction: Reaction, user: Member):
    global ROULETTE_MSG
    if user == bot.user:
        return
    if reaction.message.id != ROULETTE_MSG.id:
        return

    # Map emoji IDs to game results
    color_mapping = {
        Emoji.ID.BET_GREEN: game.Results.GREEN,
        Emoji.ID.BET_RED: game.Results.RED,
        Emoji.ID.BET_BLACK: game.Results.BLACK
    }
    bet_on = color_mapping.get(reaction.emoji.id)

    if bet_on is None:
        return  # Ignore unrelated reactions

    # Get the current round
    current_round = database.get_last_round()
    if not current_round:
        await reaction.message.channel.send(f"{user.mention}, no active round found.", delete_after=5)
        return

    # Fetch or create the gambler
    gambler: Gambler = database.get_gambler_by_id(user.id)
    if not gambler:
        gambler = database.create_gambler(
            id=user.id,
            name=user.global_name
        )

    # Place the bet
    bet_amount = gambler.default_bet_amount
    try:
        bets = database.get_all_bets_by_round_id(current_round.id)
        for bet in bets:
            if gambler.id == bet.gambler_id:
                await reaction.message.channel.send(f"{user.mention}, You have already made your bet on **{bet.bet_on}** with **{bet.amount}$**", delete_after=5)
                await reaction.remove(user)
                return
        new_bet = database.create_bet(gambler, current_round, bet_amount, bet_on)
        bets.append(new_bet)
        await update_bets_table(bets, isRoundEnd=False)
        database.update_gambler_balance(gambler.id, -bet_amount)
    except InsufficientBalanceException as e:
        await reaction.message.channel.send(f"{user.mention} {e}", delete_after=5)
    except Exception as e:
        print(f"Error processing bet: {e}")
        await reaction.message.channel.send(f"{user.mention}, there was an error placing your bet.", delete_after=5)


async def update_bets_table(bets:list[Bet]=None, isRoundEnd:bool=False):
    if not bets:
        bets = []
    global BETS_MSG
    current_round = database.get_last_round()
    round_result = current_round.result_color
    bets_table = {game.Results.GREEN: [], game.Results.RED: [], game.Results.BLACK: []}

    if isRoundEnd:
        headers = (
            ["🟥 Red 2x 💲", "🟩 Green 14x ❌", "⬛ Black 2x ❌"] if round_result == game.Results.RED
        else ["🟥 Red 2x ❌", "🟩 Green 14x 💲", "⬛ Black 2x ❌"] if round_result == game.Results.GREEN
        else ["🟥 Red 2x ❌", "🟩 Green 14x ❌", "⬛ Black 2x 💲"] if round_result == game.Results.BLACK
        else None
        )
        for bet in bets:
            gambler:Gambler = database.get_gambler_by_id(bet.gambler_id)
            bet_on = bet.bet_on
            reward = (bet.amount * game.RED_MULTIPLIER if bet_on == game.Results.RED else
                      bet.amount * game.GREEN_MULTIPLIER if bet_on == game.Results.GREEN else
                      bet.amount * game.BLACK_MULTIPLIER if bet_on == game.Results.BLACK else None)
            reward = round(reward, 2)
            bets_table[bet_on].append(f"{gambler.name:<13} +{reward:<5}") if bet_on == round_result else bets_table[bet_on].append(f"{gambler.name:<13} -{bet.amount:<5}")
        table_header = f"| {headers[0]:<17} | {headers[1]:<18} | {headers[2]:<17} |\n"

    else:
        headers = ["🟥 Red 2x", "🟩 Green 14x", "⬛ Black 2x"]
        for bet in bets:
            gambler:Gambler = database.get_gambler_by_id(bet.gambler_id)
            bet_on = bet.bet_on
            bets_table[bet_on].append(f"{gambler.name:<15}{bet.amount:<5}")
        table_header = f"| {headers[0]:<19} | {headers[1]:<19} | {headers[2]:<18} |\n"
    
    table_divider = f"+{'-'*22}+{'-'*22}+{'-'*22}+"

    table_rows = []
    max_rows = max(len(bets_table[game.Results.GREEN]), len(bets_table[game.Results.RED]), len(bets_table[game.Results.BLACK]), 5)

    for i in range(max_rows):
        green = bets_table[game.Results.GREEN][i] if i < len(bets_table[game.Results.GREEN]) else ""
        red = bets_table[game.Results.RED][i] if i < len(bets_table[game.Results.RED]) else ""
        black = bets_table[game.Results.BLACK][i] if i < len(bets_table[game.Results.BLACK]) else ""
        table_rows.append(f"| {red:<20} | {green:<20} | {black:<20} |")

    table = f"{table_divider}\n{table_header}{table_divider}\n" + "\n".join(table_rows) + f"\n{table_divider}"
    content = f"```diff\n{table}\n```"
    if not BETS_MSG:
        BETS_MSG = await ROULETTE_MSG.channel.send(content)
    else:
        await BETS_MSG.edit(content=content)

# Disable buttons in the BetView
async def set_button_states(state:bool=True):
    global BUTTONS
    if BUTTONS:
        for item in BUTTONS.children:
            if isinstance(item, Button):
                item.disabled = not(state)  # Disable the button
        await ROULETTE_MSG.edit(view=BUTTONS)  # Update the message with the disabled buttons

class BetButton(Button):
    def __init__(self, label, bet_on, style):
        super().__init__(label=label, style=style)
        self.bet_on = bet_on

    async def callback(self, interaction: Interaction):
        global ROULETTE_MSG

        # Fetch the current round
        current_round:Round = database.get_last_round()
        if not current_round:
            await interaction.response.send_message("No active round found.", ephemeral=True)
            return

        # Fetch or create the gambler
        gambler:Gambler = database.get_gambler_by_id(interaction.user.id)
        if not gambler:
            gambler = database.create_gambler(
                id=interaction.user.id,
                name=interaction.user.global_name
            )

        # Place the bet
        bet_amount = gambler.default_bet_amount
        try:
            bets = database.get_all_bets_by_round_id(current_round.id)
            for bet in bets:
                if gambler.id == bet.gambler_id:
                    await interaction.response.send_message(
                        f"You have already made your bet on **{bet.bet_on}** with **{bet.amount}$**",
                        ephemeral=True
                    )
                    return

            new_bet = database.create_bet(gambler, current_round, bet_amount, self.bet_on)
            bets.append(new_bet)
            await update_bets_table(bets, isRoundEnd=False)
            database.update_gambler_balance(gambler.id, -bet_amount)
            await interaction.response.send_message(f"Bet placed on **{self.bet_on}** for **{bet_amount}$**!", ephemeral=True, delete_after=5)
        except InsufficientBalanceException as e:
            await interaction.response.send_message(f"{e}", ephemeral=True)
        except Exception as e:
            print(f"Error processing bet: {e}")
            await interaction.response.send_message("There was an error placing your bet.", ephemeral=True)

class BetView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BetButton(label="RED", bet_on=game.Results.RED, style=ButtonStyle.red))
        self.add_item(BetButton(label="GREEN", bet_on=game.Results.GREEN, style=ButtonStyle.green))
        self.add_item(BetButton(label="BLACK", bet_on=game.Results.BLACK, style=ButtonStyle.grey))

# Run the bot
bot.run(token)