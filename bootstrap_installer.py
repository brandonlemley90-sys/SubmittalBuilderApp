"""
Bootstrap Installer for DenierAI Submittal Builder
This is a lightweight installer that downloads and installs the full application.
Users only need to run this once - it handles downloading, installing, and updating.
"""
import os
import sys
import json
import hashlib
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

# ---------------------------------------------------------
# CONFIGURATION - Pointing to your GitHub Pages Repo
# ---------------------------------------------------------
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderAgentUpdates"
APP_NAME = "DenierAI_Submittal_Builder"

# CRITICAL FIX: Use LOCALAPPDATA so the auto-updater has permission to overwrite files later
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA')) / APP_NAME
# ---------------------------------------------------------

def get_bootstrap_version():
    """Return the bootstrap version"""
    return "1.0.0"

def check_internet_connection():
    """Check if we have internet access"""
    try:
        urlopen("https://www.google.com", timeout=5)
        return True
    except:
        return False

def download_file(url, dest_path, callback=None):
    """Download a file with progress tracking"""
    try:
        def report_progress(block_num, block_size, total_size):
            if callback:
                downloaded = block_num * block_size
                percent = min(downloaded * 100 / total_size, 100)
                callback(percent)
        
        urlretrieve(url, dest_path, reporthook=report_progress)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def verify_file_hash(file_path, expected_hash):
    """Verify downloaded file integrity"""
    if not expected_hash:
        return True
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest() == expected_hash

