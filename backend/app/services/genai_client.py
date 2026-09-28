"""Shared Vertex AI GenAI client factory.

On Cloud Run (``K_SERVICE`` is set) the service account's Application Default
Credentials are used. Locally, ADC is frequently a different identity than the
one authorised for Vertex AI (it fails with ``403 aiplatform.endpoints.predict``),
so we prefer the active ``gcloud`` CLI account's access token instead — the same
strategy ``ws_live.get_bearer_token`` uses for the Live Bidi endpoint.
"""
import logging
import os
import subprocess
import threading
import time
from typing import Optional

from google import genai

from app.config import settings

logger = logging.getLogger("genai_client")

_TOKEN_TTL_SECONDS = 45 * 60  # gcloud tokens live ~60 min; refresh early.
_lock = threading.Lock()
_client: Optional[genai.Client] = None
_client_created_at: float = 0.0


def _gcloud_credentials():
    """Return OAuth credentials minted from the active gcloud account, or None."""
    try:
        token = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout.strip()
        if not token:
            return None
        from google.oauth2.credentials import Credentials
        return Credentials(token=token)
    except Exception as e:  # gcloud missing, not logged in, timeout...
        logger.warning(f"gcloud access token unavailable, falling back to ADC: {type(e).__name__}")
        return None


def get_genai_client() -> genai.Client:
    """Return a cached Vertex AI GenAI client with environment-appropriate credentials."""
    global _client, _client_created_at
    with _lock:
        on_cloud_run = bool(os.environ.get("K_SERVICE"))
        fresh = _client is not None and (on_cloud_run or time.time() - _client_created_at < _TOKEN_TTL_SECONDS)
        if fresh:
            return _client

        kwargs = dict(vertexai=True, project=settings.VERTEX_PROJECT_ID, location=settings.VERTEX_LOCATION)
        creds = None if on_cloud_run else _gcloud_credentials()
        if creds is not None:
            kwargs["credentials"] = creds
        _client = genai.Client(**kwargs)
        _client_created_at = time.time()
        logger.info(f"GenAI client initialised using {'gcloud CLI token' if creds else 'ADC'}")
        return _client
