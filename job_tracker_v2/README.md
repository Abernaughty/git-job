# Job Tracker v2

A personal job search and analytics system that monitors company job boards directly, uses Claude AI to score postings against your profile, and surfaces insights via a Streamlit dashboard.

## Design Philosophy

Rather than scraping aggregators (Indeed, LinkedIn), v2 uses a **company-first approach**:

- Maintain a curated list of target companies
- Monitor their job boards directly via **Greenhouse** and **Lever** APIs
- Get full, original job descriptions with no delay or truncation
- Score postings with LLM analysis for relevance to your profile

## Status

**Active development.** Core scraping and database layer complete. LLM scoring and Streamlit dashboard in progress.

## Tech Stack

- **Python 3.11+**
- **SQLite** — local database, no server required
- **httpx + BeautifulSoup** — async-capable scraping
- **Anthropic Claude** — LLM scoring and structured data extraction
- **Streamlit + Plotly** — analytics dashboard
- **APScheduler** — daily batch scheduling

## Quick Start

```bash
cd job_tracker_v2
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Seed the company list and initialize the database:

```bash
python scripts/seed_companies.py
```

Run a test scrape:

```bash
python scripts/test_scrape.py
```

## Project Structure

```
job_tracker_v2/
├── config/
│   ├── settings.py             # Pydantic settings with env var support
│   └── companies_seed.json     # Initial company list (Greenhouse/Lever slugs)
├── database/
│   ├── connection.py           # SQLite connection management
│   └── schema.sql              # Full database schema
├── models/
│   ├── company.py              # Company model (ATS platform, slug, metadata)
│   ├── posting.py              # Job posting model
│   └── skill.py                # Skill extraction model
├── scrapers/
│   ├── base.py                 # Abstract scraper interface
│   ├── greenhouse.py           # Greenhouse JSON API scraper
│   ├── lever.py                # Lever HTML scraper
│   └── scraper_service.py      # Orchestrates scraper runs
├── scripts/
│   ├── seed_companies.py       # Populate companies from seed file
│   ├── test_scrape.py          # Test scraping against live boards
│   ├── test_greenhouse_slugs.py
│   └── test_lever_slugs.py
├── tests/
│   ├── conftest.py
│   └── test_phase1_foundation.py
├── data/
│   └── job_search.db           # SQLite database (gitignored in production)
├── .env.example                # Environment variable template
├── pyproject.toml
├── requirements.txt
└── TESTING_PLAN.md
```

## Data Sources

### Greenhouse (Primary)
Uses the public JSON API — no HTML scraping, no auth required:
```
https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs
```

### Lever (Secondary)
Scrapes the public listing page and individual job detail pages.

### Future
- Manual URL input for one-off jobs
- Custom selectors for Workday/Taleo company pages

## Requirements

- Python 3.11+
- See `requirements.txt` for full dependency list
