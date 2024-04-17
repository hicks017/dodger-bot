import os
import discord
import datetime
import pytz
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from statsapi import next_game, last_game, boxscore_data
from pandas import json_normalize
from pybaseball import batting_stats_range

bot = commands.Bot(command_prefix = "!", intents = discord.Intents.default())

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
# guild_id = int(os.environ.get("GUILD_ID"))
channel_id = int(os.environ.get("CHANNEL_ID"))
channel = None

dodgers = 119

@bot.event
async def on_ready():
    global channel
    channel = bot.get_channel(channel_id)
    print(f'{bot.user} has connected to {channel}!')
    scheduler = AsyncIOScheduler()
    scheduler.add_job(timedMessage, 'cron', hour=18, minute=14, second=30, timezone=pytz.timezone("US/Pacific"))
    scheduler.start()

async def timedMessage():
    if 1 == 1:
        today = datetime.date.today()
        today_minus_10 = today - datetime.timedelta(days = 10)
        today = today.strftime(format = "%B %-d, %Y")
        today_minus_10 = today_minus_10.strftime(format = "%B %-d, %Y")
        await channel.send('today is ' + today + ' and 10 days ago was ' + today_minus_10)

bot.run(token)
