import os
import sys
import time
import json
import requests
import subprocess
import glob
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# --- CONFIGURATION ---
# The actual Render URL
SERVER_URL = "https://submittalbuilderapp.onrender.com" 
MASTER_ADMIN_KEY = "DenierSubmittalsLemley90"
POLL_INTERVAL = 3  
WORKER_EMAIL = "blemley@denier.com" # Set this to YOUR account email

def find_result_files(folder_path):
    """Try to find the generated submittal PDF and updated Excel in the folder."""
    # Look for the most recently modified PDF and XLSM files
    pdfs = glob.glob(os.path.join(folder_path, "*.pdf"))
    excels = glob.glob(os.path.join(folder_path, "*.xlsm"))
    
    # Prioritize the combined package if it exists
    combined = [p for p in pdfs if "COMPLETE_SUBMITTAL_PACKAGE" in os.path.basename(p)]
    if combined:
        result_pdf = combined[0]
    else:
        result_pdf = max(pdfs, key=os.path.getmtime) if pdfs else None
        
    result_excel = max(excels, key=os.path.getmtime) if excels else None
    
    return result_pdf, result_excel

def run_worker():
    print(f"🚀 DenierAI Local Worker Started (Polling {SERVER_URL})...")
    print("Keep this window open to process jobs from the website.")
    
    # Hidden root for tkinter dialogs
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    while True:
        try:
            headers = {"Authorization": MASTER_ADMIN_KEY}

            # 0. Check for Remote Browse Requests (Handshake)
            browse_res = requests.get(f"{SERVER_URL}/api/worker/check_browse_output", 
                                      headers=headers, 
                                      params={"email": WORKER_EMAIL},
                                      timeout=5)
            if browse_res.status_code == 200:
                b_data = browse_res.json()
                if b_data.get("status") == "success":
                    email = b_data['email']
                    print(f"📂 Remote Browse Request from {email}...")
                    selected_path = filedialog.askdirectory(title="Select Project Output Folder")
                    if selected_path:
                        normalized = os.path.normpath(selected_path)
                        requests.post(f"{SERVER_URL}/api/worker/submit_browse_output", 
                                     headers=headers, 
                                     json={"email": email, "path": normalized})
                        print(f"   ✅ Path sent: {normalized}")
                    else:
                        requests.post(f"{SERVER_URL}/api/worker/submit_browse_output", 
                                     headers=headers, 
                                     json={"email": email, "path": "CANCELLED"})

            # Send heartbeat ping
            requests.post(f"{SERVER_URL}/api/worker/ping", headers=headers, timeout=5)

            # 1. Ask the server for the next job
            response = requests.get(f"{SERVER_URL}/api/worker/next_job", 
                                    headers=headers, 
                                    params={"email": WORKER_EMAIL},
                                    timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    job_id = data["job_id"]
                    job_folder_id = data["upload_path"]
                    api_key = data.get("api_key", "")
                    output_folder = data.get("output_folder", "")
                    
                    print(f"\n[JOB #{job_id}] Received job. Downloading project files...")

                    # 2. Download and Extract Project Files
                    local_job_dir = os.path.join(os.getcwd(), "worker_jobs", job_folder_id)
                    os.makedirs(local_job_dir, exist_ok=True)
                    
                    try:
                        dl_res = requests.get(f"{SERVER_URL}/api/worker/download_project/{job_folder_id}", headers=headers, stream=True)
                        if dl_res.status_code == 200:
                            zip_path = os.path.join(local_job_dir, "project.zip")
                            with open(zip_path, 'wb') as f:
                                for chunk in dl_res.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            import zipfile
                            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                zip_ref.extractall(local_job_dir)
                            os.remove(zip_path) # Clean up zip
                            print(f"   ✅ Project files downloaded and extracted to: {local_job_dir}")
                        else:
                            raise Exception(f"Failed to download project files: {dl_res.status_code}")
                    except Exception as e:
                        print(f"❌ Error downloading/extracting: {e}")
                        requests.post(f"{SERVER_URL}/api/worker/update_job", 
                                     headers=headers, 
                                     json={"job_id": job_id, "status": "failed", "logs": f"Worker error: {str(e)}"})
                        continue

                    # 3. Execute the Meta Agent
                    print("🔨 Executing Submittal Builder Pipeline...")
                    env = os.environ.copy()
                    env["PROJECT_FOLDER"] = local_job_dir
                    env["HEADLESS_WORKER"] = "TRUE"
                    if api_key: env["GEMINI_API_KEY"] = api_key 
                    
                    process = subprocess.Popen(
                        [sys.executable, "SubmittalBuilderMetaAgent.py", "--web"],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    
                    # Capture logs and send to server
                    logs = ""
                    for line in iter(process.stdout.readline, ""):
                        print(f"   {line.strip()}")
                        logs += line

                    process.wait()
                    
                    if process.returncode == 0:
                        print("✅ Build successful. Locating result files...")
                        pdf_path, excel_path = find_result_files(local_job_dir)
                        
                        if pdf_path and excel_path:
                            # 4. Optional: Copy to user's local output folder if specified and accessible
                            if output_folder and os.path.isdir(output_folder):
                                try:
                                    import shutil
                                    shutil.copy2(pdf_path, os.path.join(output_folder, os.path.basename(pdf_path)))
                                    shutil.copy2(excel_path, os.path.join(output_folder, os.path.basename(excel_path)))
                                    print(f"   📂 Also copied results to: {output_folder}")
                                except Exception as e:
                                    print(f"   ⚠️ Could not copy to local output folder: {e}")

                            # 5. Upload results to server
                            print(f"⬆️ Uploading results to server...")
                            with open(pdf_path, 'rb') as pdf_f, open(excel_path, 'rb') as excel_f:
                                files = {
                                    'pdf': (os.path.basename(pdf_path), pdf_f, 'application/pdf'),
                                    'excel': (os.path.basename(excel_path), excel_f, 'application/vnd.ms-excel.sheet.macroEnabled.12')
                                }
                                upload_res = requests.post(
                                    f"{SERVER_URL}/api/worker/upload_result",
                                    headers=headers,
                                    data={'job_id': job_id},
                                    files=files,
                                    timeout=60
                                )
                                if upload_res.status_code == 200:
                                    print("🎉 Job completed and results uploaded.")
                                    # Optional: Clean up local job dir?
                                    # shutil.rmtree(local_job_dir)
                                else:
                                    print(f"❌ Upload failed: {upload_res.text}")
                        else:
                            print("❌ Could not find result files in folder.")
                            requests.post(f"{SERVER_URL}/api/worker/update_job", 
                                         headers=headers, 
                                         json={"job_id": job_id, "status": "failed", "logs": "Build finished but results not found."})
                    else:
                        print(f"❌ Build failed with return code {process.returncode}")
                        requests.post(f"{SERVER_URL}/api/worker/update_job", 
                                     headers=headers, 
                                     json={"job_id": job_id, "status": "failed", "logs": logs[-2000:]}) 
                else:
                    # No pending jobs
                    pass
            else:
                print(f"⚠️ Server status error: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Worker Error: {e}")
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run_worker()
