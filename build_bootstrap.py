"""
Build the bootstrap installer as a standalone executable.
This creates a tiny .exe that users can run to download and install the full app.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Enforce UTF-8 encoding for both building and the final console outputs
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def build_bootstrap():
    """Build bootstrap installer executable"""
    print("=" * 70)
    print("Building Bootstrap Installer...")
    print("=" * 70)
    
    # Clean previous builds
    dist_dir = Path("dist_bootstrap")
    build_dir = Path("build_bootstrap")
    
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    # Build with PyInstaller - specify output directories
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "DenierAI_Installer",
        "--onefile",
        "--console",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
    ]
    
    # Add icon if it exists
    if Path("icon.ico").exists():
        cmd.extend(["--icon", "icon.ico"])
    
    # Add the main script
    cmd.append("bootstrap_installer.py")
    
    try:
        subprocess.check_call(cmd)
        
        # Copy to distribution folder
        output_dir = Path("dist")
        if not output_dir.exists():
            output_dir.mkdir()
        
        # Find the built executable (handles both Windows .exe and Linux binaries)
        built_exe = dist_dir / "DenierAI_Installer"
        if not built_exe.exists():
            built_exe = dist_dir / "DenierAI_Installer.exe"
        
        if built_exe.exists():
            shutil.copy(built_exe, output_dir / "Setup_DenierAI_Submittal_Builder.exe")
            print(f"\n✅ Bootstrap installer created: {output_dir / 'Setup_DenierAI_Submittal_Builder.exe'}")
            print("\n📤 DISTRIBUTION INSTRUCTIONS:")
            print("   Users only need to download this ONE file:")
            print("   → Setup_DenierAI_Submittal_Builder.exe")
            print("\n   When they run it:")
            print("   1. It checks for internet connection")
            print("   2. Downloads the latest version from your server")
            print("   3. Installs to Program Files")
            print("   4. Creates desktop shortcut")
            print("   5. Launches the application")
            print("\n   Future updates are handled automatically by the app!")
            return True
        else:
            print("❌ Built executable not found")
            print(f"   Searched in: {dist_dir}")
            print(f"   Files in dist_bootstrap: {list(dist_dir.glob('*')) if dist_dir.exists() else 'N/A'}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        return False

if __name__ == "__main__":
    build_bootstrap()
