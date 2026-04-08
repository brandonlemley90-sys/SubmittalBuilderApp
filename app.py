import sys
"""
Submittal Builder Meta Agent - v1.0.4
"""
import os
import sqlite3
import subprocess
import webbrowser
import threading
import queue
import json
import hmac
import hashlib
import time
from datetime import timedelta
from threading import Timer
from tkinter import filedialog
import tkinter as tk

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from auto_updater import AutoUpdater

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

# Cached update info
_cached_update_info = None
JUST_UPDATED = False
START_TIME = time.time()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, api_key TEXT, pin TEXT)')
        for migration in [
            "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN name TEXT DEFAULT ''",
        ]:
            try: cursor.execute(migration)
            except: pass
        conn.commit()

init_db()

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 2. FLASK CONFIG ---
app = Flask(__name__, template_folder=resource_path('templates'), static_folder=resource_path('static'))
app.secret_key = "denier_vault_production_2026"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
MASTER_ADMIN_KEY = "DenierSubmittalsLemley90"

def _sign_payload(payload_str: str) -> str:
    return hmac.new(MASTER_ADMIN_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()

def enqueue_output(out, q):
    for line in iter(out.readline, ''): q.put(line)
    out.close()

# --- 3. ROUTES ---
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

@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login', **request.args))
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute("SELECT name FROM users WHERE email = ?", (session['user_email'],)).fetchone()
        user_name = user[0] if user and user[0] else ""
    return render_template('index.html', is_admin=session.get('is_admin'), user_email=session['user_email'], user_name=user_name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        with sqlite3.connect(DB_PATH) as conn:
            user = conn.execute("SELECT password, is_admin FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user[0], password):
            session.update({"logged_in": True, "user_email": email, "is_admin": bool(user[1])})
            return redirect(url_for('home', **request.args))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, generate_password_hash(password)))
            return redirect(url_for('login'))
        except: return render_template('registration.html', error="Email already registered.")
    return render_template('registration.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 4. AUTO-UPDATER ---
updater = AutoUpdater()

@app.route('/check_update')
@app.route('/check_updates')
def check_updates_route():
    global JUST_UPDATED, START_TIME, _cached_update_info
    if JUST_UPDATED and (time.time() - START_TIME < 30):
        return jsonify({"available": False, "just_updated": True})
    
    def _cb(available, info):
        global _cached_update_info
        _cached_update_info = info if available else None
        
    updater.check_updates(callback=_cb)
    time.sleep(1.2)
    info = _cached_update_info
    if info: return jsonify({"available": True, "version": info['version'], "notes": info['release_notes']})
    return jsonify({"available": False})

@app.route('/start_update', methods=['POST'])
def start_update_route():
    global _cached_update_info
    if not _cached_update_info: return jsonify({"status": "error", "message": "No update info"}), 400
    updater.update_info = _cached_update_info
    updater.update_available = True
    if updater.download_and_install(): return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Update failed to start"})

@app.route('/test_success')
def test_success(): return render_template('test_success.html')

# --- 5. BROWSE & LAUNCH ---
@app.route('/browse_folder')
def browse_folder():
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    f = filedialog.askdirectory(); root.destroy()
    return jsonify({"path": os.path.normpath(f) if f else ""})

@app.route('/launch', methods=['POST'])
def launch():
    global active_process
    if active_process and active_process.poll() is None: return jsonify({"status": "error", "message": "Already running"})
    data = request.json
    env = os.environ.copy()
    env.update({k: data.get(v, "") for k,v in {"GEMINI_API_KEY":"api_key","PROJECT_FOLDER":"folder"}.items()})
    active_process = subprocess.Popen([sys.executable, "-u", resource_path("SubmittalBuilderMetaAgent.py"), "--web"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, bufsize=1, creationflags=0x08000000)
    threading.Thread(target=enqueue_output, args=(active_process.stdout, output_queue), daemon=True).start()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    if "--updated" in sys.argv: JUST_UPDATED = True
    Timer(1.5, lambda: webbrowser.open_new("http://127.0.0.1:5002/")).start()
    app.run(debug=True, use_reloader=False, port=5002)
