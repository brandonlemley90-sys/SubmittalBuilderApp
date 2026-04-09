"""
Submittal Builder Meta Agent - v2.0.0
PythonAnywhere Edition – Full Upload Workflow with Email Admin Reset
"""
import os
import sys
import io
import uuid
import sqlite3
import queue
import json
import hmac
import hashlib
import time
import zipfile
import smtplib
from datetime import timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, send_from_directory, send_file)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ─────────────────────────────────────────────────────────────
# 1.  SMTP CONFIG
# ─────────────────────────────────────────────────────────────
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587
SMTP_USER      = "brandonlemley90@gmail.com"
SMTP_PASS      = "rikkctuvlxspciqr"          # Gmail App Password (no spaces)
SMTP_FROM_NAME = "Denier Submittal Builder"

# ─────────────────────────────────────────────────────────────
# 2.  PATHS & DATABASE
# ─────────────────────────────────────────────────────────────
if os.name == 'nt':
    app_data_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'DenierAI')
else:
    app_data_dir = os.path.expanduser('~/.denierai')

UPLOAD_DIR  = os.path.join(app_data_dir, 'uploads')
RESULTS_DIR = os.path.join(app_data_dir, 'results')
DB_PATH     = os.path.join(app_data_dir, 'users.db')

for _d in [app_data_dir, UPLOAD_DIR, RESULTS_DIR]:
    os.makedirs(_d, exist_ok=True)

MASTER_ADMIN_KEY = "DenierSubmittalsLemley90"
SUPER_ADMINS     = ['blemley@denier.com', 'brandonlemley90@gmail.com']

