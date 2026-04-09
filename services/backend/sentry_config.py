import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

SENTRY_DSN = os.getenv("SENTRY_DSN")


def init_sentry():
    """
    Initializes Sentry error monitoring.
    Call this once when the server starts.

    What Sentry does:
    - Catches all unhandled errors automatically
    - Records the full stack trace
    - Alerts you via email when something breaks
    - Tracks performance of your endpoints
    - Shows you exactly which line of code caused the error
    """
    if not SENTRY_DSN:
        print("⚠️ Sentry DSN not found — skipping error monitoring")
        return

    sentry_sdk.init(
        dsn=SENTRY_DSN,

        # Capture 100% of transactions for performance monitoring
        # In production you'd lower this to 0.1 (10%) to save quota
        traces_sample_rate=1.0,

        # Capture 100% of errors
        sample_rate=1.0,

        # FastAPI and Starlette integrations
        # These automatically capture request/response data
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],

        # Environment tag — helps you filter errors by environment
        environment=os.getenv("APP_ENV", "development"),

        # Release tag — helps you track which version caused the error
        release="signbridge-ai@1.0.0",
    )

    print("Sentry error monitoring initialized ✅")
