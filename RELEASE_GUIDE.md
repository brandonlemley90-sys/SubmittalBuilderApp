# DenierAI Submittal Builder — Release Guide

This is the **only document you need** to push a new version of the app to all users.
No other guides exist — everything is in here.

---

## Table of Contents

1. [Overview — How Releases Work](#1-overview--how-releases-work)
2. [One-Time Setup](#2-one-time-setup-do-this-once-ever)
3. [How to Push a New Release (Every Time)](#3-how-to-push-a-new-release-every-time)
4. [How to Verify It Worked](#4-how-to-verify-it-worked)
5. [What Users See](#5-what-users-see)
6. [Troubleshooting](#6-troubleshooting)
7. [Reference — File Roles](#7-reference--file-roles)

---

## 1. Overview — How Releases Work

Here is the full picture of what happens when you release an update:

```
Your Machine                    GitHub                        User's App
─────────────                   ──────────────────────────    ──────────────
python release.py               DenierSubmittalBuilderUpdates
  │                               (GitHub Pages repo)
  ├─ Builds .exe
  ├─ Packages into .zip              version.json  ◄──────── App checks this on startup
  ├─ Calculates SHA256 hash          .zip file     ◄──────── App downloads this if update found
  ├─ Writes version.json
  └─ Stages files in               You git push ──►
     release_output/               (the copy-paste
                                    commands the
                                    script prints)
```

**There are two separate GitHub repos:**

| Repo | URL | Purpose |
|---|---|---|
| **Source Code** (where you code) | `github.com/brandonlemley90-sys/SubmittalBuilderApp` | Your Python files, builders, app logic |
| **Updates Repo** (where releases go) | `github.com/brandonlemley90-sys/DenierSubmittalBuilderUpdates` | The `.zip` and `version.json` that users download |

When users open the app, it checks the **Updates Repo's GitHub Pages site**:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json
```

If the version number there is higher than what they have installed, they get an update banner.

---

## 2. One-Time Setup (Do This Once, Ever)

You only need to do this section **one time** on your development machine.
After this is done, skip straight to Section 3 for every future release.

### Step 2.1 — Install Git

If Git is not already installed:

1. Go to **https://git-scm.com/download/win**
2. Download and run the installer
3. Accept all defaults
4. When finished, open a new PowerShell window and confirm it works:
   ```powershell
   git --version
   ```
   You should see something like `git version 2.44.0.windows.1`. If you see an error, restart your computer and try again.

### Step 2.2 — Configure Git With Your GitHub Identity

Open PowerShell and run these two commands (replace the values in quotes with your actual info):

```powershell
git config --global user.name "brandonlemley90-sys"
git config --global user.email "your-email@example.com"
```

> **What this does:** Git stamps your name and email on every commit you make.
> You only run this once ever — it's saved globally on your computer.

### Step 2.3 — Clone the Updates Repo to Your Computer

The updates repo is where your `.zip` and `version.json` files live. You need a local copy on your machine so you can add files to it and push them.

1. Decide where you want to keep it. A simple location is `C:\updates-repo`.
2. Open PowerShell and run:
   ```powershell
   git clone https://github.com/brandonlemley90-sys/DenierSubmittalBuilderUpdates.git C:\updates-repo
   ```
3. You'll be prompted to sign in to GitHub. Use your GitHub username and password (or personal access token if you have two-factor auth enabled).
4. When it finishes, confirm it worked:
   ```powershell
   dir C:\updates-repo
   ```
   You should see `version.json` and any existing `.zip` files listed.

> **What this does:** Creates a local copy of the updates repo at `C:\updates-repo`.
> Git keeps it linked to GitHub so you can push files up to it with a simple `git push`.

### Step 2.4 — Test That You Can Push (Optional but Recommended)

Run the following in PowerShell to confirm your credentials work end-to-end:

```powershell
cd C:\updates-repo
git status
```

You should see `nothing to commit, working tree clean`.

If you see a credential error, you may need to set up a GitHub personal access token:
1. Go to **https://github.com/settings/tokens**
2. Click **Generate new token (classic)**
3. Give it a name, set expiration as desired, check the `repo` scope
4. Copy the token — use it as your password when git prompts for credentials

---

## 3. How to Push a New Release (Every Time)

Follow these steps **every time** you want to push an update to users.
This is the only section you'll use after the one-time setup is done.

### Step 3.1 — Open the Source Code Folder

Navigate to your source code folder in File Explorer:
```
C:\Users\blemley\Desktop\AI Agent Codes\Submittal Builder Agent
```

### Step 3.2 — Edit the Version and Release Notes in `release.py`

Open `release.py` in your editor and find the top of the file:

```python
# ===================================================================
# EDIT THESE TWO VALUES BEFORE EACH RELEASE — NOTHING ELSE NEEDED
# ===================================================================
VERSION = "1.0.2"          # e.g. "1.0.3" or "1.1.0"
RELEASE_NOTES = "Bug fixes and updated reset password functionality..."
# ===================================================================
```

**Change `VERSION`** — increment the number:
- Small bug fix → change `1.0.2` to `1.0.3`
- New feature → change `1.0.2` to `1.1.0`
- Major overhaul → change `1.0.2` to `2.0.0`

**Change `RELEASE_NOTES`** — write a short description of what changed.
Keep it to one or two sentences. Users see this in the update banner.

> **Important:** The version number you set here MUST be higher than the number
> currently in `version.json`. If it's the same or lower, users won't see the update,
> because the app only prompts for an update when the server version is higher.

### Step 3.3 — Open a Terminal in the Source Code Folder

Two ways to do this:

**Option A (easiest):** In File Explorer, click in the address bar at the top,
type `powershell`, and press Enter. A PowerShell window opens directly in that folder.

**Option B:** Open PowerShell normally, then type:
```powershell
cd "C:\Users\blemley\Desktop\AI Agent Codes\Submittal Builder Agent"
```

### Step 3.4 — Run the Release Script

In the PowerShell window, type:

```powershell
python release.py
```

Press Enter. The script will now:
1. Check and install any missing Python packages automatically
2. Clean out old build files so there's no leftover clutter
3. Build the `.exe` using PyInstaller (this takes 2–5 minutes — the window will show progress)
4. Package the `.exe` into a `.zip` file
5. Calculate the SHA256 security hash of the zip
6. Write `version.json` with all the correct information
7. Copy both files into a folder called `release_output/`
8. Print the exact git commands you need to copy and paste

> **If the build fails:** Read the error message. The most common cause is a missing
> Python package. The error will name the package — run `pip install <packagename>` and try again.

### Step 3.5 — Copy and Paste the Git Commands

When the script finishes, it will print something like this at the bottom:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COPY AND PASTE THESE COMMANDS INTO ANY TERMINAL (PowerShell/CMD)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cd C:\updates-repo
git pull origin main
copy /Y "...\release_output\DenierAI_Submittal_Builder_v1.0.3.zip" "DenierAI_Submittal_Builder_v1.0.3.zip"
copy /Y "...\release_output\version.json" "version.json"
git add DenierAI_Submittal_Builder_v1.0.3.zip version.json
git commit -m "Release v1.0.3 - Fixed login page bug"
git push origin main
```

**Copy that entire block** and paste it into a PowerShell or Command Prompt window. Then press Enter.

> **What each command does:**
> - `cd C:\updates-repo` — Moves into your local copy of the updates repo
> - `git pull origin main` — Gets any changes from GitHub first (prevents conflicts)
> - `copy /Y ...` — Copies your new zip and version.json into the updates repo folder
> - `git add ...` — Tells git which files to include in the commit
> - `git commit -m "..."` — Saves a snapshot with a description
> - `git push origin main` — Sends everything to GitHub

Git may ask for your GitHub username and password. Enter them (or your personal access token as the password if using 2FA).

### Step 3.6 — Wait for GitHub Pages to Update

After you push, GitHub automatically publishes the files to the Pages site.
**This takes 1–2 minutes.** You don't need to do anything — just wait.

After waiting, go to:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json
```

You should see the JSON in your browser showing the new version number. If it still shows the old version, wait another 60 seconds and refresh.

---

## 4. How to Verify It Worked

After pushing and waiting ~2 minutes:

**Check the version.json URL directly:**
Open your browser and go to:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json
```
You should see something like:
```json
{
  "version": "1.0.3",
  "release_notes": "Version 1.0.3 - Fixed login page bug",
  "download_url": "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/DenierAI_Submittal_Builder_v1.0.3.zip",
  "file_hash": "abc123...",
  "release_date": "2026-04-08"
}
```

If the version number matches what you just released — you're done. ✅

**Check the zip is accessible:**
Click the `download_url` in the JSON above. It should download the zip file.
If it 404s, the zip wasn't pushed correctly — re-run the git commands.

---

## 5. What Users See

When a user opens the app and an update is available:

1. A **blue banner** appears at the top of the app window showing:
   - The new version number
   - Your release notes
   - A "Download & Restart" button

2. The user clicks the button

3. The app:
   - Downloads the new `.zip` in the background (progress shown)
   - Verifies the SHA256 hash (security check)
   - Extracts the new `.exe`
   - Creates a small batch script to replace the old files
   - Closes itself
   - The batch script runs, replaces files, and relaunches the app

4. The app reopens at the new version — user doesn't need to do anything else

---

## 6. Troubleshooting

### "The update banner never appears for users"

**Check 1 — Is the version number actually higher?**
The app only shows the banner when the server version is STRICTLY higher than
what the user has installed. If you accidentally set the same version number,
nothing will happen. Fix: increment the version and re-release.

**Check 2 — Is version.json accessible?**
Open a browser and go to:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json
```
If you get a 404, either GitHub Pages isn't enabled or the push didn't work.
Check: GitHub → DenierSubmittalBuilderUpdates → Settings → Pages → confirm it's on.

**Check 3 — Did you wait long enough?**
GitHub Pages can take up to 5 minutes after a push. Wait and try again.

---

### "Hash verification failed" on user's machine

The SHA256 hash in `version.json` doesn't match the downloaded zip.
This usually means the zip was corrupted during upload or the wrong zip was pushed.

**Fix:** Re-run `python release.py` and push the newly generated files again.
The script always recalculates the hash from the actual file, so a clean run
will produce a matching pair.

---

### "Build fails — PyInstaller error"

**Most common causes:**
- A Python import in your code that PyInstaller doesn't know about.
  Fix: Add `--hidden-import yourmodulename` to the `cmd` list in `release.py` (in the `build_executable()` function).

- Missing file (templates/ or static/ folder not found).
  Fix: Make sure those folders exist in your source directory.

- Antivirus blocking the build.
  Fix: Temporarily disable real-time protection, or add an exclusion for the build folder.

---

### "Git push fails — authentication error"

Your credentials aren't saved. Fix:

1. Go to **https://github.com/settings/tokens**
2. Generate a Classic token with `repo` scope
3. When git asks for a password during push, paste the token instead
4. To save it so you're not asked again:
   ```powershell
   git config --global credential.helper manager
   ```

---

### "git is not recognized as a command"

Git isn't installed or isn't in your PATH.
Download and install from **https://git-scm.com/download/win**, then open a fresh PowerShell window.

---

### "GitHub Pages shows old version after push"

Wait up to 5 minutes. If still not updated:
1. Go to your GitHub repo → Actions tab — check if a Pages deployment is running or failed
2. Go to Settings → Pages — confirm GitHub Pages is still enabled on the `main` branch
3. Try pushing an empty commit to trigger a redeploy:
   ```powershell
   cd C:\updates-repo
   git commit --allow-empty -m "Trigger redeploy"
   git push origin main
   ```

---

## 7. Reference — File Roles

Understanding which file does what helps when something goes wrong.

| File | Where It Lives | What It Does |
|---|---|---|
| `release.py` | Source code repo | **The main release tool.** Edit VERSION/RELEASE_NOTES here, then run it. |
| `build_app.py` | Source code repo | Called internally by release.py. Handles PyInstaller build. |
| `auto_updater.py` | Source code repo | Runs inside the distributed app. Checks for updates on startup. |
| `bootstrap_installer.py` | Source code repo | First-time installer. Downloads and installs the latest version. |
| `version.json` | Source code repo | Auto-updated by release.py. Tracks current version in the source. |
| `version.json` | Updates repo | **The file the app checks.** Must be updated via git push on every release. |
| `DenierAI_Submittal_Builder_vX.X.X.zip` | Updates repo | The actual download. Must be pushed alongside version.json. |

**The golden rule:** Every release pushes exactly two files to the updates repo:
- The **new versioned zip** (e.g. `DenierAI_Submittal_Builder_v1.0.3.zip`)
- The **updated `version.json`** pointing to that zip

If either one is missing or out of sync, the update will fail for users.

---

*Last updated: 2026-04-08*
