import sys
import os
import sqlite3
import subprocess
import webbrowser
import threading
import queue
from datetime import timedelta
from threading import Timer
from tkinter import filedialog
import tkinter as tk

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

# --- 1. DATABASE & GLOBALS ---
if os.name == 'nt':
    app_data_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'DenierAI')
else:
    app_data_dir = os.path.expanduser('~/.denierai')

if not os.path.exists(app_data_dir):
    os.makedirs(app_data_dir)

DB_PATH = os.path.join(app_data_dir, 'users.db')

active_process = None
output_queue = queue.Queue()


def init_db():
    """Initializes the database and ensures the schema is up to date."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS users
                       (
                           email
                           TEXT
                           PRIMARY
                           KEY,
                           password
                           TEXT,
                           api_key
                           TEXT,
                           pin
                           TEXT
                       )
                       ''')

        # MIGRATIONS: Add new columns if they don't exist
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN name TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        conn.commit()


init_db()


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- 2. FLASK CONFIG ---
app = Flask(__name__, template_folder=resource_path('templates'), static_folder=resource_path('static'))
app.secret_key = "denier_vault_production_2026"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
MASTER_ADMIN_KEY = "Denier_Admin_2026_Global"


# --- 3. PROCESS HANDLING ---
def enqueue_output(out, q):
    for line in iter(out.readline, ''): q.put(line)
    out.close()


@app.route('/get_logs')
def get_logs():
    logs = []
    while not output_queue.empty(): logs.append(output_queue.get())
    return jsonify({"logs": logs, "active": active_process is not None and active_process.poll() is None})


@app.route('/send_input', methods=['POST'])
def send_input():
    global active_process
    data = request.json
    user_text = data.get("text", "") + "\n"
    if active_process and active_process.poll() is None:
        active_process.stdin.write(user_text)
        active_process.stdin.flush()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "No active process"}), 400


# --- 4. NAVIGATION & AUTH ---
@app.route('/')
def home():
    if not session.get('logged_in'): return redirect(url_for('login'))

    # Fetch user details to display in the Account modal
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute("SELECT name FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        user_name = user[0] if user and user[0] else ""

    return render_template('index.html',
                           is_admin=session.get('is_admin'),
                           user_email=session['user_email'],
                           user_name=user_name)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with sqlite3.connect(DB_PATH) as conn:
            user = conn.execute("SELECT password, is_admin FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user[0], password):
            session.update({"logged_in": True, "user_email": email, "is_admin": bool(user[1])})
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid password or email")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('registration.html', error="Email already registered.")
    return render_template('registration.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- 5. ACCOUNT & ADMIN TOOLS ---
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    name = request.json.get('name', '')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET name = ? WHERE email = ?", (name, session['user_email']))
    return jsonify({"status": "success"})


@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.json
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute("SELECT password FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        if user and check_password_hash(user[0], data.get('old_password')):
            new_hashed = generate_password_hash(data.get('new_password'))
            conn.execute("UPDATE users SET password = ? WHERE email = ?", (new_hashed, session['user_email']))
            return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Incorrect current password"}), 400


@app.route('/admin/promote_self', methods=['POST'])
def promote_self():
    if not session.get('logged_in'): return "Unauthorized", 401
    data = request.json
    if data.get('secret_key') == MASTER_ADMIN_KEY:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (session['user_email'],))
        session['is_admin'] = True
        return jsonify({"status": "success", "message": "Admin Access Granted!"})
    return "Forbidden", 403


@app.route('/admin/reset_user_password', methods=['POST'])
def admin_reset_password():
    if not session.get('is_admin'): return "Admin access required", 403
    data = request.json
    hashed_pw = generate_password_hash(data.get('new_password'))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_pw, data.get('email')))
    return jsonify({"status": "success", "message": "User password reset."})


# --- 6. VAULT & BROWSE ---
@app.route('/save_api_vault', methods=['POST'])
def save_api_vault():
    data = request.json
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET api_key = ?, pin = ? WHERE email = ?",
                     (data['api_key'], data['pin'], session['user_email']))
    return jsonify({"status": "success", "message": "Vault Updated!"})


@app.route('/unlock_api_vault', methods=['POST'])
def unlock_api_vault():
    with sqlite3.connect(DB_PATH) as conn:
        res = conn.execute("SELECT api_key, pin FROM users WHERE email = ?", (session['user_email'],)).fetchone()
    if res and str(res[1]) == str(request.json.get('pin')):
        return jsonify({"status": "success", "api_key": res[0]})
    return jsonify({"status": "error"}), 401


@app.route('/browse_folder')
def browse_folder():
    root = tk.Tk();
    root.withdraw();
    root.attributes('-topmost', True)
    f = filedialog.askdirectory();
    root.destroy()
    return jsonify({"path": os.path.normpath(f) if f else ""})


@app.route('/browse_file')
def browse_file():
    root = tk.Tk();
    root.withdraw();
    root.attributes('-topmost', True)
    f = filedialog.askopenfilename();
    root.destroy()
    return jsonify({"filename": os.path.basename(f) if f else ""})


# --- 7. LAUNCH ---
@app.route('/launch', methods=['POST'])
def launch():
    global active_process
    if active_process and active_process.poll() is None: return jsonify(
        {"status": "error", "message": "Builder already running!"})
    data = request.json
    meta_script = resource_path("SubmittalBuilderMetaAgent.py")
    env = os.environ.copy()
    env.update({
        "GEMINI_API_KEY": data.get("api_key", ""), "PROJECT_FOLDER": data.get("folder", ""),
        "EXCEL_WORKBOOK_NAME": data.get("excel", ""), "JOB_FORM_PDF_NAME": data.get("form", ""),
        "SPEC_PDF_NAME": data.get("specs", ""), "DRAWINGS_PDF_NAME": data.get("drawings", ""),
        "CONTRACT_PDF_NAME": data.get("contract", "")
    })
    active_process = subprocess.Popen([sys.executable, "-u", meta_script, "--web"], env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1,
                                      creationflags=0x08000000)
    t = threading.Thread(target=enqueue_output, args=(active_process.stdout, output_queue))
    t.daemon = True;
    t.start()
    return jsonify({"status": "success"})


if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new("http://127.0.0.1:5001/")).start()
    app.run(debug=True, use_reloader=False, port=5001)