FOUNDER CONTENT OS — VISUAL REFRESH PATCH

This patch updates only the visual shell and interactions:
- templates/base.html
- static/style.css
- static/app.js

It does NOT include or replace app.py or content_data.json. Your saved records are not modified.

INSTALL IN VS CODE (Windows)
1. Stop Flask with Ctrl+C in the terminal.
2. In File Explorer, make a backup copy of your existing content_data.json (for example content_data_backup_before_design.json). Do not replace it with any file from this ZIP.
3. Extract this ZIP to a temporary folder.
4. Copy the three included files into your existing project, keeping the same folders. Choose Replace when Windows asks.
5. Start the app the same way you currently do and refresh the browser with Ctrl+F5.
6. Test Content Hub, add/edit a test record, search, Calendar, and Summary. Check that existing records remain.

BRANDING NOTE
The sidebar uses a custom blue lightning emblem and Razorpay wordmark styling as a visual treatment. If your organization has an approved official Razorpay logo SVG, use that approved asset in place of the inline SVG in templates/base.html. Do not use this prototype publicly until hosting, authentication, and permissions are configured.

The cursor is a subtle decorative halo and keeps normal browser cursor behavior. It is disabled on touch screens and when reduced motion is enabled.
