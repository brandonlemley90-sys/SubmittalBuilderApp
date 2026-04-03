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

# 3. THE MASTER CATALOG FOLDER
CATALOG_FOLDER = os.path.join(
    USER_HOME,
    "Denier",
    "Denier Operations Playbook-Submittal Builder - Documents",
    "Submittal Builder",
    "Catalogs",
    "Wiring Devices"
)


# =============================================================================
# FAILURE HANDLING ENGINE
# =============================================================================

def ask_to_continue(step_name, error_msg):
    """Catches fatal errors and asks the user if they want to push through."""
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


STOP_WORDS = {'THE', 'AND', 'FOR', 'WITH', 'ASSORTED', 'SIZE', 'SIZES'}


def tokenize(norm):
    return [t for t in norm.split() if len(t) > 1 and t not in STOP_WORDS]


def token_overlap_score(filename_norm, tokens):
    score = 0
    for t in tokens:
        if t in filename_norm:
            score += 20 if any(c.isdigit() for c in t) else 10
    return score


def is_decorator_mentioned(desc_raw):
    d = desc_raw.upper()
    return 'DECORATOR' in d or 'DECORA' in d


def is_decorator_pdf_key(pdf_key_clean):
    return 'DECORATOR' in pdf_key_clean or 'DECORA' in pdf_key_clean


def get_required_plate_type(desc_raw, catalog_raw):
    d = desc_raw.upper()
    c = clean_catalog(catalog_raw)
    if c[:2] == 'SS' or 'STAINLESS' in d:
        return 'SS'
    if 'THERMOPLASTIC' in d and ('PLATE' in d or 'WALLPLATE' in d):
        return 'THERMO'
    return ''


def extract_ss_code(catalog_raw):
    c = clean_catalog(catalog_raw)
    if not c.startswith('SS'):
        return ''
    digits = ''
    for ch in c[2:]:
        if ch.isdigit():
            digits += ch
        else:
            break
    return ('SS' + digits) if digits else ''


def extract_thermo_plate_code(catalog_raw):
    s = catalog_raw.upper()
    for sep in ['/', '\\', '-', '_', ',', ';', ':', '\t']:
        s = s.replace(sep, ' ')
    for part in s.split():
        t = clean_catalog(part)
        if t in ('P1', 'P2', 'P3', 'P4', 'PJ1', 'PJ2', 'PJ3', 'PJ4'):
            return t
    return ''


def get_required_plate_token(desc_raw, catalog_raw):
    req_type = get_required_plate_type(desc_raw, catalog_raw)
    if req_type == 'THERMO':
        return extract_thermo_plate_code(catalog_raw)
    if req_type == 'SS':
        return extract_ss_code(catalog_raw)
    return ''


def passes_plate_gate(pdf_key_clean, req_type, req_token, want_decorator):
    if not req_type:
        return True
    if req_type == 'THERMO':
        return bool(req_token) and (req_token in pdf_key_clean)
    if req_type == 'SS':
        if 'SS' not in pdf_key_clean:
            return False
        if req_token and req_token not in pdf_key_clean:
            return False
        pdf_is_dec = is_decorator_pdf_key(pdf_key_clean)
        if pdf_is_dec and not want_decorator:
            return False
        if want_decorator and not pdf_is_dec:
            return False
        return True
    return True


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
    d_upper = desc_raw.upper()
    if 'TR' in c_clean or 'TAMPER' in d_upper:
        for w in ('TAMPER', 'RESISTANT'):
            if w not in tokens:
                tokens.append(w)
    return tokens


