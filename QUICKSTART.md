# 🚀 Quick Start Guide - DenierAI Submittal Builder

## What I've Built For You

I've transformed your Flask web application into a **distributable desktop app with automatic updates**. Here's what you now have:

### New Files Created:

1. **`auto_updater.py`** - The auto-update engine
2. **`build_app.py`** - Build script to create the executable
3. **`update_server.py`** - Simple server to host updates
4. **`DEPLOYMENT_GUIDE.md`** - Complete deployment documentation
5. **Updated `app.py`** - Integrated auto-update functionality
6. **Updated `templates/index.html`** - Added update check button and UI

---

## How It Works

### For Your Users:
1. They download a ZIP file (one time)
2. Run `install.bat` to install
3. App creates a desktop shortcut
4. **Every time they open the app, it checks for updates automatically**
5. If an update is available, they get a notification and can update with one click

### For You (The Developer):
1. Make changes to your code
2. Run `python build_app.py`
3. Upload the new ZIP and version.json to your server
4. **Users automatically get notified of the update!**

No more sending new files to every user manually!

---

## Step-by-Step Instructions

### Phase 1: Build the Application (Do This Once)

```bash
# On your development machine
cd /workspace
python build_app.py
```

This will create:
- `dist/DenierAI_Submittal_Builder.exe` - The Windows executable
- `dist/DenierAI_Submittal_Builder_v1.0.0.zip` - Distribution package
- `dist/install.bat` - Installer script
- `dist/README.md` - User instructions
- `dist/server_version_template.json` - Server config

### Phase 2: Set Up Your Update Server

#### Option A: Use the Included Test Server (For Testing)

```bash
# Start the test server
python update_server.py
```

Then in `auto_updater.py`, change:
```python
UPDATE_SERVER_URL = "http://localhost:8080"
```

Rebuild:
```bash
python build_app.py
```

#### Option B: Use a Real Web Server (For Production)

1. **Upload to your web server:**
   - Upload `DenierAI_Submittal_Builder_v1.0.0.zip` to your server
   - Upload `server_version_template.json` as `version.json`

2. **Edit `version.json` on your server:**
   ```json
   {
     "version": "1.0.0",
     "release_notes": "Initial release",
     "download_url": "https://your-domain.com/updates/DenierAI_Submittal_Builder_v1.0.0.zip",
     "file_hash": "COPY_HASH_FROM_BUILD_OUTPUT",
     "release_date": "2024-01-01"
   }
   ```

3. **Update `auto_updater.py`:**
   ```python
   UPDATE_SERVER_URL = "https://your-domain.com/updates"
   ```

4. **Rebuild with correct URL:**
   ```bash
   python build_app.py
   ```

### Phase 3: Distribute to Users

Send your users:
- The download link to the ZIP file, OR
- The ZIP file directly

They should:
1. Extract the ZIP
2. Run `install.bat` as Administrator
3. Launch from desktop shortcut

### Phase 4: Push Updates (Whenever You Make Changes)

1. **Make your code changes**

2. **Increment version in `build_app.py`:**
   ```python
   VERSION = "1.1.0"  # Change this
   ```

3. **Rebuild:**
   ```bash
   python build_app.py
   ```

4. **Upload new files to server:**
   - Upload new ZIP file
   - Update `version.json` with:
     - New version number
     - New hash (from build output)
     - New download URL
     - Release notes

5. **Done!** Users will be notified next time they open the app

---

## Testing the Auto-Update

### Test Locally:

1. **Start the test server:**
   ```bash
   python update_server.py
   ```

2. **Build version 1.0.0:**
   ```bash
   # In auto_updater.py set: UPDATE_SERVER_URL = "http://localhost:8080"
   python build_app.py
   ```

3. **Install and run the app** on a test machine

4. **Make a small code change**

5. **Build version 1.1.0:**
   ```bash
   # Change VERSION = "1.1.0" in build_app.py
   python build_app.py
   ```

6. **Copy new ZIP to updates folder:**
   ```bash
   cp dist/DenierAI_Submittal_Builder_v1.1.0.zip updates/
   ```

7. **Update version.json in updates folder:**
   - Change version to "1.1.0"
   - Update hash from build output
   - Update download URL

8. **Open the app** - it should detect the update!

---

## Key Features

✅ **Automatic Update Checks** - App checks on startup  
✅ **One-Click Updates** - Users just click "Update Now"  
✅ **Secure Downloads** - SHA256 hash verification  
✅ **Rollback Protection** - Failed updates restore previous version  
✅ **Version Display** - Shows current version in the UI  
✅ **Progress Tracking** - Users see download/install progress  
✅ **Auto Restart** - App restarts automatically after update  

---

## Important Notes

### Before Each Build:
- ✅ Update `VERSION` in `build_app.py`
- ✅ Update `UPDATE_SERVER_URL` in `auto_updater.py` if needed

### After Each Build:
- ✅ Copy the SHA256 hash from build output
- ✅ Update `version.json` on your server with new hash
- ✅ Test the update before releasing to all users

### Security Best Practices:
- 🔒 Use HTTPS for your update server
- 🔒 Keep backups of old versions
- 🔒 Test updates thoroughly
- 🔒 Monitor server logs for issues

---

## Troubleshooting

**Problem:** "Auto-updater not available"  
**Solution:** Make sure `auto_updater.py` is in the same directory as `app.py`

**Problem:** Update fails to download  
**Solution:** Check that the URL in `version.json` is correct and accessible

**Problem:** Hash verification failed  
**Solution:** Re-copy the hash from build output to `version.json`

**Problem:** App won't restart after update  
**Solution:** Run as Administrator or check antivirus settings

---

## Next Steps

1. **Test locally** using the test server
2. **Set up production server** (AWS S3, web hosting, etc.)
3. **Build v1.0.0** and distribute to initial users
4. **Gather feedback** and make improvements
5. **Push v1.1.0** using the update system

---

## Need Help?

- Read `DEPLOYMENT_GUIDE.md` for detailed documentation
- Check the console output when running `build_app.py`
- Review logs in `%LOCALAPPDATA%\DenierAI\` on Windows

---

**You're all set!** 🎉

Your users can now download the app once and receive automatic updates forever!
