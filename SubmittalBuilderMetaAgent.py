import os
import sys
import json
import requests
import re
import time
import tkinter as tk
from tkinter import filedialog, simpledialog
import builder_shared as shared

BUILDER_MODULES = [
    "BoxesBuilder",
    "GroundingandBondingBuilder",
    "HangersandSupports",
    "RacewaysBuilder",
    "WireandCableBuilder",
    "WiringDevicesBuilder"
]

def scan_project_folder(folder_path):
    """Auto-identify project files from folder contents."""
    config = {
        "PROJECT_FOLDER":      os.path.normpath(folder_path),
        "EXCEL_WORKBOOK_NAME": "",
        "JOB_FORM_PDF_NAME":   "",
        "SPEC_PDF_NAME":       "",
        "DRAWINGS_PDF_NAME":   "",
        "CONTRACT_PDF_NAME":   ""
    }
    if not os.path.exists(folder_path):
        return config

    for f in os.listdir(folder_path):
        f_lower = f.lower()
        if f_lower.endswith(('.xlsm', '.xlsx')) and not f.startswith('~$'):
            if 'index' in f_lower or 'master' in f_lower or not config["EXCEL_WORKBOOK_NAME"]:
                config["EXCEL_WORKBOOK_NAME"] = f
        if f_lower.endswith('.pdf'):
            if re.match(r'\d{2}-\d{2}-\d{4}', f):
                config["JOB_FORM_PDF_NAME"] = f
            elif 'spec' in f_lower:
                config["SPEC_PDF_NAME"] = f
            elif 'drawing' in f_lower or 'plan' in f_lower or 'dwg' in f_lower:
                config["DRAWINGS_PDF_NAME"] = f
            elif 'contract' in f_lower:
                config["CONTRACT_PDF_NAME"] = f
    return config