def get_latest_version_info():
    """Fetch the latest version information from server"""
    try:
        version_url = f"{UPDATE_SERVER_URL}/version.json"
        with urlopen(version_url, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Failed to fetch version info: {e}")
        return None

def install_app(progress_callback=None):
    """Download and install the application"""
    print("\n📥 Fetching latest version information...")
    
    # Get version info
    version_info = get_latest_version_info()
    if not version_info:
        print("❌ Could not retrieve version information from server.")
        print(f"   Please check your internet connection and server URL: {UPDATE_SERVER_URL}")
        return False
    
    latest_version = version_info.get('version', 'unknown')
    download_url = version_info.get('download_url', '')
    file_hash = version_info.get('file_hash', '')
    
    print(f"✅ Found version: {latest_version}")
    
    if not download_url:
        print("❌ No download URL available in version info")
        return False
    
    # Create installation directory
    print(f"\n📁 Creating installation directory: {INSTALL_DIR}")
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Download the application package
    temp_zip = INSTALL_DIR / "app_package.zip"
    print(f"\n⬇️  Downloading application ({latest_version})...")
    
    def download_progress(percent):
        if progress_callback:
            progress_callback("Downloading", percent)
        else:
            print(f"   Progress: {percent:.1f}%", end='\r')
    
    if not download_file(download_url, temp_zip, download_progress):
        print("\n❌ Download failed!")
        return False
    
    print("\n✅ Download complete!          ") # Extra spaces to clear progress line
    
    # Verify file integrity
    print("\n🔒 Verifying file integrity...")
    if not verify_file_hash(temp_zip, file_hash):
        print("❌ File verification failed! Download may be corrupted.")
        temp_zip.unlink()
        return False
    print("✅ Verification successful!")
    
    # Extract the package
    print("\n📦 Extracting application...")
    import zipfile
    
    try:
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(INSTALL_DIR)
        
        # Clean up temp zip
        temp_zip.unlink()
        
        print("✅ Extraction complete!")
        
        # Create version file locally so the auto-updater knows what version it is
        version_file = INSTALL_DIR / "version.json"
        with open(version_file, 'w') as f:
            json.dump({
                'version': latest_version,
                'installed_by': 'bootstrap_installer',
                'installer_version': get_bootstrap_version()
            }, f, indent=2)
        
        return True
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return False

def create_shortcut():
    """Create desktop shortcut"""
    print("\n🔗 Creating desktop shortcut...")
    
    try:
        # Assuming your compiled app in the zip is named main.exe, you might want to hardcode this 
        # instead of searching for the first .exe it finds. But this works for now.
        exe_files = list(INSTALL_DIR.glob("*.exe"))
        if not exe_files:
            print("⚠️  No executable found in the downloaded package, skipping shortcut creation")
            return False
        
        exe_path = exe_files[0]
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / f"{APP_NAME}.lnk"
        
        # Use PowerShell to create shortcut
        ps_command = f"""
        $WShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WShell.CreateShortcut('{shortcut_path}')
        $Shortcut.TargetPath = '{exe_path}'
        $Shortcut.WorkingDirectory = '{INSTALL_DIR}'
        $Shortcut.Description = 'DenierAI Submittal Builder'
        $Shortcut.Save()
        """
        
        subprocess.run(['powershell', '-Command', ps_command], 
                      capture_output=True, text=True)
        
        if shortcut_path.exists():
            print(f"✅ Shortcut created: {shortcut_path}")
            return True
        else:
            print("⚠️  Could not create shortcut")
            return False
            
    except Exception as e:
        print(f"⚠️  Shortcut creation failed: {e}")
        return False

def run_application():
    """Launch the installed application"""
    print("\n🚀 Starting application...")
    
    exe_files = list(INSTALL_DIR.glob("*.exe"))
    if not exe_files:
        print("❌ No executable found!")
        return False
    
    exe_path = exe_files[0]
    
    try:
        subprocess.Popen([str(exe_path)])
        print("✅ Application started!")
        return True
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        return False

def check_existing_installation():
    """Check if app is already installed"""
    if INSTALL_DIR.exists():
        version_file = INSTALL_DIR / "version.json"
        if version_file.exists():
            with open(version_file, 'r') as f:
                data = json.load(f)
                return data.get('version', 'unknown')
        return "installed (unknown version)"
    return None

def main():
    """Main installer routine"""
    print("=" * 70)
    print(f"  {APP_NAME} Bootstrap Installer")
    print(f"  Version: {get_bootstrap_version()}")
    print("=" * 70)
    
    # Check internet connection
    print("\n🌐 Checking internet connection...")
    if not check_internet_connection():
        print("❌ No internet connection detected!")
        print("   Please connect to the internet and run this installer again.")
        input("\nPress Enter to exit...")
        return False
    
    print("✅ Internet connection OK")
    
    # Check for existing installation
    existing_version = check_existing_installation()
    if existing_version:
        print(f"\n⚠️  Existing installation detected: {existing_version}")
        print("\nOptions:")
        print("  1. Reinstall/Update (recommended)")
        print("  2. Cancel")
        
        choice = input("\nChoose option (1/2): ").strip()
        if choice != '1':
            print("Installation cancelled.")
            input("\nPress Enter to exit...")
            return False
        
        print("\nRemoving old installation...")
        try:
            shutil.rmtree(INSTALL_DIR)
            print("✅ Old installation removed")
        except Exception as e:
            print(f"⚠️  Could not remove old installation: {e}")
            print("   Make sure the application is closed before reinstalling.")
            input("\nPress Enter to exit...")
            return False
    
    # Install the application
    print("\n" + "=" * 70)
    if not install_app():
        print("\n❌ Installation failed!")
        input("\nPress Enter to exit...")
        return False
    
    # Create shortcut
    create_shortcut()
    
    # Final summary
    print("\n" + "=" * 70)
    print("  ✅ INSTALLATION COMPLETE!")
    print("=" * 70)
    print(f"\n  Installation directory: {INSTALL_DIR}")
    print(f"  Desktop shortcut created")
    print("\n  The application will now start.")
    print(f"  In the future, you can launch it from:")
    print(f"    - Desktop shortcut")
    print(f"    - Directly from: {INSTALL_DIR}")
    print("\n  The app will automatically check for updates when launched!")
    print("=" * 70)
    
    # Ask if user wants to run now
    print("\n🚀 Launch application now?")
    choice = input("   Press Enter to launch, or type 'n' to cancel: ").strip().lower()
    
    if choice != 'n':
        run_application()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
