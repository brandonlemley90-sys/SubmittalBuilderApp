import os
import re
import json
<<<<<<< Updated upstream
import fitz
import xlwings as xw
=======
>>>>>>> Stashed changes
import requests
import fitz # PyMuPDF
import xlwings as xw
import time
import builder_shared as shared

# =============================================================================
# --- THE PLATINUM BOXES BUILDER ---
# =============================================================================

def _staple(job_name, PROJECT_FOLDER, review_pdf, index_pdf, cutsheets_pdf, category="Boxes"):
    """Merge the three temp PDFs into one final submittal and return the path."""
    submittal_name = f"{job_name} {category} Submittal.pdf"
    submittal_path = os.path.join(PROJECT_FOLDER, submittal_name)
    parts = [p for p in [review_pdf, index_pdf, cutsheets_pdf] if p and os.path.exists(p)]
    if not parts:
        shared.log("No PDF parts to staple for Boxes.", "WARNING")
        return None
    try:
        combined = fitz.open()
        for p in parts:
            with fitz.open(p) as part_doc:
                combined.insert_pdf(part_doc)
        combined.save(submittal_path)
        combined.close()
        shared.log(f"Stapled: {submittal_name}", "SUCCESS")
        return submittal_path
    except Exception as e:
        shared.log(f"Boxes staple failed: {e}", "ERROR")
        return None


def run(context):
    wb       = context['wb']
    api_key  = context['api_key']
    config   = context['project_config']
    job_info = context['job_info']
