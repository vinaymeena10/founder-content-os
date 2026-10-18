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

# psycopg is used only when DATABASE_URL is configured (e.g. on Render).
try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:  # Local JSON mode can still run without the database dependency.
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


def _load_json_data():
    """Load the local JSON store (used locally and for one-time DB migration)."""
    with FileLock(str(LOCK_FILE)):
        if not DATA_FILE.exists():
            DATA_FILE.write_text(json.dumps(empty_data(), indent=2), encoding="utf-8")
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                data = {"items": data, "settings": empty_data()["settings"]}
            if not isinstance(data, dict):
                raise ValueError("JSON root must be an object or legacy list.")
            data.setdefault("items", [])
            data.setdefault("settings", empty_data()["settings"])
            data["settings"].setdefault("tier_targets", empty_data()["settings"]["tier_targets"])
            data["settings"].setdefault("recovery_options", [])
            return data
        except (json.JSONDecodeError, OSError, ValueError):
            logging.exception("Could not read content_data.json")
            raise


def _normalize_data(data):
    """Keep the stored structure compatible with all existing app screens."""
    if isinstance(data, list):
        data = {"items": data, "settings": empty_data()["settings"]}
    if not isinstance(data, dict):
        raise ValueError("Stored data must be an object or legacy list.")
    data.setdefault("items", [])
    data.setdefault("settings", empty_data()["settings"])
    data["settings"].setdefault("tier_targets", empty_data()["settings"]["tier_targets"])
    data["settings"].setdefault("recovery_options", [])
    changed = False
    for item in data["items"]:
        if not item.get("planned_month"):
            item["planned_month"] = (item.get("date") or "")[:7]
            changed = True
    return data, changed


def _database_url():
    """Read the secret from the environment; never hard-code credentials."""
    return os.environ.get("DATABASE_URL", "").strip()


def _connect_database():
    url = _database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if psycopg is None:
        raise RuntimeError("psycopg is missing. Install requirements.txt.")
    # Render URLs may use postgres://; psycopg accepts postgresql:// reliably.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return psycopg.connect(url, connect_timeout=10)


