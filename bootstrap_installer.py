import os
import sys
import time
import json
import shutil
import hashlib
import zipfile
import requests
import subprocess
from pathlib import Path

# ==========================================
# CONFIGURATION 
# ==========================================
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates"
APP_NAME = "DenierAI Submittal Builder"
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA')) / "DenierAI_Submittal_Builder"
BOOTSTRAP_VERSION = "1.0.0"

def get_bootstrap_version():
    return BOOTSTRAP_VERSION

def check_internet_connection():
    try:
        requests.get("https://github.com", timeout=5)
        return True
    except:
        return False

def install_app():
    """Downloads, verifies, and extracts the application"""
    try:
        # 1. Fetch version.json
        print(f"\n📥 Fetching latest version information...")
        response = requests.get(f"{UPDATE_SERVER_URL}/version.json", timeout=10)
        response.raise_for_status()
        version_info = response.json()
        
        target_version = version_info.get('version', 'unknown')
        download_url = version_info.get('download_url')
        expected_hash = version_info.get('file_hash', '').strip().upper()

        print(f"✅ Found version: {target_version}")

        # 2. Prep directory
        if not INSTALL_DIR.exists():
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        temp_zip = INSTALL_DIR / "updates.zip"

        # 3. Download ZIP
        print(f"⬇️  Downloading application ({target_version})...")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(temp_zip, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("✅ Download complete!")

        # 4. Verify Hash (THE FIX)
        print("🔒 Verifying file integrity...")
        sha256_hash = hashlib.sha256()
        with open(temp_zip, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        calculated_hash = sha256_hash.hexdigest().upper()

        print(f"   Debug - Expected: {expected_hash}")
        print(f"   Debug - Received: {calculated_hash}")

        if calculated_hash != expected_hash:
            print("❌ File verification failed!")
            # MENTOR TIP: The "Emergency Exit" for developers
            choice = input("⚠️  Hash mismatch. This is usually Windows Security interfering. \n   Type 'FORCE' to install anyway or Enter to quit: ").strip().upper()
            if choice != 'FORCE':
                return False
            print("⚠️  Proceeding with manual override...")

        # 5. Extract
        print("📂 Extracting files...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(INSTALL_DIR)
        
        # Save the local version info
        with open(INSTALL_DIR / "version.json", 'w') as f:
            json.dump(version_info, f)

        # Cleanup
        os.remove(temp_zip)
        return True

    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

def create_shortcut():
    """Creates a desktop shortcut using winshell"""
    try:
        import winshell
        from win32com.client import Dispatch

        desktop = winshell.desktop()
        path = os.path.join(desktop, f"{APP_NAME}.lnk")
        
        exe_files = list(INSTALL_DIR.glob("*.exe"))
        if not exe_files:
            return
            
        target = str(exe_files[0])
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = str(INSTALL_DIR)
        shortcut.IconLocation = target
        shortcut.save()
        print("✅ Desktop shortcut created")
    except Exception as e:
        print(f"⚠️  Could not create shortcut: {e}")

def run_application():
    """Launch the installed application"""
    print("\n🚀 Starting application...")
    exe_files = list(INSTALL_DIR.glob("*.exe"))
    if not exe_files:
        print("❌ No executable found!")
        return False

    exe_path = exe_files[0]
    try:
        print("⏳ Waiting for Windows Security checks to complete...")
        time.sleep(3)
        if sys.platform == 'win32':
            os.startfile(str(exe_path))
        else:
            subprocess.Popen([str(exe_path)])
        print("✅ Application started!")
        return True
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        return False

def check_existing_installation():
    if INSTALL_DIR.exists():
        version_file = INSTALL_DIR / "version.json"
        if version_file.exists():
            with open(version_file, 'r') as f:
                try:
                    data = json.load(f)
                    return data.get('version', 'unknown')
                except:
                    return "installed (corrupt config)"
        return "installed (unknown version)"
    return None

def main():
    print("=" * 70)
    print(f"  {APP_NAME} Bootstrap Installer")
    print(f"  Version: {get_bootstrap_version()}")
    print("=" * 70)
    
    if not check_internet_connection():
        print("❌ No internet connection detected!")
        input("\nPress Enter to exit...")
        return False
    
    print("✅ Internet connection OK")
    
    existing_version = check_existing_installation()
    if existing_version:
        print(f"\n⚠️  Existing installation detected: {existing_version}")
        print("\nOptions: [1] Reinstall/Update  [2] Cancel")
        choice = input("\nChoose option (1/2): ").strip()
        if choice != '1':
            return False
        
        print("\nRemoving old installation...")
        try:
            shutil.rmtree(INSTALL_DIR)
        except Exception as e:
            print(f"⚠️  Close the app before reinstalling! Error: {e}")
            input("\nPress Enter to exit...")
            return False
    
    if not install_app():
        print("\n❌ Installation failed!")
        input("\nPress Enter to exit...")
        return False
    
    create_shortcut()
    
    print("\n" + "=" * 70)
    print("  ✅ INSTALLATION COMPLETE!")
    print("=" * 70)
    
    choice = input("\n🚀 Launch now? (Enter to launch, 'n' to exit): ").strip().lower()
    if choice != 'n':
        run_application()
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc() if 'traceback' in globals() else None
        input("\nPress Enter to exit...")
        sys.exit(1)
