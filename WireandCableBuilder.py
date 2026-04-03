import xlwings as xw
import json
import requests
import fitz  # PyMuPDF
import os
import re
import sys
import datetime
import time

# =============================================================================
# --- 1. CONFIGURATION & FILE PATHS ---
# =============================================================================

API_KEY = os.environ.get("GEMINI_API_KEY", "")
USER_HOME = os.environ.get('USERPROFILE', os.path.expanduser('~'))

# Look for the variables passed by the Meta Agent.
PROJECT_FOLDER = os.environ.get("PROJECT_FOLDER", r"C:\Temp\ERROR_NO_FOLDER")
EXCEL_WORKBOOK_NAME = os.environ.get("EXCEL_WORKBOOK_NAME", "ERROR_NO_EXCEL.xlsm")
SPEC_PDF_NAME = os.environ.get("SPEC_PDF_NAME", "ERROR_NO_SPEC.pdf")
DRAWINGS_PDF_NAME = os.environ.get("DRAWINGS_PDF_NAME", "ERROR_NO_DRAWING.pdf")
CONTRACT_PDF_NAME = os.environ.get("CONTRACT_PDF_NAME", "ERROR_NO_CONTRACT.pdf")
JOB_FORM_PDF_NAME = os.environ.get("JOB_FORM_PDF_NAME", "ERROR_NO_JOB_FORM.pdf")

# 1. THE MASTER CATALOG FOLDER
CATALOG_FOLDER = os.path.join(
    USER_HOME,
    "Denier",
    "Denier Operations Playbook-Submittal Builder - Documents",
    "Submittal Builder",
    "Catalogs",
    "Wire and Cable"
)

# 2. EXCEL DATABASE HEADERS (Must match the columns on your 'Wire & Cable List' tab)
COL_CATALOG = "keyword search"
COL_BRAND = "manufacturer"
COL_DESC = "description"


# =============================================================================
# FAILURE HANDLING ENGINE
# =============================================================================

def ask_to_continue(step_name, error_msg):
    print(f"\n❌ [FAILURE DETECTED] {step_name}")
    print(f"   Error Details: {error_msg}")
    ans = input("   Do you want to attempt to continue anyway? (Y/N): ").strip().upper()
    if ans != 'Y':
        print("\n🛑 Script aborted by user.")
        sys.exit(1)
    print("   ⚠️ Pushing forward...\n")


# =============================================================================
# PDF MATCHING ENGINE
# =============================================================================

def clean_catalog(txt):
    return re.sub(r'[^A-Z0-9]', '', str(txt).upper())


def digits_only(s):
    return re.sub(r'[^0-9]', '', s)


def has_digit(s):
    return bool(re.search(r'\d', s))


def get_base_model_to_last_digit(clean_tok):
    last = -1
    for i, ch in enumerate(clean_tok):
        if ch.isdigit():
            last = i
    if last == -1:
        return ''
    return clean_tok[:last + 1]


def get_leading_letters(clean_tok):
    out = ''
    for ch in clean_tok:
        if ch.isalpha():
            out += ch
        else:
            break
    return out


def normalize_for_match(s):
    t = str(s).upper().strip()
    for ch in ["'", "\u2018", "\u2019"]:
        t = t.replace(ch, '')
    for ch in ['.', ',', '\\', '-', '&', '_', '/']:
        t = t.replace(ch, ' ')
    while '  ' in t:
        t = t.replace('  ', ' ')
    return t.strip()


STOP_WORDS = {'THE', 'AND', 'FOR', 'WITH', 'ASSORTED', 'SIZE', 'SIZES', 'WIRE', 'CABLE', 'AWG'}


def tokenize(norm):
    return [t for t in norm.split() if len(t) > 1 and t not in STOP_WORDS]


def token_overlap_score(filename_norm, tokens):
    score = 0
    for t in tokens:
        if t in filename_norm:
            score += 20 if any(c.isdigit() for c in t) else 10
    return score


def filename_matches_mfg_first(filename_norm, mfg_norm):
    if not mfg_norm:
        return False
    if filename_norm.startswith(mfg_norm):
        return True
    if filename_norm.startswith(mfg_norm + ' '):
        return True
    return mfg_norm in filename_norm


def starts_with_mfg(filename_norm, mfg_norm):
    if len(filename_norm) < len(mfg_norm):
        return False
    return (filename_norm.startswith(mfg_norm) or
            filename_norm.startswith(mfg_norm + ' '))


def expand_mfg_candidates(mfg_raw):
    s = mfg_raw.replace('/', ',')
    parts = [p.strip() for p in s.split(',') if p.strip()]
    seen = set()
    out = []
    for p in parts:
        n = normalize_for_match(p)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def build_row_tokens(idx_norm, catalog_raw, desc_raw):
    tokens = list(dict.fromkeys(tokenize(idx_norm)))
    c_clean = clean_catalog(catalog_raw)
    if c_clean and c_clean not in tokens:
        tokens.append(c_clean)
    base = get_base_model_to_last_digit(c_clean)
    if base and base not in tokens:
        tokens.append(base)
    pref = get_leading_letters(c_clean)
    if len(pref) >= 2 and pref not in tokens:
        tokens.append(pref)
    return tokens