def find_best_pdf_for_mfg(pdf_cache, idx_norm, row_tokens, mfg_norm,
                          req_type, req_token, want_decorator, catalog_raw):
    cat_clean = clean_catalog(catalog_raw)
    must_have_catalog = len(cat_clean) >= 4 and has_digit(cat_clean)
    base_model = get_base_model_to_last_digit(cat_clean)

    # Strip standard amperages off the end to match files like "GFTWRST" instead of "GFTWRST20"
    cat_no_amp = re.sub(r'(15|20|30)$', '', base_model)
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
        if not passes_plate_gate(key_clean, req_type, req_token, want_decorator):
            continue

        if must_have_catalog:
            if cat_clean not in key_clean:
                if base_model and base_model not in key_clean:
                    if cat_no_amp and cat_no_amp in key_clean and len(cat_no_amp) >= 4:
                        pass
                    elif len(row_digits) >= 4:
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

    req_type = get_required_plate_type(desc_raw, catalog_raw)
    req_token = get_required_plate_token(desc_raw, catalog_raw)
    want_decorator = is_decorator_mentioned(desc_raw)

    if req_type == 'THERMO' and not req_token:
        return []

    mfg_candidates = expand_mfg_candidates(mfg_raw)
    if not mfg_candidates:
        return []

    row_tokens = build_row_tokens(idx_norm, catalog_raw, desc_raw)

    results = []
    seen_paths = set()
    for mfg_norm in mfg_candidates:
        best = find_best_pdf_for_mfg(
            pdf_cache, idx_norm, row_tokens, mfg_norm,
            req_type, req_token, want_decorator, catalog_raw
        )
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
    index_sheet_name = 'Wiring Device Index'
    cut_sheet_name = 'Wiring Device Cut Sheets'

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
    print(f"Opening PDF: {os.path.basename(pdf_path)}...")
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()

        doc.close()  # <--- Purges the PDF from RAM
        return text
    except Exception as e:
        ask_to_continue(f"Reading PDF ({pdf_path})", e)
        return ""


