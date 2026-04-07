# FREE Web Server Setup Guide for DenierAI Updates

## Overview
You need a free web server to host two files:
1. `DenierAI_Submittal_Builder_vX.X.X.zip` - Your application package
2. `version.json` - Version information file

Here are the BEST FREE options:

---

## Option 1: GitHub Pages (RECOMMENDED - Easiest & Most Reliable)

### Why GitHub Pages?
- ✅ 100% Free forever
- ✅ No credit card required
- ✅ HTTPS included automatically
- ✅ Very reliable (hosted by GitHub)
- ✅ Easy to update files
- ✅ No server maintenance

### Step-by-Step Setup

#### 1. Create a GitHub Account
Go to https://github.com and sign up (free)

#### 2. Create a New Repository
- Click the "+" icon → "New repository"
- Name it: `denierai-updates` (or any name you like)
- Make it **Public**
- Click "Create repository"

#### 3. Enable GitHub Pages
- Go to your repository Settings
- Scroll down to "Pages" section
- Under "Source", select: `main` branch → `/ (root)`
- Click "Save"
- Wait 1-2 minutes for it to deploy

#### 4. Note Your URL
Your site will be at:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates
```

#### 5. Upload Your Files

**First time setup:**

Create a folder structure in your repository:
```
denierai-updates/
└── updates/
    ├── DenierAI_Submittal_Builder_v1.0.0.zip
    └── version.json
```

**How to upload:**
1. In your repository, click "Add file" → "Upload files"
2. Create a folder called `updates`
3. Drag and drop your ZIP file and version.json into the `updates` folder
4. Click "Commit changes"

#### 6. Update Your Configuration

Edit these files in your project:

**auto_updater.py:**
```python
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/denierai-updates/updates" 
```

**bootstrap_installer.py:**
```python
UPDATE_SERVER_URL = "https://brandonlemley90-sys.github.io/denierai-updates/updates"
```

#### 7. Rebuild Your App
```bash
python build_app.py
python build_bootstrap.py
```

#### 8. Test It
Visit in your browser:
```
https://brandonlemley90-sys.github.io/denierai-updates/updates/version.json
```

You should see the JSON content displayed.

---

## Option 2: Netlify Drop (Super Easy Alternative)

### Why Netlify?
- ✅ Free tier is generous
- ✅ Drag-and-drop deployment
- ✅ Automatic HTTPS
- ✅ Custom domain support (free)

### Step-by-Step Setup

#### 1. Sign Up
Go to https://www.netlify.com/ and sign up (free)

#### 2. Create a Site
- Click "Sites" → "Add new site" → "Deploy manually"
- Create a folder on your computer with this structure:
```
my-updates/
└── updates/
    ├── DenierAI_Submittal_Builder_v1.0.0.zip
    └── version.json
```

#### 3. Deploy
- Drag the `my-updates` folder to the Netlify drop zone
- Wait for deployment (usually < 30 seconds)
- Netlify gives you a URL like: `https://random-name.netlify.app`

#### 4. Configure Your App
Update the URLs in your Python files:
```python
UPDATE_SERVER_URL = "https://your-site-name.netlify.app/updates"
```

#### 5. Update Files Later
- Make changes to your local folder
- Drag and drop the folder again to Netlify
- It updates instantly!

---

## Option 3: Vercel (Another Great Option)

### Why Vercel?
- ✅ Free for personal use
- ✅ Fast global CDN
- ✅ Automatic HTTPS
- ✅ Git integration

### Step-by-Step Setup

#### 1. Sign Up
Go to https://vercel.com/ and sign up with GitHub

#### 2. Import a Repository
- Click "Add New" → "Project"
- Import your `denierai-updates` repository (from Option 1)
- Or create a new one

#### 3. Deploy
- Vercel auto-deploys static files
- You get a URL like: `https://your-project.vercel.app`

#### 4. Update Configuration
```python
UPDATE_SERVER_URL = "https://your-project.vercel.app/updates"
```

---

## Option 4: Google Drive (Not Recommended but Works)

⚠️ **Warning**: This is less reliable and has download limits, but it's an option if you have no other choice.

### Setup Steps

#### 1. Upload Files to Google Drive
- Create a folder called "DenierAI Updates"
- Upload your ZIP and version.json files
- Right-click folder → Share → "Anyone with the link"

#### 2. Get Direct Download Links
Google Drive doesn't give direct links easily. Use a service like:
- https://drive.google.com/drive/my-drive
- Right-click file → Share → Copy link
- Convert to direct link using: https://sites.google.com/site/gdocs2direct/