def find_best_pdf_for_mfg(pdf_cache, idx_norm, row_tokens, mfg_norm, catalog_raw):
    cat_clean = clean_catalog(catalog_raw)
    must_have_catalog = len(cat_clean) >= 4 and has_digit(cat_clean)
    base_model = get_base_model_to_last_digit(cat_clean)

    row_digits = digits_only(cat_clean)

    best_score = -1
    best_path = ''

    for entry in pdf_cache:
        fn_norm = entry['name_norm']
        key_clean = entry['key_clean']
        dig_only = entry['digits_only']
        path = entry['path']

        if not filename_matches_mfg_first(fn_norm, mfg_norm):
            continue

        if must_have_catalog:
            if cat_clean not in key_clean:
                if base_model and base_model not in key_clean:
                    if len(row_digits) >= 4:
                        if row_digits not in dig_only:
                            continue
                    else:
                        continue

        score = token_overlap_score(fn_norm, row_tokens)
        if starts_with_mfg(fn_norm, mfg_norm):
            score += 25

        if score > best_score:
            best_score = score
            best_path = path

    return best_path


def best_pdfs_for_row(pdf_cache, catalog_raw, mfg_raw, desc_raw):
    idx_text = (catalog_raw + ' ' + mfg_raw + ' ' + desc_raw).strip()
    idx_norm = normalize_for_match(idx_text)

    mfg_candidates = expand_mfg_candidates(mfg_raw)
    if not mfg_candidates:
        return []

    row_tokens = build_row_tokens(idx_norm, catalog_raw, desc_raw)

    results = []
    seen_paths = set()
    for mfg_norm in mfg_candidates:
        best = find_best_pdf_for_mfg(pdf_cache, idx_norm, row_tokens, mfg_norm, catalog_raw)
        if best and best not in seen_paths:
            results.append(best)
            seen_paths.add(best)
    return results


def build_pdf_cache(root_path):
    cache = []
    for dirpath, _, filenames in os.walk(root_path):
        for fname in filenames:
            if fname.lower().endswith('.pdf'):
                full_path = os.path.join(dirpath, fname)
                name_norm = normalize_for_match(fname.upper())
                key_clean = clean_catalog(fname)
                dig_only = digits_only(key_clean)
                cache.append({
                    'path': full_path,
                    'name_norm': name_norm,
                    'key_clean': key_clean,
                    'digits_only': dig_only,
                })
    return cache


# =============================================================================
# EMBED CUT SHEET PDFs INTO EXCEL
# =============================================================================

def embed_pdfs_into_excel(wb, pdf_paths_to_embed):
    index_sheet_name = 'Wire & Cable Index'
    cut_sheet_name = 'Wire and Cable Cut Sheets'

    try:
        ws_cuts = wb.sheets[cut_sheet_name]
        try:
            for ole in ws_cuts.api.OLEObjects():
                ole.Delete()
        except Exception:
            pass
        ws_cuts.clear()
        print(f"   Cleared existing '{cut_sheet_name}' sheet.")
    except Exception:
        ws_cuts = wb.sheets.add(name=cut_sheet_name,
                                after=wb.sheets[index_sheet_name])
        print(f"   Created new '{cut_sheet_name}' sheet.")

    try:
        ws_cuts.api.PageSetup.PaperSize = 1
        ws_cuts.api.PageSetup.Orientation = 1
        ws_cuts.api.PageSetup.Zoom = False
        ws_cuts.api.PageSetup.FitToPagesWide = 1
        ws_cuts.api.PageSetup.FitToPagesTall = 1
    except Exception:
        pass

    top_pos = 10
    left_pos = 20
    icon_height = 45
    row_gap = 65
    success_count = 0

    for pdf_path in pdf_paths_to_embed:
        if not os.path.exists(pdf_path):
            continue
        try:
            ws_cuts.api.Activate()
            ole = ws_cuts.api.OLEObjects().Add(
                Filename=os.path.abspath(pdf_path),
                Link=False,
                DisplayAsIcon=True
            )
            ole.Left = left_pos
            ole.Top = top_pos
            ole.Height = icon_height
            top_pos += row_gap
            success_count += 1
            print(f"   ✅ Embedded: {os.path.basename(pdf_path)}")
        except Exception as e:
            print(f"   ❌ Failed to embed {os.path.basename(pdf_path)}: {e}")

    return success_count


# =============================================================================
# PDF READER & EXTRACTOR
# =============================================================================

