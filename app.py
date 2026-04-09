"""
Submittal Builder Meta Agent - v2.1.0
Render Edition – SQLAlchemy/PostgreSQL Integration
"""
import os
import sys
import io
import uuid
import json
import hmac
import hashlib
import time
import zipfile
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 1. PATHS & CONFIG
# Render mount point for persistent files
if os.environ.get('RENDER'):
    # Try the standard mount point, but have a local fallback if permissions fail
    BASE_DATA_DIR = "/data"
    try:
        if not os.path.exists(BASE_DATA_DIR):
            os.makedirs(BASE_DATA_DIR, exist_ok=True)
    except PermissionError:
        print("⚠️ Warning: Permission denied on /data. Falling back to local ./data")
        BASE_DATA_DIR = os.path.join(os.getcwd(), 'data')
else:
    # Local fallback
    BASE_DATA_DIR = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'DenierAI')

UPLOAD_DIR  = os.path.join(BASE_DATA_DIR, 'uploads')
RESULTS_DIR = os.path.join(BASE_DATA_DIR, 'results')

for _d in [BASE_DATA_DIR, UPLOAD_DIR, RESULTS_DIR]:
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception as e:
        print(f"⚠️ Could not create directory {_d}: {e}")

MASTER_ADMIN_KEY = "DenierSubmittalsLemley90"
SUPER_ADMINS     = ['blemley@denier.com', 'brandonlemley90@gmail.com']

# 2. FLASK & DATABASE
app = Flask(__name__)
app.secret_key = "denier_vault_production_2026"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

# Postgres on Render via DATABASE_URL, fallback to SQLite
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or f"sqlite:///{os.path.join(BASE_DATA_DIR, 'submittal_builder.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 3. MODELS
class User(db.Model):
    __tablename__ = 'users'
    email    = db.Column(db.String(120), primary_key=True)
    password = db.Column(db.String(255), nullable=False)
    api_key  = db.Column(db.String(255))
    pin      = db.Column(db.String(10))
    is_admin = db.Column(db.Integer, default=0)
    name     = db.Column(db.String(100), default="")

class Job(db.Model):
    __tablename__ = 'jobs'
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_email    = db.Column(db.String(120))
    upload_path   = db.Column(db.String(255))
    api_key       = db.Column(db.String(255))
    status        = db.Column(db.String(50), default="pending")
    result_pdf    = db.Column(db.String(255))
    result_excel  = db.Column(db.String(255))
    logs          = db.Column(db.Text, default="")
    project_name  = db.Column(db.String(255), default="")
    output_folder = db.Column(db.String(255), default="")
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow)

class BrowseRequest(db.Model):
    __tablename__ = 'browse_requests'
    email   = db.Column(db.String(120), primary_key=True)
    status  = db.Column(db.String(50), default="pending")
    path    = db.Column(db.String(500))
    created = db.Column(db.DateTime, default=datetime.utcnow)

class WorkerPing(db.Model):
    __tablename__ = 'worker_ping'
    id        = db.Column(db.Integer, primary_key=True)
    last_ping = db.Column(db.DateTime)

def init_db():
    with app.app_context():
        db.create_all()
        # Guarantee super-admins
        for email in SUPER_ADMINS:
            admin = User.query.filter_by(email=email).first()
            if admin:
                admin.is_admin = 1
        db.session.commit()

init_db()

# 4. HELPERS
def _sign_payload(p: str) -> str:
    return hmac.new(MASTER_ADMIN_KEY.encode(), p.encode(), hashlib.sha256).hexdigest()

def _check_worker_auth() -> bool:
    return request.headers.get('Authorization') == MASTER_ADMIN_KEY

def get_local_version():
    try:
        with open('version.json') as f:
            return json.load(f).get('version', 'unknown')
    except:
        return '2.1.0'

@app.context_processor
def inject_version():
    return dict(version=get_local_version())

