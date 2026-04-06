# DenierAI Submittal Builder - Deployment Guide

## Overview

This guide explains how to build, distribute, and maintain your DenierAI Submittal Builder application with automatic updates.

---

## Quick Start

### For You (The Developer)

1. **Build the Application:**
   ```bash
   python build_app.py
   ```

2. **Set Up Your Update Server:**
   - Upload the `.zip` file from the `dist/` folder to your web server
   - Upload `server_version_template.json` as `version.json` to your server
   - Update `UPDATE_SERVER_URL` in `auto_updater.py` before building

3. **Distribute to Users:**
   - Send users the download link or the ZIP file
   - They run `install.bat` to install

### For End Users

1. Download the ZIP file
2. Extract it to a folder
3. Run `install.bat` as Administrator
4. Launch the app from the desktop shortcut
5. Updates will be checked automatically on startup

---

## How Auto-Updates Work

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User's App    │────▶│  Update Server   │────▶│  New Version    │
│  (v1.0.0)       │     │  (your-server)   │     │  (v1.1.0)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
       │                        │                        │
       │ 1. Check version       │                        │
       │◀───────────────────────│                        │
       │                        │                        │
       │ 2. Available?          │                        │
       │   Yes! v1.1.0          │                        │
       │◀───────────────────────│                        │
       │                        │                        │
       │ 3. Download ZIP        │                        │
       │◀───────────────────────│                        │
       │                        │                        │
       │ 4. Verify hash         │                        │
       │                        │                        │
       │ 5. Install & Restart   │                        │
       │                        │                        │
```

### Update Flow

1. **Check**: App contacts your server and downloads `version.json`
2. **Compare**: Compares current version with latest version
3. **Notify**: Shows update dialog if newer version available
4. **Download**: Downloads the new version ZIP file
5. **Verify**: Checks SHA256 hash for security
6. **Install**: Backs up old version, extracts new files
7. **Restart**: Automatically restarts with new version
8. **Cleanup**: Removes backup after successful restart

---

## Setting Up Your Update Server

### Option 1: Simple Web Server (Recommended for Small Teams)

1. **Create a directory on your web server:**
   ```
   /var/www/denierai-updates/
   ├── DenierAI_Submittal_Builder_v1.0.0.zip
   └── version.json
   ```

2. **Upload your build artifacts:**
   - The ZIP file from `dist/` folder
   - Rename `server_version_template.json` to `version.json`

3. **Update `version.json` with correct URLs:**
   ```json
   {
     "version": "1.0.0",
     "release_notes": "Initial release with auto-update",
     "download_url": "https://your-server.com/updates/DenierAI_Submittal_Builder_v1.0.0.zip",
     "file_hash": "sha256hash...",
     "release_date": "2024-01-01"
   }
   ```

4. **Configure `auto_updater.py`:**
   ```python
   UPDATE_SERVER_URL = "https://your-server.com/updates"
   ```

### Option 2: Cloud Storage (AWS S3, Google Cloud, etc.)

1. **Create an S3 bucket:**
   ```bash
   aws s3 mb s3://denierai-updates
   ```

2. **Upload files with public read access:**
   ```bash
   aws s3 cp dist/DenierAI_Submittal_Builder_v1.0.0.zip s3://denierai-updates/ --acl public-read
   aws s3 cp dist/server_version_template.json s3://denierai-updates/version.json --acl public-read
   ```

3. **Enable static website hosting** on the bucket

4. **Update URLs** in `version.json` to point to S3 URLs

### Option 3: GitHub Releases

1. **Create a new release** on GitHub
2. **Upload the ZIP** as a release asset
3. **Use GitHub API** to serve version information
4. **Update `auto_updater.py`** to use GitHub Releases API

---

## Building for Distribution

### Prerequisites

```bash
pip install flask pyinstaller werkzeug
```

### Build Process

```bash
# Clean build
python build_app.py
```

This will create:
- `dist/DenierAI_Submittal_Builder.exe` - The executable
- `dist/DenierAI_Submittal_Builder_v1.0.0.zip` - Distribution package
- `dist/install.bat` - Windows installer
- `dist/README.md` - User instructions
- `dist/server_version_template.json` - Server configuration

### Version Management

Before each build, update the version in `build_app.py`:

```python
VERSION = "1.1.0"  # Increment this
```

The build script will:
1. Clean previous builds
2. Install dependencies
3. Build executable with PyInstaller
4. Create version file
5. Package everything into a ZIP
6. Calculate SHA256 hash
7. Generate server configuration
8. Create installer and documentation

---

## Pushing Updates

### Step-by-Step Update Process

1. **Make your code changes**

2. **Increment version number** in `build_app.py`:
   ```python
   VERSION = "1.1.0"
   ```

3. **Rebuild the application:**
   ```bash
   python build_app.py
   ```

4. **Upload new files to server:**
   ```bash
   # Upload to your server
   scp dist/DenierAI_Submittal_Builder_v1.1.0.zip user@server:/var/www/updates/
   scp dist/server_version_template.json user@server:/var/www/updates/version.json
   ```

5. **Update `version.json`** on the server with:
   - New version number
   - Correct download URL
   - SHA256 hash (from build output)
   - Release notes

6. **Test the update** on a test machine

7. **Users receive update notification** next time they open the app

---

## Security Considerations

### File Integrity

- All updates are verified with SHA256 hash
- Failed updates automatically roll back
- Backup created before installation

### Best Practices

1. **Use HTTPS** for your update server
2. **Sign your releases** with a code signing certificate (optional but recommended)
3. **Keep backup** of previous versions on your server
4. **Test updates** thoroughly before releasing
5. **Monitor update adoption** through server logs

---

## Troubleshooting

### Common Issues

**"Auto-updater not available"**
- Make sure `auto_updater.py` is included in the build
- Check that all imports work correctly

**Update fails to download**
- Verify the download URL in `version.json`
- Check firewall settings
- Ensure HTTPS is working

**Hash verification failed**
- Re-upload the ZIP file (may have been corrupted)
- Regenerate the hash and update `version.json`

**App won't restart after update**
- Check that the executable has proper permissions
- Verify all required files were extracted

### Debug Mode

To debug update issues, check the console output when running from source:
```bash
python app.py
```

Or check logs in:
- Windows: `%LOCALAPPDATA%\DenierAI\logs\`

---

## Advanced Configuration

### Custom Update Server Response

Your `version.json` should follow this format:

```json
{
  "version": "1.1.0",
  "release_notes": "- New feature X\n- Bug fix Y\n- Performance improvements",
  "download_url": "https://your-server.com/updates/DenierAI_Submittal_Builder_v1.1.0.zip",
  "file_hash": "a1b2c3d4e5f6...",
  "release_date": "2024-01-15",
  "minimum_version": "1.0.0",
  "critical": false
}
```

### Forced Updates

For critical security updates, you can add logic to force updates by checking a `critical` flag in the version response.

### Staged Rollouts

Implement staged rollouts by:
1. Serving different `version.json` to different user groups
2. Using percentage-based rollout logic on the server
3. Monitoring for issues before full rollout

---

## Support

For questions or issues:
- Check the `README.md` in the distribution package
- Review logs in the app data directory
- Contact your system administrator

---

© 2024 DenierAI. All rights reserved.
