"""
Submittal Builder Meta Agent - v2.2.0
Supabase Edition – Cloud Storage + PostgreSQL
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
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 1. SUPABASE STORAGE
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
STORAGE_BUCKET = "submittal-files"

supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Supabase storage initialized")
    except Exception as e:
        print(f"[WARN] Supabase init failed: {e}")

# Local fallback dir for development (no Supabase)
BASE_DATA_DIR = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'DenierAI')
if not supabase_client:
    for _d in [BASE_DATA_DIR,
               os.path.join(BASE_DATA_DIR, 'uploads'),
               os.path.join(BASE_DATA_DIR, 'results')]:
        try:
            os.makedirs(_d, exist_ok=True)
        except Exception:
            pass

def storage_upload(path: str, data: bytes, content_type: str = "application/octet-stream"):
    if supabase_client:
        supabase_client.storage.from_(STORAGE_BUCKET).upload(
            path, data,
            file_options={"content-type": content_type, "upsert": "true"}
        )
    else:
        local_path = os.path.join(BASE_DATA_DIR, path.replace('/', os.sep))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(data)

def storage_download(path: str) -> bytes:
    if supabase_client:
        return supabase_client.storage.from_(STORAGE_BUCKET).download(path)
    else:
        local_path = os.path.join(BASE_DATA_DIR, path.replace('/', os.sep))
        with open(local_path, 'rb') as f:
            return f.read()

def storage_list(prefix: str) -> list:
    if supabase_client:
        items = supabase_client.storage.from_(STORAGE_BUCKET).list(prefix)
        return [f['name'] for f in items] if items else []
    else:
        local_path = os.path.join(BASE_DATA_DIR, prefix.replace('/', os.sep))
        return os.listdir(local_path) if os.path.isdir(local_path) else []

# 2. CONFIG
MASTER_ADMIN_KEY = os.environ.get('MASTER_ADMIN_KEY', 'DenierSubmittalsLemley90')
SUPER_ADMINS     = ['blemley@denier.com', 'brandonlemley90@gmail.com']

# 3. FLASK & DATABASE
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'denier_vault_production_2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or f"sqlite:///{os.path.join(BASE_DATA_DIR, 'submittal_builder.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 4. MODELS
class User(db.Model):
    __tablename__ = 'users'
    email     = db.Column(db.String(120), primary_key=True)
    password  = db.Column(db.String(255), nullable=False)
    api_key   = db.Column(db.String(255))
    pin       = db.Column(db.String(10))
    is_admin  = db.Column(db.Integer, default=0)
    name      = db.Column(db.String(100), default="")
    job_title = db.Column(db.String(100), default="")

class Job(db.Model):
    __tablename__ = 'jobs'
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_email    = db.Column(db.String(120))
    upload_path   = db.Column(db.String(255))
    api_key       = db.Column(db.String(255))
    status        = db.Column(db.String(50), default="pending")
    result_pdf    = db.Column(db.String(255))   # ZIP filename in Supabase results/
    result_excel  = db.Column(db.String(255))
    logs          = db.Column(db.Text, default="")
    project_name  = db.Column(db.String(255), default="")
    output_folder = db.Column(db.String(255), default="")
    current_step  = db.Column(db.Integer, default=0)
    step_name     = db.Column(db.String(100), default="")
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

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    token      = db.Column(db.String(64), primary_key=True)
    email      = db.Column(db.String(120), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Integer, default=0)

def init_db():
    with app.app_context():
        db.create_all()
        # Run any column migrations that create_all won't handle on existing tables
        migrations = [
            "ALTER TABLE users ADD COLUMN job_title VARCHAR(100) DEFAULT ''",
            "ALTER TABLE jobs ADD COLUMN current_step INTEGER DEFAULT 0",
            "ALTER TABLE jobs ADD COLUMN step_name VARCHAR(100) DEFAULT ''",
            "ALTER TABLE jobs ADD COLUMN output_folder VARCHAR(255) DEFAULT ''",
        ]
        for sql in migrations:
            try:
                db.session.execute(db.text(sql))
            except Exception:
                pass  # Column already exists
        db.session.commit()
        for email in SUPER_ADMINS:
            admin = User.query.filter_by(email=email).first()
            if admin:
                admin.is_admin = 1
        db.session.commit()

init_db()

# 5. HELPERS
def send_email(to, subject, body):
    sender   = os.environ.get('SMTP_USER', 'blemley@denier.com')
    password = os.environ.get('SMTP_PASS')
    if not password:
        print("[WARN] SMTP_PASS not set. Email not sent.")
        return False
    msg = MIMEMultipart()
    msg['From']    = f"Denier AI <{sender}>"
    msg['To']      = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[ERROR] SMTP Error: {e}")
        return False

def _check_worker_auth() -> bool:
    return request.headers.get('Authorization') == MASTER_ADMIN_KEY

def get_local_version():
    try:
        with open('version.json') as f:
            return json.load(f).get('version', 'unknown')
    except Exception:
        return '2.2.0'

@app.context_processor
def inject_version():
    return dict(version=get_local_version())

# 6. PUBLIC VERSION + WORKER DOWNLOAD
@app.route('/api/version')
def api_version():
    try:
        with open('version.json') as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({"version": "2.2.0", "release_date": "unknown"})

@app.route('/api/worker/latest')
def download_latest_worker():
    return send_file('worker.py', as_attachment=True, download_name='worker.py')

# 7. AUTH ROUTES
@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['user_email']).first()
    user_name  = user.name      if user and user.name      else ""
    job_title  = user.job_title if user and user.job_title else ""
    return render_template('index.html', is_admin=session.get('is_admin'),
                           user_email=session['user_email'], user_name=user_name,
                           job_title=job_title)

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
        new_user = User(
            email=email,
            password=generate_password_hash(password),
            name=name,
            is_admin=1 if email in SUPER_ADMINS else 0
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('registration.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')
    email = request.form.get('email', '').strip().lower()
    user  = User.query.filter_by(email=email).first()
    # Always show success to avoid email enumeration
    if user:
        # Invalidate any existing unused tokens for this email
        PasswordResetToken.query.filter_by(email=email, used=0).delete()
        token     = secrets.token_urlsafe(32)
        expires   = datetime.utcnow() + timedelta(hours=1)
        db.session.add(PasswordResetToken(token=token, email=email, expires_at=expires))
        db.session.commit()
        base_url  = os.environ.get('APP_URL', request.host_url.rstrip('/'))
        reset_url = f"{base_url}/reset_password/{token}"
        body = (
            f"Hi {user.name or email},\n\n"
            f"A password reset was requested for your Denier Submittal Builder account.\n\n"
            f"Click the link below to set a new password (expires in 1 hour):\n\n"
            f"{reset_url}\n\n"
            f"If you did not request this, you can safely ignore this email.\n\n"
            f"— Denier Electric"
        )
        send_email(email, "Denier Submittal Builder — Password Reset", body)
    return render_template('forgot_password.html', sent=True)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    record = PasswordResetToken.query.filter_by(token=token, used=0).first()
    if not record or record.expires_at < datetime.utcnow():
        return render_template('reset.html', error="This reset link has expired or is invalid.")
    if request.method == 'GET':
        return render_template('reset.html', token=token)
    new_pw  = request.form.get('password', '')
    confirm = request.form.get('confirm', '')
    if not new_pw or len(new_pw) < 6:
        return render_template('reset.html', token=token, error="Password must be at least 6 characters.")
    if new_pw != confirm:
        return render_template('reset.html', token=token, error="Passwords do not match.")
    user = User.query.filter_by(email=record.email).first()
    if user:
        user.password = generate_password_hash(new_pw)
        record.used   = 1
        db.session.commit()
    return render_template('reset.html', success=True)

# 8. ACCOUNT & VAULT
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    data = request.json or {}
    user = User.query.filter_by(email=session['user_email']).first()
    if user:
        if 'name'      in data: user.name      = data['name']
        if 'job_title' in data: user.job_title = data['job_title']
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
        user.pin     = request.json.get('pin')
        db.session.commit()
    return jsonify({"status": "success"})

@app.route('/unlock_api_vault', methods=['POST'])
def unlock_api_vault():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    pin  = request.json.get('pin')
    user = User.query.filter_by(email=session['user_email']).first()
    if user and user.pin == pin and user.api_key:
        return jsonify({"status": "success", "api_key": user.api_key})
    return jsonify({"status": "error", "message": "Invalid PIN or no key saved."}), 400

# 9. ADMIN ROUTES
@app.route('/admin/list_users')
def list_users():
    if not session.get('is_admin'): return jsonify({"status": "error"}), 403
    users = User.query.order_by(User.email).all()
    return jsonify({"users": [{"email": u.email, "name": u.name, "is_admin": bool(u.is_admin)} for u in users]})

@app.route('/admin/toggle_admin', methods=['POST'])
def toggle_admin():
    if not session.get('is_admin'): return jsonify({'status': 'error'}), 403
    user = User.query.filter_by(email=request.json.get('email')).first()
    if not user: return jsonify({'status': 'error', 'message': 'User not found'})
    user.is_admin = 1 if user.is_admin == 0 else 0
    db.session.commit()
    return jsonify({'status': 'success', 'new_state': user.is_admin})

@app.route('/admin/reset_password', methods=['POST'])
def reset_password():
    if not session.get('is_admin'): return jsonify({'status': 'error'}), 403
    data       = request.json
    email      = data.get('email')
    temp_pass  = data.get('temp_password')
    user = User.query.filter_by(email=email).first()
    if not user: return jsonify({'status': 'error', 'message': 'User not found'})
    user.password = generate_password_hash(temp_pass)
    db.session.commit()
    body = (f"Hello,\n\nAn administrator has reset your password.\n\n"
            f"Temporary Password: {temp_pass}\n\n"
            f"Login: {request.host_url}login")
    sent = send_email(email, "Password Reset - Denier Submittal Builder", body)
    msg  = f'Password reset and email sent to {email}' if sent else 'Password reset, but email failed.'
    return jsonify({'status': 'success', 'message': msg})

@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    if not session.get('is_admin'): return jsonify({'status': 'error'}), 403
    email = request.json.get('email', '').strip().lower()
    if email in SUPER_ADMINS:
        return jsonify({'status': 'error', 'message': 'Cannot delete super admin.'}), 400
    user = User.query.filter_by(email=email).first()
    if user:
        db.session.delete(user)
        db.session.commit()
    return jsonify({'status': 'success'})

# 10. JOB SUBMISSION
@app.route('/upload_and_submit', methods=['POST'])
def upload_and_submit():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    api_key       = request.form.get('api_key', '').strip()
    project_name  = request.form.get('project_name', 'Untitled Project').strip()
    output_folder = request.form.get('output_folder', '').strip()

    if not api_key:
        return jsonify({"status": "error", "message": "API Key required."}), 400

    job_folder_id = str(uuid.uuid4())[:12]
    saved_files   = []

    # field name mapping: form field -> config key suffix
    field_map = {
        'excel':    'excel',
        'specs':    'specs',
        'dwgs':     'dwgs',     # frontend sends 'dwgs'
        'form':     'form',
        'contract': 'contract',
    }
    for field in field_map:
        f = request.files.get(field)
        if f and f.filename:
            filename = secure_filename(f.filename)
            try:
                storage_upload(
                    f"uploads/{job_folder_id}/{filename}",
                    f.read(),
                    f.content_type or "application/octet-stream"
                )
                saved_files.append(filename)
            except Exception as e:
                print(f"[WARN] Upload error for {field}: {e}")

    if not saved_files:
        return jsonify({"status": "error", "message": "No files received."}), 400

    new_job = Job(
        user_email=session['user_email'],
        upload_path=job_folder_id,
        api_key=api_key,
        project_name=project_name,
        output_folder=output_folder
    )
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
        "id":           j.id,
        "email":        j.user_email,
        "project_name": j.project_name or "Untitled",
        "status":       j.status,
        "pdf":          j.result_pdf,
        "excel":        j.result_excel,
        "time":         j.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "logs":         (j.logs or "")[-500:],
        "current_step": j.current_step or 0,
        "step_name":    j.step_name or "",
    } for j in jobs]})

@app.route('/download/<filename>')
def download_result(filename):
    if not session.get('logged_in'): return redirect(url_for('login'))
    try:
        file_data = storage_download(f"results/{filename}")
        mime = 'application/zip' if filename.endswith('.zip') else 'application/octet-stream'
        return send_file(io.BytesIO(file_data), as_attachment=True,
                         download_name=filename, mimetype=mime)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 404

# 11. WORKER API
@app.route('/api/worker/ping', methods=['POST'])
def worker_ping():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    ping = WorkerPing.query.get(1)
    if not ping:
        ping = WorkerPing(id=1)
    ping.last_ping = datetime.utcnow()
    db.session.add(ping)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/worker_status')
def worker_status_route():
    if not session.get('logged_in'): return jsonify({"status": "error"}), 401
    ping = WorkerPing.query.get(1)
    if not ping or not ping.last_ping:
        return jsonify({"online": False, "seconds_ago": None})
    secs = int((datetime.utcnow() - ping.last_ping).total_seconds())
    return jsonify({"online": secs < 60, "seconds_ago": secs})

@app.route('/api/worker/next_job')
def worker_next_job():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    email = request.args.get('email')
    if not email: return jsonify({"status": "error", "message": "Missing email"}), 400
    job = Job.query.filter_by(status='pending', user_email=email).order_by(Job.timestamp.asc()).first()
    if job:
        job.status = 'processing'
        db.session.commit()
        return jsonify({
            "status":       "success",
            "job_id":       job.id,
            "email":        job.user_email,
            "upload_path":  job.upload_path,
            "api_key":      job.api_key,
            "project_name": job.project_name,
            "output_folder": job.output_folder
        })
    return jsonify({"status": "none"})

@app.route('/api/worker/update_job', methods=['POST'])
def worker_update_job():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    data = request.json or {}
    job  = Job.query.get(data.get('job_id'))
    if job:
        new_status = data.get('status')
        if new_status:
            job.status = new_status
        new_logs = data.get('logs', '')
        if new_logs:
            job.logs = ((job.logs or "") + new_logs)[-5000:]
        current_step = data.get('current_step')
        if current_step is not None:
            job.current_step = int(current_step)
        step_name = data.get('step_name')
        if step_name:
            job.step_name = step_name
        db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/worker/upload_result', methods=['POST'])
def worker_upload_result():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    job_id = request.form.get('job_id')
    job    = Job.query.get(job_id)
    if not job: return jsonify({"status": "error"}), 404

    pdf_file   = request.files.get('pdf')    # ZIP of all submittal PDFs
    excel_file = request.files.get('excel')

    if pdf_file:
        fname = f"result_{job_id}.zip"
        storage_upload(f"results/{fname}", pdf_file.read(), "application/zip")
        job.result_pdf = fname

    if excel_file:
        fname = f"result_{job_id}.xlsm"
        storage_upload(f"results/{fname}", excel_file.read(),
                       "application/vnd.ms-excel.sheet.macroEnabled.12")
        job.result_excel = fname

    job.status       = 'completed'
    job.current_step = 6
    job.step_name    = 'Complete'
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/worker/download_project/<job_folder_id>')
def worker_download_project(job_folder_id):
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    prefix = f"uploads/{job_folder_id}"
    try:
        filenames = storage_list(prefix)
    except Exception:
        return jsonify({"status": "error", "message": "Folder not found"}), 404

    if not filenames:
        return jsonify({"status": "error", "message": "No files in folder"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in filenames:
            try:
                file_data = storage_download(f"{prefix}/{fname}")
                zf.writestr(fname, file_data)
            except Exception as e:
                print(f"[WARN] Could not pack {fname}: {e}")
    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'project_{job_folder_id}.zip')

# 12. BROWSE HANDSHAKE
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
    email = request.args.get('email')
    if not email: return jsonify({"status": "error", "message": "Missing email"}), 400
    req = BrowseRequest.query.filter_by(status='pending', email=email).first()
    if req: return jsonify({"status": "success", "email": req.email})
    return jsonify({"status": "none"})

@app.route('/api/worker/submit_browse_output', methods=['POST'])
def worker_submit_browse_output():
    if not _check_worker_auth(): return jsonify({"status": "error"}), 401
    data = request.json
    req  = BrowseRequest.query.get(data.get('email'))
    if req:
        req.status = 'completed'
        req.path   = data.get('path', 'CANCELLED')
        db.session.commit()
    return jsonify({"status": "success"})

# 13. HEALTH
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}), 200

if __name__ == '__main__':
    port       = int(os.environ.get('PORT', 5002))
    debug_mode = os.environ.get('RENDER') is None
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
