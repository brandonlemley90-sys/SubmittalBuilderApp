# DenierAI Submittal Builder — Distribution & Testing Guide

This guide explains how to get the application into the hands of your first users and how to verify everything is working correctly before you send it out.

---

## Part 1: How to Distribute to New Users

When a new user wants the app, you don't send them the code or the big zip file. Instead, you send them a tiny **Bootstrap Installer**. This installer downloads the latest version for them and sets up their desktop shortcut.

### 1. Build the Installer
Open your terminal in the source code folder and run:
```powershell
python build_bootstrap.py
```

### 2. Find the Output
Once the script finishes, look in the `dist/` folder. You will see a file named:
**`Setup_DenierAI_Submittal_Builder.exe`**

### 3. Share the File
This is the **only file** you need to give to new users. You can:
- Email it to them.
- Put it on a shared OneDrive or Dropbox folder.
- List it on a private download page.

> [!IMPORTANT]
> **Antivirus Warnings**: Because this is a custom-built installer, Windows "SmartScreen" or Antivirus might flag it as "Unknown." 
> Tell your users they need to click **"More Info"** -> **"Run Anyway"** the first time they open it.

---

## Part 2: How to Test the Installation (For You)

Before sending the `Setup` file to others, you should test it on your own machine.

### 1. Clean Up Your Old Version
The installer needs to "see" a fresh environment.
1. Close the app if it's open.
2. Delete the installation folder: `%LOCALAPPDATA%\DenierAI_Submittal_Builder`
   *(Paste that path into your File Explorer address bar to find it easily).*

### 2. Run the Setup
Double-click the `Setup_DenierAI_Submittal_Builder.exe` you created in Part 1.
- **Expected Result**: A black console window appears, shows "Fetching version information," downloads the app, and then closes.
- **Verification**: 
  - Check your Desktop for a "DenierAI Submittal Builder" shortcut.
  - Double-click the shortcut to ensure the app launches correctly.

---

## Part 3: How to Test the Update System

Once the app is installed, you want to make sure the "Auto-Update" notification actually works when you release a new version.

### Safe Testing Method (No risk to users)
If you want to see the update banner without actually publishing a "real" update to everyone:

1. **Modify your local app**: 
   Open `version.json` in your installed folder (`%LOCALAPPDATA%\DenierAI_Submittal_Builder`) and change the `"version"` number to something very low, like `"0.0.1"`.
   
2. **Launch the app**:
   Open the app using your Desktop shortcut.
   
3. **The Result**: 
   Because the version on the server (`1.0.2`) is now technically "higher" than what you just typed locally (`0.0.1`), the app will immediately show the blue update banner.

4. **Test the Download**:
   Click the **"Update & Restart"** button. The app should download the files and restart itself. If it re-opens and shows the correct version (e.g., `1.0.2`), the system is working perfectly. ✅

---

## Recap: The Life Cycle of a Version

1. **Coding**: You make changes to the builders or the UI.
2. **Testing**: You run `python app.py` to make sure your changes look good.
3. **Releasing**: You update `release.py` and run it to push the update to GitHub.
4. **Auto-Update**: Your users (who already have the app) see the blue banner and update.
5. **New Users**: New people download the `Setup_...exe` you created once in Part 1.

---

*Last updated: 2026-04-08*