def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"⚠️ Warning: Document not found: {os.path.basename(pdf_path)}")
        return ""
    print(f"Opening PDF: {os.path.basename(pdf_path)}...")
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()

        doc.close()
        return text
    except Exception as e:
        ask_to_continue(f"Reading PDF ({pdf_path})", e)
        return ""


def extract_spec_section(full_spec_text, section_label, start_patterns, end_patterns):
    if not full_spec_text:
        return ""

    start_pos = None
    for pattern in start_patterns:
        match = re.search(pattern, full_spec_text, re.IGNORECASE)
        if match and (start_pos is None or match.start() < start_pos):
            start_pos = match.start()

    if start_pos is None:
        print(f"⚠️  Could not locate explicit '{section_label}' section. Using full spec text.")
        return full_spec_text

    section_from_start = full_spec_text[start_pos:]
    end_pos = None
    for pattern in end_patterns:
        for m in re.finditer(pattern, section_from_start, re.IGNORECASE):
            if m.start() > 100:
                if end_pos is None or m.start() < end_pos:
                    end_pos = m.start()
                break

    section_text = section_from_start[:end_pos] if end_pos else section_from_start
    print(f"✅ Isolated '{section_label}' section ({len(section_text):,} characters).")
    return section_text


def extract_wiring_devices_section(full_spec_text):
    return extract_spec_section(
        full_spec_text,
        'Wire and Cable',
        start_patterns=[
            r'SECTION\s+26\s*05\s*19',
            r'SECTION\s+16\s*12\s*00',
            r'LOW-VOLTAGE\s+ELECTRICAL\s+POWER\s+CONDUCTORS',
            r'CONDUCTORS\s+AND\s+CABLES',
            r'WIRE\s+AND\s+CABLE',
        ],
        end_patterns=[
            r'SECTION\s+\d{2}\s*\d{2}\s*\d{2}',
            r'END\s+OF\s+SECTION',
            r'END\s+OF\s+PART\s+3',
        ]
    )


def get_spec_header(spec_text):
    match = re.search(r'SECTION\s+(\d{2}\s*\d{2}\s*\d{2}[^\n\r]+)', spec_text, re.IGNORECASE)
    if match:
        return re.sub(r'\s+', ' ', match.group(1).strip())
    return "26 05 19 - LOW-VOLTAGE ELECTRICAL POWER CONDUCTORS AND CABLES"


# =============================================================================
# GEMINI API
# =============================================================================

def call_llm_api(prompt, data, max_retries=3):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={API_KEY}"
    )
    headers = {"Content-Type": "application/json"}

    if len(data) > 100000:
        print(f"   ⚠️  Warning: PDF text is massive ({len(data):,} chars). Truncating to prevent connection drop...")
        data = data[:100000]

    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n{data}"}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)

            if response.status_code != 200:
                print(f"   ⚠️ API Error (Attempt {attempt}/{max_retries}): Status {response.status_code}")
                if attempt == max_retries:
                    raise Exception(f"API Failed! Status {response.status_code}: {response.text}")
                time.sleep(5)
                continue

            raw = response.json()['candidates'][0]['content']['parts'][0]['text']
            return raw.strip().removeprefix('```json').removesuffix('```').strip()

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"   ⚠️ Bad Connection or Timeout (Attempt {attempt}/{max_retries}). Retrying...")
            if attempt == max_retries:
                raise Exception(f"Network failure after {max_retries} attempts. Check your internet connection.")
            time.sleep(5)


# =============================================================================
# HELPERS
# =============================================================================

def sanitize(value):
    val = str(value) if value is not None else ''
    if val.startswith(('=', '+', '-', '@')):
        val = "'" + val
    return val


def safe_write_cell(sheet, row, col_letter, value):
    try:
        cell_range = sheet.range(f'{col_letter}{row}')
        try:
            merge_area = cell_range.api.MergeArea
            if merge_area.Count > 1:
                tl_row = merge_area.Cells(1, 1).Row
                tl_col = merge_area.Cells(1, 1).Column
                if tl_row != cell_range.row or tl_col != cell_range.column:
                    return True
        except Exception:
            pass

        try:
            cell_range.api.Validation.Delete()
        except Exception:
            pass

        cell_range.value = value
        return True
    except Exception as e:
        error_code = e.args[0] if e.args else None
        if isinstance(error_code, int) and error_code in (-2146827284, -2146827259, -2147352567):
            print(
                f"   ⚠️  Cell {col_letter}{row} blocked (validation/protection). Value: '{value}' | Code: {error_code}")
        else:
            print(f"   ⚠️  Unexpected error writing {col_letter}{row}: {e}")
        return False


def check_file_locked(filepath):
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, 'ab'):
            pass
        return False
    except PermissionError:
        return True


