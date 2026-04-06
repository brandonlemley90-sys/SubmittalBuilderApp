import os
import sys
import time
import json
import shutil
import subprocess
from pathlib import Path

# ==========================================
# CONFIGURATION 
# ==========================================
UPDATE_SERVER_URL = "https://github.com/brandonlemley90-sys/DenierSubmittalBuilderAgentUpdates.gits"

# Directory where the app will be installed
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA')) / "DenierAI_Submittal_Builder"
APP_NAME = "DenierAI Submittal Builder"

def run_application():
    """Launch the installed application"""
    print("\n🚀 Starting application...")
# ... the rest of your code continues here ...
def run_application():
    """Launch the installed application"""
    print("\n🚀 Starting application...")

    exe_files = list(INSTALL_DIR.glob("*.exe"))
    if not exe_files:
        print("❌ No executable found!")
        return False

    exe_path = exe_files[0]

    try:
        # The Security Buffer: Give Antivirus 3 seconds to finish scanning the new file
        print("⏳ Waiting for Windows Security checks to complete...")
        time.sleep(3)

        # Use os.startfile on Windows (much more reliable for launching UI apps than Popen)
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