output_queue = queue.Queue()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            email    TEXT PRIMARY KEY,
            password TEXT,
            api_key  TEXT,
            pin      TEXT,
            is_admin INTEGER DEFAULT 0,
            name     TEXT    DEFAULT ""
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email    TEXT,
            upload_path   TEXT,
            api_key       TEXT,
            status        TEXT     DEFAULT "pending",
            result_pdf    TEXT,
            result_excel  TEXT,
            logs          TEXT     DEFAULT "",
            project_name  TEXT     DEFAULT "",
            output_folder TEXT     DEFAULT "",
            timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        # Migrate existing DBs – add output_folder column if not present
        try:
            c.execute("ALTER TABLE jobs ADD COLUMN output_folder TEXT DEFAULT ''")
        except Exception:
            pass  # Already exists
        # Browse requests – persisted in DB so multi-process Flask works correctly
        c.execute('''CREATE TABLE IF NOT EXISTS browse_requests (
            email   TEXT PRIMARY KEY,
            status  TEXT DEFAULT "pending",
            path    TEXT,
            created DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        # Worker heartbeat – single row, updated every ~30s by the local worker
        c.execute('''CREATE TABLE IF NOT EXISTS worker_ping (
            id        INTEGER PRIMARY KEY CHECK (id = 1),
            last_ping TEXT
        )''')
        try:
            c.execute("INSERT OR IGNORE INTO worker_ping (id, last_ping) VALUES (1, NULL)")
        except Exception:
            pass
        # Always guarantee super-admin status for these accounts
        for email in SUPER_ADMINS:
            c.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
        conn.commit()


init_db()


def resource_path(relative_path):
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


# ─────────────────────────────────────────────────────────────
# 3.  FLASK APP
# ─────────────────────────────────────────────────────────────
app = Flask(__name__,
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))
app.secret_key = "denier_vault_production_2026"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024   # 500 MB


def _sign_payload(p: str) -> str:
    return hmac.new(MASTER_ADMIN_KEY.encode(), p.encode(), hashlib.sha256).hexdigest()


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via Gmail SMTP."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg['To']      = to
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def _check_worker_auth() -> bool:
    return request.headers.get('Authorization') == MASTER_ADMIN_KEY


def get_local_version():
    try:
        with open(resource_path('version.json')) as f:
            return json.load(f).get('version', 'unknown')
    except Exception:
        return '2.0.0'


@app.context_processor
def inject_version():
    return dict(version=get_local_version())


# ─────────────────────────────────────────────────────────────
# 4.  CORE AUTH ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute(
            "SELECT name FROM users WHERE email = ?",
            (session['user_email'],)).fetchone()
    user_name = user[0] if user and user[0] else ""
    return render_template('index.html',
                           is_admin=session.get('is_admin'),
                           user_email=session['user_email'],
                           user_name=user_name)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with sqlite3.connect(DB_PATH) as conn:
            user = conn.execute(
                "SELECT password, is_admin FROM users WHERE email = ?",
                (email,)).fetchone()
        if user and check_password_hash(user[0], password):
            session.permanent = True
            session.update({'logged_in': True,
                            'user_email': email,
                            'is_admin': bool(user[1])})
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid email or password.")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name     = request.form.get('name', '')
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
                    (email, generate_password_hash(password), name))
            return redirect(url_for('login'))
        except Exception:
            return render_template('registration.html',
                                   error="Email already registered.")
    return render_template('registration.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/reset')
def reset_page():
    return render_template('reset.html')


# ─────────────────────────────────────────────────────────────
# 5.  ACCOUNT ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    name = request.json.get('name', '')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET name = ? WHERE email = ?",
                     (name, session['user_email']))
    return jsonify({"status": "success"})


@app.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    old_pw = request.json.get('old_password')
    new_pw = request.json.get('new_password')
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute(
            "SELECT password FROM users WHERE email = ?",
            (session['user_email'],)).fetchone()
        if user and check_password_hash(user[0], old_pw):
            conn.execute("UPDATE users SET password = ? WHERE email = ?",
                         (generate_password_hash(new_pw), session['user_email']))
            return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Incorrect current password."}), 400


@app.route('/save_api_vault', methods=['POST'])
def save_api_vault():
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    api_key = request.json.get('api_key')
    pin     = request.json.get('pin')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET api_key = ?, pin = ? WHERE email = ?",
                     (api_key, pin, session['user_email']))
    return jsonify({"status": "success"})


@app.route('/unlock_api_vault', methods=['POST'])
def unlock_api_vault():
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    pin = request.json.get('pin')
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute(
            "SELECT api_key, pin FROM users WHERE email = ?",
            (session['user_email'],)).fetchone()
    if user and user[1] == pin and user[0]:
        return jsonify({"status": "success", "api_key": user[0]})
    return jsonify({"status": "error", "message": "Invalid PIN or no key saved."}), 400


# ─────────────────────────────────────────────────────────────
# 6.  ADMIN ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/admin/promote_self', methods=['POST'])
def promote_self():
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    if request.json.get('secret_key') != MASTER_ADMIN_KEY:
        return jsonify({"status": "error", "message": "Invalid key."}), 403
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET is_admin = 1 WHERE email = ?",
                     (session['user_email'],))
    session['is_admin'] = True
    return jsonify({"status": "success"})


@app.route('/admin/list_users')
def admin_list_users():
    if not session.get('is_admin'):
        return jsonify({"status": "error"}), 403
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT email, name, is_admin FROM users ORDER BY email"
        ).fetchall()
    return jsonify({
        "users": [{"email": r[0], "name": r[1], "is_admin": bool(r[2])}
                  for r in rows]
    })


@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not session.get('is_admin'):
        return jsonify({"status": "error"}), 403
    email = request.json.get('email', '').strip().lower()
    if email in SUPER_ADMINS:
        return jsonify({"status": "error",
                        "message": "Cannot delete a super admin account."}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM users WHERE email = ?", (email,))
    return jsonify({"status": "success"})


@app.route('/admin/send_reset_email', methods=['POST'])
def admin_send_reset_email():
    """Admin resets a locked-out user's password and emails them the temp password."""
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"}), 403

    email   = request.json.get('email', '').strip().lower()
    temp_pw = request.json.get('temp_password', '').strip()

    if not email or not temp_pw:
        return jsonify({"status": "error",
                        "message": "User email and temporary password are required."}), 400

    # Verify the user account exists
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute("SELECT email FROM users WHERE email = ?",
                            (email,)).fetchone()
    if not user:
        return jsonify({"status": "error",
                        "message": f"No account found for {email}. They may need to register first."}), 404

    # Update password in DB
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET password = ? WHERE email = ?",
                     (generate_password_hash(temp_pw), email))

    # Build and send email
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;
                background:#1a1a1a;color:#e0e0e0;border-radius:14px;overflow:hidden;
                border:1px solid #1d4d37;">
      <div style="background:#008751;padding:28px 32px;text-align:center;">
        <h1 style="margin:0;font-size:18px;letter-spacing:3px;color:#fff;font-weight:900;">
          DENIER SUBMITTAL BUILDER
        </h1>
        <p style="margin:6px 0 0;font-size:11px;color:rgba(255,255,255,0.7);
                  letter-spacing:2px;text-transform:uppercase;">Admin Password Reset</p>
      </div>

      <div style="padding:36px 32px;">
        <h2 style="color:#00c87a;margin-top:0;font-size:20px;">Your Password Has Been Reset</h2>
        <p style="color:#bbb;line-height:1.6;">
          Your administrator has set a temporary password for your account.
          Please log in immediately and update your password in Account Settings.
        </p>

        <div style="background:#111;border:1px solid #008751;border-radius:10px;
                    padding:20px;margin:24px 0;text-align:center;">
          <p style="margin:0;color:#777;font-size:11px;text-transform:uppercase;
                    letter-spacing:2px;">Your Temporary Password</p>
          <p style="margin:12px 0 0;font-size:28px;font-weight:900;
                    color:#00e090;letter-spacing:4px;font-family:monospace;">{temp_pw}</p>
        </div>

        <a href="https://lemley.pythonanywhere.com/login"
           style="display:block;background:#008751;color:#fff;text-align:center;
                  padding:14px;border-radius:8px;text-decoration:none;
                  font-weight:bold;letter-spacing:2px;font-size:13px;
                  text-transform:uppercase;">
          Log In Now →
        </a>

        <p style="color:#555;font-size:12px;margin-top:20px;line-height:1.6;">
          If you did not expect this email, contact your administrator or ignore it.
          This temporary password does not expire automatically — change it immediately.
        </p>
      </div>

      <div style="background:#0d0d0d;padding:16px;text-align:center;
                  color:#444;font-size:11px;letter-spacing:1px;">
        © 2026 Denier Electric · Submittal Builder Agent
      </div>
    </div>
    """

    sent = send_email(
        to      = email,
        subject = "Denier Submittal Builder — Your Temporary Password",
        html_body = html_body
    )

    if sent:
        return jsonify({"status": "success",
                        "message": f"Password updated and email sent to {email}."})
    else:
        # Password was updated even if email failed
        return jsonify({"status": "warning",
                        "message": f"Password updated but email failed to send. "
                                   f"Tell the user their password is: {temp_pw}"}), 207


# Legacy .denierreset token (kept for backwards compat with old reset.html)
@app.route('/admin/generate_reset_token', methods=['POST'])
def generate_reset_token():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"}), 403
    email   = request.json.get('email')
    new_pw  = request.json.get('new_password')
    expires = int(time.time()) + 72 * 3600
    payload = f"{email}|{new_pw}|{expires}"
    sig     = _sign_payload(payload)
    token   = {"email": email, "new_password": new_pw, "expires": expires, "sig": sig}
    return jsonify({"status": "success", "token": token,
                    "filename": f"reset_{email.split('@')[0]}.denierreset"})


@app.route('/apply_reset', methods=['POST'])
def apply_reset():
    data    = request.json
    token   = data.get('token')
    if not token:
        return jsonify({"status": "error", "message": "No token provided."}), 400
    email   = token.get('email')
    new_pw  = token.get('new_password')
    expires = token.get('expires')
    sig     = token.get('sig')
    if _sign_payload(f"{email}|{new_pw}|{expires}") != sig:
        return jsonify({"status": "error", "message": "Invalid token signature."}), 400
    if time.time() > expires:
        return jsonify({"status": "error", "message": "Token has expired."}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET password = ? WHERE email = ?",
                     (generate_password_hash(new_pw), email))
    return jsonify({"status": "success",
                    "message": "Password reset successful. Please log in with your temporary password."})


# ─────────────────────────────────────────────────────────────
# 7.  FILE UPLOAD & JOB QUEUE
# ─────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'xlsm', 'xlsx', 'xls', 'pdf', 'doc', 'docx', 'txt', 'csv'}


def _allowed(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_and_submit', methods=['POST'])
def upload_and_submit():
    """
    Accept uploaded project files from the browser, save them to the server,
    and queue a job for the local Windows worker to process.
    """
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    api_key       = request.form.get('api_key', '').strip()
    project_name  = request.form.get('project_name', 'Untitled Project').strip()
    output_folder = request.form.get('output_folder', '').strip()

    if not api_key:
        return jsonify({"status": "error",
                        "message": "Gemini API Key is required."}), 400

    # Create a unique upload directory for this submission
    job_folder_id  = str(uuid.uuid4())[:12]
    job_upload_dir = os.path.join(UPLOAD_DIR, job_folder_id)
    os.makedirs(job_upload_dir, exist_ok=True)

    saved_files = []
    for field in ['excel', 'specs', 'drawings', 'form', 'contract']:
        file = request.files.get(field)
        if file and file.filename:
            filename  = secure_filename(file.filename)
            save_path = os.path.join(job_upload_dir, filename)
            file.save(save_path)
            saved_files.append(filename)

    if not saved_files:
        return jsonify({"status": "error",
                        "message": "No files received. Please attach at least the Excel workbook."}), 400

    has_excel = any(f.lower().endswith(('.xlsm', '.xlsx', '.xls'))
                    for f in saved_files)
    if not has_excel:
        return jsonify({"status": "error",
                        "message": "An Excel workbook (.xlsm / .xlsx) is required."}), 400

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO jobs (user_email, upload_path, api_key, project_name, output_folder) "
            "VALUES (?, ?, ?, ?, ?)",
            (session['user_email'], job_folder_id, api_key, project_name, output_folder))
        job_id = cur.lastrowid

    return jsonify({
        "status":   "success",
        "message":  f"Job #{job_id} queued. Your Windows worker will pick it up shortly.",
        "job_id":   job_id,
        "files":    saved_files
    })


# ─────────────────────────────────────────────────────────────
# OUTPUT FOLDER BROWSE HANDSHAKE  (DB-backed — safe for multi-process)
# Flow: Browser → /api/request_browse_output
#       Worker  → /api/worker/check_browse_output  (polls every 2 s)
#       Worker  → opens tkinter folder dialog
#       Worker  → /api/worker/submit_browse_output  (posts selected path)
#       Browser → /api/poll_browse_output           (polls, receives path)
# ─────────────────────────────────────────────────────────────

@app.route('/api/request_browse_output', methods=['POST'])
def request_browse_output():
    """Browser queues a folder-browse request."""
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO browse_requests (email, status, path, created) "
            "VALUES (?, 'pending', NULL, CURRENT_TIMESTAMP)",
            (session['user_email'],)
        )
    return jsonify({"status": "success"})


@app.route('/api/poll_browse_output')
def poll_browse_output():
    """Browser polls until the worker returns the selected path."""
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT status, path FROM browse_requests WHERE email = ?",
            (session['user_email'],)
        ).fetchone()
        if row and row[0] == 'completed':
            path = row[1]
            conn.execute("DELETE FROM browse_requests WHERE email = ?",
                         (session['user_email'],))
            return jsonify({"status": "completed", "path": path})
    return jsonify({"status": "pending"})


@app.route('/api/worker/check_browse_output')
def worker_check_browse_output():
    """Worker polls for any pending browse request."""
    if not _check_worker_auth():
        return jsonify({"status": "error"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT email FROM browse_requests WHERE status = 'pending' "
            "ORDER BY created ASC LIMIT 1"
        ).fetchone()
    if row:
        return jsonify({"status": "success", "email": row[0]})
    return jsonify({"status": "none"})


@app.route('/api/worker/submit_browse_output', methods=['POST'])
def worker_submit_browse_output():
    """Worker delivers the chosen folder path."""
    if not _check_worker_auth():
        return jsonify({"status": "error"}), 401
    data  = request.json
    email = data.get('email', '')
    path  = data.get('path', 'CANCELLED')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE browse_requests SET status = 'completed', path = ? WHERE email = ?",
            (path, email)
        )
    return jsonify({"status": "success"})


# ─────────────────────────────────────────────────────────────
# WORKER HEARTBEAT – lets the UI show online/offline status
# ─────────────────────────────────────────────────────────────

@app.route('/api/worker/ping', methods=['POST'])
def worker_ping():
    """Worker calls this every ~30 s so the UI can show 'Worker Online'."""
    if not _check_worker_auth():
        return jsonify({"status": "error"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO worker_ping (id, last_ping) "
            "VALUES (1, CURRENT_TIMESTAMP)"
        )
    return jsonify({"status": "ok"})


@app.route('/api/worker_status')
def worker_status_route():
    """Browser calls this to display the worker online/offline badge."""
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    import datetime
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT last_ping FROM worker_ping WHERE id = 1").fetchone()
    if not row or not row[0]:
        return jsonify({"online": False, "seconds_ago": None})
    try:
        last = datetime.datetime.fromisoformat(row[0])
        now  = datetime.datetime.utcnow()
        secs = int((now - last).total_seconds())
        return jsonify({"online": secs < 60, "seconds_ago": secs})
    except Exception:
        return jsonify({"online": False, "seconds_ago": None})


@app.route('/get_jobs')
def get_jobs():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        if session.get('is_admin'):
            rows = conn.execute(
                "SELECT id, user_email, project_name, status, result_pdf, "
                "result_excel, timestamp, logs FROM jobs "
                "ORDER BY timestamp DESC LIMIT 50"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_email, project_name, status, result_pdf, "
                "result_excel, timestamp, logs FROM jobs "
                "WHERE user_email = ? ORDER BY timestamp DESC LIMIT 20",
                (session['user_email'],)
            ).fetchall()
    jobs = [{
        "id":           r[0],
        "email":        r[1],
        "project_name": r[2] or "Untitled",
        "status":       r[3],
        "pdf":          r[4],
        "excel":        r[5],
        "time":         r[6],
        "logs":         (r[7] or "")[-500:]
    } for r in rows]
    return jsonify({"jobs": jobs})


@app.route('/download/<filename>')
def download_result(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return send_from_directory(RESULTS_DIR, filename, as_attachment=True)


@app.route('/api/clear_job_log', methods=['POST'])
def clear_job_log():
    """Clear the logs field for a single job."""
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    job_id = request.json.get('job_id')
    with sqlite3.connect(DB_PATH) as conn:
        if session.get('is_admin'):
            conn.execute("UPDATE jobs SET logs = '' WHERE id = ?", (job_id,))
        else:
            conn.execute("UPDATE jobs SET logs = '' WHERE id = ? AND user_email = ?",
                         (job_id, session['user_email']))
    return jsonify({"status": "success"})


@app.route('/api/clear_all_jobs', methods=['POST'])
def clear_all_jobs():
    """Delete all job history rows for this user (admins clear all)."""
    if not session.get('logged_in'):
        return jsonify({"status": "error"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        if session.get('is_admin'):
            conn.execute("DELETE FROM jobs")
        else:
            conn.execute("DELETE FROM jobs WHERE user_email = ?", (session['user_email'],))
    return jsonify({"status": "success"})


@app.route('/download_worker')
def download_worker_launcher():
    """Serve the Start Worker.bat file for easy local download."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    # More robust path detection for PythonAnywhere
    root = os.path.dirname(os.path.abspath(__file__))
    filename = 'Start Worker.bat'
    bat_path = os.path.join(root, filename)
    
    # Fallback to current working directory if not found in script dir
    if not os.path.exists(bat_path):
        root = os.getcwd()
        bat_path = os.path.join(root, filename)

    if os.path.exists(bat_path):
        return send_from_directory(
            root,
            filename,
            as_attachment=True,
            mimetype='application/octet-stream'
        )
    
    return jsonify({
        "error": "Launcher not found on server",
        "debug_path": bat_path,
        "hint": "Ensure 'Start Worker.bat' is uploaded to your PythonAnywhere folder."
    }), 404


@app.route('/download_worker_silent')
def download_worker_silent():
    """Serve the silent VBS launcher."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    root = os.path.dirname(os.path.abspath(__file__))
    filename = 'Start Worker (Silent).vbs'
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        root = os.getcwd()
        path = os.path.join(root, filename)
    if os.path.exists(path):
        return send_from_directory(root, filename, as_attachment=True)
    return jsonify({"error": "Silent launcher not found on server"}), 404


# ─────────────────────────────────────────────────────────────
# 8.  WORKER API  (authenticated with MASTER_ADMIN_KEY)
# ─────────────────────────────────────────────────────────────

@app.route('/api/worker/next_job')
def worker_next_job():
    if not _check_worker_auth():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        job = conn.execute(
            "SELECT id, user_email, upload_path, api_key, project_name, output_folder "
            "FROM jobs WHERE status = 'pending' "
            "ORDER BY timestamp ASC LIMIT 1"
        ).fetchone()
        if job:
            conn.execute("UPDATE jobs SET status = 'processing' WHERE id = ?",
                         (job[0],))
            return jsonify({
                "status":        "success",
                "job_id":        job[0],
                "email":         job[1],
                "upload_path":   job[2],
                "api_key":       job[3],
                "project_name":  job[4],
                "output_folder": job[5] or ""
            })
    return jsonify({"status": "none"})


@app.route('/api/worker/download_project/<job_folder_id>')
def worker_download_project(job_folder_id):
    """Return a ZIP of all files uploaded for a given job folder."""
    if not _check_worker_auth():
        return jsonify({"status": "error"}), 401
    folder = os.path.join(UPLOAD_DIR, job_folder_id)
    if not os.path.isdir(folder):
        return jsonify({"status": "error",
                        "message": "Upload folder not found."}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(folder):
            zf.write(os.path.join(folder, fname), fname)
    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f'project_{job_folder_id}.zip')


@app.route('/api/worker/update_job', methods=['POST'])
def worker_update_job():
    if not _check_worker_auth():
        return jsonify({"status": "error"}), 401
    data   = request.json
    job_id = data.get('job_id')
    status = data.get('status')
    logs   = data.get('logs', '')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, logs = logs || ? WHERE id = ?",
            (status, logs, job_id))
    return jsonify({"status": "success"})


@app.route('/api/worker/upload_result', methods=['POST'])
def worker_upload_result():
    if not _check_worker_auth():
        return jsonify({"status": "error"}), 401
    job_id     = request.form.get('job_id')
    pdf_file   = request.files.get('pdf')
    excel_file = request.files.get('excel')
    pdf_name   = excel_name = None
    if pdf_file:
        pdf_name = f"result_{job_id}.pdf"
        pdf_file.save(os.path.join(RESULTS_DIR, pdf_name))
    if excel_file:
        excel_name = f"result_{job_id}.xlsm"
        excel_file.save(os.path.join(RESULTS_DIR, excel_name))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE jobs SET status = 'completed', "
            "result_pdf = ?, result_excel = ? WHERE id = ?",
            (pdf_name, excel_name, job_id))
    return jsonify({"status": "success"})


# ─────────────────────────────────────────────────────────────
# 9.  MISC / LEGACY STUBS
# ─────────────────────────────────────────────────────────────

@app.route('/get_logs')
def get_logs():
    logs = []
    while not output_queue.empty():
        logs.append(output_queue.get())
    return jsonify({"logs": logs, "active": False})


@app.route('/send_input', methods=['POST'])
def send_input():
    return jsonify({"status": "error",
                    "message": "No active local process on this server."}), 400


@app.route('/test_success')
def test_success():
    return render_template('test_success.html')


# ─────────────────────────────────────────────────────────────
# 10.  ENTRY POINT  (local dev only – PythonAnywhere uses WSGI)
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5002)
