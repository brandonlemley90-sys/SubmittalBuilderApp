"""
Script to generate the corrected version.json content
You need to upload this to your GitHub repo at: updates/version.json
"""
import json

corrected_version_data = {
    "version": "1.0.1",
    "release_notes": "Version 1.0.1 - Latest release with improvements and bug fixes",
    "download_url": "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderAgentUpdates/updates/DenierAI_Submittal_Builder_v1.0.1.zip",
    "file_hash": "574396593e0817adb5726d01c669bb401062c5e63f2355763df9c895672fbca7",
    "release_date": "2024-01-01"
}

print("CORRECTED version.json content:")
print("=" * 60)
print(json.dumps(corrected_version_data, indent=2))
print("=" * 60)
print("\nSave this content to updates/version.json in your GitHub repo")
