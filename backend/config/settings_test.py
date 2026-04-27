"""
Test settings for pytest. Keeps `manage.py` / production on `config.settings`.

- Default: in-memory SQLite (no Postgres, no CREATEDB).
- Opt-in: USE_POSTGRES_FOR_TESTS=1 — use DATABASE_URL from env / backend/.env like production.
"""

import os

_use_pg = os.environ.get("USE_POSTGRES_FOR_TESTS", "").lower() in ("1", "true", "yes")

if not _use_pg:
    # Must be set before importing config.settings (load_dotenv does not override existing keys).
    os.environ["DATABASE_URL"] = ""

from .settings import *  # noqa: E402, F403

if not _use_pg:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
