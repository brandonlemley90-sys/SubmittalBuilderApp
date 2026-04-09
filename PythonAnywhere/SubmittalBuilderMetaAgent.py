import subprocess
import os
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog
import json
import requests
import re
import time
import fitz

def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        return ""
    try:
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        return text
    except Exception:
        return ""

def call_llm_api(api_key, prompt, data):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n{data}"}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code == 200:
        raw = response.json()['candidates'][0]['content']['parts'][0]['text']
        return raw.strip().removeprefix('```json').removesuffix('```').strip()
    return "{}"

def web_prompt(prompt_type, message):
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        print(f"___PROMPT___|{prompt_type}|{message}")
        sys.stdout.flush()
        return sys.stdin.readline().strip()
    else:
        return input(message).strip()


def scan_project_folder(folder_path):
    """Scan the folder and try to auto-identify project files."""
    config = {
        "PROJECT_FOLDER": os.path.normpath(folder_path),
        "EXCEL_WORKBOOK_NAME": "",
        "JOB_FORM_PDF_NAME": "",
        "SPEC_PDF_NAME": "",
        "DRAWINGS_PDF_NAME": "",
        "CONTRACT_PDF_NAME": ""
    }
    
    if not os.path.exists(folder_path):
        return config

    try:
        files = os.listdir(folder_path)
        for f in files:
            f_lower = f.lower()
            # Excel Index
            if f_lower.endswith(('.xlsm', '.xlsx')) and not f.startswith('~$'):
                # Prioritize 'Index' or 'Master' but take any excel if empty
                if 'index' in f_lower or 'master' in f_lower or not config["EXCEL_WORKBOOK_NAME"]:
                    config["EXCEL_WORKBOOK_NAME"] = f
            
            # PDFs
            if f_lower.endswith('.pdf'):
                # Job Form (XX-XX-XXXX pattern)
                if re.match(r'\d{2}-\d{2}-\d{4}', f):
                    config["JOB_FORM_PDF_NAME"] = f
                elif 'spec' in f_lower:
                    config["SPEC_PDF_NAME"] = f
                elif 'drawing' in f_lower or 'plan' in f_lower:
                    config["DRAWINGS_PDF_NAME"] = f
                elif 'contract' in f_lower:
                    config["CONTRACT_PDF_NAME"] = f
    except Exception as e:
        print(f"   ⚠️ Error scanning folder: {e}")
                
    return config

def get_user_setup():
    """Opens Windows file dialogs to get the API key, project folder, and files."""
    # Create the main hidden UI window once
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    # 1. 🔑 POP-UP FOR API KEY
    api_key = simpledialog.askstring(
        title="Gemini API Key Required",
        prompt="🔑 Please enter your Gemini API Key:\n\n(This is securely held in memory for this session only)",
        show="*"  # This masks the characters like a password field
    )

    if not api_key or not api_key.strip():
        print("🛑 Operation cancelled (No API Key provided).")
        sys.exit(0)

    # 2. 📁 POP-UPS FOR PROJECT FILES
    print("📁 Please select the Main Project Folder...")
    project_folder = filedialog.askdirectory(title="Select Main Project Folder")

    if not project_folder:
        print("🛑 Operation cancelled by user (No folder selected).")
        sys.exit(0)

    # Auto-detect within folder
    project_config = scan_project_folder(project_folder)

    # Destroy the hidden root window now that all pop-ups are done
    root.destroy()

    return api_key.strip(), project_config


