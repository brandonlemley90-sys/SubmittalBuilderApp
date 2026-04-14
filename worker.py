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
SERVER_URL        = "https://submittalbuilderapp.onrender.com"
MASTER_ADMIN_KEY  = os.environ.get('MASTER_ADMIN_KEY', 'DenierSubmittalsLemley90')
POLL_INTERVAL     = 3
WORKER_EMAIL      = "blemley@denier.com"  # Set to YOUR account email
LOCAL_VERSION     = "2.2.0"              # Keep in sync with version.json

# -------------------------------------------------------------------
# AUTO-UPDATE
# -------------------------------------------------------------------
def check_for_update():
    """Download and restart if the server has a newer worker version."""
    try:
        r = requests.get(f"{SERVER_URL}/api/version", timeout=5)
        server_ver = r.json().get("version", LOCAL_VERSION)
        if server_ver != LOCAL_VERSION:
            print(f"[UPDATE] New version {server_ver} available. Downloading...")
            r2 = requests.get(f"{SERVER_URL}/api/worker/latest", timeout=15)
            r2.raise_for_status()
            new_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker_new.py")
            with open(new_path, 'wb') as f:
                f.write(r2.content)
            os.replace(new_path, os.path.abspath(__file__))
            print(f"[UPDATE] Updated to {server_ver}. Restarting...")
            subprocess.Popen([sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
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
    print("Keep this window open to process jobs from the website.")

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
