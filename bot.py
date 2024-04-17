import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

bot = commands.Bot(command_prefix = "!", intents = discord.Intents.default())

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
# guild_id = int(os.environ.get("GUILD_ID"))
channel_id = int(os.environ.get("CHANNEL_ID"))
channel = None

@bot.event
async def on_ready():
    global channel
    channel = bot.get_channel(channel_id)
    print(f'{bot.user} has connected to {channel}!')
    scheduler = AsyncIOScheduler()
    scheduler.add_job(timedMessage, 'cron', hour=17, minute=44, second=0, timezone=pytz.timezone("US/Pacific"))
    scheduler.start()

async def timedMessage():
    if 1 == 1:
        timezone = pytz.timezone("US/Pacific")
        now = datetime.now(timezone)
        current_time = now.strftime("%H:%M:%S")
        await channel.send("test!!!")

bot.run(token)
