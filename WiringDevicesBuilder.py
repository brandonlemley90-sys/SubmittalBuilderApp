import os
import re
import json
import datetime
import fitz
import builder_shared as shared

# =============================================================================
# WIRING DEVICES BUILDER
# =============================================================================

class WiringDevicesBuilder(shared.BaseBuilder):
    def __init__(self, context):
        super().__init__(context, "Wiring Devices", "Wiring Devices")
        self.reference_dict = {}
        self.db_for_prompt = []

    def run(self):
        self.log("Starting Wiring Devices Builder...")
        
        # 1. Load Master List
        self.load_master_device_list()
        
        # 2. Extract Specs
        spec_path = self.get_spec_path()
        full_spec_text = shared.extract_pdf_text(spec_path)
        drawing_path = os.path.join(self.config["PROJECT_FOLDER"], self.config["DRAWINGS_PDF_NAME"])
        drawing_text = shared.extract_pdf_text(drawing_path)
        
        wiring_spec_text = self.extract_wiring_devices_section(full_spec_text)
        
        # 3. Update Excel Header & Review Sheet
        spec_title = self.get_spec_header(wiring_spec_text)
        spec_num_match = re.search(r'(\d{2}\s*\d{2}\s*\d{2})', spec_title)
        spec_num = spec_num_match.group(1) if spec_num_match else "N/A"
        
        self.update_review_sheet(spec_num, "Wiring Devices")
        
        # 4. AI Analysis
        self.log("Analyzing with Gemini...", "AI")
        prompt = self.build_prompt()
        combined_data = f"--- SPECS ---\n{wiring_spec_text}\n\n--- DRAWINGS ---\n{drawing_text}"
        
        analysis_data = shared.call_gemini(self.api_key, prompt, combined_data)
        try:
            items_to_process = json.loads(analysis_data)
        except:
            self.log("AI returned invalid JSON.", "ERROR")
            return False

        # 5. Matching & Writing
        pdf_cache = self.build_pdf_cache_enhanced()
        embedded_paths = []
        current_row = 8
        ws_index = self.wb.sheets['Wiring Device Index']
        
        for item in items_to_process:
            cat_raw = item.get('Catalog Number', '')
            if cat_raw == "UNMATCHED": continue
            if cat_raw == "IN-USE-PROMPT":
                # Logic for interactive prompt if needed, but in modular mode we might automate
                continue

            cat_clean = cat_raw.strip().lower()
            if cat_clean in self.reference_dict:
                matched = self.reference_dict[cat_clean]
                # Match PDF
                paths = self.match_pdfs(matched, pdf_cache)
                for p in paths:
                    if p not in embedded_paths: embedded_paths.append(p)
                
                # Write to Excel
                ws_index.range(f'A{current_row}').value = matched['Catalog Number']
                ws_index.range(f'B{current_row}').value = matched['Brand']
                ws_index.range(f'C{current_row}').value = matched['Device Description']
                current_row += 1

        # 6. Finalize
        if embedded_paths:
            self.log(f"Embedding {len(embedded_paths)} PDFs...")
            # Use original embed logic or simplify
            
        self.log("Wiring Devices Builder Complete.", "SUCCESS")
        return True

    def load_master_device_list(self):
        ws_list = self.wb.sheets['Wiring Devices List']
        data = ws_list.used_range.value
        # (Simplified logic to populate self.reference_dict and self.db_for_prompt)
        # Assuming headers are at row 1 for now or find them
        for row in data[1:]:
             if row and row[0]:
                 cat = str(row[0]).strip()
                 self.reference_dict[cat.lower()] = {
                     'Catalog Number': cat,
                     'Brand': row[1] if len(row) > 1 else '',
                     'Device Description': row[2] if len(row) > 2 else ''
                 }
                 self.db_for_prompt.append(self.reference_dict[cat.lower()])

    def extract_wiring_devices_section(self, text):
        # Original regex patterns
        patterns = [r'SECTION\s+26\s*27\s*26', r'WIRING\s+DEVICES']
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m: return text[m.start():m.start()+50000]
        return text[:20000]

    def get_spec_header(self, text):
        match = re.search(r'SECTION\s+(\d{2}\s*\d{2}\s*\d{2}[^\n]+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else "26 27 26 - WIRING DEVICES"

    def match_pdfs(self, matched, cache):
        # Implementation of best_pdfs_for_row logic
        return [] # Placeholder

    def build_pdf_cache_enhanced(self):
        # Original build_pdf_cache with normalization
        return super().build_pdf_cache()

    def build_prompt(self):
        # Original my_smart_prompt string
        return "..." # Placeholder for length

def run(context):
    builder = WiringDevicesBuilder(context)
    return builder.run()