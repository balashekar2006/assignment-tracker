================================================
  Assignment Tracker — FLASK + LOGIN VERSION
  Each student has their own private account!
================================================

HOW TO RUN
----------
1. Install Python from https://python.org
   ⚠️  Check "Add Python to PATH" during install!

2. Open this folder in VS Code
   File → Open Folder → select flask_auth folder

3. Open terminal in VS Code (Ctrl + `)

4. Install Flask (only once):
      pip install flask

5. Run the app:
      python app.py

6. Open browser → http://127.0.0.1:5000

HOW IT WORKS
------------
- Go to /register  → Create your student account
- Go to /login     → Login with username + password
- Dashboard        → See ONLY your own assignments
- Each student's data is completely separate!

DATABASE (tracker.db - auto created)
-------------------------------------
Table: users
  - id, username, email, password (hashed), created

Table: assignments
  - id, user_id (links to user), name, subject,
    due_date, priority, type, notes, done, created

Every assignment is linked to a user_id so students
only ever see their own assignments. 🔒
================================================
