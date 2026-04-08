#!/usr/bin/env python3
"""
=======================================================================
  DenierAI Submittal Builder — Release Script
=======================================================================

HOW TO RELEASE A NEW VERSION
------------------------------
1. Edit the two values below: VERSION and RELEASE_NOTES
2. Run this script:  python release.py
3. Wait for the build to finish
4. Copy and paste the git commands printed at the end into any terminal
5. Done — your users will get the update automatically

REQUIREMENTS
------------
- Python 3.8+
- PyInstaller (installed automatically if missing)
- Git installed on your system (https://git-scm.com/)
- You must have already cloned DenierSubmittalBuilderUpdates somewhere
  (see RELEASE_GUIDE.md for one-time setup)
=======================================================================
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

# ===================================================================
# EDIT THESE TWO VALUES BEFORE EACH RELEASE — NOTHING ELSE NEEDED
# ===================================================================
VERSION = "1.0.3"          # e.g. "1.0.3" or "1.1.0"
RELEASE_NOTES = "Update copyright attributions to Brandon Lemley and fix updater download paths."
# ===================================================================

# --- Internal config — do not change these ---
APP_NAME          = "DenierAI_Submittal_Builder"
UPDATES_REPO_URL  = "https://github.com/brandonlemley90-sys/DenierSubmittalBuilderUpdates.git"
PAGES_BASE_URL    = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates"
OUTPUT_DIR        = Path("dist")
BUILD_DIR         = Path("build")
RELEASE_STAGING   = Path("release_output")   # files are placed here, ready to push


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def header(text):
    width = 65
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def step(text):
    print(f"\n>  {text}")


def ok(text):
    print(f"   DONE: {text}")


def fail(text):
    print(f"   ERROR: {text}")
    sys.exit(1)


def calculate_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ─────────────────────────────────────────────
#  STEP 1 — Validate / install dependencies
# ─────────────────────────────────────────────

def check_dependencies():
    step("Checking dependencies...")
    packages = ["flask", "werkzeug", "pyinstaller"]
    for pkg in packages:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True
        )
        if result.returncode != 0:
            fail(f"Could not install {pkg}. Run: pip install {pkg}")
    ok("All dependencies ready")


# ─────────────────────────────────────────────
#  STEP 2 — Clean previous build artifacts
# ─────────────────────────────────────────────

def clean():
    step("Cleaning previous build artifacts...")
    for d in [OUTPUT_DIR, BUILD_DIR, RELEASE_STAGING]:
        if d.exists():
            shutil.rmtree(d)
            ok(f"Removed {d}/")
    for leftover in ["update_package.zip"]:
        p = Path(leftover)
        if p.exists():
            p.unlink()
    ok("Clean complete")


# ─────────────────────────────────────────────
#  STEP 3 — Build the executable
# ─────────────────────────────────────────────

def build_executable():
    step(f"Building {APP_NAME}.exe with PyInstaller...")

    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        f"--add-data=templates{sep}templates",
        f"--add-data=static{sep}static",
        "--hidden-import", "tkinter",
        "--hidden-import", "flask",
        "--hidden-import", "werkzeug.security",
    ]
    if Path("icon.ico").exists():
        cmd.extend(["--icon", "icon.ico"])
    cmd.append("app.py")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        fail("PyInstaller build failed. Check the output above for errors.")

    exe = OUTPUT_DIR / f"{APP_NAME}.exe"
    if not exe.exists():
        fail(f"Expected {exe} but it was not created.")
    ok(f"Executable created: {exe}")


# ─────────────────────────────────────────────
#  STEP 4 — Package into a ZIP file
# ─────────────────────────────────────────────

def create_package():
    step("Creating distribution ZIP package...")

    exe_path = OUTPUT_DIR / f"{APP_NAME}.exe"
    zip_name = f"{APP_NAME}_v{VERSION}.zip"
    zip_path = OUTPUT_DIR / zip_name

    # Stage files for the zip
    pkg_dir = OUTPUT_DIR / "package_contents"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(exe_path, pkg_dir / f"{APP_NAME}.exe")

    # Also bundle a minimal version.json inside the zip so the installed
    # app knows its own version after first install
    minimal_version = {"version": VERSION, "release_notes": f"Version {VERSION} - {RELEASE_NOTES}"}
    with open(pkg_dir / "version.json", "w") as f:
        json.dump(minimal_version, f, indent=2)

    # Create the zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in pkg_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(pkg_dir))

    shutil.rmtree(pkg_dir)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    ok(f"ZIP created: {zip_path.name}  ({size_mb:.2f} MB)")
    return zip_path


# ─────────────────────────────────────────────
#  STEP 5 — Calculate hash & write version.json
# ─────────────────────────────────────────────

def create_version_files(zip_path):
    step("Calculating SHA256 hash and writing version files...")

    file_hash = calculate_sha256(zip_path)
    ok(f"SHA256: {file_hash}")

    today = date.today().isoformat()
    version_data = {
        "version": VERSION,
        "release_notes": f"Version {VERSION} - {RELEASE_NOTES}",
        "download_url": f"{PAGES_BASE_URL}/{zip_path.name}",
        "file_hash": file_hash,
        "release_date": today
    }

    # Write to dist/ (template for reference)
    template_path = OUTPUT_DIR / "server_version_template.json"
    with open(template_path, "w") as f:
        json.dump(version_data, f, indent=2)
    ok(f"Server template: {template_path}")

    # Update local version.json (keeps source repo in sync)
    with open("version.json", "w") as f:
        json.dump(version_data, f, indent=2)
    ok("Local version.json updated")

    return version_data, file_hash


# ─────────────────────────────────────────────
#  STEP 6 — Stage release output folder
# ─────────────────────────────────────────────

def stage_release(zip_path, version_data):
    step("Staging release files into release_output/...")

    RELEASE_STAGING.mkdir(parents=True, exist_ok=True)

    # Copy the zip
    dest_zip = RELEASE_STAGING / zip_path.name
    shutil.copy2(zip_path, dest_zip)
    ok(f"Copied: {zip_path.name}")

    # Write version.json (this is the file GitHub Pages will serve)
    version_dest = RELEASE_STAGING / "version.json"
    with open(version_dest, "w") as f:
        json.dump(version_data, f, indent=2)
    ok("Written: version.json")

    return dest_zip


# ─────────────────────────────────────────────
#  STEP 7 — Print copy-paste git commands
# ─────────────────────────────────────────────

def print_git_instructions(zip_path, version_data):
    zip_name = zip_path.name
    repo_url = UPDATES_REPO_URL
    abs_staging = RELEASE_STAGING.absolute()

    header("BUILD COMPLETE — PUSH YOUR UPDATE")

    print(f"""
