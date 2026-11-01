DAILY EXPENSE TRACKER - PYTHON / FLASK VERSION
================================================

WINDOWS STARTUP
1. Install Python 3.10 or newer from https://www.python.org/downloads/ .
2. During installation, tick "Add Python to PATH". The standard pip and venv options should also be selected.
3. Extract this ZIP completely (do not run the app from inside the ZIP preview).
4. Open the extracted folder and double-click run.bat.
5. The first launch creates a local .venv folder and installs Flask. Internet access is needed for this one-time installation.
6. When the server starts, open http://127.0.0.1:5000 in Chrome or Edge.
7. Keep the black command window open while using the application. Press Ctrl+C to stop it.

SAMPLE LOGIN
Email: testuser@gmail.com
Password: Test@123
You can also register a new account.

FEATURES
- Login, registration and logout
- Dashboard expense totals
- Add and manage expenses (delete)
- Daywise, monthwise, yearwise and detailed reports
- User profile update (name, email and mobile number)
- Change password
- Forgot/reset password using registered email + mobile number
- SQLite database; XAMPP/MySQL is not required

TROUBLESHOOTING
- "Python was not found": install Python 3.10+ and select Add Python to PATH; then reopen run.bat.
- "Flask could not be installed": check internet access and firewall/proxy settings; first launch needs to download Flask.
- Browser says site can't be reached: ensure the black command window is still open and shows that Flask is running; use http://127.0.0.1:5000.
- Port 5000 already in use: close another local Flask app, or change port=5000 at the bottom of app.py to 5001 and browse to http://127.0.0.1:5001.
- Keep app.py, templates, static, original_detsdb.sql, requirements.txt and run.bat together in the same extracted folder.

DATABASE
The app creates detsdb.sqlite3 automatically. It attempts to import sample records from original_detsdb.sql once when the database is first created. Keep a backup of detsdb.sqlite3 after entering your own records.

This is a fresh Python implementation based on the supplied PHP project and database schema. It preserves the main Lumino/Bootstrap-style layout and workflow; it is not the original PHP runtime.
