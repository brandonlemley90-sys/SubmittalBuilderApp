import os
import sys
import re
import time
import json
import zipfile
import shutil
import requests
import subprocess
import glob
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# --- CONFIGURATION ---
SERVER_URL       = "https://submittalbuilderapp.onrender.com"
MASTER_ADMIN_KEY = os.environ.get('MASTER_ADMIN_KEY', 'DenierSubmittalsLemley90')
POLL_INTERVAL    = 3
WORKER_EMAIL     = "blemley@denier.com"  # Set to YOUR account email
LOCAL_VERSION    = "2.2.0"              # Keep in sync with version.json

# Teams shared folder where the latest DenierWorker.exe is published
TEAMS_FOLDER = os.path.join(
    os.environ.get('USERPROFILE', ''),
    "Denier",
    "Denier Operations Playbook-Submittal Builder - Documents",
    "Submittal Builder"
)
TASK_NAME = "Denier Submittal Worker"

# True when running as a compiled PyInstaller exe
IS_EXE = getattr(sys, 'frozen', False)


# -------------------------------------------------------------------
# FIRST-RUN: REGISTER IN TASK SCHEDULER (exe mode only)
# -------------------------------------------------------------------
def ensure_task_scheduler():
    """Register this exe to auto-start silently on Windows login."""
    if not IS_EXE:
        return
    exe_path = sys.executable
    result = subprocess.run(
        ['schtasks', '/query', '/tn', TASK_NAME],
        capture_output=True
    )
    if result.returncode != 0:
        # Not registered yet — register now
        subprocess.run([
            'schtasks', '/create',
            '/tn', TASK_NAME,
            '/tr', f'"{exe_path}"',
            '/sc', 'ONLOGON',
            '/rl', 'HIGHEST',
            '/f'
        ], capture_output=True)
        print(f"[SETUP] Registered '{TASK_NAME}' in Task Scheduler.")
    else:
        # Already registered — make sure it points to the current location
        subprocess.run([
            'schtasks', '/change',
            '/tn', TASK_NAME,
            '/tr', f'"{exe_path}"'
        ], capture_output=True)


# -------------------------------------------------------------------
# AUTO-UPDATE
# -------------------------------------------------------------------
def check_for_update():
    """
    Exe mode:  look for a newer DenierWorker.exe in the Teams shared folder.
               If found, replace this exe via a helper .bat and restart.
    Script mode: download updated worker.py from the Render server.
    """
    if IS_EXE:
        _check_teams_update()
    else:
        _check_server_update()


def _check_teams_update():
    """Check Teams folder for a newer DenierWorker.exe."""
    try:
        teams_exe = os.path.join(TEAMS_FOLDER, "DenierWorker.exe")
        if not os.path.exists(teams_exe):
            return
        current_exe = sys.executable
        # If the Teams copy is newer (by mtime), self-update
        if os.path.getmtime(teams_exe) > os.path.getmtime(current_exe) + 30:
            print("[UPDATE] Newer DenierWorker.exe found in Teams folder. Updating...")
            # Can't replace a running exe on Windows directly — use a helper bat
            bat_path = os.path.join(os.path.dirname(current_exe), "_denier_update.bat")
            with open(bat_path, 'w') as f:
                f.write(
                    f'@echo off\n'
                    f'timeout /t 3 /nobreak >nul\n'
                    f'copy /Y "{teams_exe}" "{current_exe}"\n'
                    f'start "" "{current_exe}"\n'
                    f'del "%~f0"\n'
                )
            subprocess.Popen(bat_path, shell=True, creationflags=0x08000000)  # CREATE_NO_WINDOW
            sys.exit(0)
    except Exception as e:
        print(f"[UPDATE] Teams update check skipped: {e}")


def _check_server_update():
    """Script mode: download updated worker.py from the Render server."""
    try:
        r = requests.get(f"{SERVER_URL}/api/version", timeout=5)
        server_ver = r.json().get("version", LOCAL_VERSION)
        if server_ver != LOCAL_VERSION:
            print(f"[UPDATE] New version {server_ver} available. Downloading...")
            r2 = requests.get(f"{SERVER_URL}/api/worker/latest", timeout=15)
            r2.raise_for_status()
            script_path = os.path.abspath(__file__)
            new_path    = script_path + ".new"
            with open(new_path, 'wb') as f:
                f.write(r2.content)
            os.replace(new_path, script_path)
            print(f"[UPDATE] Updated to {server_ver}. Restarting...")
            subprocess.Popen([sys.executable, script_path] + sys.argv[1:])
            sys.exit(0)
        else:
            print(f"[UPDATE] Worker is up to date (v{LOCAL_VERSION}).")
    except Exception as e:
        print(f"[UPDATE] Version check skipped: {e}")