Your release files are ready in:
  {abs_staging}

    ├── {zip_name}
    └── version.json


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COPY AND PASTE THESE COMMANDS INTO ANY TERMINAL (PowerShell/CMD)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  NOTE: Replace C:\\updates-repo with whatever folder you cloned the
  updates repo into during one-time setup (see RELEASE_GUIDE.md).
  If you haven't done the one-time setup yet, do that step first.

─── Command block (copy everything between the lines) ────────────

cd C:\\updates-repo
git pull origin main
copy /Y "{abs_staging}\\{zip_name}" "{zip_name}"
copy /Y "{abs_staging}\\version.json" "version.json"
git add {zip_name} version.json
git commit -m "Release v{VERSION} - {RELEASE_NOTES[:60]}"
git push origin main

─────────────────────────────────────────────────────────────────

After pushing:
  • GitHub Pages updates automatically (takes ~1-2 minutes)
  • Test it: https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json
  • Your live users will see the update banner next time they open the app

Release summary:
  Version      : {version_data['version']}
  Download URL : {version_data['download_url']}
  Release date : {version_data['release_date']}
""")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    header(f"DenierAI Submittal Builder — Releasing v{VERSION}")
    print(f"  Release notes: {RELEASE_NOTES}")

    check_dependencies()
    clean()
    build_executable()
    zip_path = create_package()
    version_data, _ = create_version_files(zip_path)
    stage_release(zip_path, version_data)
    print_git_instructions(zip_path, version_data)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Release cancelled.")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