<<<<<<< Updated upstream

    shared.log("Starting Boxes Builder...", "BOXES")

    USER_HOME      = os.environ.get('USERPROFILE', os.path.expanduser('~'))
    CATALOG_FOLDER = os.path.join(
        USER_HOME, "Denier", "Denier Operations Playbook-Submittal Builder - Documents",
        "Submittal Builder", "Catalogs", "Boxes"
    )
    PROJECT_FOLDER = config["PROJECT_FOLDER"]
    job_name       = job_info.get('Job_Name', 'Project')

    spec_pdf_path     = os.path.join(PROJECT_FOLDER, config.get("SPEC_PDF_NAME", ""))
    drawing_pdf_path  = os.path.join(PROJECT_FOLDER, config.get("DRAWINGS_PDF_NAME", ""))

    temp_dir              = os.environ.get('TEMP', 'C:\\Temp')
    index_pdf_path        = os.path.join(temp_dir, 'Boxes_index_tmp.pdf')
    review_pdf_path       = os.path.join(temp_dir, 'Boxes_approval_tmp.pdf')
    cutsheets_pdf_path    = os.path.join(temp_dir, 'Boxes_cutsheets_tmp.pdf')

    try:
        shared.log("Loading project data...", "SYSTEM")
        full_spec_text  = shared.extract_pdf_text(spec_pdf_path)
        drawing_text    = shared.extract_pdf_text(drawing_pdf_path)

        # Combined data sent to Gemini (specs + drawings for full context)
        combined_data = f"SPECIFICATIONS:\n{full_spec_text}\n\nDRAWINGS:\n{drawing_text}"

        # Load master list from Excel
        ws_list    = wb.sheets['Boxes List']
        sheet_data = ws_list.used_range.value

        # Build prompt database from master list
        db_rows = []
        if sheet_data:
            headers = [str(h).strip().lower() for h in sheet_data[0]] if sheet_data else []
            for row in sheet_data[1:]:
                if row and row[0]:
                    db_rows.append(dict(zip(headers, row)))

        shared.log("Building Boxes prompt for Gemini...", "AI")
        prompt = (
            "You are an electrical submittal assistant. Analyze the specifications and drawings below.\n"
            "Identify ALL electrical boxes required (junction boxes, pull boxes, device boxes, etc.).\n"
            f"Match against this product database: {json.dumps(db_rows[:200])}\n\n"
            "Return a JSON array of objects with keys: "
            '"Catalog Number", "Brand", "Device Description".\n'
            "Only include items that appear in the provided database."
        )

        raw_response = shared.call_gemini(api_key, prompt, combined_data)
        try:
            matched_items = json.loads(raw_response)
            if not isinstance(matched_items, list):
                matched_items = []
        except Exception:
            shared.log("AI returned invalid JSON for Boxes.", "WARNING")
            matched_items = []

        # Write matched items to Excel index sheet
        try:
            ws_index = wb.sheets['Boxes Index']
            for idx, item in enumerate(matched_items):
                row = 8 + idx
                ws_index.range(f'A{row}').value = item.get('Catalog Number', '')
                ws_index.range(f'B{row}').value = item.get('Brand', '')
                ws_index.range(f'C{row}').value = item.get('Device Description', '')
        except Exception as e:
            shared.log(f"Excel write warning (Boxes Index): {e}", "WARNING")

        # Export review/approval sheet
        spec_num_match = re.search(r'SECTION\s+(\d[\d\s]+\d)', full_spec_text[:5000], re.IGNORECASE)
        spec_num       = spec_num_match.group(1).strip() if spec_num_match else "26 05 33"
        try:
            ws_review = wb.sheets['Submittal for Review']
            ws_review.range('B5').value  = f"Job #: {job_info.get('Job_Number', '')}"
            ws_review.range('B7').value  = job_info.get('Job_Name', '')
            ws_review.range('B8').value  = job_info.get('Address', '')
            ws_review.range('B9').value  = job_info.get('City_State_Zip', '')
            ws_review.range('B11').value = f"Spec Section No: {spec_num}"
            ws_review.range('B15').value = "Submittal Title: Electrical Boxes"
            ws_review.api.ExportAsFixedFormat(0, review_pdf_path)
        except Exception as e:
            shared.log(f"Review sheet export warning: {e}", "WARNING")

        # Build PDF index page from matched items
        try:
            idx_doc  = fitz.open()
            idx_page = idx_doc.new_page(width=612, height=792)
            y        = 72
            idx_page.insert_text((72, y), f"{job_name} - Boxes Index", fontsize=14)
            y += 28
            for item in matched_items:
                line = f"  {item.get('Catalog Number','')}  |  {item.get('Brand','')}  |  {item.get('Device Description','')}"
                idx_page.insert_text((72, y), line, fontsize=9)
                y += 14
                if y > 740:
                    idx_page = idx_doc.new_page(width=612, height=792)
                    y = 72
            idx_doc.save(index_pdf_path)
            idx_doc.close()
        except Exception as e:
            shared.log(f"Index PDF build warning: {e}", "WARNING")

        # Match and merge catalog cut sheets
        try:
            pdf_cache = []
            if os.path.exists(CATALOG_FOLDER):
                for root_dir, _, files in os.walk(CATALOG_FOLDER):
                    for f in files:
                        if f.lower().endswith('.pdf'):
                            pdf_cache.append(os.path.join(root_dir, f))

            def clean(s):
                return re.sub(r'[^A-Z0-9]', '', str(s).upper())

            embedded = []
            for item in matched_items:
                cat = clean(item.get('Catalog Number', ''))
                if not cat:
                    continue
                for pdf_path in pdf_cache:
                    if cat in clean(os.path.basename(pdf_path)):
                        if pdf_path not in embedded:
                            embedded.append(pdf_path)
                        break

            if embedded:
                cuts_doc = fitz.open()
                for p in embedded:
                    with fitz.open(p) as part:
                        cuts_doc.insert_pdf(part)
                cuts_doc.save(cutsheets_pdf_path)
                cuts_doc.close()
                shared.log(f"Embedded {len(embedded)} cut sheet(s).", "BOXES")
        except Exception as e:
            shared.log(f"Cut sheet embedding warning: {e}", "WARNING")

        shared.log("Boxes Builder Phase Completed.", "SUCCESS")
