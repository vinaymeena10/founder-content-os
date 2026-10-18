from datetime import date, datetime, timedelta
from pathlib import Path
import calendar as calendar_module
import json
import logging
import os
import shutil
import uuid

from flask import Flask, flash, redirect, render_template, request, url_for
from filelock import FileLock
try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg = None
    Jsonb = None

from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "content_data.json"
LOCK_FILE = BASE_DIR / "content_data.json.lock"
BACKUP_DIR = BASE_DIR / "backups"
LOG_DIR = BASE_DIR / "logs"

BACKUP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-before-deployment")

STATUSES = [
    "Idea",
    "Brief in progress",
    "Awaiting approval",
    "Ready to shoot",
    "Shot",
    "Editing",
    "Scheduled",
    "Published",
    "Incomplete",
    "On hold",
]
ACTIONS = ["SHOOT", "GO LIVE"]
FORMATS = ["Reel", "Carousel", "Story", "Static post", "Video", "Short", "Long-form", "Other"]
TIERS = ["TIER 1", "TIER 2", "TIER 3"]
ACTIVE_STATUSES = set(STATUSES) - {"Published", "On hold"}


def empty_data():
    return {
        "items": [],
        "settings": {
            "tier_targets": {"TIER 1": 2, "TIER 2": 6, "TIER 3": 9},
            "recovery_options": [],
        },
    }


def valid_month(value):
    """Return YYYY-MM if valid; otherwise an empty string."""
    try:
        return datetime.strptime(value or "", "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return ""


def month_for_item(item):
    """
    Workload month is planned_month. For older records without that field,
    fall back to the month from the existing date.
    """
    planned = valid_month(item.get("planned_month", ""))
    if planned:
        return planned
    item_date = item.get("date", "")
    return item_date[:7] if valid_month(item_date[:7]) else ""
def get_database_url():
    return os.environ.get("DATABASE_URL", "").strip()


def connect_database():
    url = get_database_url()

    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    if psycopg is None:
        raise RuntimeError(
            "PostgreSQL driver missing. Install psycopg[binary]."
        )

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    return psycopg.connect(url, connect_timeout=10)


def ensure_database_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS founder_content_state (
            id SMALLINT PRIMARY KEY CHECK (id = 1),
            payload JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _normalize_data(data):
    """Keep stored data compatible with all app screens."""
    if isinstance(data, list):
        data = {
            "items": data,
            "settings": empty_data()["settings"],
        }

    if not isinstance(data, dict):
        raise ValueError("Stored data must be an object or legacy list.")

    data.setdefault("items", [])
    data.setdefault("settings", empty_data()["settings"])
    data["settings"].setdefault(
        "tier_targets",
        empty_data()["settings"]["tier_targets"],
    )
    data["settings"].setdefault("recovery_options", [])

    for item in data["items"]:
        if not item.get("planned_month"):
            item["planned_month"] = (item.get("date") or "")[:7]

    return data


def _load_json_data():
    """Read the existing local JSON data safely."""
    with FileLock(str(LOCK_FILE)):
        if not DATA_FILE.exists():
            DATA_FILE.write_text(
                json.dumps(empty_data(), indent=2),
                encoding="utf-8",
            )

        try:
            data = json.loads(
                DATA_FILE.read_text(encoding="utf-8")
            )
            return _normalize_data(data)
        except (json.JSONDecodeError, OSError, ValueError):
            logging.exception("Could not read content_data.json")
            raise


def _load_database_data():
    """Load data from PostgreSQL, importing JSON on first use."""
    with connect_database() as conn:
        ensure_database_table(conn)

        with conn.transaction():
            row = conn.execute(
                "SELECT payload FROM founder_content_state WHERE id = 1"
            ).fetchone()

            if row is None:
                # Preserve existing JSON data on the first deployment.
                initial = _load_json_data()

                conn.execute(
                    """
                    INSERT INTO founder_content_state (id, payload)
                    VALUES (1, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (Jsonb(initial),),
                )

                row = conn.execute(
                    "SELECT payload FROM founder_content_state WHERE id = 1"
                ).fetchone()

            data = _normalize_data(row[0])

            conn.execute(
                """
                UPDATE founder_content_state
                SET payload = %s, updated_at = NOW()
                WHERE id = 1
                """,
                (Jsonb(data),),
            )

            return data


def load_data():
    """Use PostgreSQL on Render and JSON locally."""
    if get_database_url():
        return _load_database_data()

    return _load_json_data()


def _write_data_unlocked(data):
    """Write local JSON safely; caller must hold the file lock."""
    if DATA_FILE.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = BACKUP_DIR / f"content_data_{stamp}.json"
        shutil.copy2(DATA_FILE, backup)

    temp_file = DATA_FILE.with_suffix(".json.tmp")
    temp_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp_file.replace(DATA_FILE)


def save_data(data):
    """Save to PostgreSQL on Render and JSON locally."""
    data = _normalize_data(data)

    if get_database_url():
        with connect_database() as conn:
            ensure_database_table(conn)
            conn.execute(
                """
                INSERT INTO founder_content_state
                    (id, payload, updated_at)
                VALUES (1, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                SET payload = EXCLUDED.payload,
                    updated_at = NOW()
                """,
                (Jsonb(data),),
            )
    else:
        with FileLock(str(LOCK_FILE)):
            _write_data_unlocked(data)

    logging.info(
        "Saved content data; records=%s",
        len(data.get("items", [])),
    )
