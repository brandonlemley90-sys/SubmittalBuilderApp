#!/bin/bash
# Automated Update Server Setup Script
# This will help you set up the GitHub Pages update server

echo "========================================================================"
echo "  DENIERAI UPDATE SERVER - AUTOMATED SETUP"
echo "========================================================================"
echo ""

# Step 1: Build the app
echo "📦 Step 1: Building application..."
python build_app.py
if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi
echo ""

# Step 2: Run deployment helper
echo "🚀 Step 2: Preparing deployment files..."
echo "When prompted, use these values:"
echo "  - GitHub username: brandonlemley90-sys"
echo "  - Repository name: DenierSubmittalBuilderAgentUpdates (or press enter)"
echo ""
read -p "Press Enter to continue..."
python deploy_to_github.py

echo ""
echo "========================================================================"
echo "  ✅ FILES PREPARED SUCCESSFULLY!"
echo "========================================================================"
echo ""
echo "📁 Your deployment files are in: ./deploy_for_github/updates/"
echo ""
echo "NEXT STEPS (Do these manually in your browser):"
echo ""
echo "1. Go to: https://github.com/new"
echo "   - Repository name: DenierSubmittalBuilderAgentUpdates"
echo "   - Make it PUBLIC"
echo "   - Click 'Create repository'"
echo ""
echo "2. Enable GitHub Pages:"
echo "   - Go to Settings → Pages"
echo "   - Source: Deploy from a branch"
echo "   - Branch: main → Folder: / (root)"
echo "   - Click Save"
echo ""
echo "3. Upload your files:"
echo "   - In your GitHub repo, click 'Add file' → 'Upload files'"
echo "   - Drag EVERYTHING from ./deploy_for_github/updates/ folder"
echo "   - Click 'Commit changes'"
echo ""
echo "4. Wait 2-3 minutes for GitHub Pages to deploy"
echo ""
echo "5. Test it works:"
echo "   Visit: https://brandonlemley90-sys.github.io/DenierSubmittalBuilderAgentUpdates/updates/version.json"
echo ""
echo "6. When you see JSON (not 404), your update server is LIVE!"
echo ""
echo "========================================================================"
