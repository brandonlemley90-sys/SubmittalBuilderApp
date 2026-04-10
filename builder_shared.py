import os
import sys
import re
import json
import time
import requests
import fitz  # PyMuPDF
import xlwings as xw

class BuilderLogger:
    """Centralized logging for the Submittal Builder system."""
    @staticmethod
    def log(message, category="SYSTEM"):
        timestamp = time.strftime("%H:%M:%S")
        prefix = f"[{category}]"
        print(f"{timestamp} {prefix:<10} {message}")
        sys.stdout.flush()

    @staticmethod
    def prompt(prompt_type, message):
        """Unified prompt handler for Local and Web environments."""
        if os.environ.get("HEADLESS_WORKER") == "TRUE":
            if prompt_type == "YN": return "Y"
            if prompt_type == "ENTER": return ""
            return ""

        if os.environ.get("RUNNING_FROM_WEB") == "TRUE":
            print(f"___PROMPT___|{prompt_type}|{message}")
            sys.stdout.flush()
            return sys.stdin.readline().strip()
        else:
            return input(f"\n{message} ").strip()

def call_gemini(api_key, prompt, data, model="gemini-2.0-flash", max_retries=3):
    """Shared Gemini API connector with retry logic."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    # Payload preparation
    if len(data) > 1000000:
        BuilderLogger.log(f"Truncating massive payload ({len(data)} chars)", "AI")
        data = data[:1000000]

    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n{data}"}]}],
        "generationConfig": {
            "temperature": 0.1, 
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                raw = response.json()['candidates'][0]['content']['parts'][0]['text']
                return raw.strip().removeprefix('```json').removesuffix('```').strip()
            
            BuilderLogger.log(f"API Error {response.status_code} (Attempt {attempt})", "AI")
            if attempt < max_retries: time.sleep(2)
        except Exception as e:
            BuilderLogger.log(f"Connection Error: {e}", "AI")
            if attempt < max_retries: time.sleep(2)
    
    return "{}"

def extract_pdf_text(pdf_path):
    """Safely extract text from a PDF file."""
    if not os.path.exists(pdf_path):
        return ""
    try:
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        return text
    except Exception as e:
        BuilderLogger.log(f"Error reading PDF {os.path.basename(pdf_path)}: {e}", "ERROR")
        return ""

def format_spec_number(raw_string):
    digits = re.sub(r'\D', '', str(raw_string))
    if len(digits) >= 6:
        return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"
    return raw_string

def format_title_case(text):
    if not text: return ""
    small_words = {'and', 'or', 'the', 'for', 'a', 'an', 'of', 'in', 'to', 'with', 'on', 'at', 'by', 'as'}
    words = text.lower().split()
    if not words: return ""
    result = [words[0].capitalize()]
    for word in words[1:]:
        result.append(word if word in small_words else word.capitalize())
    return ' '.join(result)

def save_pdf_safely(doc, output_path, max_attempts=5):
    """Saves a PDF with retries if the file is locked by another app."""
    for attempt in range(1, max_attempts + 1):
        try:
            doc.save(output_path)
            return True
        except Exception:
            BuilderLogger.log(f"File Locked: {os.path.basename(output_path)}. Close it in Bluebeam/Acrobat.", "WARNING")
            if os.environ.get("HEADLESS_WORKER") == "TRUE":
                 return False
            BuilderLogger.prompt("ENTER", "Press CONFIRM / PROCEED when ready:")
    return False

def get_workbook(path):
    """Connect to an Excel workbook safely."""
    try:
        return xw.Book(path)
    except Exception as e:
        BuilderLogger.log(f"Excel Connection Failed: {e}", "ERROR")
        return None

class BaseBuilder:
    """Helper class to encapsulate common builder operations."""
    def __init__(self, context, category_name, catalog_subfolder):
        self.context = context
        self.category = category_name
        self.wb = context['wb']
        self.api_key = context['api_key']
        self.config = context['project_config']
        self.job_info = context['job_info']
        
        user_home = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        self.catalog_folder = os.path.join(
            user_home, "Denier", "Denier Operations Playbook-Submittal Builder - Documents",
            "Submittal Builder", "Catalogs", catalog_subfolder
        )
        
        self.temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        self.index_pdf_path = os.path.join(self.temp_dir, f'{category_name}_Index.pdf')
        self.review_pdf_path = os.path.join(self.temp_dir, f'{category_name}_Review.pdf')

    def log(self, message, category=None):
        BuilderLogger.log(message, category or self.category.upper())

    def get_spec_path(self):
        return os.path.join(self.config["PROJECT_FOLDER"], self.config["SPEC_PDF_NAME"])

    def load_table(self, sheet_name, table_name):
        try:
            ws = self.wb.sheets[sheet_name]
            tbl = ws.tables[table_name]
            if tbl.data_body_range is None: return []
            headers = [str(h).strip() for h in tbl.header_row_range.value]
            data = tbl.data_body_range.value
            if not data: return []
            if not isinstance(data[0], list): data = [data]
            return [dict(zip(headers, row)) for row in data]
        except: return []

    def update_review_sheet(self, spec_num, submittal_title):
        try:
            ws = self.wb.sheets['Submittal for Review']
            # Coordinates from shared pattern
            ws.range('B5').value = f"Job #: {self.job_info['Job_Number']}"
            ws.range('B7').value = self.job_info['Job_Name']
            ws.range('B8').value = self.job_info['Address']
            ws.range('B9').value = self.job_info['City_State_Zip']
            ws.range('B11').value = f"Spec Section No: {spec_num}"
            ws.range('B15').value = f"Submittal Title: {submittal_title}"
            
            ws.api.ExportAsFixedFormat(0, self.review_pdf_path)
            return True
        except Exception as e:
            self.log(f"Review sheet update failed: {e}", "WARNING")
            return False

    def build_pdf_cache(self):
        cache = []
        if not os.path.exists(self.catalog_folder): return cache
        for d, _, files in os.walk(self.catalog_folder):
            for f in files:
                if f.lower().endswith('.pdf'):
                    cache.append({
                        'path': os.path.join(d, f),
                        'name_norm': f.upper().strip(), # Simple norm for now
                        'raw_name': f.lower()
                    })
        return cache
