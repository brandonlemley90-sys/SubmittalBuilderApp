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
# The second argument (e.g., "ERROR_NO_FOLDER") is a fallback just in case
# you run the script directly instead of through the Meta Agent.
PROJECT_FOLDER = os.environ.get("PROJECT_FOLDER", r"C:\Temp\ERROR_NO_FOLDER")
EXCEL_WORKBOOK_NAME = os.environ.get("EXCEL_WORKBOOK_NAME", "ERROR_NO_EXCEL.xlsm")
SPEC_PDF_NAME = os.environ.get("SPEC_PDF_NAME", "ERROR_NO_SPEC.pdf")
DRAWINGS_PDF_NAME = os.environ.get("DRAWINGS_PDF_NAME", "ERROR_NO_DRAWING.pdf")
CONTRACT_PDF_NAME = os.environ.get("CONTRACT_PDF_NAME", "ERROR_NO_CONTRACT.pdf")
JOB_FORM_PDF_NAME = os.environ.get("JOB_FORM_PDF_NAME", "ERROR_NO_JOB_FORM.pdf")

# ... the rest of your script stays exactly the same ...

# 1. THE MASTER CATALOG FOLDER
CATALOG_FOLDER = os.path.join(
    USER_HOME,
    "Denier",
    "Denier Operations Playbook-Submittal Builder - Documents",
    "Submittal Builder",
    "Catalogs",
    "Grounding and Bonding"
)

# 2. EXCEL DATABASE HEADERS (Must match the columns on your 'Grounding and Bonding List' tab)
COL_CATALOG = "type"
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


STOP_WORDS = {'THE', 'AND', 'FOR', 'WITH', 'ASSORTED', 'SIZE', 'SIZES', 'GROUND', 'BONDING', 'WIRE', 'LUG'}


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

def embed_pdfs_into_excel(wb, pdf_paths_to_embed, sheet_index_obj):
    # Short name bypasses Excel's 31 character limit completely
    cut_sheet_name = 'G&B Cut Sheets'

    ws_cuts = None
    try:
        # Check if any spelling variation exists to avoid duplicate sheet errors
        for name in ['G&B Cut Sheets', 'Grounding and Bonding Cut Sheets', 'Grounding & Bonding Cut Sheets']:
            try:
                ws_cuts = wb.sheets[name]
                break
            except Exception:
                continue

        if ws_cuts:
            for ole in ws_cuts.api.OLEObjects():
                ole.Delete()
            ws_cuts.clear()
            print(f"   Cleared existing '{ws_cuts.name}' sheet.")
        else:
            ws_cuts = wb.sheets.add(name=cut_sheet_name, after=sheet_index_obj)
            print(f"   Created new '{cut_sheet_name}' sheet.")
    except Exception as e:
        print(f"\n❌ CRITICAL: Could not create '{cut_sheet_name}'.")
        print(f"   Ensure your Excel Workbook Structure is UNPROTECTED (Review -> Unprotect Workbook).")
        raise e

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
        print(f"⚠️  Could not locate explicit '{section_label}' section.")
        print(f"   Will rely on full text scanning and Contract deduction.")
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


def extract_grounding_section(full_spec_text):
    return extract_spec_section(
        full_spec_text,
        'Grounding and Bonding',
        start_patterns=[
            r'SECTION\s+\d{2}\s*\d{2}\s*\d{2}[^\n]*GROUNDING\s+AND\s+BONDING',
            r'SECTION\s+\d{2}\s*\d{2}\s*\d{2}[^\n]*TELECOMMUNICATIONS\s+BONDING',
            r'SECTION\s+26\s*05\s*26',
            r'SECTION\s+27\s*05\s*26'
        ],
        end_patterns=[
            r'SECTION\s+\d{2}\s*\d{2}\s*\d{2}',
            r'END\s+OF\s+SECTION',
            r'END\s+OF\s+PART\s+3',
        ]
    )


