from datetime import datetime
from discord import Interaction, Embed, Color
from emojis import Emoji
from database import Gambler
import game

def setup_roulette(roulette_sequence:list[Emoji]=None, last_results: list[Emoji]=None) -> Embed:
    if not roulette_sequence:
        roulette_sequence = [Emoji.roulette_values.get(num) for num in game.set_sequence(0)]
    if not last_results:
        last_results = [Emoji.roulette_values.get(0)]
    pivot = " ".join(["〰️" if i != 7 else "🔺" for i in range(15)])
    
    embed = Embed(title="🎲 Roulette Spin 🎲", color=Color.gold())
    embed.add_field(name="Previous Rolls", value=" ".join(last_results), inline=False)
    embed.add_field(name="Numbers", value=" ".join(roulette_sequence), inline=False)
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

def gambler_statistics(interaction: Interaction, gambler: Gambler) -> Embed:
    now = datetime.now()
    time_left = max((gambler.daily_cooldown - now).total_seconds(), 0)
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
        color=Color.gold()
    )

    # Add gambler stats
    embed.add_field(name="💰 Balance", value=f"${gambler.balance:.2f}", inline=True)
    embed.add_field(name="📈 XP", value=f"{gambler.xp} XP", inline=True)
    embed.add_field(name="⭐ Level", value=f"Level {gambler.level}", inline=True)
    embed.add_field(name="🎁 Daily Reward Rate", value=f"${gambler.daily:.2f}", inline=True)
    embed.add_field(name="⏳ Daily Cooldown", value=f"{time_left_formatted}", inline=True)
    embed.add_field(name="🎰 Total Bets", value=f"{len(gambler.bets)}", inline=True)

    # Add optional achievements or milestones
    if len(gambler.bets) > 50:
        embed.add_field(name="🏆 Achievement", value="Frequent Spinner: Over 50 bets placed!", inline=False)
    if gambler.level >= 10:
        embed.add_field(name="🏅 Milestone", value="Level 10+: Elite Gambler!", inline=False)

    # Add a footer and thumbnail (e.g., user's avatar or a custom image)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(
        text="Keep betting to level up and smash Ibu's narrow asshole! MMHMHM Leziz!",
        icon_url=interaction.user.avatar.url if interaction.user.avatar else None
    )

    return embed
