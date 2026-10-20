"""
Application Configuration & Secrets Management
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def _resolve_secret(keys: list[str] | str, default_val: str = "") -> str:
    """
    Resolves secret from environment or env.txt fallback, stripping quotes.
    SECURITY: Secrets are strictly loaded dynamically from environment files and NEVER hardcoded in code.
    """
    if isinstance(keys, str):
        keys = [keys]

    val = ""
    for k in keys:
        v = os.getenv(k, "").strip()
        if v:
            val = v
            break

    # Check env.txt fallback if still empty
    if not val:
        env_txt = BASE_DIR / "env.txt"
        if env_txt.exists():
            try:
                for line in env_txt.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k in keys and v:
                            val = v
                            break
            except Exception:
                pass

    if not val:
        val = default_val

    return val.strip().strip('"').strip("'")

# Meta Ad Library API App Token
# Permissions for the Meta Ad Library API are granted as an App Token (META_APP_TOKEN).
# SECURITY MANDATE: Never hardcode or include the Meta App Token in code.
META_APP_TOKEN: str = _resolve_secret(["META_APP_TOKEN", "META_AD_TOKEN", "MetaAd"], default_val="")
# Backward-compatibility alias
META_AD_TOKEN: str = META_APP_TOKEN

GCP_PROJECT_ID: str = _resolve_secret(["GCP_PROJECT_ID", "BigQuery"], default_val="virtualanalytics5122")
GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Google BigQuery Public Dataset identifiers
BIGQUERY_POLITICAL_ADS_DATASET: str = "bigquery-public-data.google_political_ads"
