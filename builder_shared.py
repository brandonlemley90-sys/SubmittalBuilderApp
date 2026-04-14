import os
import re
import json
import requests
import fitz # PyMuPDF
import xlwings as xw
import time
from datetime import datetime

<<<<<<< Updated upstream
class BuilderLogger:
    @staticmethod
    def log(message, category="SYSTEM"):
        timestamp = time.strftime("%H:%M:%S")
        print(f"{timestamp} [{category:<10}] {message}")
        sys.stdout.flush()

    @staticmethod
    def prompt(prompt_type, message):
        if os.environ.get("HEADLESS_WORKER") == "TRUE":
            return "Y" if prompt_type == "YN" else ""
        if os.environ.get("RUNNING_FROM_WEB") == "TRUE":
            print(f"___PROMPT___|{prompt_type}|{message}")
            sys.stdout.flush()
            return sys.stdin.readline().strip()
        return input(f"\n{message} ").strip()

# Module-level aliases used by builder modules
log    = BuilderLogger.log
prompt = BuilderLogger.prompt


def call_gemini(api_key, prompt_text, data, model="gemini-2.0-flash", max_retries=3):
    """Shared Gemini API connector with retry logic."""
    url     = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    if len(data) > 1_000_000:
        BuilderLogger.log(f"Truncating payload ({len(data)} chars)", "AI")
        data = data[:1_000_000]

    payload = {
        "contents": [{"parts": [{"text": f"{prompt_text}\n\n{data}"}]}],
        "generationConfig": {
            "temperature":      0.1,
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
                return raw.strip().removeprefix('```json').removesuffix('```').strip()
            BuilderLogger.log(f"API Error {resp.status_code} (attempt {attempt})", "AI")
            if attempt < max_retries:
                time.sleep(2)
        except Exception as e:
            BuilderLogger.log(f"Connection Error: {e}", "AI")
            if attempt < max_retries:
                time.sleep(2)
    return "{}"


def extract_pdf_text(pdf_path):
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        doc  = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        BuilderLogger.log(f"Error reading PDF {os.path.basename(pdf_path)}: {e}", "ERROR")
        return ""
=======
# =============================================================================
# --- CORE UTILITIES: Terminal Colors & Headers ---
# =============================================================================

def log(msg, category="SYSTEM"):
    time_str = datetime.now().strftime("%H:%M:%S")
    # Using plain strings to avoid UnicodeEncodeError in Windows Terminal
    # [SYSTEM], [SPEC], [EXCEL], [AI], [ERROR], [SUCCESS]
    print(f"{time_str} [{category}] {msg}")
>>>>>>> Stashed changes


def format_spec_number(raw_string):
    """Forces any 6 digit number into the XX XX XX format for standard submittals."""
    digits = re.sub(r'\D', '', str(raw_string))
    if len(digits) >= 6:
        return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"
    return raw_string


def format_title_case(text):
    if not text:
        return ""
    small_words = {'and', 'or', 'the', 'for', 'a', 'an', 'of', 'in', 'to', 'with', 'on', 'at', 'by', 'as'}
<<<<<<< Updated upstream
    words  = text.lower().split()
    result = [words[0].capitalize()] + [
        w if w in small_words else w.capitalize() for w in words[1:]
    ]
    return ' '.join(result)


def save_pdf_safely(doc, output_path, max_attempts=5):
    """Save a PDF with retries if the file is locked by another app."""
    for attempt in range(1, max_attempts + 1):
        try:
            doc.save(output_path)
            return True
        except Exception:
            BuilderLogger.log(f"File locked: {os.path.basename(output_path)}. Close it in Bluebeam/Acrobat.", "WARNING")
            if os.environ.get("HEADLESS_WORKER") == "TRUE":
                return False
            BuilderLogger.prompt("ENTER", "Press CONFIRM / PROCEED when ready:")
    return False


=======
    words = text.lower().split()
    if not words: return ""
    result = [words[0].capitalize()]
    for word in words[1:]:
        if word in small_words:
            result.append(word)
        else:
            result.append(word.capitalize())
    return ' '.join(result)

>>>>>>> Stashed changes
def get_workbook(path):
    try:
        app = xw.App(visible=True)
        return app.books.open(path)
    except Exception as e:
        log(f"Workbook Open Error: {e}", "ERROR")
        return None

<<<<<<< Updated upstream

class BaseBuilder:
    """Common operations shared by class-based builder modules."""

    def __init__(self, context, category_name, catalog_subfolder):
        self.context  = context
        self.category = category_name
        self.wb       = context['wb']
        self.api_key  = context['api_key']
        self.config   = context['project_config']
        self.job_info = context['job_info']

        user_home = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        self.catalog_folder = os.path.join(
            user_home, "Denier", "Denier Operations Playbook-Submittal Builder - Documents",
            "Submittal Builder", "Catalogs", catalog_subfolder
        )

        # Intermediate PDFs go to TEMP (overwritten each run; not the final output)
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        self.review_pdf_path    = os.path.join(temp_dir, f'{category_name}_approval_tmp.pdf')
        self.index_pdf_path     = os.path.join(temp_dir, f'{category_name}_index_tmp.pdf')
        self.cutsheets_pdf_path = os.path.join(temp_dir, f'{category_name}_cutsheets_tmp.pdf')

        # Final output: "{Job Name} {Category} Submittal.pdf" in PROJECT_FOLDER
        job_name = self.job_info.get('Job_Name', 'Project')
        self.submittal_pdf_path = os.path.join(
            self.config["PROJECT_FOLDER"],
            f"{job_name} {category_name} Submittal.pdf"
        )

    def log(self, message, category=None):
        BuilderLogger.log(message, category or self.category.upper())

    def get_spec_path(self):
        return os.path.join(self.config["PROJECT_FOLDER"], self.config.get("SPEC_PDF_NAME", ""))

    def get_drawings_path(self):
        return os.path.join(self.config["PROJECT_FOLDER"], self.config.get("DRAWINGS_PDF_NAME", ""))

    def load_table(self, sheet_name, table_name):
        try:
            ws  = self.wb.sheets[sheet_name]
            tbl = ws.tables[table_name]
            if tbl.data_body_range is None:
                return []
            headers = [str(h).strip() for h in tbl.header_row_range.value]
            data    = tbl.data_body_range.value
            if not data:
                return []
            if not isinstance(data[0], list):
                data = [data]
            return [dict(zip(headers, row)) for row in data]
        except Exception:
            return []

    def update_review_sheet(self, spec_num, submittal_title):
        try:
            ws = self.wb.sheets['Submittal for Review']
            ws.range('B5').value  = f"Job #: {self.job_info['Job_Number']}"
            ws.range('B7').value  = self.job_info['Job_Name']
            ws.range('B8').value  = self.job_info['Address']
            ws.range('B9').value  = self.job_info['City_State_Zip']
            ws.range('B11').value = f"Spec Section No: {spec_num}"
            ws.range('B15').value = f"Submittal Title: {submittal_title}"
            ws.api.ExportAsFixedFormat(0, self.review_pdf_path)
            return True
=======
def prompt(type_str, msg):
    if os.environ.get("HEADLESS") == "TRUE":
        return
    if type_str == "ENTER":
        input(f"\n[PROMPT] {msg}\n")

# =============================================================================
# --- THE PLATINUM PDF MATCHING ENGINE ---
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

def normalize_for_match(s):
    t = str(s).upper().strip()
    for ch in ["'", "\u2018", "\u2019"]:
        t = t.replace(ch, '')
    for ch in ['.', ',', '\\', '-', '&', '_', '/']:
        t = t.replace(ch, ' ')
    while '  ' in t:
        t = t.replace('  ', ' ')
    return t.strip()

def tokenize(norm, stop_words=None):
    if stop_words is None:
        stop_words = {'THE', 'AND', 'FOR', 'WITH', 'BOX', 'COVERS'}
    return [t for t in norm.split() if len(t) > 1 and t not in stop_words]

def token_overlap_score(filename_norm, tokens):
    score = 0
    for t in tokens:
        if t in filename_norm:
            score += 20 if any(c.isdigit() for c in t) else 10
    return score

# =============================================================================
# --- GEMINI API: FALLBACK & RETRY ENGINE ---
# =============================================================================

def call_gemini(api_key, prompt, data, model="gemini-2.5-flash", max_retries=3):
    """
    Robust API call with automatic fallback from 2.5 to 1.5-flash-latest on demand spikes (503/429).
    """
    headers = {"Content-Type": "application/json"}
    
    # 2.5 context window is very large, but we'll trim to 2,000,000 for stability
    if len(data) > 2000000:
        log(f"Trimming massive data ({len(data):,} chars) to 2.0M target...", "AI")
        data = data[:2000000]

    current_model = model

    for attempt in range(1, max_retries + 1):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{prompt}\n\n{data}"}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            # --- Handling High Demand / Throttling ---
            if response.status_code in [503, 429]:
                log(f"API Error {response.status_code}: {response.text} (Attempt {attempt})", "AI")
                if "gemini-2.5" in current_model:
                    log("Switching to gemini-flash-latest for stability...", "AI")
                    current_model = "gemini-flash-latest"
                    continue
                else:
                    wait_time = 5 * attempt
                    log(f"Model Busy. Retrying in {wait_time}s...", "AI")
                    time.sleep(wait_time)
                    continue

            if response.status_code != 200:
                log(f"Failed API {response.status_code}: {response.text}", "ERROR")
                return "[]"
                
            json_res = response.json()
            raw_text = json_res['candidates'][0]['content']['parts'][0]['text']
            return raw_text.strip().removeprefix('```json').removesuffix('```').strip()
            
        except Exception as e:
            log(f"API Attempt {attempt} Exception: {e}", "ERROR")
            time.sleep(2)
    return "[]"

# =============================================================================
# --- BASE BUILDER: Common Methods ---
# =============================================================================

class BaseBuilder:
    def __init__(self, context, builder_name, catalog_subfolder):
        self.context = context
        self.builder_name = builder_name
        self.catalog_folder = os.path.join(context['project_config']['CATALOG_ROOT'], catalog_subfolder)
        self.wb = context['wb']
        self.config = context['project_config']
        self.job_info = context['job_info']
        self.pdf_cache = []

    def load_material_database(self, sheet_name):
        try:
            ws = self.wb.sheets[sheet_name]
            data = ws.used_range.value
            if not data: return []
            
            header = [str(h).strip().lower() for h in data[0]]
            # Standard Denier headers: keyword search|type, manufacturer, description
            db = []
            for row in data[1:]:
                item = {}
                for i, key in enumerate(header):
                    item[key] = row[i] if i < len(row) else None
                db.append(item)
            return db
>>>>>>> Stashed changes
        except Exception as e:
            log(f"Failed to load DB {sheet_name}: {e}", "EXCEL")
            return []

    def get_spec_path(self):
        return os.path.join(self.config['PROJECT_FOLDER'], self.config['SPEC_PDF_NAME'])

    def get_drawings_path(self):
        return os.path.join(self.config['PROJECT_FOLDER'], self.config['DRAWINGS_PDF_NAME'])

    def get_contract_path(self):
        return os.path.join(self.config['PROJECT_FOLDER'], self.config['CONTRACT_PDF_NAME'])

    def build_pdf_cache(self):
        cache = []
        if not os.path.exists(self.catalog_folder):
<<<<<<< Updated upstream
            return cache
        for d, _, files in os.walk(self.catalog_folder):
=======
            log(f"Catalog folder missing: {self.catalog_folder}", "WARNING")
            return []
            
        for root, dirs, files in os.walk(self.catalog_folder):
>>>>>>> Stashed changes
            for f in files:
                if f.lower().endswith(".pdf"):
                    path = os.path.join(root, f)
                    name_norm = normalize_for_match(f.upper())
                    key_clean = clean_catalog(f)
                    cache.append({
<<<<<<< Updated upstream
                        'path':      os.path.join(d, f),
                        'name_norm': f.upper().strip(),
                        'raw_name':  f.lower()
=======
                        'path': path,
                        'name_norm': name_norm,
                        'key_clean': key_clean,
                        'digits_only': digits_only(key_clean)
>>>>>>> Stashed changes
                    })
        self.pdf_cache = cache
        return cache

<<<<<<< Updated upstream
    def staple_submittal(self):
        """
        Merge approval sheet → index → cut sheets into one final submittal PDF.
        Saves to self.submittal_pdf_path and returns the path, or None on failure.
        """
        parts = [p for p in [self.review_pdf_path, self.index_pdf_path, self.cutsheets_pdf_path]
                 if p and os.path.exists(p)]

        if not parts:
            self.log("No PDF parts found to staple.", "WARNING")
            return None

        try:
            combined = fitz.open()
            for p in parts:
                with fitz.open(p) as part_doc:
                    combined.insert_pdf(part_doc)
            combined.save(self.submittal_pdf_path)
            combined.close()
            self.log(f"Submittal stapled: {os.path.basename(self.submittal_pdf_path)}", "SUCCESS")
            return self.submittal_pdf_path
        except Exception as e:
            self.log(f"Staple failed: {e}", "ERROR")
            return None
=======
    def find_best_pdf(self, catalog_raw, mfg_raw, desc_raw):
        if not self.pdf_cache: self.build_pdf_cache()
        
        # Denier PDF Logic
        cat_clean = clean_catalog(catalog_raw)
        mfg_norm = normalize_for_match(mfg_raw)
        idx_text = normalize_for_match(f"{catalog_raw} {mfg_raw} {desc_raw}")
        tokens = tokenize(idx_text)
        if cat_clean: tokens.append(cat_clean)
        
        base_model = get_base_model_to_last_digit(cat_clean)
        row_digits = digits_only(cat_clean)
        
        best_score = -1
        best_path = None
        
        for entry in self.pdf_cache:
            # First filter: Manufacturer Must Mentioned
            if mfg_norm not in entry['name_norm']: continue
            
            # Second filter: Catalog digits safety
            if len(row_digits) >= 4:
                if row_digits not in entry['digits_only']: continue
            elif base_model and base_model not in entry['key_clean']:
                continue
            
            score = token_overlap_score(entry['name_norm'], tokens)
            if score > best_score:
                best_score = score
                best_path = entry['path']
                
        return best_path

    def embed_pdfs(self, pdf_paths, cutsheet_tab_name):
        try:
            if cutsheet_tab_name not in [s.name for s in self.wb.sheets]:
                self.wb.sheets.add(cutsheet_tab_name)
            ws = self.wb.sheets[cutsheet_tab_name]
            
            # Clear existing OLEs
            for ole in ws.api.OLEObjects():
                ole.Delete()
            ws.clear()
            
            top = 10
            for path in pdf_paths:
                if not os.path.exists(path): continue
                ws.api.Activate()
                ole = ws.api.OLEObjects().Add(
                    Filename=os.path.abspath(path),
                    Link=False,
                    DisplayAsIcon=True
                )
                ole.Left = 20
                ole.Top = top
                top += 65
                log(f"Embedded icon: {os.path.basename(path)}", "EXCEL")
            return True
        except Exception as e:
            log(f"Embed Failure: {e}", "ERROR")
            return False

    def finalize_submittal(self, category_name):
        # Placeholder for final merge logic (Approval + Index + Cuts)
        log(f"Finalizing {category_name} PDF Package...", "PIPELINE")
        pass

def extract_pdf_text(path):
    if not os.path.exists(path): return ""
    try:
        doc = fitz.open(path)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        return text
    except:
        return ""
>>>>>>> Stashed changes
