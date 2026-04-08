"""
Build script to create a distributable executable with auto-update capability
Run this script to build the application for distribution
"""
import os
import sys
import shutil
import subprocess
import zipfile
import hashlib
import json
from pathlib import Path
from datetime import date

# ================================================================
# CONFIGURATION — Edit these two values before each build
# ================================================================
APP_NAME = "DenierAI_Submittal_Builder"
VERSION = "1.0.3"          # ← Increment this before each build
RELEASE_NOTES = "Update copyright attributions to Brandon Lemley and fix updater download paths."  # ← Describe what changed
UPDATE_REPO_BASE_URL = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates"  # ← GitHub Pages URL (no trailing slash)
# ================================================================
OUTPUT_DIR = Path("dist")
BUILD_DIR = Path("build")


def clean_build_directories():
    """Clean previous build artifacts"""
    print("🧹 Cleaning build directories...")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if Path("update_package.zip").exists():
        Path("update_package.zip").unlink()


def install_dependencies():
    """Ensure all required packages are installed"""
    print("📦 Installing dependencies...")
    requirements = [
        "flask",
        "pyinstaller",
        "werkzeug"
    ]

    for package in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not install {package}: {e}")


def build_executable():
    """Build the executable using PyInstaller"""
    print("🔨 Building executable...")

    if sys.platform == 'win32':
        data_sep = ';'
    else:
        data_sep = ':'

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        f"--add-data=templates{data_sep}templates",
        f"--add-data=static{data_sep}static",
        "--hidden-import", "tkinter",
        "--hidden-import", "flask",
        "--hidden-import", "werkzeug.security",
    ]

    if Path("icon.ico").exists():
        cmd.extend(["--icon", "icon.ico"])

    if Path("version.txt").exists():
        cmd.extend(["--version-file", "version.txt"])

    cmd.append("app.py")

    try:
        subprocess.check_call(cmd)
        print("✅ Executable built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        return False


def create_version_file():
    """Create version information file"""
    print("📝 Creating version file...")

    version_info = {
        "version": VERSION,
        "release_notes": RELEASE_NOTES,
        "build_date": "2026"
    }

    with open(OUTPUT_DIR / "version.json", 'w') as f:
        json.dump(version_info, f, indent=2)

    print(f"✅ Version file created: {VERSION}")


def create_update_package():
    """Create a zip package for distribution and updates"""
    print("📦 Creating update package...")

    exe_path = OUTPUT_DIR / f"{APP_NAME}.exe" if sys.platform == 'win32' else OUTPUT_DIR / APP_NAME

    if not exe_path.exists():
        print("❌ Executable not found! Build first.")
        return False

    package_dir = OUTPUT_DIR / "package_contents"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()

    shutil.copy(exe_path, package_dir / f"{APP_NAME}.exe")

    supporting_files = ['version.json']
    for file in supporting_files:
        src = OUTPUT_DIR / file
        if src.exists():
            shutil.copy(src, package_dir / file)

    zip_path = OUTPUT_DIR / f"{APP_NAME}_v{VERSION}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in package_dir.rglob('*'):
            if file.is_file():
                arcname = file.relative_to(package_dir)
                zipf.write(file, arcname)

    sha256_hash = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    file_hash = sha256_hash.hexdigest()

    shutil.rmtree(package_dir)

    print(f"✅ Update package created: {zip_path.name}")
    print(f"   SHA256: {file_hash}")

    # Build server_version_template.json from top-level constants — no hardcoded strings
    today = date.today().isoformat()  # e.g. "2026-04-08"
    server_version_info = {
        "version": VERSION,
        "release_notes": f"Version {VERSION} - {RELEASE_NOTES}",
        "download_url": f"{UPDATE_REPO_BASE_URL}/{APP_NAME}_v{VERSION}.zip",
        "file_hash": file_hash,
        "release_date": today
    }

    with open(OUTPUT_DIR / "server_version_template.json", 'w') as f:
        json.dump(server_version_info, f, indent=2)

    # Also update the local version.json so the source repo stays in sync
    with open("version.json", 'w') as f:
        json.dump(server_version_info, f, indent=2)
    print("✅ version.json (local) updated")

    print("✅ Server version template created")

    return True


def create_installer_script():
    """Create a simple installer batch script for Windows"""
    print("📜 Creating installer script...")

    installer_content = f'''@echo off
echo ========================================
echo {APP_NAME} Installer
echo Version {VERSION}
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run as Administrator
    pause
    exit /b
)

REM Set installation directory
set INSTALL_DIR=%PROGRAMFILES%\\{APP_NAME}

echo Installing to %INSTALL_DIR%
echo.

REM Create installation directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Extract files (assuming this is run from the extracted zip)
echo Copying files...
xcopy /E /Y /Q "%~dp0*" "%INSTALL_DIR%\\"

REM Create shortcut
echo Creating desktop shortcut...
powershell "$WShell = New-Object -ComObject WScript.Shell; $Shortcut = $WShell.CreateShortcut('%USERPROFILE%\\Desktop\\{APP_NAME}.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\\{APP_NAME}.exe'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Save()"

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo You can now run {APP_NAME} from your desktop.
echo.
pause
'''

    installer_path = OUTPUT_DIR / "install.bat"
    with open(installer_path, 'w') as f:
        f.write(installer_content)

    print(f"✅ Installer script created: {installer_path.name}")


def create_readme():
    """Create README with installation and update instructions"""
    print("📖 Creating README...")

    readme_content = f'''# {APP_NAME} v{VERSION}

## Release Notes

{RELEASE_NOTES}

## Installation Instructions

### For End Users:

1. Download the ZIP file: `{APP_NAME}_v{VERSION}.zip`
2. Extract the contents to a folder
3. Run `install.bat` as Administrator
4. A shortcut will be created on your desktop

### Manual Installation:

1. Download and extract the ZIP file
2. Copy all files to your desired installation folder (e.g., `C:\\Program Files\\{APP_NAME}`)
3. Create a shortcut to `{APP_NAME}.exe` on your desktop

## Auto-Update Feature

This application includes automatic update functionality:

1. When you start the app, it will check for updates automatically
2. If an update is available, you'll be prompted to download and install it
3. The update will download in the background and install automatically
4. The application will restart with the new version

### How Updates Work:

- The app checks a central server for new versions
- Updates are downloaded securely with hash verification
- Your settings and data are preserved during updates
- Failed updates automatically roll back to the previous version

## Requirements

- Windows 10 or later
- Internet connection (for initial setup and updates)
- Python 3.8+ (only if running from source)

## Running from Source (Developers)

If you want to run the application without building:

```bash
# Install dependencies
pip install flask werkzeug pyinstaller

# Run the application
python app.py
```

## For Administrators/Deployers

To set up the update server:

1. Host the ZIP file on a web server
2. Host the `server_version_template.json` file (rename to `version.json`)
3. Update the `UPDATE_SERVER_URL` in `auto_updater.py` before building
4. Distribute the built application to users

## Troubleshooting

### App won't start:
- Make sure you have administrator privileges
- Check if Windows Defender is blocking the app
- Try running as Administrator

### Updates failing:
- Check your internet connection
- Make sure your firewall allows the app
- Contact support if the problem persists

## Support

For issues or questions, please contact your system administrator.

---

© 2026 Brandon Lemley.
'''

    readme_path = OUTPUT_DIR / "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)

    print(f"✅ README created: {readme_path.name}")


def main():
    """Main build process"""
    print("=" * 60)
    print(f"Building {APP_NAME} v{VERSION}")
    print("=" * 60)
    print()

    clean_build_directories()
    install_dependencies()

    if not build_executable():
        print("\n❌ Build failed! Exiting.")
        return False

    create_version_file()

    if not create_update_package():
        print("\n❌ Package creation failed! Exiting.")
        return False

    create_installer_script()
    create_readme()

    print()
    print("=" * 60)
    print("✅ BUILD COMPLETE!")
    print("=" * 60)
    print()
    print(f"Distribution files are in: {OUTPUT_DIR.absolute()}")
    print()
    print("Files created:")
    print(f"  - {APP_NAME}.exe (the application)")
    print(f"  - {APP_NAME}_v{VERSION}.zip (distribution package)")
    print(f"  - install.bat (Windows installer)")
    print(f"  - README.md (instructions)")
    print(f"  - server_version_template.json (for update server)")
    print()
    print("Next steps:")
    print("  1. Upload the .zip file to your update server")
    print("  2. Upload server_version_template.json as version.json")
    print("  3. Update VERSION and RELEASE_NOTES at the top of this file for next build")
    print("  4. Distribute the .zip file to users or provide download link")
    print()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)