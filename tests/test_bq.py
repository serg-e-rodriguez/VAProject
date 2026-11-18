"""BigQuery credentials: Streamlit secrets first, Application Default Credentials otherwise. No network calls."""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from campaign_intel.data import bq


def _fake_key_info() -> dict:
    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    return {"type": "service_account", "project_id": "key-project", "private_key_id": "x",
            "private_key": pem.replace("\n", "\\n"),  # as if pasted as a one-line string
            "client_email": "sa@key-project.iam.gserviceaccount.com", "client_id": "1",
            "token_uri": "https://oauth2.googleapis.com/token"}


def test_client_uses_service_account_from_secrets(monkeypatch):
    info = _fake_key_info()
    monkeypatch.setattr(bq, "_secrets", lambda: {"gcp_service_account": info, "GCP_PROJECT_ID": "billing-project"})
    client = bq.make_client()
    assert client.project == "billing-project"
    assert client._credentials.service_account_email == "sa@key-project.iam.gserviceaccount.com"
    assert "\n" in bq.service_account_info()["private_key"]


def test_project_falls_back_to_key_project(monkeypatch):
    monkeypatch.setattr(bq, "_secrets", lambda: {"gcp_service_account": _fake_key_info()})
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    assert bq.project_id(bq.service_account_info()) == "key-project"


def test_no_secrets_uses_default_credentials(monkeypatch):
    monkeypatch.setattr(bq, "_secrets", lambda: None)
    assert bq.service_account_info() is None
    seen = {}

    class FakeClient:
        def __init__(self, project=None, credentials=None):
            seen.update(project=project, credentials=credentials)

    monkeypatch.setattr("google.cloud.bigquery.Client", FakeClient)
    bq.make_client()
    assert seen["credentials"] is None  # google-auth picks up ADC itself
