import os
import discord
import datetime
import pytz
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from statsapi import next_game, last_game, boxscore_data
from pandas import json_normalize
from pybaseball import batting_stats_range, standings

bot = commands.Bot(command_prefix = "!", intents = discord.Intents.default())

# Obtain environment variables defined in .env file
load_dotenv()
token = os.getenv("DISCORD_TOKEN")
# guild_id = int(os.environ.get("GUILD_ID"))
channel_id = int(os.environ.get("CHANNEL_ID"))
channel = None

# Define Dodgers team ID from the MLB API
dodgers = 119

# Define bot startup actions
@bot.event
async def on_ready():

    # Confirm bot connection to target Discord channel
    global channel
    channel = bot.get_channel(channel_id)
    print(f'{bot.user} has connected to {channel}!')

    # Define schedule for function message_top_batters()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        message_top_batters,
        'cron',
        hour=9,
        minute=0,
        second=0,
        timezone=pytz.timezone("US/Pacific")
    )
    scheduler.add_job(
        message_standings,
        'cron',
        hour=9,
        minute=0,
        second=0,
        timezone=pytz.timezone("US/Pacific")
    )
    scheduler.start()

# Setup scheduled bot message for recent top batters
async def message_top_batters():
    
    # Obtain dates for current day and 10 days ago
    today = datetime.date.today()
    today_minus_10 = today - datetime.timedelta(days = 10)

    # Obtain date and team names for next Dodgers' game
    next_game_id = next_game(dodgers)
    next_game_data = boxscore_data(next_game_id)

    next_game_teams = sorted((
        next_game_data["teamInfo"]["away"]["teamName"],
        next_game_data["teamInfo"]["home"]["teamName"]
    ))

    next_game_calendar_date = json_normalize(next_game_data["gameBoxInfo"])
    next_game_calendar_date = (
        next_game_calendar_date[
            next_game_calendar_date["label"].str.endswith(
                ("2024", "2025", "2026", "2027", "2028", "2029")
            )
        ]["label"].values[0]
    )

    # Compare today's date to date of next Dodgers' game
    if today.strftime(format = "%B %-d, %Y") == next_game_calendar_date:

        # Grab opponent team name for next game
        opponent = [team for team in next_game_teams if team != 'Dodgers']
        
        # Obtain team names for previous Dodgers' game
        last_game_id = last_game(dodgers)
        last_game_data = boxscore_data(last_game_id)
        last_game_teams = sorted((
            last_game_data["teamInfo"]["away"]["teamName"],
            last_game_data["teamInfo"]["home"]["teamName"]
        ))

        # Compare opponents between next game and
        # last game to identify new series
        if next_game_teams != last_game_teams:
            # Obtain batting stats for Dodgers hitters within last 10 days
            batting_all = batting_stats_range(
                today_minus_10.strftime(format = "%Y-%m-%d"),
                today.strftime(format = "%Y-%m-%d")
            )
            batting_dodgers = batting_all[
                (batting_all["Tm"] == "Los Angeles") &
                (batting_all["Lev"] == "Maj-NL")
            ].sort_values(by = "BA", ascending = False)

            # Calculate median at-bats
            batting_abs_median = batting_dodgers["AB"].median()

            # Compile top 3 Dodgers hitters with at least
            # the median at-bats into a data frame
            batting_dodgers_top_3 = (
                batting_dodgers[batting_dodgers["AB"] >= batting_abs_median]
                [["Name", "BA", "HR"]]
                .head(3)
                .reset_index(drop=True)
            )

            batting_dodgers_top_3.index = batting_dodgers_top_3.index + 1

            # Send data frame to Discord inside a code block
            await channel.send(
                'Wake up!! Dodgers vs. ' + ', '.join(opponent) +
                ' starts today!\n' +
                'Top 3 hitters for the last 10 days are:\n' +
                '```' + batting_dodgers_top_3.to_string() + '```'
            )
# Set up scheduled bot message for team standings
async def message_standings():

    # Check if today is Thursday (4)
    today = datetime.date.today()
    if today.isoweekday() == 4:

        # Obtain standings for NL West
        standings_data = standings()[5]
        standings_data = standings_data.loc[:, ['Tm', 'W', 'L', 'GB']]

        # Rename Tm values
        mapping = {
            "Los Angeles Dodgers": "Dodgers",
            "San Diego Padres": "Padres",
            "Arizona Diamondbacks": "Dbacks",
            "San Francisco Giants": "Giants",
            "Colorado Rockies": "Rockies"
        }
        standings_data['Tm'] = standings_data['Tm'].replace(mapping)

        # Send data frame to Discord inside a code block
        await channel.send(
            'NL West standings going into the weekend:\n' +
            '```' + standings_data.to_string() + '```'
        )

# Define command resposne to check that bot is live
@bot.command(name='status')
async def test(ctx):
    await ctx.send('Bot is live!')

# Run bot
bot.run(token)
