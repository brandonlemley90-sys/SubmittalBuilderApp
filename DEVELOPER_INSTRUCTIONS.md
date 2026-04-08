# Developer Distribution & Update Guide

This guide details the process for building, releasing, and managing updates for the Submittal Builder application.

## 1. AI-Managed Update Workflow (Recommended)
You can manage the entire application lifecycle through Antigravity. This is the fastest and most reliable way to ship updates to your users.

### The Process:
1.  **Request Changes**: Ask Antigravity to modify the code or fix a bug.
2.  **Request Release**: Once the changes are verified, say: *"Antigravity, push a new update to GitHub."*
3.  **Automatic Deployment**: Antigravity will:
    -   Run `python release.py` to package the app and bump the version.
    -   Push the update files to the `DenierSubmittalBuilderUpdates` repository.
4.  **Instant Delivery**: Your users will immediately see the **Blue Update Banner** in their application.

---

## 2. Visual Verification States
The application has been verified to transition through these states in real-time.

### State A: Update Available (Blue)
Triggered automatically when the local `version.json` is older than the server version.
![Blue Banner](file:///C:/Users/blemley/.gemini/antigravity/brain/bbc41b1a-af22-467d-8cc6-f3ccbf60dba9/update_available_blue_banner_1775668796206.png)

### State B: Update Installed (Green)
Appears for 5 seconds after the application restarts following a successful update.
![Green Success Banner](file:///C:/Users/blemley/.gemini/antigravity/brain/bbc41b1a-af22-467d-8cc6-f3ccbf60dba9/update_installed_green_banner_final_1775668845224.png)

---

## 3. Manual Build Commands
If you need to build or release manually, use these commands in PowerShell:

- **Build Installer**: `python build_bootstrap.py`
  - Creates: `dist_bootstrap/Setup_DenierAI_Submittal_Builder.exe`
- **Push Update**: `python release.py`
  - Creates the ZIP, updates `version.json`, and stages it for GitHub.

---

## 4. Troubleshooting & Maintenance
- **Port Conflict**: The application uses **Port 5002** by default to avoid common Windows system conflicts.
- **Zombies**: if the app won't start, run:
  `taskkill /F /IM python.exe`
- **Update Server**: All update files are hosted at:
  `https://github.com/brandonlemley90-sys/DenierSubmittalBuilderUpdates`

> [!IMPORTANT]
> Always ensure `GEMINI_API_KEY` is set in your environment before building or releasing.