def save_pdf_with_retry(merged_doc, output_path, max_attempts=3):
    output_path = os.path.abspath(output_path)
    for attempt in range(1, max_attempts + 1):
        if check_file_locked(output_path):
            print(f"\n⚠️  OUTPUT FILE IS LOCKED (attempt {attempt}/{max_attempts})")
            print(f"   Close '{output_path}' in Bluebeam/Acrobat, then press Enter...")
            input("   Press Enter when ready: ")
        else:
            try:
                merged_doc.save(output_path)
                return True
            except PermissionError:
                print(f"⚠️  Still locked. Close the file and press Enter... ({attempt}/{max_attempts})")
                if attempt < max_attempts:
                    input("   Press Enter when ready: ")
    print(f"❌ Could not save after {max_attempts} attempts.")
    return False


# =============================================================================
# MAIN EXECUTION BLOCK
# =============================================================================
try:
    if not API_KEY:
        print("\n❌ [CRITICAL ERROR] No API key found. Ensure you are running this via the Meta Agent.")
        sys.exit(1)

    if not os.path.exists(PROJECT_FOLDER):
        print(f"\n❌ [CRITICAL ERROR] The PROJECT_FOLDER does not exist:\n   {PROJECT_FOLDER}")
        print("   Please check the configuration block at the top of the script.")
        sys.exit(1)

    temp_dir = os.environ.get('TEMP', 'C:\\Temp')

    spec_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, SPEC_PDF_NAME))
    drawing_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, DRAWINGS_PDF_NAME))
    contract_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, CONTRACT_PDF_NAME))
    excel_path = os.path.abspath(os.path.join(PROJECT_FOLDER, EXCEL_WORKBOOK_NAME))

    # Check for all required files including the Contract
    for path, name in [(spec_pdf_path, SPEC_PDF_NAME), (drawing_pdf_path, DRAWINGS_PDF_NAME),
                       (contract_pdf_path, CONTRACT_PDF_NAME), (excel_path, EXCEL_WORKBOOK_NAME)]:
        if not os.path.exists(path):
            print(f"\n❌ [CRITICAL ERROR] Could not find '{name}' inside the Project Folder.")
            sys.exit(1)

    index_pdf_path = os.path.abspath(os.path.join(temp_dir, 'Index_Cover.pdf'))
    approval_pdf_path = os.path.abspath(os.path.join(temp_dir, 'Approval_Cover.pdf'))

    print("Connecting to Excel...")
    try:
        wb = xw.Book(excel_path)
    except Exception as e:
        print(f"\n❌ [CRITICAL ERROR] Could not connect to Excel Workbook. Is it open? Error: {e}")
        sys.exit(1)

    match = re.search(r'\((.*?)\)', wb.name)
    project_name = match.group(1).strip() if match else "Unknown Project"

    try:
        sheet_index = wb.sheets['Wire & Cable Index']
        raw_a5 = str(sheet_index.range('A5').value).strip()

        a5_match = re.search(r'\((.*?)\)', raw_a5)
        name_in_a5 = a5_match.group(1).strip() if a5_match else raw_a5

        name_in_a5 = re.sub(r'^\d{2}\s*\d{2}\s*\d{2}\s*[-:]?\s*', '', name_in_a5).strip()

        if name_in_a5 == "None" or not name_in_a5:
            name_in_a5 = "Wire and Cable"

    except Exception as e:
        ask_to_continue("Reading 'Wire & Cable Index' sheet", e)
        name_in_a5 = "Wire and Cable"

    safe_project = re.sub(r'[\\/*?:"<>|]', "", project_name).strip()

    pdf_filename = f"{safe_project} Wire and Cable Submittal.pdf"

    wireandcablePDF = os.path.abspath(os.path.join(PROJECT_FOLDER, pdf_filename))
    print(f"Target Output: {pdf_filename}\n")

    # --- LOAD PROJECT INFO FORM ---
    print("--- Loading Project Form PDF ---")

    job_info = {
        "Job_Number": "Unknown",
        "Job_Name": project_name,  # Fallback to excel workbook name
        "Address": "",
        "City_State_Zip": ""
    }

    if JOB_FORM_PDF_NAME and "ERROR" not in JOB_FORM_PDF_NAME:
        form_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, JOB_FORM_PDF_NAME))
        print(f"   ✅ Using Selected Form: {JOB_FORM_PDF_NAME}")

        # Try to pull the Job Number and Name directly from the filename
        name_match = re.match(r'(\d{2}-\d{2}-\d{4})\s*-\s*(.*)\.pdf', JOB_FORM_PDF_NAME, re.IGNORECASE)
        if name_match:
            job_info["Job_Number"] = name_match.group(1).strip()
            job_info["Job_Name"] = name_match.group(2).strip()

        print("   Asking AI to extract address information from the form...")
        try:
            form_text = extract_text_from_pdf(form_pdf_path)
            address_prompt = f"""
                Extract the project details from the following form text and filename.
                Filename: {JOB_FORM_PDF_NAME}

                RULES:
                1. Find the Job Number (format usually XX-XX-XXXX).
                2. Find the Job Name (Project Name).
                3. Find the Street Address.
                4. Find the City, State, and Zip Code.

                Return ONLY a raw JSON object with these exact keys:
                "Job_Number", "Job_Name", "Address", "City_State_Zip"
                """

            raw_job_ai = call_llm_api(prompt=address_prompt, data=form_text[:15000])
            extracted_job_info = json.loads(raw_job_ai)

            for key in job_info.keys():
                if extracted_job_info.get(key):
                    job_info[key] = extracted_job_info[key]

            print(f"   ✅ Extracted Data: {job_info['Job_Number']} | {job_info['Address']}")
        except Exception as e:
            print(f"   ⚠️ Could not fully extract data from form using AI: {e}")
    else:
        print("   ⚠️ No Job Setup Form was selected in the Meta Agent.")

    # --- LOAD MASTER DEVICE LIST ---
    try:
        ws_list = wb.sheets['Wire & Cable List']
        sheet_data = ws_list.used_range.value

        if not sheet_data:
            raise Exception("The 'Wire & Cable List' sheet appears to be empty.")

        header_row_idx = -1
        headers = []
        for i, row in enumerate(sheet_data):
            clean_row = [str(cell).strip().lower() if cell else '' for cell in row]

            if COL_CATALOG in clean_row and COL_BRAND in clean_row and COL_DESC in clean_row:
                header_row_idx = i
                headers = clean_row
                break

        if header_row_idx == -1:
            raise Exception(
                f"Could not find a row containing '{COL_CATALOG}', '{COL_BRAND}', and '{COL_DESC}'. Check your headers!")

        cat_idx = headers.index(COL_CATALOG)
        brand_idx = headers.index(COL_BRAND)
        desc_idx = headers.index(COL_DESC)

        reference_dict = {}
        db_for_prompt = []

        for row in sheet_data[header_row_idx + 1:]:
            if row and len(row) > cat_idx and row[cat_idx] is not None:
                raw_catalog = str(row[cat_idx]).strip()
                key = raw_catalog.lower()

                brand_val = row[brand_idx] if len(row) > brand_idx else ''
                desc_val = row[desc_idx] if len(row) > desc_idx else ''

                reference_dict[key] = {
                    'Catalog Number': raw_catalog,
                    'Brand': brand_val,
                    'Device Description': desc_val
                }

                db_for_prompt.append({
                    "Catalog Number": raw_catalog,
                    "Brand": brand_val,
                    "Device Description": desc_val
                })

        print(f"\nLoaded {len(db_for_prompt)} official items from Excel.")
    except Exception as e:
        ask_to_continue("Loading Master Device List from Excel", e)

    # --- EXTRACT & ISOLATE SPEC TEXT ---
    full_spec_text = extract_text_from_pdf(spec_pdf_path)
    drawing_text = extract_text_from_pdf(drawing_pdf_path)
    contract_text = extract_text_from_pdf(contract_pdf_path)
    wiring_spec_text = extract_wiring_devices_section(full_spec_text)

    # --- EXTRACT SPEC HEADER & WRITE TO A5 ---
    spec_title = get_spec_header(wiring_spec_text)
    final_a5_string = f"{spec_title} ({name_in_a5})"
    print(f"Setting A5 Header to: {final_a5_string}")

    try:
        sheet_index.api.Unprotect()
    except:
        pass
    safe_write_cell(sheet_index, 5, 'A', final_a5_string)

    # =========================================================================
    # UPDATE EXCEL APPROVAL SHEET
    # =========================================================================
    print("\n--- Updating Approval Sheet ---")
    has_approval_sheet = False

    try:
        ws_app = wb.sheets['Submittal for Review']

        try:
            ws_app.api.Unprotect()
        except:
            pass

        spec_num_match = re.search(r'(\d{2}\s*\d{2}\s*\d{2})', spec_title)
        spec_num = spec_num_match.group(1) if spec_num_match else "Unknown"

        now = datetime.datetime.now()
        current_date = f"{now.month}/{now.day}/{now.strftime('%y')}"

        print(f"   Injecting → Job #: {job_info['Job_Number']} | Spec: {spec_num} | Title: {name_in_a5}")

        safe_write_cell(ws_app, 5, 'B', f"Job #: {job_info['Job_Number']}")
        safe_write_cell(ws_app, 7, 'B', job_info['Job_Name'])
        safe_write_cell(ws_app, 8, 'B', job_info['Address'])
        safe_write_cell(ws_app, 9, 'B', job_info['City_State_Zip'])

        safe_write_cell(ws_app, 11, 'B', f"Spec Section No: {spec_num}")
        safe_write_cell(ws_app, 15, 'B', f"Submittal Title: {name_in_a5}")

        for row in range(1, 40):
            for col in ['A', 'B', 'C']:
                cell_val = str(ws_app.range(f'{col}{row}').value).strip()
                if cell_val.startswith("Date:"):
                    safe_write_cell(ws_app, row, col, f"Date: {current_date}")
                    break

        print("   Exporting Approval Sheet to PDF...")

        try:
            ws_app.api.ExportAsFixedFormat(0, approval_pdf_path)
            print(f"   ✅ Approval PDF saved → {approval_pdf_path}")
            has_approval_sheet = True
        except Exception as export_e:
            ask_to_continue("Exporting Approval Sheet to PDF", export_e)
            has_approval_sheet = False

    except Exception as e:
        ask_to_continue("Updating Approval Sheet ('Submittal for Review')", e)

    # --- DATA BUDGETING ---
    combined_project_data = (
        f"--- CONTRACT DOCUMENT (ULTIMATE AUTHORITY) ---\n{contract_text}\n\n"
        f"--- WIRE AND CABLE SPECIFICATION SECTION ---\n{wiring_spec_text}\n\n"
        f"--- PROJECT DRAWINGS (NOTES/SCHEDULES) ---\n{drawing_text}"
    )

    # --- BUILD PROMPT ---
    my_smart_prompt = f"""
You are a senior electrical estimator performing a submittal review for a construction project.

YOUR TASK:
Review the project specification section, contract, and drawing notes provided below.
Identify every item that is explicitly called out or required by those documents AND that has a matching entry in the OFFICIAL DATABASE LIST.

THE PLATINUM RULE — CONTRACT & SCOPE ALTERNATES ARE THE ULTIMATE AUTHORITY:
You have been provided with the Contract Document, the Specifications, and the Drawings.
1. The Contract has the absolute final say. Actively hunt the Contract text for keywords like "Scope Alternates", "Value Engineering", "VE", "Substitutions", and "in lieu".
2. If the Contract explicitly adds, requires, or substitutes a material, you MUST include it.
3. If the Contract explicitly EXCLUDES or removes a material entirely, you MUST NOT include it.

THE GOLDEN RULE — DATABASE IS THE AUTHORITY:
The OFFICIAL DATABASE LIST defines the complete universe of items. If it is required and in the database, include it. 

WIRE AND CABLE SPECIFIC RULES (CRITICAL MANDATE):
1. COPPER VS ALUMINUM: Always submit Copper unless Aluminum is explicitly and specifically called out in the documents. 
2. ALUMINUM CONDUCTORS (<600V): If Aluminum is specified, actively scan for and enforce Usage Thresholds (e.g., permitted only on 1/0 and larger). Identify required alloy (e.g., AA-8000) and insulation (e.g., XHHW-2).
3. COPPER CONDUCTORS (<600V): Identify requirements for THHN/THWN-2 vs XHHW-2, and Environmental mandates (SUN-RES, Direct Burial, Oil/Gas Resistant). Check for stranded vs. solid requirements based on AWG size.
4. GROUNDING: If grounding is required by the spec or drawings, ALWAYS include Bare Copper from the database.
5. ELECTRICAL TAPE: You MUST always include standard electrical tape. If the spec mandates field-applied color-coding tape for certain wire sizes (e.g., >#6 AWG), pull colored tape matching the required phase colors for 120/208V and 277/480V systems.
6. SPLICING & TERMINATIONS: Actively look for splicing components (Wagos, Wire Nuts, MC Connectors, Stak-ons, AL/CU-rated lugs, antioxidant joint compound). 
7. THHN RULE: If THHN wire is being submitted, you MUST always submit wire connectors (e.g., Wire Nuts, Wagos).
8. MC CABLE RULE: If ANY type of MC Cable is being submitted, you MUST always submit MC Connectors.

SPEC CITATIONS (MANDATORY):
You must find and record the exact Specification Section and Page Number (or Contract Clause) for the specific rules and thresholds you apply (e.g., usage thresholds, color coding rules, alloy types, approved manufacturers). Put this information in the "Spec_Citation" field for the relevant item.

SPEC VS DRAWING CONFLICTS:
If drawings conflict with specifications, the SPECIFICATION takes precedence. You MUST follow the spec, but fill out the "Conflict_Flag" field in your JSON output to warn the user.

DEDUPLICATION: List each catalog number only ONCE.

JSON FORMAT (STRICT):
Return ONLY a raw JSON array. No markdown.
Keys: "Catalog Number", "Brand", "Device Description", "Original_Name", "Reason", "Spec_Citation", "Conflict_Flag"

OFFICIAL DATABASE LIST:
{json.dumps(db_for_prompt)}
"""

    # --- CALL GEMINI ---
    print("\nSending Wire and Cable spec section, contract, and drawing notes to Gemini...")
    extracted_data = []
    try:
        api_response = call_llm_api(prompt=my_smart_prompt, data=combined_project_data)
        extracted_data = json.loads(api_response)
        print(f"Success! Gemini analyzed the documents. Processing items...\n")

        print("--- AI RAW OUTPUT PRE-FILTER ---")
        for item in extracted_data:
            citation = item.get('Spec_Citation', '')
            cite_str = f" | Citation: {citation}" if citation else ""
            print(f"AI suggested: {item.get('Catalog Number', 'N/A')} | Reason: {item.get('Reason', 'None')}{cite_str}")
        print("--------------------------------\n")

    except json.JSONDecodeError as jde:
        print("\n❌ AI FORMATTING ERROR ❌")
        print(api_response)
        raise Exception(f"JSON Parsing failed: {jde}")
    except Exception as e:
        ask_to_continue("Calling Gemini API", e)

    # --- BUILD PDF CACHE FIRST ---
    print("--- Scanning for Cut Sheet PDFs ---")
    pdf_cache = []
    if not os.path.isdir(CATALOG_FOLDER):
        print(f"⚠️  Master Catalog folder not found: {CATALOG_FOLDER}")
    else:
        pdf_cache = build_pdf_cache(CATALOG_FOLDER)
        print(f"   Found {len(pdf_cache)} PDF files in catalog folder.\n")

    # --- WRITE MATCHED ITEMS TO EXCEL ---
    START_ROW = 8
    current_row = START_ROW
    write_failures = []
    seen_types = set()
    embedded_paths_list = []

    items_to_process = list(extracted_data)

    print("--- Audit Trail & Cross-Referencing Data ---")
    print(f"    Writing starts at row {START_ROW}.")

    try:
        sheet_index.api.Unprotect()
        print("    🔓 Automatically unprotected sheet to bypass Data Validation.")
    except Exception:
        pass
    print()

    for item in items_to_process:
        extracted_type_raw = item.get('Catalog Number', '')

        # --- CONFLICT FLAG CHECK ---
        raw_conflict = item.get('Conflict_Flag', '')
        conflict = str(raw_conflict).strip() if raw_conflict is not None else ""

        if conflict and conflict.upper() not in ["", "NONE", "N/A", "FALSE"]:
            print(f"    🚨 CONFLICT DETECTED: {conflict}")

        if extracted_type_raw == "UNMATCHED":
            print(f"⚠️  UNMATCHED: '{item.get('Original_Name', '?')}'\n"
                  f"    └─ {item.get('Reason', 'Not in database.')}")
            continue

        extracted_type_clean = str(extracted_type_raw).strip().lower()

        if extracted_type_clean in seen_types:
            continue

        # --- THE INTERACTIVE DATABASE MISS CATCHER ---
        if extracted_type_clean not in reference_dict:
            print(f"\n⚠️  [DATABASE MISS] The AI pulled '{extracted_type_raw}' but it is NOT in your Master List.")
            print(f"   AI's Reason: {item.get('Reason', 'No reason provided.')}")
            print(f"   Original Name: {item.get('Original_Name', 'Unknown')}")
            print("   What would you like to do?")
            print("   [1] Substitute with a correct/alternate catalog number")
            print("   [2] Skip this item entirely")
            print("   [3] Abort the script so I can add it to my Excel database")

            choice = input("   Select 1, 2, or 3: ").strip()

            if choice == '3':
                print("\n🛑 Script aborted by user. Go update your Excel database and run it again!")
                sys.exit()
            elif choice == '1':
                sub_cat = input("   Enter the exact catalog number you want to use from the database: ").strip()
                if sub_cat.lower() in reference_dict:
                    extracted_type_clean = sub_cat.lower()
                    print(f"   ✅ Substituted '{extracted_type_raw}' with '{sub_cat}'.")
                    extracted_type_raw = sub_cat
                else:
                    print(f"   ❌ '{sub_cat}' is ALSO not in the database. Skipping item.")
                    continue
            else:
                print(f"   ⏭️  Skipping '{extracted_type_raw}'.")
                continue

        matched_data = reference_dict[extracted_type_clean]

        cat_val = sanitize(matched_data.get('Catalog Number', ''))
        brand_val = sanitize(matched_data.get('Brand', ''))
        desc_val = sanitize(matched_data.get('Device Description', ''))

        # --- BASE MODEL FALLBACK PROMPT ---
        pdf_paths = []
        if pdf_cache:
            pdf_paths = best_pdfs_for_row(pdf_cache, cat_val, brand_val, desc_val)

        if not pdf_paths:
            base_cat = get_base_model_to_last_digit(cat_val)
            fallback_paths = []

            if base_cat and base_cat != clean_catalog(cat_val):
                fallback_paths = best_pdfs_for_row(pdf_cache, base_cat, brand_val, desc_val)

            if fallback_paths:
                print(f"\n    ⚠️  [ACTION REQUIRED] MISSING CUT SHEET FOR '{cat_val}'")
                ans = input(f"    Do you want to use the base model '{base_cat}' PDF instead? (Y/N): ").strip().upper()
                if ans == 'Y':
                    pdf_paths = fallback_paths
                    cat_val = base_cat
                else:
                    ans2 = input(f"    Write '{cat_val}' to the Excel Index WITHOUT a PDF? (Y/N): ").strip().upper()
                    if ans2 != 'Y':
                        print(f"    ⏭️  SKIPPED: '{cat_val}'")
                        continue
            else:
                print(f"\n    ⚠️  [MISSING PDF] No cut sheet found in folder for '{cat_val}'.")
                ans2 = input(f"    Write '{cat_val}' to the Excel Index WITHOUT a PDF? (Y/N): ").strip().upper()
                if ans2 != 'Y':
                    print(f"    ⏭️  SKIPPED: '{cat_val}'")
                    continue

        seen_types.add(extracted_type_clean)

        for p in pdf_paths:
            if p not in embedded_paths_list:
                embedded_paths_list.append(p)

        print(f"    → Writing row {current_row}: {cat_val}  |  {brand_val}  |  {desc_val}")

        a_ok = safe_write_cell(sheet_index, current_row, 'A', cat_val)
        b_ok = safe_write_cell(sheet_index, current_row, 'B', brand_val)
        c_ok = safe_write_cell(sheet_index, current_row, 'C', desc_val)

        if not (a_ok and b_ok and c_ok):
            print(f"❌ FAILED  → row {current_row} ({cat_val})")
            write_failures.append({'row': current_row, 'catalog': cat_val,
                                   'brand': brand_val, 'desc': desc_val})

        current_row += 1

    items_written = (current_row - START_ROW) - len(write_failures)
    print()
    print("--- Write Summary ---")
    print(f"   Rows used    : {START_ROW} → {current_row - 1}")
    print(f"   Written OK   : {items_written}")
    print(f"   Failed writes: {len(write_failures)}")

    if write_failures:
        print()
        for f in write_failures:
            print(f"   Row {f['row']}: {f['catalog']} | {f['brand']} | {f['desc']}")
        print()
        print("   Fix: Review tab → Unprotect Sheet, then Data → Data Validation → Clear All")

    print("\nSUCCESS: Index written to Excel!")

    # --- EMBED CUT SHEET PDFs ---
    print("\n--- Embedding Cut Sheet PDFs ---")
    if embedded_paths_list:
        success_count = embed_pdfs_into_excel(wb, embedded_paths_list)
        print(f"\n✅ Embedded {success_count} cut sheet PDF(s) into 'Wire and Cable Cut Sheets' tab.")
    else:
        print("⚠️  No PDFs to embed.")

    # --- EXPORT INDEX TO PDF & BUILD FINAL SUBMITTAL ---
    print("\n--- Compiling Final Submittal Package ---")

    try:
        last_row = current_row - 1 if current_row > START_ROW else START_ROW
        sheet_index.page_setup.print_area = f"A1:C{last_row}"

        print(f"Exporting Index (A1:C{last_row}) to PDF...")
        sheet_index.api.ExportAsFixedFormat(0, index_pdf_path)
    except Exception as e:
        ask_to_continue("Exporting Index Sheet to PDF", e)

    print("Stitching pages into a single master PDF...")
    merged_doc = fitz.open()

    if has_approval_sheet and os.path.exists(approval_pdf_path):
        app_doc = fitz.open(approval_pdf_path)
        merged_doc.insert_pdf(app_doc)
        app_doc.close()
        print("   + Merged: Approval Sheet  [Page 1]")
    else:
        print("   ⚠️  Approval Sheet not available — omitted from package.")

    if os.path.exists(index_pdf_path):
        index_doc = fitz.open(index_pdf_path)
        merged_doc.insert_pdf(index_doc)
        index_doc.close()
        print("   + Merged: Index Page")

    if embedded_paths_list:
        for pdf_file in embedded_paths_list:
            try:
                src_doc = fitz.open(pdf_file)
                merged_doc.insert_pdf(src_doc)
                src_doc.close()
                print(f"   + Merged: {os.path.basename(pdf_file)}")
            except Exception as pdf_err:
                print(f"⚠️  Skipping {os.path.basename(pdf_file)}: {pdf_err}")
    else:
        print("⚠️  No cut sheet PDFs were found/embedded — final PDF will contain index only.")

    try:
        print(f"Saving final submittal to: {wireandcablePDF}")
        saved = save_pdf_with_retry(merged_doc, wireandcablePDF)
        merged_doc.close()

        if saved:
            print(f"✅ Master Submittal created: {wireandcablePDF}")
            print("Launching final document...")
            os.startfile(wireandcablePDF)
        else:
            print("⚠️  Submittal PDF was NOT saved. Close it in Bluebeam and re-run.")
    except Exception as e:
        ask_to_continue("Saving Final PDF Compilation", e)

except Exception as e:
    print("\n❌ CRITICAL ERROR DETECTED ❌")
    print(f"The script stopped because: {e}")

finally:
    print("\n" + "=" * 40)
    input("Press Enter to exit...")