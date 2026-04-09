"""
DenierAI Local Worker v2.0
Polls lemley.pythonanywhere.com for queued build jobs, downloads uploaded
project files, runs the Excel macro pipeline on this Windows PC, then uploads
the resulting PDF and Excel back to the server.

REQUIREMENTS on this machine:
  - Python 3.x  with: requests
  - Microsoft Excel installed (for VBA macro execution via win32com)
  - tkinter (included with standard Python on Windows)
  - SubmittalBuilderMetaAgent.py in the same folder as this script
"""
import os
import sys
import time
import glob
import zipfile
import tempfile
import shutil
import subprocess
import requests
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import signal

# ─────────────────────────────────────────────────────────────
# SINGLE INSTANCE LOCK
# ─────────────────────────────────────────────────────────────
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.lock")

def check_single_instance():
    """Ensure only one instance of the worker is running."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # Check if process with this PID is actually running
            import ctypes
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, old_pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                print(f"\n[!] ERROR: Worker is already running (PID {old_pid}).")
                print("    Check Task Manager or close the other terminal window.")
                print("    (If you are sure it is not running, delete 'worker.lock' and retry)\n")
                time.sleep(5)
                sys.exit(0)
        except (ValueError, OSError):
            pass # Stale lock file

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def cleanup_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except:
            pass

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
SERVER_URL       = "https://lemley.pythonanywhere.com"   # ← PythonAnywhere site
MASTER_ADMIN_KEY = "DenierSubmittalsLemley90"
POLL_INTERVAL    = 10    # seconds between job polls
SHOW_TERMINAL    = True  # Set to False to run silently in background after testing

# Terminal visibility control
if not SHOW_TERMINAL:
    # Hide console window when running in production/background mode
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def find_result_files(folder_path, start_time=None):
    """
    Locate PDF and Excel files produced by the pipeline.
    When start_time (epoch float) is provided, only files modified AFTER
    that timestamp are considered – this prevents returning the original
    input files if the pipeline fails to generate new outputs.
    """
    pdfs   = glob.glob(os.path.join(folder_path, "**", "*.pdf"),   recursive=True)
    excels = glob.glob(os.path.join(folder_path, "**", "*.xlsm"),  recursive=True)
    if not excels:
        excels = glob.glob(os.path.join(folder_path, "**", "*.xlsx"), recursive=True)

    if start_time is not None:
        pdfs   = [f for f in pdfs   if os.path.getmtime(f) > start_time]
        excels = [f for f in excels if os.path.getmtime(f) > start_time]

    result_pdf   = max(pdfs,   key=os.path.getmtime) if pdfs   else None
    result_excel = max(excels, key=os.path.getmtime) if excels else None
    return result_pdf, result_excel


def download_project_files(job_folder_id: str, auth_header: dict) -> tuple[str, str]:
    """
    Download the project ZIP from the server, extract it to a temp folder.
    Returns (extract_dir, tmp_root) – caller must clean up tmp_root when done.
    """
    url  = f"{SERVER_URL}/api/worker/download_project/{job_folder_id}"
    resp = requests.get(url, headers=auth_header, timeout=120, stream=True)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Download failed: HTTP {resp.status_code}\n{resp.text[:300]}"
        )

    tmp_root    = tempfile.mkdtemp(prefix=f"denier_job_{job_folder_id}_")
    zip_path    = os.path.join(tmp_root, "project.zip")
    extract_dir = os.path.join(tmp_root, "project")
    os.makedirs(extract_dir)

    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    os.remove(zip_path)
    return extract_dir, tmp_root


def post_log(auth_header: dict, job_id: int, status: str, logs: str):
    """Flush an incremental log chunk to the server."""
    try:
        requests.post(
            f"{SERVER_URL}/api/worker/update_job",
            headers=auth_header,
            json={"job_id": job_id, "status": status, "logs": logs},
            timeout=15
        )
    except Exception as e:
        print(f"   [WARN] Could not post log: {e}")


# ─────────────────────────────────────────────────────────────
# MAIN WORKER LOOP
# ─────────────────────────────────────────────────────────────

def run_worker():
    print("=" * 60)
    print("  DenierAI Local Worker v2.1")
    print(f"  Server : {SERVER_URL}")
    print(f"  Job poll : every {POLL_INTERVAL}s  |  Browse poll : every 2s")
    print("=" * 60)
    print("Keep this window open.  Press Ctrl+C to stop.\n")

    auth_header = {"Authorization": MASTER_ADMIN_KEY}

    # Hidden tkinter root for folder dialogs – created once, reused
    _tk_root = tk.Tk()
    _tk_root.withdraw()
    _tk_root.attributes('-topmost', True)

    tick = 0   # increments every 2 seconds; controls sub-task frequency

    while True:
        tick += 1

        # ── BROWSE CHECK (every tick → every 2 s) ──────────────────────
        try:
            br = requests.get(
                f"{SERVER_URL}/api/worker/check_browse_output",
                headers=auth_header, timeout=4
            )
            if br.ok:
                bd = br.json()
                if bd.get("status") == "success":
                    req_email = bd["email"]
                    print(f"\n[BROWSE] 📂 Folder dialog requested by {req_email}")
                    selected = filedialog.askdirectory(
                        parent=_tk_root,
                        title="Select Output Folder for Submittals"
                    )
                    path = selected.replace('/', '\\') if selected else "CANCELLED"
                    requests.post(
                        f"{SERVER_URL}/api/worker/submit_browse_output",
                        headers=auth_header,
                        json={"email": req_email, "path": path},
                        timeout=10
                    )
                    print(f"         ✅  Returned: {path}\n")
        except Exception as _e:
            pass   # Browse check is entirely non-critical

        # ── SERVER PING (every 15 ticks → every 30 s) ──────────────────
        if tick % 15 == 0:
            try:
                requests.post(f"{SERVER_URL}/api/worker/ping",
                              headers=auth_header, timeout=5)
            except Exception:
                pass

        # ── JOB POLL (every 5 ticks → every 10 s) ──────────────────────
        if tick % 5 == 0:
            try:
                resp = requests.get(
                    f"{SERVER_URL}/api/worker/next_job",
                    headers=auth_header, timeout=15
                )
                if not resp.ok:
                    time.sleep(2)
                    continue

                data = resp.json()
                if data.get("status") != "success":
                    # No jobs waiting – quiet idle
                    time.sleep(2)
                    continue

                job_id        = data["job_id"]
                upload_path   = data["upload_path"]
                api_key       = data.get("api_key", "")
                project_name  = data.get("project_name", "Project")
                output_folder = data.get("output_folder", "")

                print(f"\n{'─'*60}")
                print(f"[JOB #{job_id}]  '{project_name}'")
                print(f"  Server folder:  {upload_path}")
                if output_folder:
                    print(f"  Output path:    {output_folder}")
                print(f"{'─'*60}")

                tmp_root_dir = None
                try:
                    # 1. Download project files
                    print("[1/4] Downloading project files from server...")
                    extract_dir, tmp_root_dir = download_project_files(
                        upload_path, auth_header
                    )
                    print(f"      Files: {os.listdir(extract_dir)}")

                    # 2. Run SubmittalBuilder agent
                    print("[2/4] Running Submittal Builder pipeline...")
                    script = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "SubmittalBuilderMetaAgent.py"
                    )
                    pipeline_start = time.time()  # Snapshot time – only files created AFTER this are outputs
                    env = os.environ.copy()
                    env["PROJECT_FOLDER"]    = extract_dir
                    env["HEADLESS_WORKER"]   = "TRUE"
                    env["PYTHONUTF8"]        = "1"          # Force UTF-8 stdout/stderr on Windows
                    env["PYTHONIOENCODING"]  = "utf-8"      # Belt-and-suspenders for older Python
                    if api_key:
                        env["GEMINI_API_KEY"] = api_key
                    if output_folder:
                        env["OUTPUT_FOLDER"] = output_folder
                        os.makedirs(output_folder, exist_ok=True)
                        print(f"      Output folder ready: {output_folder}")

                    process = subprocess.Popen(
                        [sys.executable, script, "--web"],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,  # Enable stdin for prompt responses
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1
                    )
                    logs = log_buf = ""
                    current_prompt_id = None

                    for line in iter(process.stdout.readline, ""):
                        line_stripped = line.rstrip()

                        # Check if this line contains a prompt
                        if line_stripped.startswith("___PROMPT___|"):
                            parts = line_stripped.split("|", 2)
                            if len(parts) >= 3:
                                prompt_type = parts[1]
                                message = parts[2]

                                # Post prompt to server
                                try:
                                    resp = requests.post(
                                        f"{SERVER_URL}/api/worker/submit_prompt",
                                        headers=auth_header,
                                        json={
                                            "job_id": job_id,
                                            "prompt_type": prompt_type,
                                            "message": message
                                        },
                                        timeout=10
                                    )
                                    if resp.status_code == 200:
                                        current_prompt_id = resp.json().get("prompt_id")
                                        print(f"   [PROMPT] Waiting for user response...")

                                        # Poll for user response
                                        while True:
                                            time.sleep(2)  # Poll every 2 seconds
                                            check_resp = requests.get(
                                                f"{SERVER_URL}/api/worker/get_prompt_response/{current_prompt_id}",
                                                headers=auth_header,
                                                timeout=10
                                            )
                                            if check_resp.status_code == 200:
                                                check_data = check_resp.json()
                                                if check_data.get("status") == "success":
                                                    user_response = check_data.get("response", "")
                                                    print(f"   [PROMPT] User responded: {user_response}")
                                                    process.stdin.write(user_response + "\n")
                                                    process.stdin.flush()
                                                    current_prompt_id = None
                                                    break
                                                elif check_data.get("status") == "waiting":
                                                    continue
                                except Exception as e:
                                    print(f"   [WARN] Prompt handling error: {e}")
                                    # Fall back to allowing process to continue
                                    process.stdin.write("\n")
                                    process.stdin.flush()
                        else:
                            print(f"   {line_stripped}")
                            logs    += line
                            log_buf += line
                            if len(log_buf) >= 3000:
                                post_log(auth_header, job_id, "processing", log_buf)
                                log_buf = ""

                    process.wait()
                    if log_buf:
                        post_log(auth_header, job_id, "processing", log_buf)

                    # 3. Upload results
                    if process.returncode == 0:
                        print("[3/4] Locating output files...")
                        pdf_path, excel_path = find_result_files(extract_dir, pipeline_start)
                        if pdf_path and excel_path:
                            print(f"      PDF:   {os.path.basename(pdf_path)}")
                            print(f"      Excel: {os.path.basename(excel_path)}")
                            print("[4/4] Uploading results to server...")
                            with open(pdf_path, "rb") as pf, \
                                 open(excel_path, "rb") as ef:
                                up = requests.post(
                                    f"{SERVER_URL}/api/worker/upload_result",
                                    headers=auth_header,
                                    data={"job_id": job_id},
                                    files={
                                        "pdf":   (os.path.basename(pdf_path),   pf,  "application/pdf"),
                                        "excel": (os.path.basename(excel_path), ef,
                                                  "application/vnd.ms-excel.sheet.macroEnabled.12"),
                                    },
                                    timeout=180
                                )
                            if up.status_code == 200:
                                print(f"[DONE] Job #{job_id} completed. ✅")
                            else:
                                print(f"[ERR]  Upload failed {up.status_code}: {up.text[:200]}")
                        else:
                            print("[ERR]  No PDF/Excel found after pipeline run.")
                            post_log(auth_header, job_id, "failed",
                                     "Result files not found after pipeline.")
                    else:
                        print(f"[ERR]  Pipeline exit code {process.returncode}")
                        post_log(auth_header, job_id, "failed",
                                 f"Exit code {process.returncode}\n{logs[-2000:]}")

                except Exception as exc:
                    print(f"[ERR]  Job #{job_id}: {exc}")
                    post_log(auth_header, job_id, "failed", str(exc))

                finally:
                    if tmp_root_dir and os.path.exists(tmp_root_dir):
                        shutil.rmtree(tmp_root_dir, ignore_errors=True)
                        print("      Temp folder cleaned up.")

            except requests.exceptions.ConnectionError:
                print(f"[WARN] Cannot reach {SERVER_URL} – retrying...")
            except Exception as e:
                print(f"[WARN] Job poll error: {e}")

        time.sleep(2)


if __name__ == "__main__":
    print("\n" + "═"*60)
    print("  DENIER ELECTRIC - SUBMITTAL BUILDER WORKER v2.1")
    print("  Mode:   DEVELOPMENT (TERMINAL VISIBLE)")
    print(f"  PID:    {os.getpid()}")
    print(f"  Server: {SERVER_URL}")
    print("═"*60)
    print("Keep this window open to monitor progress.\n")

    check_single_instance()
    try:
        run_worker()
    except KeyboardInterrupt:
        print("\n[!] User stopped the worker.")
    finally:
        cleanup_lock()
        print("[*] Lock file removed.")