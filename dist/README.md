# DenierAI_Submittal_Builder v1.0.0

## Installation Instructions

### For End Users:

1. Download the ZIP file: `DenierAI_Submittal_Builder_v1.0.0.zip`
2. Extract the contents to a folder
3. Run `install.bat` as Administrator
4. A shortcut will be created on your desktop

### Manual Installation:

1. Download and extract the ZIP file
2. Copy all files to your desired installation folder (e.g., `C:\Program Files\DenierAI_Submittal_Builder`)
3. Create a shortcut to `DenierAI_Submittal_Builder.exe` on your desktop

## Auto-Update Feature

This application includes automatic update functionality:

1. When you start the app, it will check for updates automatically
2. If an update is available, you'll be prompted to download and install it
3. The update will download in the background and install automatically
4. The application will restart with the new version

### How Updates Work:

- The app checks a central server for new versions
- Updates are downloaded securely with hash verification
- Your settings and data are preserved during updates
- Failed updates automatically roll back to the previous version

## Requirements

- Windows 10 or later
- Internet connection (for initial setup and updates)
- Python 3.8+ (only if running from source)

## Running from Source (Developers)

If you want to run the application without building:

```bash
# Install dependencies
pip install flask werkzeug pyinstaller

# Run the application
python app.py
```

## For Administrators/Deployers

To set up the update server:

1. Host the ZIP file on a web server
2. Host the `server_version_template.json` file (rename to `version.json`)
3. Update the `UPDATE_SERVER_URL` in `auto_updater.py` before building
4. Distribute the built application to users

## Troubleshooting

### App won't start:
- Make sure you have administrator privileges
- Check if Windows Defender is blocking the app
- Try running as Administrator

### Updates failing:
- Check your internet connection
- Make sure your firewall allows the app
- Contact support if the problem persists

## Support

For issues or questions, please contact your system administrator.

---

© 2024 DenierAI. All rights reserved.