# -------------------------------------------------------------------
# RESULT FILE DISCOVERY
# -------------------------------------------------------------------
def find_result_files(folder_path):
    """Find all *Submittal.pdf files and the updated Excel workbook."""
    all_pdfs  = glob.glob(os.path.join(folder_path, "* Submittal.pdf"))
    if not all_pdfs:
        # Fallback without leading space
        all_pdfs = glob.glob(os.path.join(folder_path, "*Submittal.pdf"))

    excels       = glob.glob(os.path.join(folder_path, "*.xlsm"))
    result_excel = max(excels, key=os.path.getmtime) if excels else None

    return all_pdfs, result_excel

# -------------------------------------------------------------------
# STEP UPDATE HELPER
# -------------------------------------------------------------------
def post_step_update(headers, job_id, step_num, step_name, logs=""):
    try:
        requests.post(
            f"{SERVER_URL}/api/worker/update_job",
            headers=headers,
            json={"job_id": job_id, "current_step": step_num,
                  "step_name": step_name, "logs": logs},
            timeout=5
        )
    except Exception:
        pass

# -------------------------------------------------------------------
# MAIN WORKER LOOP
# -------------------------------------------------------------------
def run_worker():
    print(f"[WORKER] DenierAI Local Worker v{LOCAL_VERSION} Started (Polling {SERVER_URL})...")

    # First-run: silently register in Task Scheduler so we auto-start on login
    ensure_task_scheduler()

    # Check for updates before starting loop
    check_for_update()

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    while True:
        try:
            headers = {"Authorization": MASTER_ADMIN_KEY}

            # --- Browse handshake ---
            browse_res = requests.get(
                f"{SERVER_URL}/api/worker/check_browse_output",
                headers=headers, params={"email": WORKER_EMAIL}, timeout=5
            )
            if browse_res.status_code == 200 and browse_res.json().get("status") == "success":
                email = browse_res.json()['email']
                print(f"[BROWSE] Remote Browse Request from {email}...")
                selected_path = filedialog.askdirectory(title="Select Project Output Folder")
                path_to_send  = os.path.normpath(selected_path) if selected_path else "CANCELLED"
                requests.post(f"{SERVER_URL}/api/worker/submit_browse_output",
                              headers=headers, json={"email": email, "path": path_to_send})
                if selected_path:
                    print(f"   [OK] Path sent: {path_to_send}")

            # --- Heartbeat ---
            requests.post(f"{SERVER_URL}/api/worker/ping", headers=headers, timeout=5)

            # --- Poll for next job ---
            response = requests.get(
                f"{SERVER_URL}/api/worker/next_job",
                headers=headers, params={"email": WORKER_EMAIL}, timeout=10
            )

            if response.status_code == 200 and response.json().get("status") == "success":
                data          = response.json()
                job_id        = data["job_id"]
                job_folder_id = data["upload_path"]
                api_key       = data.get("api_key", "")
                output_folder = data.get("output_folder", "")

                print(f"\n[JOB #{job_id}] Received. Downloading project files...")

                # --- Download & extract project ZIP ---
                local_job_dir = os.path.join(os.getcwd(), "worker_jobs", job_folder_id)
                os.makedirs(local_job_dir, exist_ok=True)

                try:
                    dl_res = requests.get(
                        f"{SERVER_URL}/api/worker/download_project/{job_folder_id}",
                        headers=headers, stream=True
                    )
                    dl_res.raise_for_status()
                    zip_path = os.path.join(local_job_dir, "project.zip")
                    with open(zip_path, 'wb') as f:
                        for chunk in dl_res.iter_content(chunk_size=8192):
                            f.write(chunk)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(local_job_dir)
                    os.remove(zip_path)
                    print(f"   [OK] Files extracted to: {local_job_dir}")
                except Exception as e:
                    print(f"[ERROR] Download/extract error: {e}")
                    requests.post(f"{SERVER_URL}/api/worker/update_job",
                                  headers=headers,
                                  json={"job_id": job_id, "status": "failed",
                                        "logs": f"Worker download error: {e}"})
                    time.sleep(POLL_INTERVAL)
                    continue

                # --- Execute pipeline subprocess ---
                print("[BUILD] Executing Submittal Builder Pipeline...")
                env = os.environ.copy()
                env["PROJECT_FOLDER"]   = local_job_dir
                env["HEADLESS_WORKER"]  = "TRUE"
                if api_key:
                    env["GEMINI_API_KEY"] = api_key

                process = subprocess.Popen(
                    [sys.executable, "SubmittalBuilderMetaAgent.py", "--web"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                # Stream logs; parse step progress from MetaAgent output
                logs      = ""
                log_chunk = ""
                for line in iter(process.stdout.readline, ""):
                    line_stripped = line.strip()
                    print(f"   {line_stripped}")
                    logs      += line
                    log_chunk += line

                    # Detect "STEP X OF 6: [BuilderName]" lines
                    step_match = re.search(r'STEP\s+(\d+)\s+OF\s+\d+.*\[(\w+)\]', line_stripped)
                    if step_match:
                        step_num  = int(step_match.group(1))
                        step_name = step_match.group(2)
                        post_step_update(headers, job_id, step_num, step_name, log_chunk)
                        log_chunk = ""

                    # Flush log chunks periodically (every ~20 lines)
                    elif len(log_chunk.splitlines()) >= 20:
                        post_step_update(headers, job_id, 0, "", log_chunk)
                        log_chunk = ""

                process.wait()

                if process.returncode == 0:
                    print("[OK] Build successful. Locating result files...")
                    all_pdfs, result_excel = find_result_files(local_job_dir)

                    if all_pdfs:
                        # --- Optional: copy to local output folder ---
                        if output_folder and os.path.isdir(output_folder):
                            try:
                                for pdf in all_pdfs:
                                    shutil.copy2(pdf, os.path.join(output_folder, os.path.basename(pdf)))
                                if result_excel:
                                    shutil.copy2(result_excel, os.path.join(output_folder, os.path.basename(result_excel)))
                                print(f"   [COPY] Copied results to: {output_folder}")
                            except Exception as e:
                                print(f"   [WARN] Could not copy to output folder: {e}")

                        # --- Zip all submittal PDFs ---
                        zip_result_path = os.path.join(local_job_dir, f"submittals_{job_id}.zip")
                        with zipfile.ZipFile(zip_result_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for pdf in all_pdfs:
                                zf.write(pdf, os.path.basename(pdf))
                        print(f"   [ZIP] Zipped {len(all_pdfs)} submittal(s).")

                        # --- Upload results ---
                        print("[UPLOAD] Uploading results to server...")
                        upload_files = {}
                        file_handles = []
                        try:
                            zip_f = open(zip_result_path, 'rb')
                            file_handles.append(zip_f)
                            upload_files['pdf'] = (os.path.basename(zip_result_path), zip_f, 'application/zip')

                            if result_excel:
                                excel_f = open(result_excel, 'rb')
                                file_handles.append(excel_f)
                                upload_files['excel'] = (
                                    os.path.basename(result_excel), excel_f,
                                    'application/vnd.ms-excel.sheet.macroEnabled.12'
                                )

                            upload_res = requests.post(
                                f"{SERVER_URL}/api/worker/upload_result",
                                headers=headers,
                                data={'job_id': job_id},
                                files=upload_files,
                                timeout=120
                            )
                            if upload_res.status_code == 200:
                                print(f"[DONE] Job #{job_id} complete. {len(all_pdfs)} submittal(s) uploaded.")
                            else:
                                print(f"[ERROR] Upload failed: {upload_res.text}")
                        finally:
                            for fh in file_handles:
                                fh.close()
                    else:
                        print("[ERROR] No submittal PDFs found in output folder.")
                        requests.post(f"{SERVER_URL}/api/worker/update_job",
                                      headers=headers,
                                      json={"job_id": job_id, "status": "failed",
                                            "logs": "Build finished but no Submittal PDFs found."})
                else:
                    print(f"[ERROR] Build failed (return code {process.returncode})")
                    requests.post(f"{SERVER_URL}/api/worker/update_job",
                                  headers=headers,
                                  json={"job_id": job_id, "status": "failed",
                                        "logs": logs[-2000:]})

        except Exception as e:
            print(f"[WARN] Worker Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_worker()
