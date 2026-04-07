"""
This creates the CORRECT version.json file that you need to upload to GitHub
"""
import json
import hashlib
from pathlib import Path

# Create the corrected version.json
correct_content = {
    "version": "1.0.1",
    "release_notes": "Version 1.0.1 - Latest release with improvements and bug fixes",
    "download_url": "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderAgentUpdates/updates/DenierAI_Submittal_Builder_v1.0.1.zip",
    "file_hash": "574396593e0817adb5726d01c669bb401062c5e63f2355763df9c895672fbca7",
    "release_date": "2024-01-01"
}

# Save to file
output_file = Path("/workspace/corrected_version.json")
with open(output_file, 'w') as f:
    json.dump(correct_content, f, indent=2)

print(f"✅ Created {output_file}")
print("\n📋 Content:")
print("=" * 70)
print(json.dumps(correct_content, indent=2))
print("=" * 70)
print("\n🎯 NEXT STEPS:")
print("1. Go to: https://github.com/brandonlemley90-sys/DenierSubmittalBuilderAgentUpdates/tree/main/updates")
print("2. Click on 'version.json'")
print("3. Click the pencil icon (✏️) to edit")
print("4. Replace ALL content with the JSON above")
print("5. Click 'Commit changes'")
print("6. Wait 2-3 minutes for GitHub Pages to update")
print("\n✨ After that, your update system will work for all users!")