def get_actual_spec_title(full_text):
    """
    Searches the entire spec book for the EXACT title of the grounding section.
    Accounts for line breaks between the section number and the title.
    Returns (spec_number, spec_title) or (None, None) if not found.
    """
    patterns = [
        r'SECTION\s+(\d{2}\s*\d{2}\s*\d{2})[\s\r\n\-:]+([^\n\r]*GROUNDING\s+AND\s+BONDING[^\n\r]*)',
        r'SECTION\s+(\d{2}\s*\d{2}\s*\d{2})[\s\r\n\-:]+([^\n\r]*TELECOMMUNICATIONS\s+BONDING[^\n\r]*)',
        r'SECTION\s+(26\s*05\s*26)[\s\r\n\-:]+([^\n\r]+)',
        r'SECTION\s+(27\s*05\s*26)[\s\r\n\-:]+([^\n\r]+)'
    ]

    for p in patterns:
        match = re.search(p, full_text, re.IGNORECASE)
        if match:
            num = format_spec_number(match.group(1))
            title = match.group(2).strip()
            # Clean up extra spacing just in case
            title = re.sub(r'\s+', ' ', title)
            return num, title

    return None, None


# =============================================================================
# GEMINI API
# =============================================================================

def call_llm_api(api_key, prompt, data, max_retries=3):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}

    if len(data) > 2000000:
        print(
            f"   ⚠️  Warning: API payload text is massive ({len(data):,} chars). Truncating to prevent connection drop...")
        data = data[:2000000]

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


