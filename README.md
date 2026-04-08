# DenierAI Submittal Builder

A desktop application for building electrical submittal packages. Runs as a Windows `.exe` with a built-in web interface (Flask). Includes a live auto-update system — users receive new versions automatically every time they open the app.

---

## For Developers — Running From Source

If you want to run the app directly without building an executable:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the app
python app.py
```

The app will open a local browser window automatically.

---

## For Developers — Releasing & Distribution

See **[RELEASE_GUIDE.md](RELEASE_GUIDE.md)** for how to push updates.

See **[DISTRIBUTION_AND_TESTING_GUIDE.md](DISTRIBUTION_AND_TESTING_GUIDE.md)** for how to give the app to new users and how to test for yourself.

Short version:
1. Edit `VERSION` and `RELEASE_NOTES` at the top of `release.py`
2. Run `python release.py`
3. Copy-paste the git commands it prints

---

## How the Auto-Update System Works

Each time a user opens the app, it checks:
```
https://brandonlemley90-sys.github.io/DenierSubmittalBuilderUpdates/version.json
```

If the version number there is higher than what the user has installed, a blue update banner appears. The user clicks it, the update downloads and installs, and the app restarts — no manual steps needed on the user's end.

---

## Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | Main application entry point |
| `auto_updater.py` | Checks for updates and handles downloads |
| `bootstrap_installer.py` | First-time installer for new users |
| `release.py` | **← Use this to publish new releases** |
| `build_app.py` | Low-level build logic (called by release.py) |
| `build_bootstrap.py` | Builds the installer executable |
| `version.json` | Current version info (auto-updated by release.py) |
| `templates/` | HTML templates for the web UI |
| `static/` | CSS, JS, images |
| `dist/` | Build output (generated, not committed) |
| `release_output/` | Staged files ready to push (generated) |

---

## Builder Modules

| Module | What It Builds |
|---|---|
| `BoxesBuilder.py` | Electrical boxes submittal |
| `GroundingandBondingBuilder.py` | Grounding & bonding submittal |
| `HangersandSupports.py` | Hangers & supports submittal |
| `RacewaysBuilder.py` | Raceways submittal |
| `WireandCableBuilder.py` | Wire & cable submittal |
| `WiringDevicesBuilder.py` | Wiring devices submittal |
| `SubmittalBuilderMetaAgent.py` | AI meta-agent coordinator |

---

© 2026 DenierAI. All rights reserved.
