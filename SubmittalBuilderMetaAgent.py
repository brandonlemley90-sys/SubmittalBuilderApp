import subprocess
import os
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog


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

    print("📊 Please select the Excel Workbook...")
    excel_path = filedialog.askopenfilename(
        initialdir=project_folder,
        title="Select Excel Workbook",
        filetypes=[("Excel Files", "*.xlsm;*.xlsx")]
    )

    print("📝 Please select the Job Setup Form PDF...")
    job_form_path = filedialog.askopenfilename(
        initialdir=project_folder,
        title="Select Job Setup Form PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    print("📄 Please select the Specs PDF...")
    spec_path = filedialog.askopenfilename(
        initialdir=project_folder,
        title="Select Specs PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    print("📐 Please select the Drawings PDF...")
    drawings_path = filedialog.askopenfilename(
        initialdir=project_folder,
        title="Select Drawings PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    print("🤝 Please select the Contract PDF...")
    contract_path = filedialog.askopenfilename(
        initialdir=project_folder,
        title="Select Contract PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )

    # Destroy the hidden root window now that all pop-ups are done
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

    print(f"\n🚀 Initiating One-Click Pipeline for folder:\n{project_config['PROJECT_FOLDER']}\n")

    for i, script in enumerate(scripts):
        print("\n" + "=" * 60)
        print(f"📦 STEP {i + 1} OF {len(scripts)}: Executing [{script}]")
        print("=" * 60 + "\n")

        if not os.path.exists(script):
            print(f"❌ Error: Could not find '{script}' in the current directory.")
            break

        try:
            # The Meta Agent freezes on this line until the child script finishes
            result = subprocess.run(
                [sys.executable, script],
                env=env_vars,
                check=True
            )
            print(f"\n✅ [{script}] -> Successfully Built and Opened in Bluebeam.")

            # If there are more scripts left, explicitly pause the pipeline
            if i < len(scripts) - 1:
                print("\n⏸️  PIPELINE PAUSED.")
                input("👉 Review your document in Bluebeam, then press ENTER to start the next submittal... ")

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
        project_config = {
            "PROJECT_FOLDER": os.environ.get("PROJECT_FOLDER", ""),
            "EXCEL_WORKBOOK_NAME": os.environ.get("EXCEL_WORKBOOK_NAME", ""),
            "JOB_FORM_PDF_NAME": os.environ.get("JOB_FORM_PDF_NAME", ""),
            "SPEC_PDF_NAME": os.environ.get("SPEC_PDF_NAME", ""),
            "DRAWINGS_PDF_NAME": os.environ.get("DRAWINGS_PDF_NAME", ""),
            "CONTRACT_PDF_NAME": os.environ.get("CONTRACT_PDF_NAME", "")
        }

        # 2. Run the pipeline
        run_pipeline(api_key, project_config)

        # 3. Prevent the new native window from closing instantly when finished
        print("\n" + "=" * 60)
        input("You may close this window. Press Enter to exit...")

    else:
        # If you run it manually without the web app, use the old tkinter pop-ups
        user_api_key, user_project_files = get_user_setup()
        run_pipeline(user_api_key, user_project_files)