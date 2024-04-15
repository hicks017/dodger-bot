# TO DO
# Run script at 9:00 AM US Pacific UTC-8 each day
# Host on Oracle Cloud Ampere or other cloud service
# Implement Discord bot

# Dependencies
from datetime import date, time, timedelta
from pybaseball import batting_stats_range
from unidecode import unidecode
from pandas import json_normalize
from statsapi import next_game, last_game, boxscore_data

# Basic info
today = date.today()
today_minus_10 = today - timedelta(days = 10)
dodgers = 119

# Next game
next_game = next_game(dodgers)
next_game_data = boxscore_data(next_game)
next_game_teams = sorted((next_game_data["teamInfo"]["away"]["teamName"], next_game_data["teamInfo"]["home"]["teamName"]))
next_game_calendar_date = json_normalize(next_game_data["gameBoxInfo"])
next_game_calendar_date = next_game_calendar_date[next_game_calendar_date["label"].str.endswith(("2024", "2025", "2026", "2027", "2028", "2029"))]["label"].values[0]

# Compare today's date to next game's date
if today.strftime(format = "%B %-d, %Y") == next_game_calendar_date:

    # Last game
    last_game = last_game(dodgers)
    last_game_data = boxscore_data(last_game)
    last_game_teams = sorted((last_game_data["teamInfo"]["away"]["teamName"], last_game_data["teamInfo"]["home"]["teamName"]))

    # Compare opponents from previous game to next game
    if next_game_teams != last_game_teams:

        # Batting stats
        batting_all = batting_stats_range(today_minus_10.strftime(format = "%Y-%m-%d"), today.strftime(format = "%Y-%m-%d"))
        batting_dodgers = batting_all[(batting_all["Tm"] == "Los Angeles") & (batting_all["Lev"] == "Maj-NL")].sort_values(by = "BA", ascending = False)
        batting_abs_median = batting_dodgers["AB"].median()

        # Top 3 Dodgers batters in last 10 days
        batting_dodgers_top_3 = batting_dodgers[batting_dodgers["AB"] >= batting_abs_median][["Name", "BA", "AB", "H", "2B", "3B", "HR"]].head(3)

        # Print
        print(batting_dodgers_top_3)