# 5. CORE AUTH ROUTES
@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    user_name = user.name if user and user.name else ""
    return render_template('index.html', is_admin=session.get('is_admin'), user_email=session['user_email'], user_name=user_name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session.permanent = True
            session.update({'logged_in': True, 'user_email': email, 'is_admin': bool(user.is_admin)})
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid email or password.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name     = request.form.get('name', '')
        if User.query.filter_by(email=email).first():
            return render_template('registration.html', error="Email already registered.")
        new_user = User(email=email, password=generate_password_hash(password), name=name)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('registration.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 6. ACCOUNT & VAULT
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    name = request.json.get('name', '')
    user = User.query.filter_by(email=session['user_email']).first()
    if user:
        user.name = name
        db.session.commit()
    return jsonify({"status": "success"})

@app.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    old_pw = request.json.get('old_password')
    new_pw = request.json.get('new_password')
    user = User.query.filter_by(email=session['user_email']).first()
    if user and check_password_hash(user.password, old_pw):
        user.password = generate_password_hash(new_pw)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Incorrect current password."}), 400

@app.route('/save_api_vault', methods=['POST'])
def save_api_vault():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    user = User.query.filter_by(email=session['user_email']).first()
    if user:
        user.api_key = request.json.get('api_key')
        user.pin = request.json.get('pin')
        db.session.commit()
    return jsonify({"status": "success"})

@app.route('/unlock_api_vault', methods=['POST'])
def unlock_api_vault():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    pin = request.json.get('pin')
    user = User.query.filter_by(email=session['user_email']).first()
    if user and user.pin == pin and user.api_key:
        return jsonify({"status": "success", "api_key": user.api_key})
    return jsonify({"status": "error", "message": "Invalid PIN or no key saved."}), 400

# 7. ADMIN ROUTES
@app.route('/admin/list_users')
def admin_list_users():
    if not session.get('is_admin'): return jsonify({"status": "error"}), 403
    users = User.query.order_by(User.email).all()
    return jsonify({"users": [{"email": u.email, "name": u.name, "is_admin": bool(u.is_admin)} for u in users]})

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if not session.get('is_admin'): return jsonify({"status": "error"}), 403
    email = request.json.get('email', '').strip().lower()
    if email in SUPER_ADMINS: return jsonify({"status": "error", "message": "Cannot delete super admin."}), 400
    user = User.query.filter_by(email=email).first()
    if user:
        db.session.delete(user)
        db.session.commit()
    return jsonify({"status": "success"})

# 8. JOB SUBMISSION
@app.route('/upload_and_submit', methods=['POST'])
def upload_and_submit():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    api_key       = request.form.get('api_key', '').strip()
    project_name  = request.form.get('project_name', 'Untitled Project').strip()
    output_folder = request.form.get('output_folder', '').strip()
    
    if not api_key: return jsonify({"status": "error", "message": "API Key required."}), 400

    job_folder_id = str(uuid.uuid4())[:12]
    job_upload_dir = os.path.join(UPLOAD_DIR, job_folder_id)
    os.makedirs(job_upload_dir, exist_ok=True)

    saved_files = []
    for field in ['excel', 'specs', 'drawings', 'form', 'contract']:
        file = request.files.get(field)
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(job_upload_dir, filename))
            saved_files.append(filename)

    if not saved_files: return jsonify({"status": "error", "message": "No files received."}), 400

    new_job = Job(user_email=session['user_email'], upload_path=job_folder_id, api_key=api_key, project_name=project_name, output_folder=output_folder)
    db.session.add(new_job)
    db.session.commit()

    return jsonify({"status": "success", "job_id": new_job.id})

@app.route('/get_jobs')
def get_jobs():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    if session.get('is_admin'):
        jobs = Job.query.order_by(Job.timestamp.desc()).limit(50).all()
    else:
        jobs = Job.query.filter_by(user_email=session['user_email']).order_by(Job.timestamp.desc()).limit(20).all()
    
    return jsonify({"jobs": [{
        "id": j.id, "email": j.user_email, "project_name": j.project_name or "Untitled",
        "status": j.status, "pdf": j.result_pdf, "excel": j.result_excel,
        "time": j.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "logs": (j.logs or "")[-500:]
    } for j in jobs]})

@app.route('/download/<filename>')
def download_result(filename):
    if not session.get('logged_in'): return redirect(url_for('login'))
    return send_from_directory(RESULTS_DIR, filename, as_attachment=True)

# 9. WORKER API
@app.route('/api/worker/ping', methods=['POST'])
def worker_ping():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    ping = WorkerPing.query.get(1)
    if not ping: ping = WorkerPing(id=1)
    ping.last_ping = datetime.utcnow()
    db.session.add(ping)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/worker_status')
def worker_status_route():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    ping = WorkerPing.query.get(1)
    if not ping or not ping.last_ping: return jsonify({"online": False, "seconds_ago": None})
    secs = int((datetime.utcnow() - ping.last_ping).total_seconds())
    return jsonify({"online": secs < 60, "seconds_ago": secs})

@app.route('/api/worker/next_job')
def worker_next_job():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    job = Job.query.filter_by(status='pending').order_by(Job.timestamp.asc()).first()
    if job:
        job.status = 'processing'
        db.session.commit()
        return jsonify({
            "status": "success", "job_id": job.id, "email": job.user_email,
            "upload_path": job.upload_path, "api_key": job.api_key,
            "project_name": job.project_name, "output_folder": job.output_folder
        })
    return jsonify({"status": "none"})

@app.route('/api/worker/update_job', methods=['POST'])
def worker_update_job():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    data = request.json
    job = Job.query.get(data.get('job_id'))
    if job:
        job.status = data.get('status')
        job.logs = (job.logs or "") + (data.get('logs', ''))
        db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/worker/upload_result', methods=['POST'])
def worker_upload_result():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    job_id = request.form.get('job_id')
    job = Job.query.get(job_id)
    if not job: return jsonify({"status": "error"}), 404
    
    pdf_file = request.files.get('pdf')
    excel_file = request.files.get('excel')
    if pdf_file:
        fname = f"result_{job_id}.pdf"
        pdf_file.save(os.path.join(RESULTS_DIR, fname))
        job.result_pdf = fname
    if excel_file:
        fname = f"result_{job_id}.xlsm"
        excel_file.save(os.path.join(RESULTS_DIR, fname))
        job.result_excel = fname
    
    job.status = 'completed'
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/worker/download_project/<job_folder_id>')
def worker_download_project(job_folder_id):
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    folder = os.path.join(UPLOAD_DIR, job_folder_id)
    if not os.path.isdir(folder): return jsonify({"status": "error"}), 404
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(folder):
            zf.write(os.path.join(folder, fname), fname)
    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f'project_{job_folder_id}.zip')

# 10. BROWSE HANDSHAKE
@app.route('/api/request_browse_output', methods=['POST'])
def request_browse_output():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    req = BrowseRequest(email=session['user_email'], status='pending', path=None, created=datetime.utcnow())
    db.session.merge(req)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/poll_browse_output')
def poll_browse_output():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    req = BrowseRequest.query.get(session['user_email'])
    if req and req.status == 'completed':
        path = req.path
        db.session.delete(req)
        db.session.commit()
        return jsonify({"status": "completed", "path": path})
    return jsonify({"status": "pending"})

@app.route('/api/worker/check_browse_output')
def worker_check_browse_output():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    req = BrowseRequest.query.filter_by(status='pending').order_by(BrowseRequest.created.asc()).first()
    if req: return jsonify({"status": "success", "email": req.email})
    return jsonify({"status": "none"})

@app.route('/api/worker/submit_browse_output', methods=['POST'])
def worker_submit_browse_output():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    data = request.json
    req = BrowseRequest.query.get(data.get('email'))
    if req:
        req.status = 'completed'
        req.path = data.get('path', 'CANCELLED')
        db.session.commit()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5002)
