# git-job

A personal job search automation and tracking system, built in Python.

## Versions

| Version | Status | Description |
|---|---|---|
| [job_tracker_v1](./job_tracker_v1) | Prototype | CLI-based scraper targeting Greenhouse and Indeed |
| [job_tracker_v2](./job_tracker_v2) | Active development | Company-first approach, LLM scoring, Streamlit dashboard |

## Quick Start

**Use v2** — it's the current, more capable version:

```bash
cd job_tracker_v2
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python scripts/seed_companies.py
```

See each version's README for full setup instructions.
