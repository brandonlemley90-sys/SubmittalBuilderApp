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
# --- THE PLATINUM WIRE AND CABLE BUILDER ---
# =============================================================================

def _staple(job_name, PROJECT_FOLDER, review_pdf, index_pdf, cutsheets_pdf):
    submittal_name = f"{job_name} Wire and Cable Submittal.pdf"
    submittal_path = os.path.join(PROJECT_FOLDER, submittal_name)
    parts = [p for p in [review_pdf, index_pdf, cutsheets_pdf] if p and os.path.exists(p)]
    if not parts:
        shared.log("No PDF parts to staple for Wire and Cable.", "WARNING")
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
        shared.log(f"Wire and Cable staple failed: {e}", "ERROR")
        return None


def run(context):
    wb       = context['wb']
    api_key  = context['api_key']
    config   = context['project_config']
    job_info = context['job_info']
<<<<<<< Updated upstream

    shared.log("Starting Wire and Cable Builder...", "WIRE")

    USER_HOME      = os.environ.get('USERPROFILE', os.path.expanduser('~'))
    CATALOG_FOLDER = os.path.join(
        USER_HOME, "Denier", "Denier Operations Playbook-Submittal Builder - Documents",
        "Submittal Builder", "Catalogs", "Wire and Cable"
    )
    PROJECT_FOLDER = config["PROJECT_FOLDER"]
    job_name       = job_info.get('Job_Name', 'Project')

    spec_pdf_path    = os.path.join(PROJECT_FOLDER, config.get("SPEC_PDF_NAME", ""))
    drawing_pdf_path = os.path.join(PROJECT_FOLDER, config.get("DRAWINGS_PDF_NAME", ""))

    temp_dir           = os.environ.get('TEMP', 'C:\\Temp')
    index_pdf_path     = os.path.join(temp_dir, 'Wire_index_tmp.pdf')
    review_pdf_path    = os.path.join(temp_dir, 'Wire_approval_tmp.pdf')
    cutsheets_pdf_path = os.path.join(temp_dir, 'Wire_cutsheets_tmp.pdf')

    try:
        shared.log("Opening documents...", "SYSTEM")
        full_spec_text = shared.extract_pdf_text(spec_pdf_path)
        drawing_text   = shared.extract_pdf_text(drawing_pdf_path)
        combined_data  = f"SPECIFICATIONS:\n{full_spec_text}\n\nDRAWINGS:\n{drawing_text}"

        # Load master list
        ws_list = None
        for name in ['Wire and Cable List', 'Wire & Cable List', 'Wire List']:
            try:
                ws_list = wb.sheets[name]
                break
            except Exception:
                continue

        db_rows = []
        if ws_list:
            sheet_data = ws_list.used_range.value or []
            if sheet_data:
                headers = [str(h).strip().lower() for h in sheet_data[0]]
                for row in sheet_data[1:]:
                    if row and row[0]:
                        db_rows.append(dict(zip(headers, row)))

        shared.log("Building Wire and Cable prompt for Gemini...", "AI")
        prompt = (
            "You are an electrical submittal assistant. Analyze the specifications and drawings.\n"
            "Identify ALL wire and cable products required.\n"
            "Include THHN, XHHW, MC cable, service entrance cable, control cable, and any other conductors.\n"
            f"Match against this product database: {json.dumps(db_rows[:200])}\n\n"
            "Return a JSON array with keys: "
            '"Catalog Number", "Brand", "Device Description".'
        )

        raw_response  = shared.call_gemini(api_key, prompt, combined_data)
        try:
            matched_items = json.loads(raw_response)
            if not isinstance(matched_items, list):
                matched_items = []
        except Exception:
            shared.log("AI returned invalid JSON for Wire and Cable.", "WARNING")
            matched_items = []

        # Write to Excel
        try:
            ws_index = None
            for name in ['Wire & Cable Index', 'Wire and Cable Index', 'Wire Index']:
                try:
                    ws_index = wb.sheets[name]
                    break
                except Exception:
                    continue
            if ws_index:
                for idx, item in enumerate(matched_items):
                    row = 8 + idx
                    ws_index.range(f'A{row}').value = item.get('Catalog Number', '')
                    ws_index.range(f'B{row}').value = item.get('Brand', '')
                    ws_index.range(f'C{row}').value = item.get('Device Description', '')
        except Exception as e:
            shared.log(f"Excel write warning (Wire & Cable Index): {e}", "WARNING")

        # Export review/approval sheet
        spec_num = "26 05 19"
        try:
            ws_review = wb.sheets['Submittal for Review']
            ws_review.range('B5').value  = f"Job #: {job_info.get('Job_Number', '')}"
            ws_review.range('B7').value  = job_info.get('Job_Name', '')
            ws_review.range('B8').value  = job_info.get('Address', '')
            ws_review.range('B9').value  = job_info.get('City_State_Zip', '')
            ws_review.range('B11').value = f"Spec Section No: {spec_num}"
            ws_review.range('B15').value = "Submittal Title: Wire and Cable"
            ws_review.api.ExportAsFixedFormat(0, review_pdf_path)
        except Exception as e:
            shared.log(f"Review sheet export warning: {e}", "WARNING")

        # Build index PDF
        try:
            idx_doc  = fitz.open()
            idx_page = idx_doc.new_page(width=612, height=792)
            y        = 72
            idx_page.insert_text((72, y), f"{job_name} - Wire and Cable Index", fontsize=14)
            y += 28
            for item in matched_items:
                line = (f"  {item.get('Catalog Number','')}  |  "
                        f"{item.get('Brand','')}  |  {item.get('Device Description','')}")
                idx_page.insert_text((72, y), line, fontsize=9)
                y += 14
                if y > 740:
                    idx_page = idx_doc.new_page(width=612, height=792)
                    y = 72
            idx_doc.save(index_pdf_path)
            idx_doc.close()
        except Exception as e:
            shared.log(f"Index PDF warning: {e}", "WARNING")

        # Match cut sheets
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
                for pdf_path in pdf_cache:
                    if cat and cat in clean(os.path.basename(pdf_path)):
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
                shared.log(f"Embedded {len(embedded)} cut sheet(s).", "WIRE")
        except Exception as e:
            shared.log(f"Cut sheet warning: {e}", "WARNING")

        shared.log("Wire and Cable Builder Complete.", "SUCCESS")

    except Exception as e:
        shared.log(f"Wire and Cable Builder Error: {e}", "ERROR")
        return None

    return _staple(job_name, PROJECT_FOLDER, review_pdf_path, index_pdf_path, cutsheets_pdf_path)