def format_spec_number(raw_string):
    """Forces any 6 digit number into the XX XX XX format for standard submittals."""
    digits = re.sub(r'\D', '', str(raw_string))
    if len(digits) >= 6:
        return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"
    return raw_string


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

        # ActiveX Injection handling (ComboBox on A column)
        if col_letter == 'A':
            try:
                for ole in sheet.api.OLEObjects():
                    if ole.TopLeftCell.Row == row and ole.TopLeftCell.Column == cell_range.column:
                        try:
                            ole.Object.Value = value
                        except Exception:
                            pass
            except Exception:
                pass

        cell_range.value = value
        return True
    except Exception as e:
        error_code = e.args[0] if e.args else None
        if isinstance(error_code, int) and error_code in (-2146827284, -2146827259, -2147352567):
            print(f"   ⚠️  Cell {col_letter}{row} blocked by Excel Protection/Validation. Value: '{value}'")
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
    # --- PROMPT FOR API KEY EVERY TIME ---
    print("\n" + "=" * 50)
    user_api_key = input("🔑 Please enter your Gemini API Key: ").strip()
    print("=" * 50 + "\n")

    if not user_api_key:
        print("❌ No API key provided. Exiting script.")
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

    # Check for required files
    for path, name in [(spec_pdf_path, SPEC_PDF_NAME), (drawing_pdf_path, DRAWINGS_PDF_NAME),
                       (excel_path, EXCEL_WORKBOOK_NAME)]:
        if not os.path.exists(path):
            print(f"\n❌ [CRITICAL ERROR] Could not find '{name}' inside the Project Folder.")
            sys.exit(1)

    index_pdf_path = os.path.abspath(os.path.join(temp_dir, 'Index_Cover.pdf'))
    review_sheet_pdf_path = os.path.abspath(os.path.join(temp_dir, 'Submittal_For_Review.pdf'))

    print("Connecting to Excel...")
    try:
        wb = xw.Book(excel_path)
    except Exception as e:
        print(f"\n❌ [CRITICAL ERROR] Could not connect to Excel Workbook. Is it open? Error: {e}")
        sys.exit(1)

    match = re.search(r'\((.*?)\)', wb.name)
    project_name = match.group(1).strip() if match else "Unknown Project"

    try:
        # Dynamically grab the index sheet
        sheet_index = None
        for name in ['Grounding and Bonding Index', 'Grounding & Bonding Index']:
            try:
                sheet_index = wb.sheets[name]
                break
            except Exception:
                continue

        if sheet_index is None:
            raise Exception("Could not find the Index tab. Check the spelling.")

        raw_a5 = str(sheet_index.range('A5').value).strip()

        a5_match = re.search(r'\((.*?)\)', raw_a5)
        name_in_a5 = a5_match.group(1).strip() if a5_match else raw_a5

        name_in_a5 = re.sub(r'^\d{2}\s*\d{2}\s*\d{2}\s*[-:]?\s*', '', name_in_a5).strip()

        if name_in_a5 == "None" or not name_in_a5:
            name_in_a5 = "Grounding and Bonding"

    except Exception as e:
        ask_to_continue("Reading 'Grounding and Bonding Index' sheet", e)
        name_in_a5 = "Grounding and Bonding"

    safe_project = re.sub(r'[\\/*?:"<>|]', "", project_name).strip()

    pdf_filename = f"{safe_project} {name_in_a5} Submittal.pdf"

    GroundingandBonding = os.path.abspath(os.path.join(PROJECT_FOLDER, pdf_filename))
    print(f"Target Output: {pdf_filename}\n")

    # --- PROJECT INFO FORM AUTO-DISCOVERY & PARSING ---
    print("--- Searching for Project Form PDF ---")
    form_pdfs = []

    for f in os.listdir(PROJECT_FOLDER):
        if f.lower().endswith('.pdf'):
            if re.search(r'\d{2}-\d{2}-\d{4}', f):
                form_pdfs.append(f)

    job_info = {
        "Job_Number": "Unknown",
        "Job_Name": project_name,
        "Address": "",
        "City_State_Zip": ""
    }

    if form_pdfs:
        form_pdfs.sort(key=lambda x: os.path.getmtime(os.path.join(PROJECT_FOLDER, x)), reverse=True)
        form_pdf_name = form_pdfs[0]
        form_pdf_path = os.path.join(PROJECT_FOLDER, form_pdf_name)
        print(f"   ✅ Auto-detected Form: {form_pdf_name}")

        name_match = re.match(r'(\d{2}-\d{2}-\d{4})\s*-\s*(.*)\.pdf', form_pdf_name, re.IGNORECASE)
        if name_match:
            job_info["Job_Number"] = name_match.group(1).strip()
            job_info["Job_Name"] = name_match.group(2).strip()

        print("   Asking AI to extract address information from the form...")
        try:
            form_text = extract_text_from_pdf(form_pdf_path)
            address_prompt = f"""
            Extract the project details from the following form text and filename.
            Filename: {form_pdf_name}

            RULES:
            1. Find the Job Number (format usually XX-XX-XXXX).
            2. Find the Job Name (Project Name).
            3. Find the Street Address.
            4. Find the City, State, and Zip Code.

            Return ONLY a raw JSON object with these exact keys:
            "Job_Number", "Job_Name", "Address", "City_State_Zip"
            """

            raw_job_ai = call_llm_api(user_api_key, address_prompt, form_text[:15000])
            extracted_job_info = json.loads(raw_job_ai)

            for key in job_info.keys():
                if extracted_job_info.get(key):
                    job_info[key] = extracted_job_info[key]

            print(f"   ✅ Extracted Data: {job_info['Job_Number']} | {job_info['Address']}")
        except Exception as e:
            print(f"   ⚠️ Could not fully extract data from form using AI: {e}")
    else:
        print("   ⚠️ No file matching format 'XX-XX-XXXX - Job Name.pdf' found in the Project Folder.")

    # --- LOAD MASTER DEVICE LIST ---
    try:
        ws_list = None
        for name in ['Grounding & Bonding List', 'Grounding and Bonding List']:
            try:
                ws_list = wb.sheets[name]
                break
            except Exception:
                continue

        if ws_list is None:
            raise Exception("Could not find the 'Grounding & Bonding List' tab in Excel.")

        sheet_data = ws_list.used_range.value

        if not sheet_data:
            raise Exception("The List sheet appears to be empty.")

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
    wiring_spec_text = extract_grounding_section(full_spec_text)

    # --- EXTRACT EXACT SPEC HEADER & WRITE TO A5 ---
    actual_spec_num, actual_spec_title = get_actual_spec_title(full_spec_text)

    if actual_spec_num and actual_spec_title:
        final_a5_string = f"{actual_spec_num} - {actual_spec_title}"
        spec_num_for_review = actual_spec_num
        submittal_title_for_review = actual_spec_title
    else:
        final_a5_string = name_in_a5
        spec_num_for_review = "N/A"
        submittal_title_for_review = name_in_a5

    print(f"Setting A5 Header to: {final_a5_string}")

    try:
        sheet_index.api.Unprotect()
    except:
        pass

    safe_write_cell(sheet_index, 5, 'A', final_a5_string)

    # =========================================================================
    # UPDATE EXCEL APPROVAL SHEET (Submittal for Review)
    # =========================================================================
    print("\n--- Updating Submittal for Review Sheet ---")
    has_review_sheet = False

    try:
        ws_review = None
        for name in ['Submittal for Review', 'Submittals for Review']:
            try:
                ws_review = wb.sheets[name]
                break
            except:
                continue

        if ws_review is None:
            raise Exception("Could not find the 'Submittal for Review' tab.")

        try:
            ws_review.api.Unprotect()
        except:
            pass

        now = datetime.datetime.now()
        current_date = f"{now.month}/{now.day}/{now.strftime('%y')}"

        print(
            f"   Injecting → Job #: {job_info['Job_Number']} | Spec: {spec_num_for_review} | Title: {submittal_title_for_review}")

        safe_write_cell(ws_review, 5, 'B', f"Job #: {job_info['Job_Number']}")
        safe_write_cell(ws_review, 7, 'B', job_info['Job_Name'])
        safe_write_cell(ws_review, 8, 'B', job_info['Address'])
        safe_write_cell(ws_review, 9, 'B', job_info['City_State_Zip'])

        safe_write_cell(ws_review, 11, 'B', f"Spec Section No: {spec_num_for_review}")
        safe_write_cell(ws_review, 15, 'B', f"Submittal Title: {submittal_title_for_review}")

        for row in range(1, 40):
            for col in ['A', 'B', 'C']:
                cell_val = str(ws_review.range(f'{col}{row}').value).strip()
                if cell_val.startswith("Date:"):
                    safe_write_cell(ws_review, row, col, f"Date: {current_date}")
                    break

        print("   Exporting Submittal for Review Sheet to PDF...")

        try:
            ws_review.api.ExportAsFixedFormat(0, review_sheet_pdf_path)
            print(f"   ✅ Review Sheet PDF saved → {review_sheet_pdf_path}")
            has_review_sheet = True
        except Exception as export_e:
            ask_to_continue("Exporting Submittal for Review Sheet to PDF", export_e)
            has_review_sheet = False

    except Exception as e:
        ask_to_continue("Updating 'Submittal for Review' Sheet", e)

    # --- DATA BUDGETING ---
    combined_project_data = (
        f"--- CONTRACT DOCUMENT (ULTIMATE AUTHORITY) ---\n{contract_text}\n\n"
        f"--- GROUNDING AND BONDING SPECIFICATION SECTION ---\n{wiring_spec_text}\n\n"
        f"--- PROJECT DRAWINGS (NOTES/SCHEDULES) ---\n{drawing_text}"
    )

    # --- BUILD PROMPT ---
    my_smart_prompt = f"""
You are a senior electrical estimator performing a submittal review for a construction project.

YOUR TASK:
Review the project specification section, contract, and drawing notes provided below.
Identify every item that is explicitly called out or required by those documents AND that has a matching entry in the OFFICIAL DATABASE LIST.

THE PLATINUM RULE — CONTRACT IS THE ULTIMATE AUTHORITY:
1. The Contract has the absolute final say. Actively hunt the Contract text for keywords like "Scope Alternates", "Value Engineering", "VE", "Substitutions", and "in lieu".
2. If the Contract explicitly adds, requires, or substitutes a material, you MUST include it.
3. If the Contract explicitly EXCLUDES a material, you MUST NOT include it.

THE GOLDEN RULE — DATABASE IS THE AUTHORITY:
The OFFICIAL DATABASE LIST defines the complete universe of items. If it is required and in the database, include it. 

GROUNDING AND BONDING SPECIFIC RULES (CRITICAL MANDATE):
1. GROUND ROD & WELD KITTING (MANDATORY): If Ground Rods are pulled, you MUST pull "Acorn Clamps". If Exothermic Welds are pulled, you MUST pull the corresponding "Various Exothermic Weld Connections" items. Do not pull a rod or weld without its specific connection items.
2. EXOTHERMIC WELDS MANUFACTURER PREFERENCE: For Exothermic Welds and their connections, you MUST prioritize the manufacturer "Harger" over "Cadweld" or others, unless Harger is explicitly banned by the specs. Do not pull multiple brands of the same weld type.
3. CONDUCTOR SPECIFICATIONS: You must explicitly determine the required grounding conductor types. Actively scan for requirements dictating "Bare Copper", "Insulated Green", "Solid", or "Stranded" and pull the exact matching wire types from the database. 
4. BUSBARS, TELECOM, & RACK KITS (CRITICAL): Scan the drawings and specs for electrical rooms, service entrances, and Telecomm/Data rooms. You MUST specifically hunt for and pull ALL required busbars: Telecommunications Main Grounding Busbars (TMGB) AND Secondary Grounding Busbars (TGB). Furthermore, if data/IT racks are mentioned in the specs or drawings, you MUST explicitly pull the "Vertical Rack Bonding Busbar Kit" from the database.
5. LUGS AND TERMINATIONS: Actively hunt for the required termination types. Determine if the project requires Mechanical Lugs or Compression Lugs (e.g., Burndy). If Compression, strictly determine if they must be 1-Hole or 2-Hole lugs and pull the exact matching item.
6. THE "MISSING SPEC" PROTOCOL: If the explicit "Grounding and Bonding" specification section is missing, deduce the required grounding components based strictly on the Contract Scope of Work, the service entrance size on the drawings, and standard NEC grounding requirements for the building type.

SPEC/CONTRACT CITATIONS (MANDATORY):
You must find and record the exact Specification Section, Page Number, OR Contract Clause for the specific rules and thresholds you apply. Put this information in the "Spec_Citation" field for the relevant item. If you deduced the requirement based on Building Type or Missing Specs, note "Deduced from Contract Scope/Drawings".

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
    print("\nSending Contract, Grounding & Bonding specs, and drawing notes to Gemini...")
    extracted_data = []
    try:
        api_response = call_llm_api(user_api_key, prompt=my_smart_prompt, data=combined_project_data)
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
        success_count = embed_pdfs_into_excel(wb, embedded_paths_list, sheet_index)
        print(f"\n✅ Embedded {success_count} cut sheet PDF(s) into 'G&B Cut Sheets' tab.")
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

    if has_review_sheet and os.path.exists(review_sheet_pdf_path):
        app_doc = fitz.open(review_sheet_pdf_path)
        merged_doc.insert_pdf(app_doc)
        app_doc.close()
        print("   + Merged: Submittal for Review Sheet  [Page 1]")
    else:
        print("   ⚠️  Submittal for Review Sheet not available — omitted from package.")

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
        print(f"Saving final submittal to: {GroundingandBonding}")
        saved = save_pdf_with_retry(merged_doc, GroundingandBonding)
        merged_doc.close()

        if saved:
            print(f"✅ Master Submittal created: {GroundingandBonding}")
            print("Launching final document...")
            os.startfile(GroundingandBonding)
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