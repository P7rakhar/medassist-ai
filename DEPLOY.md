# Put MedAssist AI online for free (Render.com, about 15 minutes, browser only)

You get a public HTTPS link like `https://medassist-ai.onrender.com` that judges can open on any phone or laptop.
HTTPS also lets the microphone work on phones. No Docker and no payment needed.

> Note: Hugging Face Docker Spaces now need a paid PRO plan, so we use Render's free Python hosting instead.

## Step 1 — Put the code on GitHub (5 minutes)

1. Create a free account at https://github.com/signup (skip if you have one).
2. Go to https://github.com/new
   - **Repository name:** `medassist-ai`
   - **Public**
   - Leave "Add a README" **unticked**
   - Click **Create repository**.
3. On the next page click the link **"uploading an existing file"**.
4. Open your project folder (the one that contains `run.py`). First delete `medassist.db` and any `__pycache__`
   folders. Then select everything inside it (**Ctrl + A**) and drag it onto the GitHub page. Use Chrome or Edge.
5. Wait until every file is listed, then click **Commit changes**.
6. Check the repository page shows the `backend`, `frontend` and `tests` folders plus `requirements.txt` and `render.yaml`.

## Step 2 — Deploy on Render (5–10 minutes)

1. Go to https://render.com and click **Get Started** → **Sign up with GitHub**. Allow access.
2. Click **New +** → **Web Service** → choose your `medassist-ai` repository
   (if it isn't listed: **Configure account** → give Render access to that repository).
3. Fill in:
   | Setting | Value |
   |---|---|
   | Name | `medassist-ai` |
   | Language | **Python 3** |
   | Branch | `main` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
   | Instance Type | **Free** |
4. Open **Environment Variables** (or "Advanced") and add:
   - `PYTHON_VERSION` = `3.11.9`
   - `TZ` = `Asia/Kolkata`  (so appointment times are in Indian time)
5. Click **Create Web Service**. Watch the log; after 2–5 minutes it says **"Your service is live"**.
6. Your link is at the top of the page (`https://medassist-ai-xxxx.onrender.com`). Open it, then `/docs` and
   `/insights.html`. Test it on your phone, including the mic.

**Good to know**
- Free services **sleep after 15 minutes without visitors** and take about **1 minute** to wake up. Open the link
  a couple of minutes before any demo.
- The free disk is wiped when the service sleeps or restarts, so bookings and the case log start fresh. Fine for a demo.
- To update the live site later, upload changed files to GitHub again — Render redeploys automatically.
- If the deploy fails, copy the last red lines from Render's **Logs** tab.

## Optional settings (Render → your service → Environment)

| Name | What it does |
|---|---|
| `MEDASSIST_LLM_API_KEY` | Turns on the optional Llama 3 fallback (Groq key) |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Uses a Neo4j AuraDB Free instance. Also add `neo4j>=5.0` to `requirements.txt` |

## Other hosts

A `Dockerfile` is included for any host that runs containers (Google Cloud Run, Railway, a university server, or
Hugging Face Spaces with a PRO plan).

## Run it locally

```bash
pip install -r requirements.txt
python run.py
```
