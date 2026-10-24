"""
Google BigQuery Client initialization using GCP_PROJECT_ID.
"""

import logging

import streamlit as st
from google.cloud import bigquery

from campaign_intel.config import GCP_PROJECT_ID

logger = logging.getLogger(__name__)


@st.cache_resource
def get_bq_client() -> bigquery.Client | None:
    """
    Initializes BigQuery client using GCP_PROJECT_ID directly.
    Returns None if client creation fails.
    """
    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
        return client
    except Exception as exc:
        logger.info(f"BigQuery client unavailable: {exc}")
        return None


def test_connection() -> tuple[bool, str]:
    """
    Tests connection to BigQuery with a simple SELECT 1 query using GCP_PROJECT_ID.
    Returns (success, message).
    """
    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
        query_job = client.query("SELECT 1")
        _ = query_job.result()
        return True, f"Successfully connected to BigQuery with project '{GCP_PROJECT_ID}'!"
    except Exception as exc:
        return False, f"BigQuery error: {exc}"
