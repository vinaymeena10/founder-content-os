# Founder Content OS — tier planning and recovery update

## Features
- Content Hub uses three tier cards instead of generic total/status KPI boxes.
- Tier cards show planned GO LIVE items, actual Published items, base target, carry-forward, and adjusted target.
- Monthly shortfalls carry forward without duplicating old content records.
- Content Hub table shows only the selected month; history remains in `content_data.json`.
- Calendar events display action, brand/founder, IP name, and topic.
- Recovery tab lets you maintain backup brand/IP options by tier and highlights tier shortfalls.
- Local JSON storage with file locking and backups remains in place in this version.

## Run locally
```bash
pip install -r requirements.txt
python app.py
```
Then open http://127.0.0.1:5000.

## Notes
- A GO LIVE item counts as planned when its action is `GO LIVE` and it is assigned to the selected planned month.
- It counts as delivered only when its status is `Published`.
- Carry-forward is calculated from previous months that contain records. Review the target settings and month records as you begin using the dashboard.
- This update does not implement PostgreSQL persistence yet; it focuses on the dashboard, calendar, and recovery workflow.


Logo setup: place your horizontal Razorpay wordmark at `static/razorpay-icon.png`. The sidebar displays it directly on the navy background without a frame. Keep the file name exactly as shown or update the image filename in `templates/base.html`.