def _ensure_database_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS founder_content_state (
            id SMALLINT PRIMARY KEY CHECK (id = 1),
            payload JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _load_database_data():
    """Load app state from PostgreSQL, importing JSON once if the DB is empty."""
    with _connect_database() as conn:
        _ensure_database_table(conn)
        with conn.transaction():
            row = conn.execute(
                "SELECT payload FROM founder_content_state WHERE id = 1 FOR UPDATE"
            ).fetchone()
            if row is None:
                # First deploy: preserve existing JSON data if it is available.
                initial = _load_json_data()
                initial, _ = _normalize_data(initial)
                conn.execute(
                    "INSERT INTO founder_content_state (id, payload) VALUES (1, %s) ON CONFLICT (id) DO NOTHING",
                    (Jsonb(initial),),
                )
                row = conn.execute(
                    "SELECT payload FROM founder_content_state WHERE id = 1"
                ).fetchone()
            data, changed = _normalize_data(row[0])
            if changed:
                conn.execute(
                    "UPDATE founder_content_state SET payload = %s, updated_at = NOW() WHERE id = 1",
                    (Jsonb(data),),
                )
            return data


def load_data():
    """Use PostgreSQL in deployment; retain JSON storage for local development."""
    if _database_url():
        return _load_database_data()
    data, changed = _normalize_data(_load_json_data())
    if changed:
        save_data(data)
    return data


def _write_data_unlocked(data):
    """Atomic local JSON write helper; caller must hold the file lock."""
    if DATA_FILE.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = BACKUP_DIR / f"content_data_{stamp}.json"
        shutil.copy2(DATA_FILE, backup)
    temp_file = DATA_FILE.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(DATA_FILE)


def save_data(data):
    """Persist to PostgreSQL when configured, otherwise use the local JSON store."""
    data, _ = _normalize_data(data)
    if _database_url():
        with _connect_database() as conn:
            _ensure_database_table(conn)
            conn.execute(
                """
                INSERT INTO founder_content_state (id, payload, updated_at)
                VALUES (1, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = NOW()
                """,
                (Jsonb(data),),
            )
    else:
        with FileLock(str(LOCK_FILE)):
            _write_data_unlocked(data)
    logging.info("Saved content data; records=%s; backend=%s",
                 len(data.get("items", [])), "postgresql" if _database_url() else "json")


def normalize_date(value):
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def item_from_form(form, existing=None):
    existing = existing or {}
    date_value = normalize_date(form.get("date", ""))
    planned_month = valid_month(form.get("planned_month", ""))
    if not planned_month and date_value:
        planned_month = date_value[:7]

    status = form.get("status", "Idea")
    if status not in STATUSES:
        status = "Idea"

    return {
        "id": existing.get("id") or str(uuid.uuid4()),
        "date": date_value,
        "planned_month": planned_month,
        "action": form.get("action", "GO LIVE")
        if form.get("action") in ACTIONS else "GO LIVE",
        "tier": form.get("tier", "TIER 1")
        if form.get("tier") in TIERS else "TIER 1",
        "ip": form.get("ip", "").strip(),
        "brand_founder": form.get("brand_founder", "").strip(),
        "topic_brief": form.get("topic_brief", "").strip(),
        "format": form.get("format", "Other")
        if form.get("format") in FORMATS else "Other",
        "editor": form.get("editor", "").strip(),
        "brief_shared": bool(form.get("brief_shared")),
        "internal_approval": bool(form.get("internal_approval")),
        "founder_approval": bool(form.get("founder_approval")),
        "status": status,
        "remarks": form.get("remarks", "").strip(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return error
    logging.exception("Unhandled application error")
    if app.debug:
        raise error
    return render_template("error.html"), 500


def tier_progress(data, month_str):
    """Calculate tier targets, prior-month carry-forward, and delivery counts.

    A GO LIVE record counts as planned for its planned month. It counts as
    delivered only when its status is Published. Shortfalls carry forward
    without creating duplicate content records.
    """
    targets = data.get("settings", {}).get("tier_targets", empty_data()["settings"]["tier_targets"])
    try:
        selected = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
    except ValueError:
        selected = date.today().replace(day=1)
    # Work forward from the earliest month that actually has a content record.
    months_with_records = sorted({month_for_item(x) for x in data.get("items", []) if month_for_item(x) and month_for_item(x) <= month_str})
    previous_carry = {tier: 0 for tier in TIERS}
    if months_with_records:
        first = datetime.strptime(months_with_records[0], "%Y-%m").date().replace(day=1)
        cursor = first
        while cursor < selected:
            m = cursor.strftime("%Y-%m")
            month_items = [x for x in data.get("items", []) if month_for_item(x) == m and x.get("action") == "GO LIVE"]
            for tier in TIERS:
                base = int(targets.get(tier, 0) or 0)
                published = sum(1 for x in month_items if x.get("tier") == tier and x.get("status") == "Published")
                previous_carry[tier] = max(0, previous_carry[tier] + base - published)
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    current_items = [x for x in data.get("items", []) if month_for_item(x) == month_str and x.get("action") == "GO LIVE"]
    result = {}
    for tier in TIERS:
        base = int(targets.get(tier, 0) or 0)
        planned = sum(1 for x in current_items if x.get("tier") == tier)
        published = sum(1 for x in current_items if x.get("tier") == tier and x.get("status") == "Published")
        carry = previous_carry[tier]
        adjusted = base + carry
        # Current-month recovery need is based on planned GO LIVE items.
        # Actual delivery is shown separately; only published items reduce
        # the carry-forward calculation for completed prior months.
        planned_shortfall = max(0, adjusted - planned)
        result[tier] = {
            "base_target": base,
            "carryover": carry,
            "target": adjusted,
            "planned": planned,
            "published": published,
            "remaining": planned_shortfall,
            "shortfall": planned_shortfall,
            "delivery_shortfall": max(0, adjusted - published),
            "on_track": planned >= adjusted,
        }
    return result


@app.get("/")
def index():
    data = load_data()
    current_month = valid_month(request.args.get("month", "")) or date.today().strftime("%Y-%m")
    # The table shows only the selected calendar month. Earlier records remain
    # stored and are used by carry-forward calculations; no record is duplicated.
    items = [item for item in data["items"] if month_for_item(item) == current_month]
    items.sort(key=lambda x: (x.get("date") or "9999-12-31", x.get("brand_founder", "").lower()))
    tier_cards = tier_progress(data, current_month)
    return render_template("index.html", items=items, statuses=STATUSES, actions=ACTIONS,
        tiers=TIERS, formats=FORMATS, current_month=current_month,
        incomplete_count=sum(1 for x in data["items"] if x.get("status") == "Incomplete" and month_for_item(x) < current_month),
        tier_cards=tier_cards)


@app.post("/add")
def add_item():
    form = request.form
    if not form.get("brand_founder", "").strip() or not form.get("topic_brief", "").strip():
        flash("Brand/founder and topic/brief are required.", "error")
        return redirect(url_for("index"))
    if not normalize_date(form.get("date", "")):
        flash("Please enter a valid shoot/go-live date.", "error")
        return redirect(url_for("index"))
    planned_month = valid_month(form.get("planned_month", ""))
    if not planned_month:
        planned_month = normalize_date(form.get("date", ""))[:7]

    data = load_data()
    item = item_from_form(form)
    item["planned_month"] = planned_month
    data["items"].append(item)
    save_data(data)
    flash("Content item added.", "success")
    return redirect(url_for("index", month=planned_month))


@app.post("/edit/<item_id>")
def edit_item(item_id):
    data = load_data()
    for i, existing in enumerate(data["items"]):
        if existing.get("id") == item_id:
            form = request.form
            if not form.get("brand_founder", "").strip() or not form.get("topic_brief", "").strip():
                flash("Brand/founder and topic/brief are required.", "error")
                return redirect(url_for("index"))
            if not normalize_date(form.get("date", "")):
                flash("Please enter a valid shoot/go-live date.", "error")
                return redirect(url_for("index"))
            data["items"][i] = item_from_form(form, existing)
            save_data(data)
            flash("Content item updated.", "success")
            return redirect(url_for("index", month=month_for_item(data["items"][i]) or date.today().strftime("%Y-%m")))
    flash("Content item not found.", "error")
    return redirect(url_for("index"))


@app.post("/delete/<item_id>")
def delete_item(item_id):
    data = load_data()
    old_count = len(data["items"])
    data["items"] = [x for x in data["items"] if x.get("id") != item_id]
    if len(data["items"]) != old_count:
        save_data(data)
        flash("Content item deleted.", "success")
    else:
        flash("Content item not found.", "error")
    return redirect(url_for("index"))


@app.get("/calendar")
def calendar():
    data = load_data()
    month_str = valid_month(request.args.get("month", "")) or date.today().strftime("%Y-%m")
    month = datetime.strptime(month_str, "%Y-%m")
    year, month_num = month.year, month.month
    first_weekday, days_in_month = calendar_module.monthrange(year, month_num)
    weeks, week = [], [None] * first_weekday
    for day in range(1, days_in_month + 1):
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        weeks.append(week + [None] * (7 - len(week)))

    events = {}
    for item in data["items"]:
        event_date = item.get("date", "")
        if event_date.startswith(f"{year:04d}-{month_num:02d}-"):
            events.setdefault(int(event_date[-2:]), []).append(item)

    previous = (date(year, month_num, 1) - timedelta(days=1)).strftime("%Y-%m")
    next_month_date = date(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1)
    next_month = next_month_date.strftime("%Y-%m")

    return render_template(
        "calendar.html",
        year=year,
        month_name=month.strftime("%B"),
        month_str=month_str,
        weeks=weeks,
        events=events,
        previous=previous,
        next_month=next_month,
    )


@app.get("/summary")
def summary():
    data = load_data()
    month_str = valid_month(request.args.get("month", "")) or date.today().strftime("%Y-%m")
    month_items = [x for x in data["items"] if month_for_item(x) == month_str]
    published = [x for x in month_items if x.get("action") == "GO LIVE" and x.get("status") == "Published"]
    tier_cards = tier_progress(data, month_str)
    return render_template("summary.html", month_str=month_str, total=len(month_items),
        published=len(published), pending=sum(1 for x in month_items if x.get("status") not in ("Published", "On hold")),
        shoots=sum(1 for x in month_items if x.get("action") == "SHOOT"),
        targets=data.get("settings", {}).get("tier_targets", empty_data()["settings"]["tier_targets"]),
        tier_counts={tier: tier_cards[tier]["published"] for tier in TIERS}, items=month_items,
        tier_cards=tier_cards)


@app.get("/recovery")
def recovery():
    data = load_data()
    month_str = valid_month(request.args.get("month", "")) or date.today().strftime("%Y-%m")
    tier_cards = tier_progress(data, month_str)
    options = data.get("settings", {}).get("recovery_options", [])
    return render_template("recovery.html", month_str=month_str, tier_cards=tier_cards,
                           options=options, tiers=TIERS)


@app.post("/recovery/add")
def add_recovery_option():
    brand = request.form.get("brand", "").strip()
    tier = request.form.get("tier", "TIER 1")
    notes = request.form.get("notes", "").strip()
    if not brand:
        flash("Enter a brand or backup option name.", "error")
        return redirect(url_for("recovery"))
    if tier not in TIERS:
        tier = "TIER 1"
    data = load_data()
    data.setdefault("settings", {}).setdefault("recovery_options", []).append({
        "id": str(uuid.uuid4()), "brand": brand, "tier": tier, "notes": notes,
        "created_at": datetime.now().isoformat(timespec="seconds")})
    save_data(data)
    flash("Recovery option added.", "success")
    return redirect(url_for("recovery"))


@app.post("/recovery/delete/<option_id>")
def delete_recovery_option(option_id):
    data = load_data()
    options = data.setdefault("settings", {}).setdefault("recovery_options", [])
    data["settings"]["recovery_options"] = [x for x in options if x.get("id") != option_id]
    save_data(data)
    flash("Recovery option removed.", "success")
    return redirect(url_for("recovery"))


if __name__ == "__main__":
    load_data()
    # Local development only; deploy behind a production WSGI server for team access.
    app.run(host="127.0.0.1", port=5000, debug=True)