def extract_spec_section(full_spec_text, section_label, start_patterns, end_patterns):
    start_pos = None
    for pattern in start_patterns:
        match = re.search(pattern, full_spec_text, re.IGNORECASE)
        if match and (start_pos is None or match.start() < start_pos):
            start_pos = match.start()

    if start_pos is None:
        print(f"⚠️  Could not locate '{section_label}' section. Using full spec text.")
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
        'Wiring Devices',
        start_patterns=[
            r'SECTION\s+26\s*27\s*26',
            r'SECTION\s+16\s*14\s*[05]',
            r'WIRING\s+DEVICES',
            r'WIRING\s+DEVICE[S]?',
            r'RECEPTACLES?\s+AND\s+SWITCHES',
            r'SWITCHES\s+AND\s+RECEPTACLES',
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
    return "26 27 26 - WIRING DEVICES"


# =============================================================================
# GEMINI API
# =============================================================================

def call_llm_api(prompt, data, max_retries=3):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={API_KEY}"
    )
    headers = {"Content-Type": "application/json"}

    # Prevent massive payloads from crashing the connection
    if len(data) > 100000:
        print(f"   ⚠️  Warning: PDF text is massive ({len(data):,} chars). Truncating to prevent connection drop...")
        data = data[:100000]

    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n{data}"}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }

    for attempt in range(1, max_retries + 1):
        try:
            # 90-second timeout
            response = requests.post(url, headers=headers, json=payload, timeout=90)

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

    # Construct the absolute paths based on the CONFIG variables
    spec_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, SPEC_PDF_NAME))
    drawing_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, DRAWINGS_PDF_NAME))
    excel_path = os.path.abspath(os.path.join(PROJECT_FOLDER, EXCEL_WORKBOOK_NAME))

    # Check if files actually exist in the folder
    for path, name in [(spec_pdf_path, SPEC_PDF_NAME), (drawing_pdf_path, DRAWINGS_PDF_NAME),
                       (excel_path, EXCEL_WORKBOOK_NAME)]:
        if not os.path.exists(path):
            print(f"\n❌ [CRITICAL ERROR] Could not find '{name}' inside the Project Folder.")
            sys.exit(1)

    index_pdf_path = os.path.abspath(os.path.join(temp_dir, 'Index_Cover.pdf'))
    approval_pdf_path = os.path.abspath(os.path.join(temp_dir, 'Approval_Cover.pdf'))

    # --- CONNECT TO EXCEL ---
    print("Connecting to Excel...")
    try:
        wb = xw.Book(excel_path)
    except Exception as e:
        print(f"\n❌ [CRITICAL ERROR] Could not connect to Excel Workbook. Is it open? Error: {e}")
        sys.exit(1)

    # --- DYNAMIC FILE NAMING ---
    match = re.search(r'\((.*?)\)', wb.name)
    project_name = match.group(1).strip() if match else "Unknown Project"

    try:
        sheet_index = wb.sheets['Wiring Device Index']
        raw_a5 = str(sheet_index.range('A5').value).strip()

        # 1. If A5 already has "Spec (Title)" from a previous run, grab just the Title from inside parentheses
        a5_match = re.search(r'\((.*?)\)', raw_a5)
        name_in_a5 = a5_match.group(1).strip() if a5_match else raw_a5

        # 2. CRITICAL FIX: Scrubber to permanently strip stray Spec Numbers out of the title string
        name_in_a5 = re.sub(r'^\d{2}\s*\d{2}\s*\d{2}\s*[-:]?\s*', '', name_in_a5).strip()

        if name_in_a5 == "None" or not name_in_a5:
            name_in_a5 = "Wiring Devices"

    except Exception as e:
        ask_to_continue("Reading 'Wiring Device Index' sheet", e)
        name_in_a5 = "Wiring Devices"

    safe_a5 = re.sub(r'[\\/*?:"<>|]', "", name_in_a5).strip()
    safe_project = re.sub(r'[\\/*?:"<>|]', "", project_name).strip()

    pdf_filename = f"{safe_project} {safe_a5} Submittal.pdf"

    # Final Output saved directly to the Project Folder
    wiringdevicesPDF = os.path.abspath(os.path.join(PROJECT_FOLDER, pdf_filename))
    print(f"Target Output: {pdf_filename}\n")

    # --- LOAD PROJECT INFO FORM ---
    print("--- Loading Project Form PDF ---")
    job_info = {
        "Job_Number": "Unknown",
        "Job_Name": project_name,
        "Address": "",
        "City_State_Zip": ""
    }

    if JOB_FORM_PDF_NAME and "ERROR" not in JOB_FORM_PDF_NAME:
        form_pdf_path = os.path.abspath(os.path.join(PROJECT_FOLDER, JOB_FORM_PDF_NAME))
        print(f"   ✅ Using Selected Form: {JOB_FORM_PDF_NAME}")

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

            raw_job_ai = call_llm_api(address_prompt, form_text[:15000])
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
        ws_list = wb.sheets['Wiring Devices List']
        sheet_data = ws_list.used_range.value

        if not sheet_data:
            raise Exception("The 'Wiring Devices List' sheet appears to be empty.")

        header_row_idx = -1
        headers = []
        for i, row in enumerate(sheet_data):
            clean_row = [str(cell).strip().lower() if cell else '' for cell in row]
            if 'catalog number' in clean_row and 'brand' in clean_row and 'device description' in clean_row:
                header_row_idx = i
                headers = clean_row
                break

        if header_row_idx == -1:
            raise Exception("Could not find header row on 'Wiring Devices List' sheet.")

        cat_idx = headers.index('catalog number')
        brand_idx = headers.index('brand')
        desc_idx = headers.index('device description')

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

        print(f"\nLoaded {len(db_for_prompt)} official wiring devices from Excel.")
    except Exception as e:
        ask_to_continue("Loading Master Device List from Excel", e)

    # --- EXTRACT & ISOLATE SPEC TEXT ---
    full_spec_text = extract_text_from_pdf(spec_pdf_path)
    drawing_text = extract_text_from_pdf(drawing_pdf_path)
    wiring_spec_text = extract_wiring_devices_section(full_spec_text)

    # --- EXTRACT SPEC HEADER & WRITE TO A5 ---
    spec_title = get_spec_header(wiring_spec_text)
    final_a5_string = f"{spec_title} ({name_in_a5})"
    print(f"Setting A5 Header to: {final_a5_string}")
    safe_write_cell(sheet_index, 5, 'A', final_a5_string)

    # =========================================================================
    # UPDATE EXCEL APPROVAL SHEET
    # =========================================================================
    print("\n--- Updating Approval Sheet ---")
    has_approval_sheet = False

    try:
        ws_app = wb.sheets['Submittal for Review']
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

    combined_project_data = (
        f"--- WIRING DEVICES SPECIFICATION SECTION ---\n{wiring_spec_text}\n\n"
        f"--- PROJECT DRAWINGS (NOTES/SCHEDULES) ---\n{drawing_text}"
    )

    # --- BUILD PROMPT ---
    my_smart_prompt = f"""
You are a senior electrical estimator performing a submittal review for a construction project.

YOUR TASK:
Review the project specification section and drawing notes provided below.
Identify every item that is explicitly called out or required by those documents AND that has a matching entry in the OFFICIAL DATABASE LIST.

THE GOLDEN RULE — DATABASE IS THE AUTHORITY:
The OFFICIAL DATABASE LIST defines the complete universe of items. If it is required and in the database, include it. 
EXCLUSIONS: Completely ignore Floor Boxes, Poke-Thrus, Dimmers, Occupancy Sensors, and Timers. These are handled in separate submittals. Do not attempt to pull them.

SYMBOL DICTIONARY:
Use this to translate drawing symbols:
- S = Single Pole Switch
- S3, S_3, S3W = 3-Way Switch
- S4, S_4, S4W = 4-Way Switch
- SK, S_K = Key Operated Switch
- Standard Receptacle Symbol (Circle with two lines) = Duplex Receptacle
- GFI or GFCI = Ground Fault Circuit Interrupter
- WP = Weatherproof
- TR = Tamper Resistant

GENERIC MATCHING & EQUAL TRANSLATOR (CRITICAL): 
1. Translate generics (e.g., "Toggle Switch") to specific catalog numbers.
2. EQUAL TRANSLATOR: Find equivalents for competitor parts (Leviton, Pass & Seymour, Hubbell, etc.) based strictly on the provided database.
3. DEVICE VARIANTS: Identify environmental variants (TR, WR). Pull ALL required specific catalog numbers if the spec dictates different types for different areas.

GRADE, COLOR & MATERIAL RULES (CRITICAL):
1. READ THE SPEC: Actively scan the specification text to determine the required device grade (e.g., Commercial, Specification, Industrial, Hospital) and wallplate material (e.g., Thermoplastic, Nylon, Stainless Steel).
2. DEFAULT COLOR: Identify the required device color. If the specification does NOT explicitly state a device or thermoplastic plate color, you MUST default to IVORY. 
3. THE HUBBELL BROWN RULE: If the spec requires "Brown", Hubbell and Pass & Seymour use their base catalog number (e.g., "GF20", "GFTW20", "HBL1221") to represent brown. DO NOT append "I" or "W" to these parts. The base number IS the brown device.
4. AMPERAGE (ABSOLUTE MANDATE): NEVER pull 15A devices (e.g., GF15, 5262, 5252). You are FORBIDDEN from using 15A. You MUST ALWAYS pull the 20A versions (e.g., GF20, 5362). The commercial standard is strictly 20A.
5. THE DATABASE IS THE UNIVERSE: The OFFICIAL DATABASE LIST contains every color and grade variant. You must pull the exact catalog number from the database. If you cannot find the exact color/grade match, output the closest 20A match you can find and explain the discrepancy in the "Reason" field.

WALLPLATE RULES (CRITICAL MANDATE):
1. MATERIAL STRICTNESS: Actively scan the specification for the required wallplate material. Parking garages and commercial spaces almost always specify Stainless Steel (e.g., Type 302/304). 
2. THE THERMOPLASTIC BAN: If the spec calls for Stainless Steel, you are STRICTLY FORBIDDEN from pulling Nylon or Thermoplastic plates (e.g., SP8, P8, TP8). You MUST pull the Stainless Steel catalog numbers (e.g., SS8, SS26) from the database.
3. DEVICE MATCHING: Standard toggle switches and duplex receptacles take standard plates. GFCIs and Decora switches require "Decorator" wallplates (e.g., SS26).

GFCI EXPLICIT MANDATE (CRITICAL):
1. You MUST actively scan the drawings and spec for GFI or GFCI requirements. 
2. If they exist, you are STRICTLY REQUIRED to output the 20A GFCI catalog numbers in your JSON array. If you skip the GFCIs, the submittal will be rejected.

WEATHERPROOF & IN-USE COVER RULES (CRITICAL):
1. If Weatherproof (WP) or In-Use covers are required by the drawings or specs, you CANNOT just pull one GFCI. You MUST pull ALL THREE of the following 20A variants and list them as separate items in your JSON array:
   - Item 1: Standard indoor 20A GFCI (e.g., "GF20")
   - Item 2: Weather Resistant 20A GFCI (e.g., "GFTW20")
   - Item 3: Tamper & Weather Resistant 20A GFCI (e.g., "GFTWRST20")
2. You must output all three of those catalog numbers into the final list. Do not skip any.
3. IN-USE COVER MANDATE: If Weatherproof or In-Use covers are required by the spec or drawings, DO NOT attempt to select a specific cover catalog number yourself. You are FORBIDDEN from guessing the cover brand. You MUST output exactly ONE special entry formatted as: "Catalog Number": "IN-USE-PROMPT". 
4. TAYMAC RULE: If Taymac MX3200 is pulled, you MUST also pull Taymac MX6200.

SPEC VS DRAWING CONFLICTS:
If drawings conflict with specifications, the SPECIFICATION takes precedence. You MUST follow the spec, but fill out the "Conflict_Flag" field in your JSON output to warn the user.

DEDUPLICATION: List each catalog number only ONCE.

JSON FORMAT (STRICT):
Return ONLY a raw JSON array. No markdown.
Keys: "Catalog Number", "Brand", "Device Description", "Original_Name", "Reason", "Conflict_Flag"

OFFICIAL DATABASE LIST:
{json.dumps(db_for_prompt)}
"""

    # --- CALL GEMINI ---
    print("\nSending Wiring Devices spec section and drawing notes to Gemini...")
    extracted_data = []
    try:
        api_response = call_llm_api(prompt=my_smart_prompt, data=combined_project_data)
        extracted_data = json.loads(api_response)
        print(f"Success! Gemini analyzed the documents. Processing items...\n")

        print("--- AI RAW OUTPUT PRE-FILTER ---")
        for item in extracted_data:
            print(f"AI suggested: {item.get('Catalog Number', 'N/A')} | Reason: {item.get('Reason', 'None')}")
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
    print()

    in_use_prompt_answered = False

    for item in items_to_process:
        extracted_type_raw = item.get('Catalog Number', '')

        # --- INTERACTIVE IN-USE PROMPT ---
        if extracted_type_raw == "IN-USE-PROMPT":
            if not in_use_prompt_answered:
                print(f"\n⚠️  [ACTION REQUIRED] IN-USE COVER REQUIREMENT DETECTED")
                print(f"    AI Note: {item.get('Reason', 'WP covers required.')}")
                ans = input("    Do you want to use Taymac MX3200 & MX6200? (Y/N): ").strip().upper()
                if ans == 'Y':
                    items_to_process.append({"Catalog Number": "MX3200", "Reason": ""})
                    items_to_process.append({"Catalog Number": "MX6200", "Reason": ""})
                else:
                    ans2 = input("    Do you want to use Hubbell WP26E instead? (Y/N): ").strip().upper()
                    if ans2 == 'Y':
                        items_to_process.append({"Catalog Number": "WP26E", "Reason": ""})
                in_use_prompt_answered = True
            continue

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
        print(f"\n✅ Embedded {success_count} cut sheet PDF(s) into 'Wiring Device Cut Sheets' tab.")
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

    # ---- PAGE ORDER ----
    # 1. Approval Sheet  (always first)
    # 2. Index Cover Page
    # 3. Cut Sheet PDFs  (one per matched device)
    # --------------------

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
        print(f"Saving final submittal to: {wiringdevicesPDF}")
        saved = save_pdf_with_retry(merged_doc, wiringdevicesPDF)
        merged_doc.close()

        if saved:
            print(f"✅ Master Submittal created: {wiringdevicesPDF}")
            print("Launching final document...")
            os.startfile(wiringdevicesPDF)
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