=======
    base = shared.BaseBuilder(context, "Boxes", "Boxes")
    
    shared.log("Starting Boxes Builder...", "BOXES")

    try:
        # 1. Load Denier Material Database for Boxes
        shared.log("Loading Boxes Material Database...", "EXCEL")
        material_db = base.load_material_database("Boxes List")
        if not material_db:
            shared.log("Boxes List database is empty or missing!", "ERROR")
            return False

        # 2. Extract Source Text (Contract is Authority)
        shared.log("Extracting Spec and Drawing Text (Expanded Context)...", "AI")
        spec_text = shared.extract_pdf_text(base.get_spec_path())
        drawing_text = shared.extract_pdf_text(base.get_drawings_path())
        contract_text = shared.extract_pdf_text(base.get_contract_path())
        
        db_summary = [{"Catalog": m.get('type', ''), "Mfg": m.get('manufacturer', ''), "Desc": m.get('description', '')} for m in material_db]
        
        prompt = f"""
        ACT AS AN ELECTRICAL PROJECT MANAGER. Perform a submittal review.
        
        CONTRACT (ULTIMATE AUTHORITY):
        {contract_text[:100000]}
        
        SPECIFICATIONS:
        {spec_text[:150000]}
        
        DRAWINGS:
        {drawing_text[:50000]}

        MATERIAL DATABASE (Match strictly against these types):
        {json.dumps(db_summary)}

        PLATINUM RULES:
        1. THE CONTRACT HAS THE FINAL SAY. If the contract mandates a substitution (e.g., "Aluminum in lieu of Iron"), YOU MUST FOLLOW IT regardless of the Spec.
        2. BOX DEPTH SCAN: Actively search for minimum depth requirements (e.g. 2-1/2", 3-1/2"). Select from the database that match those depths.
        3. DEDUCTION RULE: For exposed areas like Parking Garages, assume Surface-Mounted Weatherproof or Cast Metal boxes unless specified otherwise.
        4. KITTING RULE: For every Sheet Metal Box (4-square, 4-11/16) discovered, YOU MUST also return the matching "Blank Covers" and "Extension Rings" from the database.
        5. UNDERGROUND EXCLUSION: IGNORE all Quazite, precast, or handhole boxes. They are not part of this submittal.
        6. EXCLUSIONS: DO NOT include Fire Putty Pads or In-Use covers.
        
        Return ONLY a JSON array of objects.
        Object Format: {{"Catalog": "XX", "Brand": "XX", "Description": "XX", "Reason": "XX"}}
        """
        raw_ai = shared.call_gemini(api_key, prompt, "")
        final_items = json.loads(raw_ai)

        # 3. Update Excel
        sheet_name = 'Boxes Index'
        if sheet_name not in [s.name for s in wb.sheets]:
            shared.log(f"'{sheet_name}' sheet not found. Creating it...", "WARNING")
            wb.sheets.add(sheet_name)
        
        ws_index = wb.sheets[sheet_name]
        try:
            ws_index.api.Unprotect()
            shared.log("🔓 Sheet unprotected to allow writing.", "EXCEL")
        except:
            pass
            
        shared.log(f"Writing {len(final_items)} items to {sheet_name}...", "EXCEL")
        
        # Clear rows 8 to 100
        ws_index.range('A8:C100').clear_contents()
        
        pdf_paths = []
        for i, item in enumerate(final_items):
            row = 8 + i
            cat = item.get('Catalog', '')
            mfg = item.get('Brand', '')
            desc = item.get('Description', '')
            
            ws_index.range(f'A{row}').value = cat
            ws_index.range(f'B{row}').value = mfg
            ws_index.range(f'C{row}').value = desc
            
            # Find matching PDF path
            path = base.find_best_pdf(cat, mfg, desc)
            if path and path not in pdf_paths:
                pdf_paths.append(path)

        # 4. Embed PDFs into "Boxes Cut Sheets"
        if pdf_paths:
            base.embed_pdfs(pdf_paths, "Boxes Cut Sheets")
        
        # 5. Finalize Individual PDF Package
        base.finalize_submittal("Boxes")
        
        wb.save()
        shared.log("Boxes Builder Phase Completed Successfully.", "SUCCESS")
        return True
>>>>>>> Stashed changes

    except Exception as e:
        shared.log(f"Boxes Builder Error: {e}", "ERROR")
        return None

    return _staple(job_name, PROJECT_FOLDER, review_pdf_path, index_pdf_path, cutsheets_pdf_path)
