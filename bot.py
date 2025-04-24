import os
import requests
import datetime
from zoneinfo import ZoneInfo  # Python 3.9+ for timezone support
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Constants for MLB/Dodgers
TEAM_ID = 119  # Los Angeles Dodgers
TEAM_NAME = "Los Angeles Dodgers"
BASE_URL = "https://statsapi.mlb.com/api"

def upcoming_regular_season_game_exists(team_id, max_days=30):
    """
    Checks if at least one Regular season game exists for the given team within the next `max_days`.
    Returns True if found, False otherwise.
    """
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=max_days)
    start_date_str = today.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    schedule_url = f"{BASE_URL}/v1/schedule?teamId={team_id}&startDate={start_date_str}&endDate={end_date_str}&sportId=1"
    response = requests.get(schedule_url)
    if response.status_code != 200:
        print("Error fetching upcoming schedule data.")
        return False
    
    data = response.json()
    
    # Loop through all scheduled game dates
    for date_record in data.get("dates", []):
        for game in date_record.get("games", []):
            # Check if the game is a Regular season game.
            # The API designates regular season games with gameType "R".
            if game.get("gameType") == "R":
                return True
    return False
    
def get_recent_games(team_id, days_delta=60, max_games=10):
    """
    Retrieve the team's most recent completed games over the past `days_delta` days.
    Returns at most `max_games` games.
    """
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days_delta)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = today.strftime("%Y-%m-%d")
    
    schedule_url = f"{BASE_URL}/v1/schedule?teamId={team_id}&sportId=1&startDate={start_date_str}&endDate={end_date_str}"
    response = requests.get(schedule_url)
    if response.status_code != 200:
        raise Exception("Error fetching schedule data")
    
    data = response.json()
    games = []
    for date_obj in data.get("dates", []):
        for game in date_obj.get("games", []):
            if game.get("status", {}).get("abstractGameState") == "Final":
                games.append(game)
    
    games.sort(key=lambda g: g.get("gameDate"), reverse=True)
    return games[:max_games]

def get_boxscore(game_pk):
    """
    Retrieves the boxscore data via the /feed/live endpoint for a specific game.
    The live feed JSON contains boxscore info under "liveData" -> "boxscore".
    """
    url = f"{BASE_URL}/v1.1/game/{game_pk}/feed/live"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Error fetching live feed for game {game_pk}")
    
    data = response.json()
    boxscore = data.get("liveData", {}).get("boxscore")
    if not boxscore:
        raise Exception("No boxscore data found in the live feed.")
    return boxscore

def aggregate_player_stats(games, team_id):
    """
    For each game in `games`, fetch the Dodgers’ boxscore and accumulate batting stats.
    Returns a dictionary keyed by player id.
    """
    aggregated_stats = {}
    
    for game in games:
        game_pk = game.get("gamePk")
        try:
            boxscore = get_boxscore(game_pk)
        except Exception as e:
            print(e)
            continue
        
        teams_data = boxscore.get("teams", {})
        if teams_data.get("home", {}).get("team", {}).get("id") == team_id:
            team_box = teams_data.get("home")
        elif teams_data.get("away", {}).get("team", {}).get("id") == team_id:
            team_box = teams_data.get("away")
        else:
            continue
        
        players = team_box.get("players", {})
        for player_key, player_info in players.items():
            batting_stats = player_info.get("stats", {}).get("batting")
            if not batting_stats:
                continue  # skip if no batting stats
            
            at_bats = int(batting_stats.get("atBats", 0))
            hits = int(batting_stats.get("hits", 0))
            home_runs = int(batting_stats.get("homeRuns", 0))
            # Extract RBI values
            rbi = int(batting_stats.get("rbi", 0))
            
            pid = player_info.get("person", {}).get("id")
            pname = player_info.get("person", {}).get("fullName", "Unknown")
            if pid is None:
                continue
            
            if pid not in aggregated_stats:
                aggregated_stats[pid] = {
                    "name": pname,
                    "atBats": 0,
                    "hits": 0,
                    "homeRuns": 0,
                    "rbi": 0
                }
            
            aggregated_stats[pid]["atBats"] += at_bats
            aggregated_stats[pid]["hits"] += hits
            aggregated_stats[pid]["homeRuns"] += home_runs
            aggregated_stats[pid]["rbi"] += rbi
    
    return aggregated_stats

