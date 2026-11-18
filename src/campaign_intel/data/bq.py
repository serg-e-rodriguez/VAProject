"""
Google BigQuery client.

Credentials, in order:
  1. Streamlit secrets: a `[gcp_service_account]` table holding a service-account key (Streamlit Community Cloud,
     or a local `.streamlit/secrets.toml`). See `.streamlit/secrets.toml.example`.
  2. Application Default Credentials: `gcloud auth application-default login`, or
     `GOOGLE_APPLICATION_CREDENTIALS` pointing at a key file (local runs and the snapshot build).

The billing project is `GCP_PROJECT_ID` from secrets, then the environment / `.env`, then the key's own project.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import streamlit as st

from campaign_intel.config import GCP_PROJECT_ID

logger = logging.getLogger(__name__)

SECRETS_KEY = "gcp_service_account"


def _secrets() -> Any | None:
    """st.secrets, or None when there is no secrets file (accessing it then raises)."""
    try:
        return st.secrets if len(st.secrets) else None
    except Exception:
        return None


def service_account_info() -> dict | None:
    """The service-account key from Streamlit secrets, or None if it isn't configured."""
    secrets = _secrets()
    if secrets is None or SECRETS_KEY not in secrets:
        return None
    info = dict(secrets[SECRETS_KEY])
    # Keys pasted with literal "\n" sequences (e.g. single-line strings) must become real newlines.
    if isinstance(info.get("private_key"), str):
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    return info


def project_id(info: dict | None = None) -> str:
    secrets = _secrets()
    from_secrets = secrets.get("GCP_PROJECT_ID") if secrets is not None else None
    return from_secrets or os.getenv("GCP_PROJECT_ID") or (info or {}).get("project_id") or GCP_PROJECT_ID


def make_client():
    """A BigQuery client from Streamlit secrets if present, otherwise Application Default Credentials.
    Raises if neither is available."""
    from google.cloud import bigquery

    info = service_account_info()
    if info is not None:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        logger.info("BigQuery: using the service account from Streamlit secrets")
        return bigquery.Client(project=project_id(info), credentials=creds)
    logger.info("BigQuery: using Application Default Credentials")
    return bigquery.Client(project=project_id())


@st.cache_resource
def get_bq_client():
    """Cached BigQuery client, or None if no credentials are available."""
    try:
        return make_client()
    except Exception as exc:
        logger.info("BigQuery client unavailable: %s", exc)
        return None


def test_connection() -> tuple[bool, str]:
    """Run SELECT 1. Returns (success, message); the message never includes key material."""
    try:
        client = make_client()
        client.query("SELECT 1").result()
        source = "Streamlit secrets" if service_account_info() is not None else "Application Default Credentials"
        return True, f"Connected to BigQuery (project '{client.project}', credentials from {source})."
    except Exception as exc:
        return False, f"BigQuery error: {type(exc).__name__}: {exc}"
