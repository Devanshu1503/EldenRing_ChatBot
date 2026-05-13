# Elden Ring Convergence Mod Chatbot

A RAG-powered chatbot for Elden Ring with the Convergence overhaul mod.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
```

## Step 1 — Gather data (run once)

```bash
python scraper/scrape_convergence.py   # ~5 min
python scraper/scrape_fextralife.py    # ~2 min
python scraper/fetch_fanapi.py         # ~2 min
```

## Step 2 — Build the vector database (run once)

```bash
python rag/ingest.py
```

## Step 3 — Run the chatbot

```bash
streamlit run app/main.py
```

Open http://localhost:8501 in your browser.

## Deploy to Railway (share with friends)

1. Push this repo to GitHub (data/raw and rag/chroma_db are gitignored — see note below)
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variable: `ANTHROPIC_API_KEY=your-key`
4. Railway auto-detects the Procfile and deploys

> **Note on the vector DB:** The chroma_db folder is gitignored because it can be large.
> For deployment, either commit it (remove from .gitignore) or add a build step that runs
> the scrapers + ingest automatically on first deploy.
