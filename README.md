# DenierAI Submittal Builder

A cloud-based web application for building electrical submittal packages. Hosted on **Render.com**, it provides a centralized dashboard for generating submittals using AI-powered builders.

---

## Accessing the Application

The production application is accessible at:
**[https://submittalbuilderapp.onrender.com/](https://submittalbuilderapp.onrender.com/)**

---

## For Developers — Running Locally

If you want to run the app locally for development:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the app
python app.py
```

The app will be available at `http://127.0.0.1:5002`.

---

## Deployment — Render.com

The application is configured for automatic deployment via `render.yaml`. Every push to the `main` branch of the source repository triggers a new build and deployment on Render.

## Project Structure

| File / Folder | Purpose |
|---|---|
| `app.py` | Main application entry point |
| `worker.py` | Local worker logic for processing intensive PDF tasks |
| `render.yaml` | Render.com deployment configuration |
| `requirements.txt` | Python dependencies |
| `templates/` | Jinja2 HTML templates |
| `static/` | CSS, JS, and branding assets |
| `version.json` | Current application version tracker |

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

© 2026 Brandon Lemley.
