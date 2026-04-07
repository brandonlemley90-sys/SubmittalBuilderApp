#!/usr/bin/env python3
"""
Quick test to verify your update server configuration is correct.
Run this to diagnose update system issues.
"""
import json
from urllib.request import urlopen
from urllib.error import URLError

# Test the current configuration
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderAgentUpdates/updates"

print("=" * 70)
print("  UPDATE SYSTEM DIAGNOSTIC TOOL")
print("=" * 70)
print()

print(f"Testing update server URL:")
print(f"  {UPDATE_SERVER_URL}/version.json")
print()

try:
    # Try to fetch version.json
    print("📡 Attempting to connect...")
    response = urlopen(f"{UPDATE_SERVER_URL}/version.json", timeout=10)
    data = json.loads(response.read().decode())
    
    print("✅ SUCCESS! Server is reachable!")
    print()
    print("Current version info from server:")
    print(f"  Version: {data.get('version', 'unknown')}")
    print(f"  Release Notes: {data.get('release_notes', 'none')}")
    print(f"  Download URL: {data.get('download_url', 'missing')}")
    print(f"  File Hash: {data.get('file_hash', 'missing')[:20]}..." if data.get('file_hash') else "  File Hash: missing")
    print()
    
    # Test download URL
    download_url = data.get('download_url', '')
    if download_url:
        print(f"📦 Testing download URL...")
        print(f"   {download_url}")
        try:
            download_response = urlopen(download_url, timeout=5)
            size = download_response.headers.get('Content-Length', 'unknown')
            print(f"✅ Download URL works! File size: {size} bytes")
        except Exception as e:
            print(f"❌ Download URL failed: {e}")
    print()
    
    # Compare with local version
    from auto_updater import CURRENT_VERSION
    server_version = data.get('version', '0.0.0')
    
    print(f"📊 Version Comparison:")
    print(f"   Local app version:  {CURRENT_VERSION}")
    print(f"   Server version:     {server_version}")
    
    def version_compare(v1, v2):
        import re
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
    
    cmp = version_compare(server_version, CURRENT_VERSION)
    print()
    if cmp > 0:
        print("🚀 UPDATE AVAILABLE! Users will see the update banner.")
    elif cmp == 0:
        print("✅ App is up to date. No update banner will show.")
    else:
        print("⚠️  Local version is newer than server (development mode?)")
    
except URLError as e:
    print("❌ FAILED! Cannot reach update server.")
    print()
    print(f"Error: {e}")
    print()
    print("Possible causes:")
    print("  1. GitHub Pages repo doesn't exist yet")
    print("  2. GitHub Pages is not enabled in repo settings")
    print("  3. Files haven't been uploaded to the repo")
    print("  4. GitHub Pages is still deploying (wait 2-3 minutes)")
    print("  5. The URL is incorrect")
    print()
    print("Next steps:")
    print("  1. Visit: https://github.com/brandonlemley90-sys/DenierSubmittalBuilderAgentUpdates")
    print("  2. Go to Settings → Pages")
    print("  3. Ensure Pages is enabled with branch: main, folder: / (root)")
    print("  4. Upload files to the repo (see COMPLETE_UPDATE_GUIDE.md)")
    print("  5. Wait 2-3 minutes for deployment")
    print()
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
