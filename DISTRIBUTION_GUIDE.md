# DenierAI Submittal Builder - Distribution Without ZIP Files

## Overview

This solution eliminates the need to send ZIP files to users. Instead, users download a **single small installer executable** that automatically downloads and installs the latest version of your application.

## How It Works

### For You (The Developer)

1. **Make your changes** to the application code
2. **Run the build scripts**: 
   ```bash
   python build_app.py
   python build_bootstrap.py
   ```
3. **Upload to your server**:
   - Upload `DenierAI_Submittal_Builder_v1.0.0.zip` from `dist/` folder to your web server
   - Upload `server_version_template.json` as `version.json` to your server
4. **Distribute ONE file to users**: `Setup_DenierAI_Submittal_Builder.exe` (~8MB)
5. **Users automatically get notified** of future updates when they launch the app

### For Users (First Time Installation)

1. **Download ONE file**: `Setup_DenierAI_Submittal_Builder.exe` (~8 MB)
2. **Run the installer** - it automatically:
   - Checks internet connection
   - Downloads the latest full application from your server
   - Installs to Program Files
   - Creates desktop shortcut
   - Launches the app
3. **Done!** No ZIP extraction, no manual setup

### For Users (Future Updates)

1. **Launch the app** as usual
2. **Automatic update check** happens on startup
3. **If update available**: User clicks "Update Now"
4. **App downloads and installs** the update automatically
5. **App restarts** with the new version

## File Structure

```
/workspace/
├── app.py                      # Main application
├── auto_updater.py             # Auto-update functionality
├── bootstrap_installer.py      # Lightweight downloader/installer
├── build_app.py                # Builds the main application
├── build_bootstrap.py          # Builds the bootstrap installer
├── install.bat                 # Simple installer launcher
└── dist/                       # Output folder after building
    ├── Setup_DenierAI_Submittal_Builder.exe  ← Give this to users!
    ├── DenierAI_Submittal_Builder_v1.0.0.zip ← Upload to server
    └── server_version_template.json          ← Upload to server as version.json
```

## Setup Instructions

### Step 1: Configure Your Server

Edit `auto_updater.py` and `bootstrap_installer.py`:
```python
UPDATE_SERVER_URL = https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json"
```

Replace with your actual server URL where you'll host updates.

### Step 2: Build Everything

```bash
# Build the main application
python build_app.py

# Build the bootstrap installer
python build_bootstrap.py
```

### Step 3: Upload to Your Server

After building, upload these files to your server:

1. **ZIP package**: `dist/DenierAI_Submittal_Builder_v1.0.0.zip`
2. **Version info**: Rename `dist/server_version_template.json` to `version.json` and upload

Your server should have:
```
https://your-server.com/updates/
├── DenierAI_Submittal_Builder_v1.0.0.zip
└── version.json
```

### Step 4: Distribute to Users

Give users this single file:
- `dist/Setup_DenierAI_Submittal_Builder.exe`

They can download it from:
- Your website
- Email attachment
- File sharing service
- Network share

## Version Management

When releasing updates:

1. **Update version in `build_app.py`**:
   ```python
   VERSION = "1.0.1"  # Increment version
   ```

2. **Update release notes in `build_app.py`**:
   ```python
   "release_notes": f"Version {VERSION} - Bug fixes and improvements"
   ```

3. **Rebuild**:
   ```bash
   python build_app.py
   ```

4. **Upload new files to server**:
   - New ZIP file
   - Updated `version.json`

5. **Users automatically get notified** next time they launch the app!

## Server Configuration Examples

### Apache (.htaccess)
```apache
# Enable CORS for update server
Header set Access-Control-Allow-Origin "*"
Header set Access-Control-Allow-Methods "GET, OPTIONS"
```

### Nginx
```nginx
location /updates/ {
    add_header 'Access-Control-Allow-Origin' '*';
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS';
    autoindex on;
}
```

### AWS S3 Bucket Policy
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": ["s3:GetObject"],
        "Resource": ["arn:aws:s3:::your-bucket/updates/*"]
    }]
}
```

## Security Features

- ✅ **SHA256 hash verification** - Ensures downloaded files aren't corrupted or tampered with
- ✅ **HTTPS support** - Use HTTPS in your UPDATE_SERVER_URL for encrypted downloads
- ✅ **Automatic rollback** - Failed updates revert to previous version
- ✅ **Version checking** - Only updates to newer versions

## Troubleshooting

### Users can't download updates
- Check that your server is accessible
- Verify `UPDATE_SERVER_URL` is correct
- Ensure CORS headers are set properly
- Check firewall settings

### Update fails to install
- Run as Administrator
- Check antivirus isn't blocking
- Verify file permissions on installation directory

### App doesn't check for updates
- Internet connection required
- Check `auto_updater.py` configuration
- Look at console output for error messages

## Benefits Over ZIP Distribution

| Traditional ZIP | Bootstrap Installer |
|----------------|---------------------|
| ❌ Large file to send every time | ✅ Small installer (~2MB) |
| ❌ Manual extraction required | ✅ Fully automatic |
| ❌ Users might use old version | ✅ Always gets latest |
| ❌ You send files repeatedly | ✅ Send once, updates forever |
| ❌ No update notifications | ✅ Automatic update alerts |
| ❌ Manual installation steps | ✅ One-click install |

## Testing Locally

Before deploying to production, test locally:

1. **Set up local server**:
   ```bash
   python update_server.py
   ```

2. **Point to localhost**:
   ```python
   UPDATE_SERVER_URL = "http://localhost:8080"
   ```

3. **Build and test**:
   ```bash
   python build_app.py
   python build_bootstrap.py
   ```

4. **Run the installer** and verify everything works

## Support

For issues or questions about the distribution system, check:
- Console output for error messages
- `version.json` in installation directory
- Server logs for download requests

---

© 2024 DenierAI. All rights reserved.