def run_pipeline(master_api_key, project_config):
    scripts = [
        "BoxesBuilder.py",
        "GroundingandBondingBuilder.py",
        "HangersandSupports.py",
        "RacewaysBuilder.py",
        "WireandCableBuilder.py",
        "WiringDevicesBuilder.py"
    ]

    env_vars = os.environ.copy()

    # Inject the captured API Key and Paths into the execution environment
    env_vars["GEMINI_API_KEY"] = master_api_key
    env_vars["PROJECT_FOLDER"] = project_config["PROJECT_FOLDER"]
    env_vars["EXCEL_WORKBOOK_NAME"] = project_config["EXCEL_WORKBOOK_NAME"]
    env_vars["JOB_FORM_PDF_NAME"] = project_config["JOB_FORM_PDF_NAME"]
    env_vars["SPEC_PDF_NAME"] = project_config["SPEC_PDF_NAME"]
    env_vars["DRAWINGS_PDF_NAME"] = project_config["DRAWINGS_PDF_NAME"]
    env_vars["CONTRACT_PDF_NAME"] = project_config["CONTRACT_PDF_NAME"]

    print("--- Extracting Job Core Info from Form ---")
    form_pdf_path = os.path.join(project_config["PROJECT_FOLDER"], project_config["JOB_FORM_PDF_NAME"])
    extracted_job_info = {"Job_Number": "Unknown", "Job_Name": "Unknown", "Address": "", "City_State_Zip": ""}
    
    if os.path.exists(form_pdf_path) and "ERROR" not in form_pdf_path:
        name_match = re.match(r'(\d{2}-\d{2}-\d{4})\s*-\s*(.*)\.pdf', project_config["JOB_FORM_PDF_NAME"], re.IGNORECASE)
        if name_match:
            extracted_job_info["Job_Number"] = name_match.group(1).strip()
            extracted_job_info["Job_Name"] = name_match.group(2).strip()

        form_text = extract_text_from_pdf(form_pdf_path)
        prompt = f"""
        Extract the project details from the following form text and filename.
        Filename: {project_config["JOB_FORM_PDF_NAME"]}
        RULES:
        1. Find the Job Number (format usually XX-XX-XXXX).
        2. Find the Job Name (Project Name).
        3. Find the Street Address.
        4. Find the City, State, and Zip Code.
        Return ONLY a raw JSON object with these exact keys:
        "Job_Number", "Job_Name", "Address", "City_State_Zip"
        """
        try:
            print("   Asking AI to extract address information from the form...")
            raw_job_ai = call_llm_api(master_api_key, prompt, form_text[:15000])
            ai_data = json.loads(raw_job_ai)
            for k in extracted_job_info.keys():
                if ai_data.get(k): extracted_job_info[k] = ai_data[k]
            print(f"   ✅ Extracted Data: {extracted_job_info['Job_Number']} | {extracted_job_info['Address']}")
        except Exception as e:
            print(f"   ⚠️ Could not fully extract data from form using AI: {e}")
    else:
        print("   ⚠️ No Job Setup Form was selected. Moving on...")

    # Fallback to folder name if extraction failed
    if not extracted_job_info["Job_Name"] or extracted_job_info["Job_Name"] == "Unknown":
        extracted_job_info["Job_Name"] = os.path.basename(project_config["PROJECT_FOLDER"])

    env_vars["META_JOB_NUMBER"] = extracted_job_info["Job_Number"]
    env_vars["META_JOB_NAME"] = extracted_job_info["Job_Name"]
    env_vars["META_JOB_ADDRESS"] = extracted_job_info["Address"]
    env_vars["META_JOB_CITY_STATE_ZIP"] = extracted_job_info["City_State_Zip"]

    # Let the builder scripts know they don't need to prompt for an API key manually
    env_vars["RUNNING_FROM_META"] = "TRUE"
    if "--web" in sys.argv:
        env_vars["RUNNING_FROM_WEB"] = "TRUE"

    print(f"\n🚀 Initiating One-Click Pipeline for folder:\n{project_config['PROJECT_FOLDER']}\n")

    for i, script in enumerate(scripts):
        print("\n" + "=" * 60)
        print(f"📦 STEP {i + 1} OF {len(scripts)}: Executing [{script}]")
        print("=" * 60 + "\n")

        if not os.path.exists(script):
            print(f"❌ Error: Could not find '{script}' in the current directory.")
            continue

        try:
            # The Meta Agent freezes on this line until the child script finishes
            result = subprocess.run(
                [sys.executable, script],
                env=env_vars,
                check=True
            )
            print(f"\n✅ [{script}] -> Successfully Built.")

            # If there are more scripts left, explicitly pause the pipeline
            if i < len(scripts) - 1:
                print("\n⏸️  PIPELINE PAUSED.")
                web_prompt("ENTER", "Review your document. Press 'CONFIRM / PROCEED' when ready to start the next submittal.")

        except subprocess.CalledProcessError as e:
            print(f"\n❌ [{script}] -> FAILED.")
            print("🛑 Pipeline halted to prevent downstream errors.")
            break

    else:
        # This only runs if the loop finishes without hitting a 'break' (error)
        print("\n" + "🎉" * 20)
        print("ALL SUBMITTALS COMPLETED SUCCESSFULLY!")
        print("🎉" * 20 + "\n")


if __name__ == "__main__":
    # If the Web App launches this file, it will pass "--web" as an argument
    if len(sys.argv) > 1 and sys.argv[1] == "--web":

        # 1. Pull the data that the Web Server injected into memory
        api_key = os.environ.get("GEMINI_API_KEY", "")
        folder_path = os.environ.get("PROJECT_FOLDER", "")
        
        # Auto-detect files if names weren't provided
        project_config = scan_project_folder(folder_path)
        
        # Override with env vars if they exist
        for key in ["EXCEL_WORKBOOK_NAME", "JOB_FORM_PDF_NAME", "SPEC_PDF_NAME", "DRAWINGS_PDF_NAME", "CONTRACT_PDF_NAME"]:
            val = os.environ.get(key)
            if val: project_config[key] = val

        # 2. Run the pipeline
        run_pipeline(api_key, project_config)

        # 3. Prevent the new native window from closing instantly when finished
        print("\n" + "=" * 60)
        # In automation mode (worker), we don't want to wait for an ENTER if it's headless
        if os.environ.get("HEADLESS_WORKER") != "TRUE":
            web_prompt("ENTER", "All builds complete. You may close this page.")

    else:
        # If you run it manually without the web app, use the old tkinter pop-ups
        user_api_key, user_project_files = get_user_setup()
        run_pipeline(user_api_key, user_project_files)