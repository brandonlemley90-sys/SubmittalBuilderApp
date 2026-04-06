"""
Auto-updater module for DenierAI Submittal Builder
Checks for updates and downloads new versions automatically
"""
import os
import sys
import json
import hashlib
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

# Configuration - Update these values in your release server
UPDATE_SERVER_URL = "https://your-server.com/updates"  # Replace with your actual server
CURRENT_VERSION = "1.0.0"
VERSION_FILE = "version.json"
APP_NAME = "DenierAI_Submittal_Builder"


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
    
    import re
    parts1 = normalize(v1)
    parts2 = normalize(v2)
    
    # Pad shorter version with zeros
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
        return True
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest() == expected_hash


def install_update(update_package, callback=None):
    """Install the update by extracting and replacing files"""
    import zipfile
    
    app_dir = get_app_directory()
    temp_dir = app_dir / "temp_update"
    backup_dir = app_dir / "backup_old"
    
    try:
        # Create temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        
        # Extract update package
        if callback:
            callback("Extracting update...", 50)
        
        with zipfile.ZipFile(update_package, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Backup current version
        if callback:
            callback("Backing up current version...", 70)
        
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        
        # Move current files to backup (except the updater itself)
        files_to_move = [f for f in app_dir.iterdir() 
                        if f.name not in ['temp_update', 'backup_old', 'update_package.zip']]
        
        for file in files_to_move:
            if file.is_file() or file.is_dir():
                shutil.move(str(file), str(backup_dir / file.name))
        
        # Move new files
        if callback:
            callback("Installing new version...", 85)
        
        for file in temp_dir.iterdir():
            shutil.move(str(file), str(app_dir / file.name))
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        if callback:
            callback("Update complete!", 100)
        
        return True
        
    except Exception as e:
        print(f"Installation failed: {e}")
        # Restore from backup if installation fails
        if backup_dir.exists():
            for file in backup_dir.iterdir():
                shutil.move(str(file), str(app_dir / file.name))
        raise


def restart_application():
    """Restart the application after update"""
    app_dir = get_app_directory()
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    
    # Clean up backup after successful restart
    backup_dir = app_dir / "backup_old"
    if backup_dir.exists():
        threading.Thread(target=lambda: (time.sleep(5), shutil.rmtree(backup_dir))).start()
    
    # Restart
    os.execl(exe_path, exe_path, *sys.argv[1:])


def auto_update_check(on_update_available=None, on_download_progress=None):
    """Background thread to check and optionally download updates"""
    update_info = check_for_updates()
    
    if update_info.get('available'):
        if on_update_available:
            on_update_available(update_info)
    else:
        print("Application is up to date.")


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
                # Download
                update_file = download_update(
                    self.update_info['download_url'],
                    lambda pct: progress_callback("Downloading", pct) if progress_callback else None
                )
                
                # Verify
                if not verify_file_hash(update_file, self.update_info.get('file_hash')):
                    raise Exception("File hash verification failed")
                
                # Install
                install_update(
                    update_file,
                    lambda msg, pct: progress_callback(msg, pct) if progress_callback else None
                )
                
                # Clean up download
                update_file.unlink()
                
                # Restart
                if progress_callback:
                    progress_callback("Restarting...", 100)
                time.sleep(2)
                restart_application()
                
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error: {str(e)}", 0)
                raise
        
        threading.Thread(target=_install, daemon=True).start()
        return True


if __name__ == "__main__":
    # Test the updater
    print(f"Current version: {get_current_version()}")
    print("Checking for updates...")
    result = check_for_updates()
    print(f"Update available: {result.get('available', False)}")
    if result.get('available'):
        print(f"Latest version: {result.get('version')}")
        print(f"Release notes: {result.get('release_notes')}")
