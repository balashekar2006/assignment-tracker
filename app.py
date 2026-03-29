from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3, hashlib, os
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = 'tracker-secret-2024-xyz'
DB = 'tracker.db'

# ── DATABASE ──────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            email    TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            created  TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS assignments (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL,
            name     TEXT    NOT NULL,
            subject  TEXT    DEFAULT 'General',
            due_date TEXT    NOT NULL,
            priority TEXT    DEFAULT 'medium',
            type     TEXT    DEFAULT 'Homework',
            notes    TEXT,
            done     INTEGER DEFAULT 0,
            created  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')
    conn.commit()
    conn.close()

# ── HELPERS ───────────────────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def current_user():
    return session.get('user_id')

def days_until(due_str):
    try:
        return (datetime.strptime(due_str, '%Y-%m-%d').date() - date.today()).days
    except:
        return None

def enrich(t):
    t = dict(t)
    d = days_until(t['due_date'])
    if t['done']:
        t['due_status'] = 'done'
        t['due_label']  = t['due_date']
    elif d is not None and d < 0:
        t['due_status'] = 'overdue'
        t['due_label']  = f"Overdue by {abs(d)} day{'s' if abs(d)!=1 else ''}"
    elif d == 0:
        t['due_status'] = 'today'
        t['due_label']  = 'Due TODAY'
    elif d == 1:
        t['due_status'] = 'soon'
        t['due_label']  = 'Due TOMORROW'
    elif d and d <= 3:
        t['due_status'] = 'soon'
        t['due_label']  = f'Due in {d} days'
    else:
        t['due_status'] = 'normal'
        t['due_label']  = t['due_date']
    return t

# ── AUTH ROUTES ───────────────────────────────────────────────────
@app.route('/register', methods=['GET','POST'])
def register():
    if current_user():
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email    = request.form.get('email','').strip()
        password = request.form.get('password','')
        confirm  = request.form.get('confirm','')

        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters!', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username,email,password) VALUES (?,?,?)",
                (username, email, hash_pw(password))
            )
            conn.commit()
            flash(f'✅ Account created! Welcome, {username}! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user():
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_pw(password))
        ).fetchone()
        conn.close()

        if user:
            session['user_id']   = user['id']
            session['username']  = user['username']
            flash(f'👋 Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Wrong username or password!', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ── MAIN ROUTES ───────────────────────────────────────────────────
@app.route('/')
def index():
    if not current_user():
        return redirect(url_for('login'))

    uid   = current_user()
    f     = request.args.get('filter','all')
    today = date.today().isoformat()
    conn  = get_db()

    if f == 'pending':
        rows = conn.execute("SELECT * FROM assignments WHERE user_id=? AND done=0 ORDER BY due_date",(uid,)).fetchall()
    elif f == 'done':
        rows = conn.execute("SELECT * FROM assignments WHERE user_id=? AND done=1 ORDER BY due_date",(uid,)).fetchall()
    elif f == 'overdue':
        rows = conn.execute("SELECT * FROM assignments WHERE user_id=? AND done=0 AND due_date<? ORDER BY due_date",(uid,today)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM assignments WHERE user_id=? ORDER BY done ASC, due_date ASC",(uid,)).fetchall()

    total   = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=?",(uid,)).fetchone()[0]
    done    = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=? AND done=1",(uid,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=? AND done=0",(uid,)).fetchone()[0]
    overdue = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=? AND done=0 AND due_date<?",(uid,today)).fetchone()[0]
    conn.close()

    tasks = [enrich(r) for r in rows]
    return render_template('index.html',
        tasks=tasks, active=f,
        total=total, done=done, pending=pending, overdue=overdue,
        username=session.get('username'), today=today
    )

@app.route('/add', methods=['POST'])
def add():
    if not current_user():
        return redirect(url_for('login'))
    name     = request.form.get('name','').strip()
    subject  = request.form.get('subject','General').strip() or 'General'
    due_date = request.form.get('due_date','')
    priority = request.form.get('priority','medium')
    atype    = request.form.get('type','Homework')
    notes    = request.form.get('notes','').strip()

    if not name:
        flash('Please enter an assignment name!','error')
        return redirect(url_for('index'))
    if not due_date:
        flash('Please pick a due date!','error')
        return redirect(url_for('index'))

    conn = get_db()
    conn.execute(
        "INSERT INTO assignments (user_id,name,subject,due_date,priority,type,notes) VALUES (?,?,?,?,?,?,?)",
        (current_user(), name, subject, due_date, priority, atype, notes)
    )
    conn.commit()
    conn.close()
    flash(f'✅ "{name}" added!','success')
    return redirect(url_for('index'))

@app.route('/toggle/<int:tid>')
def toggle(tid):
    if not current_user():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("UPDATE assignments SET done=1-done WHERE id=? AND user_id=?",(tid, current_user()))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:tid>')
def delete(tid):
    if not current_user():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("DELETE FROM assignments WHERE id=? AND user_id=?",(tid, current_user()))
    conn.commit()
    conn.close()
    flash('🗑️ Deleted.','info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET','POST'])
