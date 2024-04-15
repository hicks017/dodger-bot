import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime

bot = commands.Bot(command_prefix = "!", intents = discord.Intents.default())

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
# guild_id = int(os.environ.get("GUILD_ID"))
# guild = bot.get_guild(guild_id)
channel_id = int(os.environ.get("CHANNEL_ID"))
channel = bot.get_channel(channel_id)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@tasks.loop(seconds = 5)
async def timedMessage():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Connected to loop")
    await print(f"{current_time}")

@timedMessage.before_loop
async def before():
    await bot.wait_until_ready()
    print("Finished waiting")

timedMessage.start()
bot.run(token)
