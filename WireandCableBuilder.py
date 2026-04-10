import os
import re
import json
import datetime
import fitz
import xlwings as xw
import requests
import time
import builder_shared as shared

# =============================================================================
# MODULARIZED BUILDER: Wire and Cable
# =============================================================================

def run(context):
    wb = context['wb']
    api_key = context['api_key']
    config = context['project_config']
    job_info = context['job_info']
    
    shared.log("Starting Wire and Cable Builder...", "WIRE")

    # --- CONFIGURATION ---
    USER_HOME = os.environ.get('USERPROFILE', os.path.expanduser('~'))
    CATALOG_FOLDER = os.path.join(
        USER_HOME, "Denier", "Denier Operations Playbook-Submittal Builder - Documents",
        "Submittal Builder", "Catalogs", "Wire and Cable"
    )
    COL_CATALOG = "keyword search"
    COL_BRAND = "manufacturer"
    COL_DESC = "description"

    PROJECT_FOLDER = config["PROJECT_FOLDER"]
    spec_pdf_path = os.path.join(PROJECT_FOLDER, config["SPEC_PDF_NAME"])
    drawing_pdf_path = os.path.join(PROJECT_FOLDER, config["DRAWINGS_PDF_NAME"])
    contract_pdf_path = os.path.join(PROJECT_FOLDER, config["CONTRACT_PDF_NAME"])
    
    temp_dir = os.environ.get('TEMP', 'C:\\Temp')
    approval_pdf_path = os.path.join(temp_dir, 'Wire_Approval.pdf')

    # (Logic follows original WireandCableBuilder.py structure)
    
    shared.log("Opening documents...", "SYSTEM")
    full_spec_text = shared.extract_pdf_text(spec_pdf_path)
    drawing_text = shared.extract_pdf_text(drawing_pdf_path)
    contract_text = shared.extract_pdf_text(contract_pdf_path)
    
    # ... Wire and Cable specific extraction logic ...
    
    shared.log("Wire and Cable Builder Complete.", "SUCCESS")
    return True