"""
Configuration settings, environment variables, and project constants.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Base directory: project root
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
GEO_DIR = DATA_DIR / "geo"
CACHE_DIR = DATA_DIR / "cache"
SEEDS_DIR = ROOT_DIR / "seeds"
SCENARIOS_DB = DATA_DIR / "scenarios.db"

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

# Credentials and project configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "virtualanalytics5122")
GCP_KEY_PATH = os.getenv("GCP_KEY_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
META_USER_TOKEN = os.getenv("META_USER_TOKEN", "")
META_AD_TOKEN = os.getenv("META_AD_TOKEN", "")
DATA_MODE = os.getenv("DATA_MODE", "live").lower().strip()  # "live" or "snapshot"

# BigQuery Dataset Constants
BIGQUERY_POLITICAL_ADS_DATASET = "bigquery-public-data.google_political_ads"
BQ_MART_DATASET = f"{GCP_PROJECT_ID}.mart"

# Default Model & War Room Parameters
DEFAULT_BUDGET = 2_000_000.0
DEFAULT_WEEKS = 8
DEFAULT_SCOPE = "statewide"
DEFAULT_GEO_MODE = "district"
DEFAULT_DISTRICT_TYPE = "cd"
DEFAULT_THEME = "dark"

# Allowed Choices
CHANNELS = ["meta", "youtube", "search", "display", "ctv"]
AUDIENCES = ["persuasion", "mobilization"]
DISTRICT_TYPES = ["cd", "sd", "hd"]
GEO_MODES = ["district", "county"]
SCOPES = ["statewide", "district"]

# Channel display metadata
CHANNEL_LABELS = {
    "meta": "Meta (FB / IG)",
    "youtube": "YouTube (Video)",
    "search": "Google Search",
    "display": "Google Display",
    "ctv": "Connected TV (CTV)"
}

AUDIENCE_LABELS = {
    "persuasion": "Persuasion (Unaffiliated / Soft)",
    "mobilization": "Mobilization (Low-propensity Dems)"
}
