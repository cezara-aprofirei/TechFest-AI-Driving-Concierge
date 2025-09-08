# -------------------------------------------------
# utils/settings.py
#
# Purpose:
# - Central place to load configuration values (like API keys).
# - Keeps secrets out of the codebase and hardcoded strings.
#
# Why this matters:
# - Never hardcode secrets (API keys, passwords) directly in your code.
# - Instead, put them in a `.env` file (not committed to git).
# - This module loads them once and makes them available everywhere.
# -------------------------------------------------

import os
from dotenv import load_dotenv

# -------------------------------------------------
# Load variables from `.env`
# -------------------------------------------------
# - load_dotenv() looks for a file named `.env` in the project folder.
# - Each line in .env is KEY=VALUE (e.g., GOOGLE_MAPS_API_KEY=ABC123).
# - These values are then added to the process environment so os.getenv() can read them.
# -------------------------------------------------
load_dotenv()

# -------------------------------------------------
# Expose Google Maps API key
# -------------------------------------------------
# - We grab the value from environment variables.
# - If the .env file is missing or the key is not set, this will be None.
# - Other modules (like services/maps.py) import this variable and
#   raise a clear error if it's missing.
# -------------------------------------------------
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
