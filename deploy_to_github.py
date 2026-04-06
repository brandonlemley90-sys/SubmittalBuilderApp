#!/usr/bin/env python3
"""
Quick Deploy Script for GitHub Pages
This script helps you prepare and deploy your update files to GitHub Pages.
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_latest_zip():
    """Find the latest ZIP file in dist/ directory"""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("❌ dist/ directory not found. Run 'python build_app.py' first.")
        return None
    
    zip_files = list(dist_dir.glob("DenierAI_Submittal_Builder_v*.zip"))
    if not zip_files:
        print("❌ No ZIP files found in dist/. Run 'python build_app.py' first.")
        return None
    
    # Get the most recent one
    latest = max(zip_files, key=lambda p: p.stat().st_mtime)
    return latest

def extract_version_from_filename(filename):
    """Extract version number from filename like DenierAI_Submittal_Builder_v1.0.1.zip"""
    import re
    match = re.search(r'v(\d+\.\d+\.\d+)', filename)
    if match:
        return match.group(1)
    return "1.0.0"

def create_version_json(zip_file, github_username, repo_name):
    """Create version.json file"""
    version = extract_version_from_filename(zip_file.name)
    file_hash = calculate_sha256(zip_file)
    
    download_url = f"https://{github_username}.github.io/{repo_name}/updates/{zip_file.name}"
    
    version_data = {
        "version": version,
        "release_notes": f"Version {version} - Latest release with improvements and bug fixes",
        "download_url": download_url,
        "file_hash": file_hash,
        "release_date": "2024-01-01"  # You can update this
    }
    
    return version_data

def main():
    print("=" * 70)
    print("  GitHub Pages Deployment Helper")
    print("=" * 70)
    print()
    
    # Get GitHub info
    print("📝 Enter your GitHub information:")
    print()
    github_username = input("   GitHub username: ").strip()
    if not github_username:
        print("❌ GitHub username is required!")
        return False
    
    repo_name = input("   Repository name (default: denierai-updates): ").strip()
    if not repo_name:
        repo_name = "denierai-updates"
    
    print()
    print(f"✅ Using: {github_username}/{repo_name}")
    print()
    
    # Find ZIP file
    print("🔍 Looking for application package...")
    zip_file = get_latest_zip()
    if not zip_file:
        return False
    
    print(f"✅ Found: {zip_file.name}")
    print(f"   Size: {zip_file.stat().st_size / (1024*1024):.2f} MB")
    print()
    
    # Create version.json
    print("📄 Creating version.json...")
    version_data = create_version_json(zip_file, github_username, repo_name)
    
    # Show preview
    print()
    print("📋 Preview of version.json:")
    print("-" * 70)
    print(json.dumps(version_data, indent=2))
    print("-" * 70)
    print()
    
    # Save version.json
    output_dir = Path("deploy_for_github")
    output_dir.mkdir(exist_ok=True)
    
    updates_dir = output_dir / "updates"
    updates_dir.mkdir(exist_ok=True)
    
    # Copy ZIP file
    import shutil
    dest_zip = updates_dir / zip_file.name
    print(f"📦 Copying {zip_file.name} to {output_dir}/updates/...")
    shutil.copy2(zip_file, dest_zip)
    
    # Save version.json
    version_file = updates_dir / "version.json"
    with open(version_file, 'w') as f:
        json.dump(version_data, f, indent=2)
    print(f"💾 Saved version.json to {output_dir}/updates/")
    print()
    
    # Instructions
    print("=" * 70)
    print("  🎉 FILES READY FOR DEPLOYMENT!")
    print("=" * 70)
    print()
    print(f"📁 Your files are in: ./{output_dir}/updates/")
    print()
    print("📤 NEXT STEPS:")
    print()
    print("1. Go to https://github.com/new")
    print(f"   - Repository name: {repo_name}")
    print("   - Make it Public")
    print("   - Click 'Create repository'")
    print()
    print("2. Enable GitHub Pages:")
    print("   - Go to Settings → Pages")
    print("   - Source: Deploy from a branch")
    print("   - Branch: main → / (root)")
    print("   - Click Save")
    print()
    print("3. Upload your files:")
    print(f"   - Click 'Add file' → 'Upload files'")
    print(f"   - Drag the entire '{output_dir}' folder")
    print("   - Or upload the contents of the 'updates' folder")
    print("   - Click 'Commit changes'")
    print()
    print("4. Wait 1-2 minutes for deployment")
    print()
    print("5. Test your URL:")
    print(f"   https://{github_username}.github.io/{repo_name}/updates/version.json")
    print()
    print("6. Update your Python files:")
    print(f'   UPDATE_SERVER_URL = "https://{github_username}.github.io/{repo_name}/updates"')
    print()
    print("   Edit these files:")
    print("   - auto_updater.py")
    print("   - bootstrap_installer.py")
    print()
    print("7. Rebuild your app:")
    print("   python build_app.py")
    print("   python build_bootstrap.py")
    print()
    print("=" * 70)
    print()
    
    # Ask if user wants to auto-commit (if git is available)
    if Path(".git").exists():
        response = input("🚀 Want to automatically commit these files to a new branch? (y/n): ").strip().lower()
        if response == 'y':
            print()
            print("🔄 Creating deployment branch...")
            try:
                # Create a temporary branch for deployment
                subprocess.run(["git", "checkout", "-b", "deploy-temp"], check=True, capture_output=True)
                
                # Move files to root for deployment
                shutil.copy2(version_file, "version.json")
                shutil.copy2(dest_zip, zip_file.name)
                
                # Add and commit
                subprocess.run(["git", "add", "version.json", zip_file.name], check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", f"Deploy version {version_data['version']}"], check=True, capture_output=True)
                
                print("✅ Files committed to 'deploy-temp' branch")
                print()
                print("Now push to GitHub:")
                print(f"   git push origin deploy-temp")
                print()
                print("Then merge or use as your Pages source.")
                
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Git operation failed: {e}")
                print("   You can still manually upload the files as described above.")
    
    print()
    print("✨ Done! Your update server will be live once you upload to GitHub!")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