def get_user_setup():
    """Opens Windows dialogs to get API key and project files (desktop mode)."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    api_key = simpledialog.askstring(
        title="Gemini API Key Required",
        prompt="🔑 Please enter your Gemini API Key:",
        show="*"
    )
    if not api_key or not api_key.strip():
        print("🛑 Operation cancelled (No API Key).")
        sys.exit(0)

    print("📁 Please select the Main Project Folder...")
    project_folder = filedialog.askdirectory(title="Select Main Project Folder")
    if not project_folder:
        print("🛑 Operation cancelled.")
        sys.exit(0)

    def pick_file(title, filetypes):
        return filedialog.askopenfilename(initialdir=project_folder, title=title, filetypes=filetypes)

    excel_path    = pick_file("Select Excel Workbook",      [("Excel Files", "*.xlsm;*.xlsx")])
    job_form_path = pick_file("Select Job Setup Form PDF",  [("PDF Files", "*.pdf")])
    spec_path     = pick_file("Select Specs PDF",           [("PDF Files", "*.pdf")])
    drawings_path = pick_file("Select Drawings PDF",        [("PDF Files", "*.pdf")])
    contract_path = pick_file("Select Contract PDF",        [("PDF Files", "*.pdf")])
    root.destroy()

    project_config = {
        "PROJECT_FOLDER":      os.path.normpath(project_folder),
        "EXCEL_WORKBOOK_NAME": os.path.basename(excel_path)    if excel_path    else "",
        "JOB_FORM_PDF_NAME":   os.path.basename(job_form_path) if job_form_path else "",
        "SPEC_PDF_NAME":       os.path.basename(spec_path)     if spec_path     else "",
        "DRAWINGS_PDF_NAME":   os.path.basename(drawings_path) if drawings_path else "",
        "CONTRACT_PDF_NAME":   os.path.basename(contract_path) if contract_path else "",
    }
    return api_key.strip(), project_config

def run_pipeline(master_api_key, project_config):
    # --- Validate API key ---
    if not master_api_key or len(master_api_key.strip()) < 10:
        shared.log("ERROR: No valid Gemini API key provided. Halting.", "ERROR")
        return

    # --- Extract job info from form PDF ---
    shared.log("--- Extracting Job Core Info from Form ---", "SYSTEM")
    form_pdf_path  = os.path.join(project_config["PROJECT_FOLDER"], project_config.get("JOB_FORM_PDF_NAME", ""))
    extracted_job_info = {"Job_Number": "Unknown", "Job_Name": "Unknown", "Address": "", "City_State_Zip": ""}

    if os.path.exists(form_pdf_path):
        name_match = re.match(r'(\d{2}-\d{2}-\d{4})\s*-\s*(.*)\.pdf',
                              project_config.get("JOB_FORM_PDF_NAME", ""), re.IGNORECASE)
        if name_match:
            extracted_job_info["Job_Number"] = name_match.group(1).strip()
            extracted_job_info["Job_Name"]   = name_match.group(2).strip()

        form_text = shared.extract_pdf_text(form_pdf_path)
        prompt = ('Extract project details. Return raw JSON.\n'
                  'Keys: "Job_Number", "Job_Name", "Address", "City_State_Zip"')
        try:
            shared.log("Asking AI to extract address information...", "AI")
            raw = shared.call_gemini(master_api_key, prompt, form_text[:15000])
            ai_data = json.loads(raw)
            for k in extracted_job_info:
                if ai_data.get(k):
                    extracted_job_info[k] = ai_data[k]
            shared.log(f"Extracted: {extracted_job_info['Job_Number']} | {extracted_job_info['Address']}", "SYSTEM")
        except Exception as e:
            shared.log(f"Form extraction partial: {e}", "WARNING")

    if not extracted_job_info["Job_Name"] or extracted_job_info["Job_Name"] == "Unknown":
        extracted_job_info["Job_Name"] = os.path.basename(project_config["PROJECT_FOLDER"])

    # --- Build shared context ---
    context = {
        "api_key":        master_api_key,
        "project_config": project_config,
        "job_info":       extracted_job_info,
        "wb":             None
    }

    excel_path = os.path.join(project_config["PROJECT_FOLDER"], project_config.get("EXCEL_WORKBOOK_NAME", ""))
    shared.log(f"Opening Excel Workbook: {project_config.get('EXCEL_WORKBOOK_NAME', '')}", "EXCEL")
    context["wb"] = shared.get_workbook(excel_path)
    if not context["wb"]:
        shared.log("Could not open Excel. Halting.", "ERROR")
        return

    shared.log("Initiating One-Click Pipeline...", "SYSTEM")

    # --- Run each builder sequentially ---
    completed_pdfs = []
    for i, mod_name in enumerate(BUILDER_MODULES):
        shared.log(f"STEP {i + 1} OF {len(BUILDER_MODULES)}: [{mod_name}]", "PIPELINE")
        try:
            module      = __import__(mod_name)
            result_path = module.run(context)   # returns path string or None

            if result_path and os.path.exists(result_path):
                shared.log(f"[{mod_name}] Submittal ready: {os.path.basename(result_path)}", "PIPELINE")
                completed_pdfs.append(result_path)
                if i < len(BUILDER_MODULES) - 1:
                    shared.prompt("ENTER", "Review document. Press CONFIRM / PROCEED for next builder.")
            else:
                shared.log(f"[{mod_name}] Failed or no output. Halting pipeline.", "ERROR")
                break

        except ImportError:
            shared.log(f"Could not find builder module: {mod_name}", "ERROR")
            break
        except Exception as e:
            shared.log(f"Error in {mod_name}: {e}", "ERROR")
            break

    shared.log(f"Pipeline complete. {len(completed_pdfs)} of {len(BUILDER_MODULES)} submittals built.", "PIPELINE")
    for pdf in completed_pdfs:
        shared.log(f"  - {os.path.basename(pdf)}", "PIPELINE")

    if completed_pdfs:
        shared.log("ALL SUBMITTALS COMPLETED SUCCESSFULLY!", "PIPELINE")
    else:
        shared.log("No submittals were generated. Check logs above.", "WARNING")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        api_key     = os.environ.get("GEMINI_API_KEY", "")
        folder_path = os.environ.get("PROJECT_FOLDER", "")
        project_config = scan_project_folder(folder_path)
        for key in ["EXCEL_WORKBOOK_NAME", "JOB_FORM_PDF_NAME", "SPEC_PDF_NAME",
                    "DRAWINGS_PDF_NAME", "CONTRACT_PDF_NAME"]:
            val = os.environ.get(key)
            if val:
                project_config[key] = val
        run_pipeline(api_key, project_config)
    else:
        user_api_key, user_project_files = get_user_setup()
        run_pipeline(user_api_key, user_project_files)
