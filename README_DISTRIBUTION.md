# 🚀 DenierAI Submittal Builder - No-ZIP Distribution System

## ✅ What You Get

A complete distribution system where users:
- **Download ONE file** (Setup_DenierAI_Submittal_Builder.exe)
- **Run it once** - automatically downloads and installs the full app
- **Get automatic updates** forever without you sending anything else

## 📦 Built Files

After running the build scripts, you'll have in `/workspace/dist/`:

| File | Size | Purpose |
|------|------|---------|
| `Setup_DenierAI_Submittal_Builder.exe` | ~8MB | **Give this to users!** |
| `DenierAI_Submittal_Builder_v1.0.0.zip` | ~16MB | Upload to your server |
| `server_version_template.json` | <1KB | Upload to your server as `version.json` |

## 🎯 Quick Start

### Step 1: Build Everything
```bash
python build_app.py
python build_bootstrap.py
```

### Step 2: Configure Server URL
Edit these files with your actual server URL:
- `auto_updater.py` (line 18)
- `bootstrap_installer.py` (line 15)

```python
UPDATE_SERVER_URL = "https://your-server.com/updates"
```

### Step 3: Upload to Your Server
Upload these two files to your web server:
1. `dist/DenierAI_Submittal_Builder_v1.0.0.zip`
2. `dist/server_version_template.json` (rename to `version.json`)

Your server should look like:
```
https://your-server.com/updates/
├── DenierAI_Submittal_Builder_v1.0.0.zip
└── version.json
```

### Step 4: Distribute to Users
Send users this single file:
- `dist/Setup_DenierAI_Submittal_Builder.exe`

They can get it from:
- Email attachment
- Your website download page
- Network share
- Cloud storage link

## 🔄 How Updates Work

### When You Make Changes:

1. Update version number in `build_app.py`:
   ```python
   VERSION = "1.0.1"  # Increment from 1.0.0
   ```

2. Rebuild:
   ```bash
   python build_app.py
   ```

3. Upload new files to server:
   - New ZIP file
   - Updated `version.json`

4. **Done!** Users will be notified next time they launch the app

### What Users Experience:

1. Launch the app
2. See notification: "Update available! Version 1.0.1"
3. Click "Update Now"
4. App downloads, installs, and restarts automatically
5. Continue working with new version

## 🛡️ Security Features

- ✅ SHA256 hash verification prevents tampered downloads
- ✅ HTTPS support for encrypted transfers
- ✅ Automatic rollback if update fails
- ✅ Version checking prevents downgrades

## 📝 Complete Documentation

See `DISTRIBUTION_GUIDE.md` for:
- Detailed setup instructions
- Server configuration examples (Apache, Nginx, AWS S3)
- Troubleshooting guide
- Testing procedures

## 💡 Key Benefits

| Traditional Method | This Solution |
|-------------------|---------------|
| Send large ZIP every update | Send ONE small installer |
| Users manually extract | Fully automatic install |
| Users might miss updates | Automatic notifications |
| You manage versions manually | Server-managed versions |
| Multiple support requests | Self-updating system |

## 🆘 Support

If users have issues:
1. Check internet connection
2. Verify server is accessible
3. Check console output for errors
4. Review `version.json` in installation folder

---

**Need help?** Check `DISTRIBUTION_GUIDE.md` for detailed documentation.
