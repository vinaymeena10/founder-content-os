# Founder Content OS

White-and-blue content planning dashboard with PostgreSQL support for Render and JSON storage for local development.

## Features
- Content Hub, Calendar, Summary, and Recovery pages.
- Editable content records with SHOOT / GO LIVE, tier, and status.
- Tier scoreboard on the Content Hub: published GO LIVE items versus each tier's target (Tier 1: 2, Tier 2: 6, Tier 3: 9 by default).
- A Carry Forward card showing the cumulative number of pieces below the monthly target from previous tracked months.
- Overall monthly target defaults to 20 published GO LIVE pieces.
- A GO LIVE item counts as delivered only when its status is `Published`.
- Tier labels are normalized when stored data is loaded so `tier 3`, `Tier-3`, and `TIER 3` are counted consistently.
- Render PostgreSQL persistence via `DATABASE_URL`; local JSON persistence when `DATABASE_URL` is not set.
- Local JSON backup and file-lock behavior.

## Run locally
```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000.

## Render
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set `DATABASE_URL` to the Render PostgreSQL internal connection URL.
- Keep database credentials in Render environment variables; do not commit them.

The app imports `content_data.json` into PostgreSQL only if the database has no saved application state yet. Existing PostgreSQL data takes precedence on subsequent deployments.

## Counting rules
- Tier scoreboard counts only records with action `GO LIVE`, the matching tier, and status `Published`.
- The overall carry-forward calculation uses the 20-piece monthly target and published GO LIVE items in previous tracked months. It adds previous shortfall to the next month and never duplicates content records.
- Tier planning shortfalls on Recovery remain a separate measure from actual published delivery.
