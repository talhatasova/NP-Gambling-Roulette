from datetime import datetime, timedelta, timezone
from discord import Interaction, Embed, Color
from emojis import Emoji
from database import Gambler, get_all_gamblers, Item
import game

def setup_roulette(roulette_sequence:list[Emoji]=None, last_results: list[Emoji]=None) -> Embed:
    if not roulette_sequence:
        roulette_sequence = [Emoji.roulette_values.get(num) for num in game.set_sequence(0)]
    if not last_results:
        last_results = [Emoji.roulette_values.get(0)]
    pivot = " ".join(["〰️" if i != 7 else "🔺" for i in range(15)])
    
    embed = Embed(title="🎲 Roulette Spin 🎲", color=Color.gold())
    embed.add_field(name="Previous Rolls", value=" ".join(last_results), inline=False)
    embed.add_field(name="Roulette", value=" ".join(roulette_sequence), inline=False)
    embed.add_field(name="", value=pivot, inline=False)
    embed.set_footer(text="Spinning...")
    return embed

def result_roulette(roulette_sequence:list[Emoji]=None, last_results: list[Emoji]=None, color=Color.gold()) -> Embed:
    if not roulette_sequence:
        roulette_sequence = [Emoji.roulette_values.get(num) for num in game.set_sequence(0)]
    if not last_results:
        last_results = [Emoji.roulette_values.get(0)]
    
    embed = Embed(title="🎲 Roulette Spin 🎲", color=color)
    embed.add_field(name="Previous Rolls", value=" ".join(last_results), inline=False)
    embed.add_field(name="Result", value=f"The ball landed on {last_results[-1]}!", inline=False)
    embed.set_footer(text="Spinned...")
    return embed

def leaderboard() -> Embed:
    # Fetch all gamblers and sort them
    gamblers: list[Gambler] = sorted(get_all_gamblers(), reverse=True)
    
    # Get the last update time
    last_update_date = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

    # Prepare the leaderboard content
    leaderboard_rows = []
    rank = 1
    for gambler in gamblers:
        if rank > 10:
            break
        name = gambler.name[:16].ljust(16)  # Truncate and align name to 10 chars
        balance = f"{gambler.balance:.2f}".rjust(10)  # Format balance
        bet_so_far = f"{sum(bet.amount for bet in gambler.bets):.2f}".rjust(10)  # Total bets placed
        leaderboard_rows.append(f"{rank:<4} {name} {balance} {bet_so_far}")
        rank += 1

    # Create the embed
    embed = Embed(
        title="🏆 LEADERBOARD 🏆",
        description=f"`{last_update_date} GMT+3`",
        color=Color.gold()
    )

    # Add leaderboard content
    embed.add_field(
        name="Rank"+6*" "+"Name"+46*" "+"Balance ($)"+7*" "+"Bets Total ($)",
        value=(
            "```diff\n" +
            "\n".join(leaderboard_rows) +
            "\n```"
        ),
        inline=False
    )

    return embed