def compute_batting_average(aggregated_stats):
    """
    Computes batting average (hits/atBats) for each player and filters out those
    with fewer at-bats than the median at-bats for the team.
    Returns a list of stat dictionaries.
    """
    players_list = []
    # Get list of atBats values (considering only players that had at least one AB)
    at_bats_values = [stats["atBats"] for stats in aggregated_stats.values() if stats["atBats"] > 0]
    
    if not at_bats_values:
        return players_list
    
    at_bats_values.sort()
    n = len(at_bats_values)
    if n % 2 == 1:
        median_at_bats = at_bats_values[n // 2]
    else:
        median_at_bats = (at_bats_values[(n // 2) - 1] + at_bats_values[n // 2]) / 2
    
    # Filter players based on the median atBats and compute average
    for stats in aggregated_stats.values():
        if stats["atBats"] < median_at_bats:
            continue
        
        if stats["atBats"] > 0:
            avg = stats["hits"] / stats["atBats"]
        else:
            avg = 0
        stats["avg"] = avg
        players_list.append(stats)
    return players_list

def format_batting_stats(players_list, top_n=3):
    """
    Formats the top N players (by batting average) as a text table.
    Now includes RBI after home runs.
    """
    sorted_players = sorted(players_list, key=lambda x: x["avg"], reverse=True)
    lines = []
    header = f"Top {top_n} Batters for the {TEAM_NAME} over the last 10 games:"
    lines.append(header)
    lines.append("-" * 70)
    lines.append(f"{'Player':30s} {'AVG':>6s} {'HR':>4s} {'RBI':>5s}")
    lines.append("-" * 70)
    for player in sorted_players[:top_n]:
        avg_str = f"{player['avg']:.3f}"
        line = f"{player['name']:30s} {avg_str:>6s} {player['homeRuns']:>4d} {player['rbi']:>5d}"
        lines.append(line)
    return "\n".join(lines)

def get_dodgers_batting_stats():
    """
    Combines data fetching and formatting to produce a message of top batters.
    """
    try:
        games = get_recent_games(TEAM_ID, days_delta=60, max_games=10)
        if not games:
            return "No completed games found in the specified date range."
        
        aggregated_stats = aggregate_player_stats(games, TEAM_ID)
        players_list = compute_batting_average(aggregated_stats)
        if not players_list:
            return "No batting stats available from the recent games."
        
        return format_batting_stats(players_list, top_n=3)
    except Exception as e:
        return f"An error occurred while fetching data: {e}"

####################################
# NL West Standings
####################################

def get_nlwest_standings():
    """
    Fetches the current standings for the National League West division.
    Returns a formatted string displaying team name, wins, losses, win percentage, and games behind.
    """
    url = f"{BASE_URL}/v1/standings?leagueId=104&standingsTypes=regularSeason"
    response = requests.get(url)
    if response.status_code != 200:
        return "Error fetching standings data."
    data = response.json()
    records = data.get("records", [])
    nlwest_record = None

    # Check for division id 203 in the standings records.
    for record in records:
        division = record.get("division", {})
        if division.get("id") == 203:
            nlwest_record = record
            break

    if nlwest_record is None:
        return "National League West standings not found."
    
    lines = []
    header = f"{'Team':30s} {'W':>3s} {'L':>3s} {'Win%':>6s} {'GB':>5s}"
    lines.append(header)
    lines.append("-" * len(header))
    for teamRec in nlwest_record.get("teamRecords", []):
        team_name = teamRec.get("team", {}).get("name", "Unknown")
        wins = teamRec.get("wins", 0)
        losses = teamRec.get("losses", 0)
        win_pct = teamRec.get("winningPercentage", "N/A")
        games_back = teamRec.get("gamesBack", "0")
        line = f"{team_name:30s} {str(wins):>3s} {str(losses):>3s} {win_pct:>6s} {str(games_back):>5s}"
        lines.append(line)
    return "\n".join(lines)

####################################
# Discord Bot Setup
####################################
intents = discord.Intents.default()
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    if not scheduled_stats.is_running():
        scheduled_stats.start()

@bot.command(name="avg")
async def avg(ctx):
    """
    Manually triggered command that responds with the Dodgers batting stats.
    """
    await ctx.send("Fetching Dodgers stats...")
    stats_message = get_dodgers_batting_stats()
    await ctx.send(f"```{stats_message}```")

@bot.command(name="standings")
async def standings(ctx):
    """
    Manually triggered command that responds with the NL West standings.
    """
    await ctx.send("Fetching NL West standings...")
    standings_message = get_nlwest_standings()
    await ctx.send(f"```{standings_message}```")

@bot.command(name="ping")
async def ping(ctx):
    """
    Checks if the bot is active.
    """
    await ctx.send("Pong!")

####################################
# Scheduled Task: Daily at 9:00 AM Pacific Time
####################################
@tasks.loop(time=datetime.time(hour=9, minute=0, second=0, tzinfo=ZoneInfo("America/Los_Angeles")))
async def scheduled_stats():
    """
    Runs every day at 9:00 AM Pacific Time.
      - On Friday, it posts the current NL West standings.
      - On other days, if a new series starts today, it posts Dodgers batting stats.
    This task only runs if at least one Regular season game is scheduled within the next 30 days.
    """
    # Check if there is an upcoming Regular season game for the Dodgers.
    if not upcoming_regular_season_game_exists(TEAM_ID):
        print("No upcoming Regular season game for the Dodgers within the next 30 days. Skipping scheduled task.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {CHANNEL_ID} not found.")
        return

    now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    if now.weekday() == 4:  # Friday (Monday=0, Fri=4)
        standings_message = get_nlwest_standings()
        message = (
            "**National League West Standings:**\n"
            f"```{standings_message}```"
        )
        await channel.send(message)
    else:
        # Only post Dodgers batting stats if a new series has started today.
        if is_new_series_today(TEAM_ID):
            stats_message = get_dodgers_batting_stats()
            message = (
                "New series has started! Here are the Dodgers' top batters from the last 10 games:\n"
                f"```{stats_message}```"
            )
            await channel.send(message)
        else:
            print("No new series started today.")

bot.run(DISCORD_TOKEN)
