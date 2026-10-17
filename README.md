
# Founder Content OS — MVP

A Flask website prototype for managing a founder/brand content pipeline. It uses local JSON storage and does not use Google Sheets or Google OAuth.

## Pages
- Content Hub: create, edit, search, and delete content records
- Calendar: monthly view of shoot and go-live dates
- Summary: monthly KPIs and tier progress

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract this folder somewhere easy to find.
3. Open Command Prompt in this folder and run:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your browser.

## Important before organization-wide use

This is a local development MVP. It currently binds to `127.0.0.1`, so only the same computer can access it. For organizational access, deploy it on an approved company server or cloud environment, use a production server such as Waitress, enable HTTPS, add authentication and role permissions, and configure backups. Do not expose this prototype publicly as-is.

## JSON storage

Records are stored in `content_data.json`. Each save creates a timestamped backup in `backups/`, and application logs go to `logs/app.log`. The app uses a file lock and atomic replacement to reduce the risk of conflicting writes.

The initial tier targets are placeholders copied from one earlier prototype: Tier 1 = 2, Tier 2 = 6, Tier 3 = 9. Confirm these targets before relying on the Summary page.

## Suggested next steps
1. Confirm fields, statuses, tier targets, and monthly KPI definitions.
2. Add login and role-based permissions.
3. Deploy to an organization-approved server.
4. Test simultaneous editing, backup restore, and error handling.
