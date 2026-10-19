"""
Application Configuration & Secrets Management
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

META_AD_TOKEN: str = os.getenv("META_AD_TOKEN", "")
GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "virtualanalytics5122")
GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Google BigQuery Public Dataset identifiers
BIGQUERY_POLITICAL_ADS_DATASET: str = "bigquery-public-data.google_political_ads"