#### 3. Limitations
- ❌ 10GB/day download limit
- ❌ Links can break
- ❌ Not professional
- ❌ Users see Google Drive interface

**Only use this for testing or very small user bases!**

---

## Updating Your Application (All Methods)

### When You Release a New Version:

#### 1. Update Version Number
Edit `build_app.py`:
```python
VERSION = "1.0.1"  # Increment from 1.0.0
```

#### 2. Update Release Notes
In `build_app.py`:
```python
"release_notes": "Version 1.0.1 - Fixed bug with submittal exports"
```

#### 3. Rebuild
```bash
python build_app.py
```

#### 4. Upload New Files

**For GitHub Pages:**
- Go to your repository
- Click on the old ZIP file
- Click "Delete file" → "Commit changes"
- Click "Add file" → "Upload files"
- Upload the new ZIP
- Do the same for version.json (or edit it directly)
- Commit changes
- Wait 1-2 minutes for deployment

**For Netlify:**
- Replace files in your local folder
- Drag and drop the folder to Netlify again

**For Vercel:**
- Push to Git repository
- Vercel auto-deploys

#### 5. Users Get Updated Automatically!
Next time users launch the app:
- It checks version.json
- Sees new version available
- Shows update notification
- User clicks "Update Now"
- Done! ✅

---

## Creating version.json File

Your `version.json` should look like this:

```json
{
  "version": "1.0.1",
  "release_date": "2024-01-15",
  "release_notes": "- Fixed bug with PDF exports\n- Improved performance\n- Added new wire types",
  "download_url": "https://brandonlemley90-sys.github.io/denierai-updates/updates/DenierAI_Submittal_Builder_v1.0.1.zip",
  "file_hash": "SHA256_HASH_OF_ZIP_FILE",
  "minimum_version": "1.0.0"
}
```

### How to Get the SHA256 Hash:

**Windows PowerShell:**
```powershell
Get-FileHash -Algorithm SHA256 .\DenierAI_Submittal_Builder_v1.0.1.zip
```

**Mac/Linux Terminal:**
```bash
shasum -a 256 DenierAI_Submittal_Builder_v1.0.1.zip
```

**Python:**
```python
import hashlib
sha256_hash = hashlib.sha256()
with open("DenierAI_Submittal_Builder_v1.0.1.zip", "rb") as f:
    for byte_block in iter(lambda: f.read(4096), b""):
        sha256_hash.update(byte_block)
print(sha256_hash.hexdigest())
```

---

## Quick Comparison Table

| Method | Ease | Reliability | Speed | Best For |
|--------|------|-------------|-------|----------|
| **GitHub Pages** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Everyone (Recommended) |
| **Netlify** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Easy updates |
| **Vercel** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Git users |
| **Google Drive** | ⭐⭐ | ⭐⭐ | ⭐⭐ | Testing only |

---

## Troubleshooting

### "Could not check for updates" Error
- Verify your UPDATE_SERVER_URL is correct
- Check that version.json is accessible in browser
- Ensure CORS is enabled (GitHub Pages does this automatically)

### Download Fails
- Check that the ZIP file URL in version.json is correct
- Test the download URL directly in browser
- Verify file permissions (should be public)

### Users Behind Firewalls
- Some corporate firewalls block GitHub/Netlify
- Consider using a custom domain if needed
- Test from different networks

---

## My Recommendation

**Use GitHub Pages** because:
1. It's completely free forever
2. No maintenance required
3. HTTPS included automatically
4. Very reliable (backed by GitHub/Microsoft)
5. Easy to update via web interface
6. Professional and trustworthy for users

### Quick Start with GitHub Pages:

```bash
# 1. Install GitHub CLI (optional but helpful)
# Download from: https://cli.github.com/

# 2. Create and deploy in one go
gh repo create denierai-updates --public
# Add files via web interface at github.com/YOUR_USERNAME/denierai-updates
# Enable Pages in Settings
# Upload your files to /updates folder
```

That's it! Your update server is live! 🎉

---

## Need Help?

Common issues and solutions:

**Q: My version.json shows as plain text instead of JSON**
A: That's normal! The app reads it programmatically. Test by visiting the URL in browser.

**Q: Changes aren't showing up immediately**
A: GitHub Pages can take 1-2 minutes to deploy. Netlify/Vercel are faster (~30 seconds).

**Q: Can I use a custom domain?**
A: Yes! All these services support custom domains for free. Just configure DNS settings.

**Q: What if I exceed bandwidth limits?**
A: GitHub Pages: Very generous (100GB/month). Netlify: 100GB/month. Both are enough for thousands of users.

---

© 2024 DenierAI. All rights reserved.
