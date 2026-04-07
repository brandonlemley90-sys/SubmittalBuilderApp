# 🚀 COMPLETE UPDATE SYSTEM SETUP GUIDE

This guide will help you set up a working auto-update system that shows updates to ALL users.

---

## 🔍 QUICK DIAGNOSIS

Your app currently checks for updates at:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates
```

If this URL doesn't exist or returns an error, users won't see update notifications.

---

## ✅ OPTION 1: LOCAL TESTING (Recommended First)

### Step 1: Create Your Update Files Locally

```bash
# Run this in your workspace
python build_app.py
```

This creates a ZIP file in the `dist/` folder.

### Step 2: Start Local Update Server

```bash
# Create updates folder
mkdir -p updates

# Copy your built ZIP file to updates folder
cp dist/DenierAI_Submittal_Builder_v*.zip updates/

# Create version.json (update the filename to match your actual ZIP)
cat > updates/version.json << 'EOF'
{
  "version": "1.0.2",
  "release_notes": "Fixed update notification system - all users will now see updates!",
  "download_url": "http://localhost:8080/DenierAI_Submittal_Builder_v1.0.2.zip",
  "file_hash": "PLACEHOLDER_HASH",
  "release_date": "2024-01-07"
}
EOF
```

### Step 3: Calculate the Real Hash

```bash
# Get the SHA256 hash of your ZIP file
sha256sum updates/DenierAI_Submittal_Builder_v*.zip
```

Copy the hash and update the `file_hash` field in `version.json`.

### Step 4: Start the Local Server

```bash
python update_server.py
```

Keep this terminal open!

### Step 5: Update Your App Config (For Testing Only)

Edit `auto_updater.py`, change line 21:
```python
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates"
```

### Step 6: Test It!

1. Run your app: `python app.py`
2. You should see the update banner appear at the top
3. Click "Download & Restart"
4. The app will download, install, and restart

---

## ✅ OPTION 2: GITHUB PAGES (Production - For All Users)

### Step 1: Build Your App

```bash
python build_app.py
```

### Step 2: Prepare Deployment Files

```bash
python deploy_to_github.py
```

Follow the prompts:
- Enter your GitHub username: `brandonlemley90-sys`
- Enter repo name: `DenierSubmittalBuilderUpdates` (or press enter for default)

This creates a `deploy_for_github/updates/` folder with:
- Your ZIP file
- `version.json` with correct hash

### Step 3: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `DenierSubmittalBuilderUpdates`
3. Make it **Public**
4. Click "Create repository"

### Step 4: Enable GitHub Pages

1. Go to your repo → Settings → Pages
2. Under "Source", select: **Deploy from a branch**
3. Branch: **main** → Folder: **/(root)**
4. Click **Save**

### Step 5: Upload Your Files

**Method A: Using Git Command Line**
```bash
cd deploy_for_github
git init
git add .
git commit -m "Initial update server deployment"
git branch -M main
git remote add origin https://github.com/brandonlemley90-sys/DenierSubmittalBuilderAgentUpdates.git
git push -u origin main
```

**Method B: Using GitHub Web Interface**
1. In your GitHub repo, click "Add file" → "Upload files"
2. Drag the entire contents of `deploy_for_github/updates/` folder
3. Click "Commit changes"

### Step 6: Wait for Deployment

GitHub Pages takes 1-3 minutes to deploy. Test it:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates
```

You should see JSON output. If you get 404, wait longer or check Steps 3-4.

### Step 7: Verify Configuration

Your `auto_updater.py` should already have the correct URL:
```python
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates"
```

And `bootstrap_installer.py` line 15 should match.

### Step 8: Rebuild and Distribute

```bash
# Rebuild with correct URLs
python build_app.py
python build_bootstrap.py
```

Now when users run the app:
1. They'll see the update banner if a newer version exists
2. Clicking "Download & Restart" installs the update automatically
3. All users see the same update notification

---

## 🔄 HOW TO PUSH UPDATES IN THE FUTURE

Every time you want to release an update:

### 1. Make Your Code Changes
Edit your Python files, templates, etc.

### 2. Commit to Git
```bash
git add .
git commit -m "Description of changes"
git push origin main
```

### 3. Build New Version
```bash
python build_app.py
```

### 4. Increment Version Number
Edit `auto_updater.py` line 22:
```python
CURRENT_VERSION = "1.0.2"  # Change to next version
```

### 5. Prepare Deployment
```bash
python deploy_to_github.py
```
Use same GitHub username and repo name.

### 6. Update GitHub Pages Repo
```bash
cd deploy_for_github
# Copy new files to your GitHub Pages repo
git remote add origin https://github.com/brandonlemley90-sys/DenierSubmittalBuilderAgentUpdates.git
git add .
git commit -m "Update to version 1.0.2"
git push origin main
```

### 7. Wait 1-2 Minutes
GitHub Pages will deploy automatically.

### 8. Test
Visit the version.json URL to confirm it shows the new version.

---

## 🎯 WHAT USERS SEE

When an update is available:

1. **Blue Banner Appears** at top of app
   - Shows new version number
   - Shows release notes
   - Has "Download & Restart" button

2. **User Clicks Button**
   - Download progress shown
   - App closes automatically
   - Update extracts and replaces old files
   - App restarts with new version

3. **All Users See Same Update**
   - Because they all check the same GitHub Pages URL
   - Centralized update server = synchronized updates

---

## ⚠️ TROUBLESHOOTING

### "Update banner never appears"
- Check browser console (F12) for errors
- Visit your version.json URL directly in browser
- Ensure `CURRENT_VERSION` in code is LOWER than server version

### "Download fails"
- Check that download_url in version.json is correct
- Ensure ZIP file exists at that URL
- Check Windows Security/Antivirus isn't blocking

### "Hash verification failed"
- This is normal during development
- Users can type "FORCE" to bypass
- In production, ensure hash in version.json matches actual file

### "GitHub Pages shows 404"
- Wait 2-3 minutes after pushing
- Check Settings → Pages is enabled
- Ensure files are in root or correct folder
- Try: `https://username.github.io/repo

---

## 📋 FILE CHECKLIST

Make sure these files have matching URLs:

- [ ] `auto_updater.py` line 21: `UPDATE_SERVER_URL`
- [ ] `bootstrap_installer.py` line 15: `UPDATE_SERVER_URL`
- [ ] GitHub Pages repo contains: `updates/version.json` + `updates/*.zip`
- [ ] `version.json` download_url points to correct ZIP location

---

## 🎉 SUCCESS VERIFICATION

To verify everything works:

1. Open app → Should see update banner (if server version > local version)
2. Click "Download & Restart"
3. App closes, updates, restarts
4. Check version number increased
5. Tell a friend to test → They should also see the update!

---

## 📞 NEED HELP?

Common issues and solutions:

| Problem | Solution |
|---------|----------|
| No update banner | Check version.json is accessible via URL |
| Download fails | Verify download_url in version.json |
| Hash mismatch | Recalculate hash or use FORCE during dev |
| GitHub Pages 404 | Wait longer, check Settings → Pages |
| App won't restart | Check apply_update.bat was created |

---

**Remember**: The key is that ALL users check the SAME GitHub Pages URL. Once you deploy there, everyone gets notified of updates automatically!
