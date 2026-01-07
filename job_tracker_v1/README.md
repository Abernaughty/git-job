# Job Scraper & Application Tracker

Local-first job scraping and application tracking CLI.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r job_tracker/requirements.txt
```

```bash
python job_tracker/cli.py --help
```

## Config

- `job_tracker/config/settings.yaml`
- `job_tracker/config/searches.yaml`

## Data

SQLite database path is configured in `settings.yaml`.
