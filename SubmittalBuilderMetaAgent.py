import os
import sys
import json
import requests
import re
import time
import glob
import tkinter as tk
from tkinter import filedialog, simpledialog
import builder_shared as shared

# Dynamically import builders here (they need to exist or we handle missing ones)
BUILDER_MODULES = [
    "BoxesBuilder",
    "GroundingandBondingBuilder",
    "HangersandSupports",
    "RacewaysBuilder",
    "WireandCableBuilder",
    "WiringDevicesBuilder"
]

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
                
    return config

def get_user_setup():
    """Opens Windows file dialogs to get the API key, project folder, and files."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    api_key = simpledialog.askstring(
        title="Gemini API Key Required",
        prompt="🔑 Please enter your Gemini API Key:\n\n(This is securely held in memory for this session only)",
        show="*"
    )

    if not api_key or not api_key.strip():
        print("🛑 Operation cancelled (No API Key provided).")
        sys.exit(0)

    print("📁 Please select the Main Project Folder...")
    project_folder = filedialog.askdirectory(title="Select Main Project Folder")

    if not project_folder:
        print("🛑 Operation cancelled by user (No folder selected).")
        sys.exit(0)

    print("📊 Please select the Excel Workbook...")
    excel_path = filedialog.askopenfilename(
        initialdir=project_folder, title="Select Excel Workbook",
        filetypes=[("Excel Files", "*.xlsm;*.xlsx")]
    )

    print("📝 Please select the Job Setup Form PDF...")
    job_form_path = filedialog.askopenfilename(
        initialdir=project_folder, title="Select Job Setup Form PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    print("📄 Please select the Specs PDF...")
    spec_path = filedialog.askopenfilename(
        initialdir=project_folder, title="Select Specs PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    print("📐 Please select the Drawings PDF...")
    drawings_path = filedialog.askopenfilename(
        initialdir=project_folder, title="Select Drawings PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    print("🤝 Please select the Contract PDF...")
    contract_path = filedialog.askopenfilename(
        initialdir=project_folder, title="Select Contract PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    root.destroy()

    project_config = {
        "PROJECT_FOLDER": os.path.normpath(project_folder),
        "EXCEL_WORKBOOK_NAME": os.path.basename(excel_path) if excel_path else "",
        "JOB_FORM_PDF_NAME": os.path.basename(job_form_path) if job_form_path else "",
        "SPEC_PDF_NAME": os.path.basename(spec_path) if spec_path else "",
        "DRAWINGS_PDF_NAME": os.path.basename(drawings_path) if drawings_path else "",
        "CONTRACT_PDF_NAME": os.path.basename(contract_path) if contract_path else ""
    }

    return api_key.strip(), project_config

def run_pipeline(master_api_key, project_config):
    shared.log("--- Extracting Job Core Info from Form ---", "SYSTEM")
    form_pdf_path = os.path.join(project_config["PROJECT_FOLDER"], project_config["JOB_FORM_PDF_NAME"])
    extracted_job_info = {"Job_Number": "Unknown", "Job_Name": "Unknown", "Address": "", "City_State_Zip": ""}
    
    if os.path.exists(form_pdf_path) and "ERROR" not in form_pdf_path:
        name_match = re.match(r'(\d{2}-\d{2}-\d{4})\s*-\s*(.*)\.pdf', project_config["JOB_FORM_PDF_NAME"], re.IGNORECASE)
        if name_match:
            extracted_job_info["Job_Number"] = name_match.group(1).strip()
            extracted_job_info["Job_Name"] = name_match.group(2).strip()

        form_text = shared.extract_pdf_text(form_pdf_path)
        prompt = """
        Extract project details. Return raw JSON. 
        Keys: "Job_Number", "Job_Name", "Address", "City_State_Zip"
        """
        try:
            shared.log("Asking AI to extract address information...", "AI")
            raw_job_ai = shared.call_gemini(master_api_key, prompt, form_text[:15000])
            ai_data = json.loads(raw_job_ai)
            for k in extracted_job_info.keys():
                if ai_data.get(k): extracted_job_info[k] = ai_data[k]
            shared.log(f"Extracted: {extracted_job_info['Job_Number']} | {extracted_job_info['Address']}", "SYSTEM")
        except Exception as e:
            shared.log(f"Form extraction partial: {e}", "WARNING")

    if not extracted_job_info["Job_Name"] or extracted_job_info["Job_Name"] == "Unknown":
        extracted_job_info["Job_Name"] = os.path.basename(project_config["PROJECT_FOLDER"])

    # Build consistent context for all builders
    context = {
        "api_key": master_api_key,
        "project_config": project_config,
        "job_info": extracted_job_info,
        "wb": None # Will open shortly
    }

    excel_path = os.path.join(project_config["PROJECT_FOLDER"], project_config["EXCEL_WORKBOOK_NAME"])
    shared.log(f"Opening Excel Workbook: {project_config['EXCEL_WORKBOOK_NAME']}", "EXCEL")
    context["wb"] = shared.get_workbook(excel_path)
    if not context["wb"]:
        shared.log("Could not open Excel. Halting.", "ERROR")
        return

    shared.log(f"Initiating One-Click Pipeline...", "SYSTEM")

    for i, mod_name in enumerate(BUILDER_MODULES):
        shared.log(f"STEP {i + 1} OF {len(BUILDER_MODULES)}: [{mod_name}]", "PIPELINE")
        
        try:
            # Import builder dynamically
            module = __import__(mod_name)
            
            # Execute the builder
            success = module.run(context)
            
            if success:
                shared.log(f"[{mod_name}] Successfully Completed.", "PIPELINE")
                if i < len(BUILDER_MODULES) - 1:
                    shared.prompt("ENTER", "Review document. Press 'CONFIRM / PROCEED' for next builder.")
            else:
                shared.log(f"[{mod_name}] Failed. Halting pipeline.", "ERROR")
                break
                
        except ImportError:
            shared.log(f"Could not find builder module: {mod_name}", "ERROR")
            break
        except Exception as e:
            shared.log(f"Error in {mod_name}: {e}", "ERROR")
            break

    shared.log("Generating Combined Submittal Package...", "PIPELINE")
    try:
        import fitz
        output_folder = project_config["PROJECT_FOLDER"]
        all_pdfs = glob.glob(os.path.join(output_folder, "*.pdf"))
        
        originals = [project_config.get(k) for k in ["SPEC_PDF_NAME", "DRAWINGS_PDF_NAME", "CONTRACT_PDF_NAME", "JOB_FORM_PDF_NAME"]]
        originals = [os.path.abspath(os.path.join(output_folder, f)) for f in originals if f]
        
        results = []
        for p in all_pdfs:
            abs_p = os.path.abspath(p)
            if abs_p not in originals and "COMPLETE_SUBMITTAL_PACKAGE" not in abs_p and "Index_Cover" not in abs_p and "Approval_Cover" not in abs_p:
                results.append(abs_p)
        
        if results:
            results.sort()
            combined_doc = fitz.open()
            for pdf in results:
                with fitz.open(pdf) as m_doc:
                    combined_doc.insert_pdf(m_doc)
            
            final_name = f"COMPLETE_SUBMITTAL_PACKAGE_{extracted_job_info['Job_Name']}.pdf"
            final_path = os.path.join(output_folder, final_name)
            combined_doc.save(final_path)
            combined_doc.close()
            shared.log(f"Final Merged Package Created: {final_name}", "PIPELINE")
            
            if os.environ.get("HEADLESS_WORKER") != "TRUE":
                os.startfile(final_path)
    except Exception as e:
        shared.log(f"Merged package failure: {e}", "WARNING")

    shared.log("ALL SUBMITTALS COMPLETED SUCCESSFULLY!", "PIPELINE")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        folder_path = os.environ.get("PROJECT_FOLDER", "")
        project_config = scan_project_folder(folder_path)
        
        for key in ["EXCEL_WORKBOOK_NAME", "JOB_FORM_PDF_NAME", "SPEC_PDF_NAME", "DRAWINGS_PDF_NAME", "CONTRACT_PDF_NAME"]:
            val = os.environ.get(key)
            if val: project_config[key] = val

        run_pipeline(api_key, project_config)
    else:
        user_api_key, user_project_files = get_user_setup()
        run_pipeline(user_api_key, user_project_files)