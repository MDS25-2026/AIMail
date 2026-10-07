"""The one place the backend builds a Gemini client, so every call has a deadline and retries."""

from google import genai
from google.genai import types

from app.core.config import get_settings

# Milliseconds, the SDK's unit. Without a timeout the SDK waits on a stalled call forever.
REQUEST_TIMEOUT_MS = 20_000
# Two attempts at 20 s keep embedding well inside the dashboard's own 120 s generation budget.
_RETRY = types.HttpRetryOptions(
    attempts=2,
    initial_delay=1.0,
    max_delay=8.0,
    http_status_codes=[408, 429, 500, 502, 503, 504],
)


def gemini_client() -> genai.Client:
    return genai.Client(
        api_key=get_settings().google_api_key,
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS, retry_options=_RETRY),
    )