def gambler_statistics(interaction: Interaction, gambler: Gambler) -> Embed:
    now = datetime.now(timezone.utc)
    cooldown:datetime = gambler.daily_cooldown.astimezone(timezone.utc)
    time_left = max((cooldown - now).total_seconds(), 0)
    daily_ready = time_left <= 0

    # Format time left as HH:MM:SS
    if not daily_ready:
        hours, remainder = divmod(time_left, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_left_formatted = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    else:
        time_left_formatted = "Ready to claim!"

    # Create an embed with statistics
    embed = Embed(
        title=f"🎲 {interaction.user.display_name} 🎲",
        color=Color.blurple()
    )
    red_bets = [bet for bet in gambler.bets if bet.bet_on == 'RED']
    red_correct = len([bet for bet in red_bets if bet.is_correct])
    red_wrong = len(red_bets) - red_correct
    red_percent = f"{red_correct/len(red_bets)*100:.2f}%" if len(red_bets) > 0 else "N/A"

    green_bets = [bet for bet in gambler.bets if bet.bet_on == 'GREEN']
    green_correct = len([bet for bet in green_bets if bet.is_correct])
    green_wrong = len(green_bets) - green_correct
    green_percent = f"{green_correct/len(green_bets)*100:.2f}%" if len(green_bets) > 0 else "N/A"

    black_bets = [bet for bet in gambler.bets if bet.bet_on == 'BLACK']
    black_correct = len([bet for bet in black_bets if bet.is_correct])
    black_wrong = len(black_bets) - black_correct
    black_percent = f"{black_correct/len(black_bets)*100:.2f}%" if len(black_bets) > 0 else "N/A"

    # Add gambler stats
    embed.add_field(name="💰 Balance", value=f"**`${gambler.balance:.2f}`**", inline=True)
    embed.add_field(name="🎲 Bet Each Round", value=f"**`${gambler.default_bet_amount:.2f}`**", inline=True)
    embed.add_field(name="📈 XP", value=f"**{gambler.xp} XP**", inline=True)
    embed.add_field(name="⭐ Level", value=f"**Level {gambler.level}**", inline=True)
    embed.add_field(name="🎁 Daily Reward Rate", value=f"**${gambler.daily:.2f}**", inline=True)
    embed.add_field(name="⏳ Daily Cooldown", value=f"**{time_left_formatted}**", inline=True)

    # Add color-coded bets stats
    embed.add_field(
        name="🎰 Rounds Played",
        value=(
            "```diff\n"
            f"- {len(red_bets)}|{red_correct}-{red_wrong}  ({red_percent})\n"
            f"+ {len(green_bets)}|{green_correct}-{green_wrong}  ({green_percent})\n"
            f"  {len(black_bets)}|{black_correct}-{black_wrong}  ({black_percent})\n"
            "```"
        ),
        inline=False
    )

    embed.add_field(
        name="🎲 Total",
        value=(
            f"**Rounds Played**: {len(gambler.bets)}\n"
            f"**Total Bet Placed**: `${sum([bet.amount for bet in gambler.bets]):.2f}`"
        ),
        inline=False
    )

    # Add a footer and thumbnail (e.g., user's avatar or a custom image)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(
        text="Keep betting to level up and smash Ibu's narrow asshole! MMHMHM Leziz!",
        icon_url=interaction.user.avatar.url if interaction.user.avatar else None
    )

    return embed

def daily_claimed_fail(interaction: Interaction, gambler: Gambler) -> Embed:
    next_claimable:datetime = gambler.daily_cooldown.astimezone(timezone.utc)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    remaining_time = timedelta(seconds=(next_claimable - now).total_seconds())
    hours, remainder = divmod(remaining_time.total_seconds(), 3600)
    minutes, _ = divmod(remainder, 60)

    embed = Embed(
        title="❌ Daily Reward Already Claimed!",
        description=(
            f"Hi {interaction.user.mention}, you've already claimed your daily reward today.\n"
            f"Come back in **{int(hours)} hours and {int(minutes)} minutes** to claim it again!"
        ),
        color=Color.red()
    )
    #embed.set_thumbnail(url="https://example.com/failure-icon.png")  # Replace with a valid failure image URL
    embed.set_footer(text="Keep playing daily to maximize your rewards!")
    return embed

def daily_claimed_success(interaction: Interaction, gambler: Gambler) -> Embed:
    embed = Embed(
        title="🎉 Daily Reward Claimed!",
        description=(
            f"Great job, {interaction.user.mention}!\n"
            f"You've successfully claimed your daily reward of **${gambler.daily}**. 💰"
        ),
        color=Color.green()
    )
    #embed.set_thumbnail(url="https://example.com/success-icon.png")
    embed.add_field(name="Your Updated Balance", value=f"**{gambler.balance:.2f}** coins", inline=False)
    embed.set_footer(text="Don't forget to come back tomorrow for another reward!")
    return embed

def show_items(interaction: Interaction, items: list[Item], page_size:int=10) -> list[list[Embed]]:
    embeds_pages = []

    # Create embeds grouped by page size
    items.sort(reverse=True)
    for i in range(0, len(items), page_size):
        page_items = items[i:i+page_size]
        embeds = []
        for item in page_items:
            if not item.is_tradable:
                continue
            embed = Embed(
            title=item.name,
            # **Float:** {item.float_val}
            description=f'''
                **Price:** ${round(item.buff_price, 2)}
            ''',
            color=Color.gold(),
            timestamp=datetime.now()
            )
            if item.image_url:
                embed.set_thumbnail(url=item.image_url)
            embeds.append(embed)
        embeds_pages.append(embeds)

    return embeds_pages

