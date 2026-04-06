"""
Auto-updater module for DenierAI Submittal Builder
Checks for updates and downloads new versions automatically
"""
import os
import sys
import json
import hashlib
import shutil
import threading
import time
import re
import subprocess
from pathlib import Path
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

# ---------------------------------------------------------
# CONFIGURATION - Pointing to your GitHub Pages Repo
# ---------------------------------------------------------
UPDATE_SERVER_URL = "https://github.com/brandonlemley90-sys/DenierSubmittalBuilderAgentUpdates.git" 
CURRENT_VERSION = "1.0.0"
VERSION_FILE = "version.json"
APP_NAME = "DenierAI_Submittal_Builder"
# ---------------------------------------------------------

def get_app_directory():
    """Get the application directory"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.absolute()

def get_current_version():
    """Read current version from version file"""
    app_dir = get_app_directory()
    version_path = app_dir / VERSION_FILE
    
    if version_path.exists():
        try:
            with open(version_path, 'r') as f:
                data = json.load(f)
                return data.get('version', CURRENT_VERSION)
        except:
            pass
    return CURRENT_VERSION

def check_for_updates():
    """Check if a new version is available"""
    try:
        # Download version info from server
        version_url = f"{UPDATE_SERVER_URL}/version.json"
        with urlopen(version_url, timeout=10) as response:
            latest_version_info = json.loads(response.read().decode())
            
        latest_version = latest_version_info.get('version', CURRENT_VERSION)
        
        # Compare versions
        if version_compare(latest_version, get_current_version()) > 0:
            return {
                'available': True,
                'version': latest_version,
                'release_notes': latest_version_info.get('release_notes', ''),
                'download_url': latest_version_info.get('download_url', ''),
                'file_hash': latest_version_info.get('file_hash', '')
            }
        return {'available': False}
        
    except URLError as e:
        print(f"Could not check for updates: {e}")
        return {'available': False, 'error': str(e)}
    except Exception as e:
        print(f"Update check failed: {e}")
        return {'available': False, 'error': str(e)}

def version_compare(v1, v2):
    """Compare two version strings. Returns: 1 if v1>v2, -1 if v1<v2, 0 if equal"""
    def normalize(v):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', v).split(".")]
    
    parts1 = normalize(v1)
    parts2 = normalize(v2)
    
    while len(parts1) < len(parts2):
        parts1.append(0)
    while len(parts2) < len(parts1):
        parts2.append(0)
    
    for i in range(len(parts1)):
        if parts1[i] > parts2[i]:
            return 1
        elif parts1[i] < parts2[i]:
            return -1
    return 0

def download_update(download_url, callback=None):
    """Download the update file"""
    app_dir = get_app_directory()
    update_file = app_dir / "update_package.zip"
    
    try:
        def report_progress(block_num, block_size, total_size):
            if callback:
                downloaded = block_num * block_size
                percent = min(downloaded * 100 / total_size, 100)
                callback(percent)
        
        urlretrieve(download_url, update_file, reporthook=report_progress)
        return update_file
    except Exception as e:
        print(f"Download failed: {e}")
        raise

def verify_file_hash(file_path, expected_hash):
    """Verify downloaded file integrity"""
    if not expected_hash:
        return True # Safely bypass if no hash is provided in version.json
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest() == expected_hash

def install_update(update_package, callback=None):
    """Install the update using a batch script to avoid Windows file locks"""
    import zipfile
    
    app_dir = get_app_directory()
    temp_dir = app_dir / "temp_update"
    
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        
        if callback:
            callback("Extracting update...", 50)
        
        with zipfile.ZipFile(update_package, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        if callback:
            callback("Preparing installation script...", 85)
            
        # Determine the name of the main executable
        exe_name = Path(sys.executable).name if getattr(sys, 'frozen', False) else "main.py"
        
        # Create a batch script to handle the overwrite after the app closes
        bat_path = app_dir / "apply_update.bat"
        bat_content = f"""@echo off
echo Updating {APP_NAME}... Please wait.
timeout /t 2 /nobreak > nul
xcopy /y /s /e /q "{temp_dir}\\*" "{app_dir}\\"
rmdir /s /q "{temp_dir}"
del "{update_package}"
start "" "{app_dir}\\{exe_name}"
del "%~f0"
"""
        with open(bat_path, "w") as f:
            f.write(bat_content)
            
        return bat_path
        
    except Exception as e:
        print(f"Extraction failed: {e}")
        raise

def restart_application(bat_path):
    """Launch the batch script and kill the current process"""
    # Launch the bat file detached from the current process
    subprocess.Popen([str(bat_path)], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
    sys.exit(0) # Immediately kill the Python app so the bat file can overwrite it

class AutoUpdater:
    """Main auto-updater class for integration with the app"""
    
    def __init__(self, parent_window=None):
        self.parent = parent_window
        self.update_available = False
        self.update_info = None
    
    def check_updates(self, callback=None):
        """Check for updates and call callback with results"""
        def _check():
            self.update_info = check_for_updates()
            self.update_available = self.update_info.get('available', False)
            if callback:
                callback(self.update_available, self.update_info)
        
        threading.Thread(target=_check, daemon=True).start()
    
    def download_and_install(self, progress_callback=None):
        """Download and install update"""
        if not self.update_info or not self.update_info.get('download_url'):
            return False
        
        def _install():
            try:
                update_file = download_update(
                    self.update_info['download_url'],
                    lambda pct: progress_callback("Downloading", pct) if progress_callback else None
                )
                
                if not verify_file_hash(update_file, self.update_info.get('file_hash')):
                    raise Exception("File hash verification failed")
                
                # Returns the path to the batch script
                bat_path = install_update(
                    update_file,
                    lambda msg, pct: progress_callback(msg, pct) if progress_callback else None
                )
                
                if progress_callback:
                    progress_callback("Restarting to apply updates...", 100)
                time.sleep(1)
                
                # Execute batch script and self-terminate
                restart_application(bat_path)
                
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error: {str(e)}", 0)
                raise
        
        threading.Thread(target=_install, daemon=True).start()
        return True

if __name__ == "__main__":
    print(f"Current version: {get_current_version()}")
    print("Checking for updates...")
    result = check_for_updates()
    print(f"Update available: {result.get('available', False)}")
    if result.get('available'):
        print(f"Latest version: {result.get('version')}")
        print(f"Release notes: {result.get('release_notes')}")
