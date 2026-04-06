"""
Simple Update Server for DenierAI Submittal Builder
This is an example server to host your application updates.
You can deploy this on any web server or use alternatives like AWS S3.

Usage:
    python update_server.py
    
Then upload your build files to the 'updates' folder.
"""
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver

PORT = 8080
UPDATES_DIR = "updates"

# Ensure updates directory exists
if not os.path.exists(UPDATES_DIR):
    os.makedirs(UPDATES_DIR)
    print(f"Created updates directory: {UPDATES_DIR}")
    print("Please place your build files here:")
    print("  - DenierAI_Submittal_Builder_v1.0.0.zip")
    print("  - version.json")


class UpdateServerHandler(SimpleHTTPRequestHandler):
    """Custom handler for serving updates with proper CORS headers"""
    
    def end_headers(self):
        # Add CORS headers to allow cross-origin requests from the app
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        # Handle preflight CORS requests
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        # Log the request
        print(f"[{self.command}] {self.path} from {self.client_address[0]}")
        
        # Serve version.json with proper content type
        if self.path.endswith('/version.json') or self.path == '/version.json':
            self.path = f'{UPDATES_DIR}/version.json'
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                with open(self.path, 'rb') as f:
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.send_error(404, "version.json not found")
            return
        
        # Serve ZIP files
        if self.path.endswith('.zip'):
            zip_path = f"{UPDATES_DIR}{self.path}"
            if os.path.exists(zip_path):
                self.path = zip_path
                self.send_response(200)
                self.send_header('Content-type', 'application/zip')
                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(self.path)}"')
                self.end_headers()
                
                with open(self.path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "ZIP file not found")
                return
        
        # Default handling
        super().do_GET()


def create_sample_version_file():
    """Create a sample version.json file for testing"""
    sample_version = {
        "version": "1.0.0",
        "release_notes": "Initial release with auto-update functionality",
        "download_url": f"http://localhost:{PORT}/DenierAI_Submittal_Builder_v1.0.0.zip",
        "file_hash": "placeholder_hash_update_after_build",
        "release_date": "2024-01-01"
    }
    
    version_path = os.path.join(UPDATES_DIR, "version.json")
    if not os.path.exists(version_path):
        with open(version_path, 'w') as f:
            json.dump(sample_version, f, indent=2)
        print(f"\nCreated sample version.json in {UPDATES_DIR}/")
        print("⚠️  Remember to update the file_hash and download_url after building!")


if __name__ == "__main__":
    print("=" * 60)
    print("DenierAI Update Server")
    print("=" * 60)
    print()
    
    create_sample_version_file()
    
    print(f"Serving updates on port {PORT}")
    print(f"Updates directory: {os.path.abspath(UPDATES_DIR)}")
    print()
    print("Available endpoints:")
    print(f"  - http://localhost:{PORT}/version.json")
    print(f"  - http://localhost:{PORT}/DenierAI_Submittal_Builder_v1.0.0.zip")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    with socketserver.TCPServer(("", PORT), UpdateServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")