def profile():
    if not current_user():
        return redirect(url_for('login'))

    uid  = current_user()
    conn = get_db()

    if request.method == 'POST':
        action = request.form.get('action')

        # ── Change Password ───────────────────────────────────────
        if action == 'change_password':
            old_pw  = request.form.get('old_password','')
            new_pw  = request.form.get('new_password','')
            confirm = request.form.get('confirm_password','')

            user = conn.execute(
                "SELECT * FROM users WHERE id=? AND password=?",
                (uid, hash_pw(old_pw))
            ).fetchone()

            if not user:
                flash('❌ Current password is wrong!', 'error')
            elif len(new_pw) < 6:
                flash('❌ New password must be at least 6 characters!', 'error')
            elif new_pw != confirm:
                flash('❌ New passwords do not match!', 'error')
            else:
                conn.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(new_pw), uid))
                conn.commit()
                flash('✅ Password changed successfully!', 'success')

        # ── Update Email ──────────────────────────────────────────
        elif action == 'update_email':
            new_email = request.form.get('email','').strip()
            if not new_email:
                flash('❌ Email cannot be empty!', 'error')
            else:
                try:
                    conn.execute("UPDATE users SET email=? WHERE id=?", (new_email, uid))
                    conn.commit()
                    flash('✅ Email updated!', 'success')
                except sqlite3.IntegrityError:
                    flash('❌ That email is already used by another account!', 'error')

        # ── Delete Account ────────────────────────────────────────
        elif action == 'delete_account':
            confirm_del = request.form.get('confirm_delete','')
            if confirm_del == session.get('username'):
                conn.execute("DELETE FROM assignments WHERE user_id=?", (uid,))
                conn.execute("DELETE FROM users WHERE id=?", (uid,))
                conn.commit()
                conn.close()
                session.clear()
                flash('Account deleted. Goodbye! 👋', 'info')
                return redirect(url_for('register'))
            else:
                flash('❌ Username did not match. Account not deleted.', 'error')

        conn.close()
        return redirect(url_for('profile'))

    # GET — load profile data
    user  = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    today = date.today().isoformat()

    total      = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=?", (uid,)).fetchone()[0]
    done       = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=? AND done=1", (uid,)).fetchone()[0]
    pending    = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=? AND done=0", (uid,)).fetchone()[0]
    overdue    = conn.execute("SELECT COUNT(*) FROM assignments WHERE user_id=? AND done=0 AND due_date<?", (uid, today)).fetchone()[0]
    subjects   = conn.execute("SELECT subject, COUNT(*) as cnt FROM assignments WHERE user_id=? GROUP BY subject ORDER BY cnt DESC LIMIT 5", (uid,)).fetchall()
    recent     = conn.execute("SELECT * FROM assignments WHERE user_id=? ORDER BY created DESC LIMIT 5", (uid,)).fetchall()
    conn.close()

    return render_template('profile.html',
        user=user, total=total, done=done,
        pending=pending, overdue=overdue,
        subjects=subjects, recent=recent,
        username=session.get('username')
    )


if __name__ == '__main__':
    init_db()
    print("\n✅ Tracker running! Go to: http://127.0.0.1:5000\n")
    app.run(debug=True)