=======
    base = shared.BaseBuilder(context, "Wire and Cable", "Wire and Cable")
    
    shared.log("Starting Wire and Cable Builder...", "WIRE")

    try:
        # 1. Load Denier Material Database for Wire and Cable
        shared.log("Loading Wire & Cable Material Database...", "EXCEL")
        material_db = base.load_material_database("Wire & Cable List")
        if not material_db:
            shared.log("Wire & Cable List database is empty or missing!", "ERROR")
            return False

        # 2. Extract Source Text (Contract is Authority)
        shared.log("Extracting Spec and Drawing Text (Expanded Context)...", "AI")
        spec_text = shared.extract_pdf_text(base.get_spec_path())
        drawing_text = shared.extract_pdf_text(base.get_drawings_path())
        contract_text = shared.extract_pdf_text(base.get_contract_path())
        
        db_summary = [{"Catalog": m.get('keyword search', ''), "Mfg": m.get('manufacturer', ''), "Desc": m.get('description', '')} for m in material_db]
        
        prompt = f"""
        ACT AS AN ELECTRICAL PROJECT MANAGER. Perform a submittal review for Wire and Cable.
        
        CONTRACT (ULTIMATE AUTHORITY):
        {contract_text[:100000]}
        
        SPECIFICATIONS:
        {spec_text[:150000]}
        
        DRAWINGS:
        {drawing_text[:50000]}

        MATERIAL DATABASE (Match against 'Catalog'):
        {json.dumps(db_summary)}

        PLATINUM RULES:
        1. THE CONTRACT HAS THE FINAL SAY. If the contract mandates Aluminum in lieu of Copper, prioritize Aluminum.
        2. COPPER VS ALUMINUM: Always submit Copper unless Aluminum is explicitly called out for specific feeders.
        3. ALUMINUM THRESHOLDS: permitted only on 1/0 and larger feeders unless stated otherwise.
        4. GROUNDING RULE: If grounding is required, ALWAYS include Bare Copper from the database.
        5. CONNECTION KITS (MANDATORY):
           - IF THHN wire is being submitted, you MUST always submit wire connectors (e.g. Wire Nuts, Wagos).
           - IF ANY type of MC Cable is being submitted, you MUST always submit MC Connectors.
        6. TAPE RULE: You MUST always include standard electrical tape and colored phase-coding tape for 120/208V and 277/480V systems.
        
        Return ONLY a JSON array of objects.
        Object Format: {{"Catalog": "XX", "Brand": "XX", "Description": "XX", "Reason": "XX"}}
        """
        raw_ai = shared.call_gemini(api_key, prompt, "")
        final_items = json.loads(raw_ai)

        # 3. Update Excel
        sheet_name = 'Wire & Cable Index'
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

        # 4. Embed PDFs into "Wire & Cable Cut Sheets"
        if pdf_paths:
            base.embed_pdfs(pdf_paths, "Wire and Cable Cut Sheets")
        
        # 5. Finalize Submittal
        base.finalize_submittal("Wire and Cable")
        
        wb.save()
        shared.log("Wire and Cable Builder Phase Completed Successfully.", "SUCCESS")
        return True

    except Exception as e:
        shared.log(f"Wire and Cable Builder Error: {e}", "ERROR")
        return False
>>>>>>> Stashed changes
