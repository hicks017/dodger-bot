import os
import requests
import datetime
from zoneinfo import ZoneInfo  # Python 3.9+ for timezone support
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID") # Optional

# Constants for MLB/Dodgers
TEAM_ID = 119  # Los Angeles Dodgers
TEAM_NAME = "Los Angeles Dodgers"
BASE_URL = "https://statsapi.mlb.com/api"

# Optional admin channel for error and status notifications
if ADMIN_CHANNEL_ID is not None:
    try:
        ADMIN_CHANNEL_ID = int(ADMIN_CHANNEL_ID)
    except ValueError:
        ADMIN_CHANNEL_ID = None
async def notify_admin_channel(message):
    """
    Sends a message to the admin channel if ADMIN_CHANNEL_ID is set.
    """
    if ADMIN_CHANNEL_ID:
        channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if channel:
            try:
                await channel.send(message)
            except Exception as e:
                print(f"[admin notify error] {e}")

async def admin_log(message):
    print(message)
    await notify_admin_channel(message)

def is_new_series_today(team_id=TEAM_ID):
    """
    Checks if the Dodgers are starting a new series today against a new opponent.
    Returns True if yes, False otherwise.
    """
    today = datetime.date.today()
    today_str = today.strftime('%Y-%m-%d')
    
    # Get today's game for the Dodgers.
    schedule_url = f"{BASE_URL}/v1/schedule?teamId={team_id}&startDate={today_str}&endDate={today_str}&sportId=1"
    response = requests.get(schedule_url)
    if response.status_code != 200:
        asyncio.create_task(admin_log("Error fetching schedule data for today."))
        return False
    data = response.json()
    if not data.get("dates"):
        return False  # No game today.
    
    today_game = None
    for date_record in data.get("dates", []):
        for game in date_record.get("games", []):
            if game.get("gameType") == "R":  # Consider only regular season games.
                today_game = game
                break
        if today_game:
            break
    if not today_game:
        return False

    # Determine today's opponent.
    # The API returns a "teams" dict with "home" and "away".
    if today_game["teams"]["away"]["team"]["id"] == team_id:
        opponent_id = today_game["teams"]["home"]["team"]["id"]
    else:
        opponent_id = today_game["teams"]["away"]["team"]["id"]

    # Fetch past 30 days of regular season games (if any) for the Dodgers.
    start_date_past = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    yesterday = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    past_schedule_url = f"{BASE_URL}/v1/schedule?teamId={team_id}&startDate={start_date_past}&endDate={yesterday}&sportId=1"
    response_past = requests.get(past_schedule_url)
    if response_past.status_code != 200:
        asyncio.create_task(admin_log("Error fetching past schedule data."))
        # In case of error, we assume it might be a new series.
        return True
    data_past = response_past.json()
    
    # Find the most recent previous regular season game.
    last_game = None
    last_game_date = None
    for date_record in data_past.get("dates", []):
        game_date = datetime.datetime.strptime(date_record.get("date"), '%Y-%m-%d').date()
        for game in date_record.get("games", []):
            if game.get("gameType") == "R":
                if last_game_date is None or game_date > last_game_date:
                    last_game = game
                    last_game_date = game_date
                    
    # If there was no previous game, assume it is the first game (thus a new series).
    if last_game is None:
        return True

    # Determine the opponent in the last game.
    if last_game["teams"]["away"]["team"]["id"] == team_id:
        last_opponent_id = last_game["teams"]["home"]["team"]["id"]
    else:
        last_opponent_id = last_game["teams"]["away"]["team"]["id"]

    # If today's opponent is different from the opponent in the last game, it's a new series.
    return opponent_id != last_opponent_id

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
        asyncio.create_task(admin_log("Error fetching upcoming schedule data."))
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
  
