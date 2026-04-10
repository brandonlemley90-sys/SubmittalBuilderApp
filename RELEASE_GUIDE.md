# DenierAI Submittal Builder — Deployment Guide (Render.com)

This application is now a web-based service hosted on **Render.com**. The release process is fully automated via continuous integration with GitHub.

---

## 1. How Releases Work

The application uses a **Git-based deployment** strategy. Every time you push code to the `main` branch of the GitHub repository, Render automatically:

1.  Detects the new changes.
2.  Triggers a new build based on `render.yaml`.
3.  Installs dependencies from `requirements.txt`.
4.  Restarts the web service with the new code.
5.  Updates the live site at `https://submittalbuilderapp.onrender.com/`.

---

## 2. Pushing an Update

To release a new version of the application:

1.  **Commit your changes** locally.
2.  **Push to GitHub**:
    ```powershell
    git add .
    git commit -m "Description of your changes"
    git push origin main
    ```
3.  **Monitor Deployment**:
    - Go to the [Render Dashboard](https://dashboard.render.com/).
    - Select the `submittal-builder-app` service.
    - View the **"Events"** or **"Logs"** tab to see the build progress.

---

## 3. Persistent Data & Database

- **Database**: The app uses a Render PostgreSQL database. You can manage this through the Render dashboard under the "Databases" section.
- **Disk Storage**: Uploads and results are stored on a persistent 1GB disk. This ensures that files are not lost when the application restarts or redeploys.

---

## 4. Environment Variables

If you need to update secrets like `GEMINI_API_KEY` or `SMTP_PASS`:

1.  Go to the Render Dashboard.
2.  Select the `submittal-builder-app`.
3.  Navigate to **Environment**.
4.  Add or update keys and click "Save Changes". The app will restart automatically.

---

## 5. Troubleshooting Deployment

### Build Fails (Python Error)
Check the **Deployment Logs** on Render. Common causes include:
- Missing dependency in `requirements.txt`.
- Syntax error in a newly added file.
- Incompatible library version.

### Database Connection Issues
Ensure the `DATABASE_URL` environment variable is correctly linked from the Render PostgreSQL service. This is handled automatically by the `render.yaml` configuration.

---

*Last updated: 2026-04-10*