def get_today_opponent(team_id):
    """
    Retrieve the opponent for today's regular season game for the given team.
    Returns the opponent's nickname (without the city name) if found; otherwise returns "Unknown".
    """
    # Define multi-word team names here
    multi_word_teams = {"Red Sox", "White Sox", "Blue Jays"}
    
    today = datetime.date.today()
    date_str = today.strftime('%Y-%m-%d')
    schedule_url = f"{BASE_URL}/v1/schedule?teamId={team_id}&startDate={date_str}&endDate={date_str}&sportId=1"
    try:
        response = requests.get(schedule_url)
        if response.status_code != 200:
            asyncio.create_task(admin_log(f"Error fetching today's opponent: {response.status_code}"))
            return "Unknown"
        data = response.json()
        for date_obj in data.get("dates", []):
            for game in date_obj.get("games", []):
                if game.get("gameType") != "R":
                    continue
                teams = game.get("teams", {})
                home_team = teams.get("home", {}).get("team", {})
                away_team = teams.get("away", {}).get("team", {})
                
                if home_team.get("id") == team_id:
                    opponent_full_name = away_team.get("name", "Unknown")
                elif away_team.get("id") == team_id:
                    opponent_full_name = home_team.get("name", "Unknown")
                else:
                    continue

                # Check if for multi-word teams in opponent team name
                for indicator in multi_word_teams:
                    if indicator in opponent_full_name:
                        return indicator
                # Otherwise, return the last token (nickname)
                return opponent_full_name.split()[-1]
        asyncio.create_task(admin_log("No regular season game found for today when fetching opponent."))
        return "Unknown"
    except Exception as e:
        asyncio.create_task(admin_log(f"Exception in get_today_opponent: {e}"))
        return "Unknown"
    
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
            asyncio.create_task(admin_log(str(e)))
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
    """
    sorted_players = sorted(players_list, key=lambda x: x["avg"], reverse=True)
    lines = []
    header = f"{'Player':20s} {'AVG':>5s} {'HR':>3s} {'RBI':>3s}"
    lines.append(header)
    lines.append("-" * len(header))
    for player in sorted_players[:top_n]:
        avg_str = f"{player['avg']:.3f}"
        # Truncate player name if necessary for compact display
        line = f"{player['name'][:20]:20s} {avg_str:>5s} {str(player['homeRuns']):>3s} {str(player['rbi']):>3s}"
        lines.append(line)
    return "\n".join(lines)

def get_dodgers_batting_stats():
    """
    Combines data fetching and formatting to produce a message of top batters.
    """
    try:
        games = get_recent_games(TEAM_ID, days_delta=60, max_games=10)
        if not games:
            asyncio.create_task(admin_log("No completed games found in the specified date range."))
            return "No completed games found in the specified date range."
        
        aggregated_stats = aggregate_player_stats(games, TEAM_ID)
        players_list = compute_batting_average(aggregated_stats)
        if not players_list:
            asyncio.create_task(admin_log("No batting stats available from the recent games."))
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
    header = f"{'Team':13s} {'W':>3s} {'L':>3s} {'Pct':>5s} {'GB':>3s}"
    lines.append(header)
    lines.append("-" * len(header))
    for teamRec in nlwest_record.get("teamRecords", []):
        team_name = teamRec.get("team", {}).get("name", "Unknown")
        # Extract just the nickname by using the last word.
        team_nickname = team_name.split()[-1]
        wins = teamRec.get("wins", 0)
        losses = teamRec.get("losses", 0)
        win_pct = teamRec.get("winningPercentage", "N/A")
        games_back = teamRec.get("gamesBack", "0")
        line = f"{team_nickname:13s} {str(wins):>3s} {str(losses):>3s} {win_pct:>5s} {str(games_back):>3s}"
        lines.append(line)
    return "\n".join(lines)

####################################
# Discord Bot Setup
####################################
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

# --- Discord Bot Events and Commands ---
@bot.event
async def on_ready():
    await admin_log(f":white_check_mark: Dodger Bot is live! Logged in as {bot.user.name} ({bot.user.id})")
    if not scheduled_stats.is_running():
        scheduled_stats.start()

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

# --- Test commands for each function ---
@bot.command(name="avg")
async def avg(ctx):
    stats_message = get_dodgers_batting_stats()
    await ctx.send(f"```{stats_message}```")

@bot.command(name="standings")
async def standings(ctx):
    standings_message = get_nlwest_standings()
    await ctx.send(f"```{standings_message}```")

@bot.command(name="is_new_series_today")
async def cmd_is_new_series_today(ctx):
    result = is_new_series_today(TEAM_ID)
    await ctx.send(f"is_new_series_today: {result}")

@bot.command(name="upcoming_regular_season_game_exists")
async def cmd_upcoming_regular_season_game_exists(ctx):
    result = upcoming_regular_season_game_exists(TEAM_ID)
    await ctx.send(f"upcoming_regular_season_game_exists: {result}")

@bot.command(name="get_today_opponent")
async def cmd_get_today_opponent(ctx):
    result = get_today_opponent(TEAM_ID)
    await ctx.send(f"get_today_opponent: {result}")

@bot.command(name="get_recent_games")
async def cmd_get_recent_games(ctx):
    try:
        games = get_recent_games(TEAM_ID)
        msg = f"Found {len(games)} recent games. First gamePk: {games[0]['gamePk'] if games else 'N/A'}"
    except Exception as e:
        msg = f"Error: {e}"
    await ctx.send(msg)

@bot.command(name="get_boxscore")
async def cmd_get_boxscore(ctx, game_pk: int = None):
    if game_pk is None:
        # Try to get a recent game
        try:
            games = get_recent_games(TEAM_ID)
            if not games:
                await ctx.send("No recent games found.")
                return
            game_pk = games[0]["gamePk"]
        except Exception as e:
            await ctx.send(f"Error: {e}")
            return
    try:
        boxscore = get_boxscore(game_pk)
        summary = f"Boxscore for gamePk {game_pk}: keys: {list(boxscore.keys())}"
    except Exception as e:
        summary = f"Error: {e}"
    await ctx.send(summary)

@bot.command(name="aggregate_player_stats")
async def cmd_aggregate_player_stats(ctx):
    try:
        games = get_recent_games(TEAM_ID)
        stats = aggregate_player_stats(games, TEAM_ID)
        await ctx.send(f"Aggregated stats for {len(stats)} players.")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name="compute_batting_average")
async def cmd_compute_batting_average(ctx):
    try:
        games = get_recent_games(TEAM_ID)
        stats = aggregate_player_stats(games, TEAM_ID)
        players = compute_batting_average(stats)
        await ctx.send(f"Players with computed avg: {len(players)}")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name="format_batting_stats")
async def cmd_format_batting_stats(ctx):
    try:
        games = get_recent_games(TEAM_ID)
        stats = aggregate_player_stats(games, TEAM_ID)
        players = compute_batting_average(stats)
        formatted = format_batting_stats(players, top_n=3)
        await ctx.send(f"```{formatted}```")
    except Exception as e:
        await ctx.send(f"Error: {e}")

####################################
# Scheduled Task: Daily at 9:00 AM Pacific Time
####################################
standings_messages = [
    "Kick off the weekend with the NL West standings:",
    "Weekend update! Here’s where the NL West sits heading into Friday:",
    "Happy Friday! Check out the NL West standings as we roll into the weekend:",
    "NL West snapshot for your weekend:",
    "NL West rundown for Friday — see who’s leading as the weekend arrives:",
    "It’s Friday! Here’s your NL West standings update:"
]

series_messages = [
    "Wake up!! New series vs. {opponent}. Here are the hottest bats from the last 10 games:",
    "Rise and shine! New series vs. {opponent}. Peep the top bats from the last 10 games:",
    "Time for a matchup against {opponent}! Check out who’s been crushing it over the past 10 games:",
    "We’re about to take on {opponent}! Feast your eyes on the hottest bats of the last 10 games:",
    "Batter up! Series vs. {opponent} is here. These hitters have been locked-in for the last 10 games:",
    "It’s go time! Series vs. {opponent} is starting. Check out who’s been on fire these last 10 games:",
    "Let’s get it! New series against {opponent} — here’s a breakdown of our top sluggers of the last 10 games:",
    "Matchup vs. {opponent} starts today! These hitters have been red-hot in the last 10 games:"
]

standings_message_idx = 0
series_message_idx = 0

@tasks.loop(time=datetime.time(hour=9, minute=0, second=0, tzinfo=ZoneInfo("America/Los_Angeles")))
async def scheduled_stats():
    try:
        """
        Runs every day at 9:00 AM Pacific Time.
          - On Friday, it posts the current NL West standings.
          - On other days, if a new series starts today, it posts Dodgers batting stats.
        This task only runs if at least one Regular season game is scheduled within the next 30 days.
        """
        # Check if there is an upcoming Regular season game for the Dodgers.
        if not upcoming_regular_season_game_exists(TEAM_ID):
            await admin_log("No upcoming Regular season game for the Dodgers within the next 30 days. Skipping scheduled task.")
            return

        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            await admin_log(f"Channel with ID {CHANNEL_ID} not found.")
            return

        now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
        global standings_message_idx, series_message_idx
        if now.weekday() == 4:  # Friday (Monday=0, Fri=4)
            standings_message = get_nlwest_standings()
            intro = standings_messages[standings_message_idx]
            standings_message_idx = (standings_message_idx + 1) % len(standings_messages)
            message = f"{intro}\n```{standings_message}```"
            await channel.send(message)
        else:
            # Only post Dodgers batting stats if a new series has started today.
            if is_new_series_today(TEAM_ID):
                stats_message = get_dodgers_batting_stats()
                opponent = get_today_opponent(TEAM_ID)  # Fetch the opponent
                intro = series_messages[series_message_idx].format(opponent=opponent)
                series_message_idx = (series_message_idx + 1) % len(series_messages)
                message = f"{intro}\n```{stats_message}```"
                await channel.send(message)
            else:
                print("No new series started today.")
    except Exception as e:
        await admin_log(f":warning: [scheduled_stats] error: {e}")

@scheduled_stats.before_loop
async def before_scheduled_stats():
    await bot.wait_until_ready()

@scheduled_stats.error
async def scheduled_stats_error(exc, _task):
    await admin_log(f":warning: [scheduled_stats] crashed: {exc}")

bot.run(DISCORD_TOKEN)
