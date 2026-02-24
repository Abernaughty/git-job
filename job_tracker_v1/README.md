# Job Tracker v1

Prototype CLI for scraping job postings and tracking applications. Superseded by [v2](../job_tracker_v2).

## Status

**Prototype / deprecated.** Core scraping and storage works. Not actively maintained — see v2 for the current version.

## Features

- Scrapes job postings from **Greenhouse** and **Indeed**
- Stores results in a local **SQLite** database
- Parses job descriptions for experience level, qualifications, skills, and salary
- Tracks job applications separately from raw postings

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Initialize the database:

```bash
python cli.py init-db
```

Run configured searches:

```bash
python cli.py scrape
```

List stored jobs:

```bash
python cli.py jobs list
python cli.py jobs list --limit 50
python cli.py jobs list --since 2025-01-01
```

## Configuration

- `config/settings.yaml` — database path and scraper settings
- `config/searches.yaml` — define search queries (keywords, location, sources)

## Project Structure

```
job_tracker_v1/
├── cli.py                  # Entry point — Click CLI
├── config/
│   ├── settings.yaml       # Database and scraper config
│   └── searches.yaml       # Search definitions
├── models/
│   ├── database.py         # SQLite schema and initialization
│   ├── job.py              # Job model and queries
│   └── application.py      # Application tracking model
├── scrapers/
│   ├── base.py             # Abstract scraper base class
│   ├── greenhouse.py       # Greenhouse job board scraper
│   └── indeed.py           # Indeed scraper
├── parsers/
│   ├── experience.py       # Experience level extraction
│   ├── qualifications.py   # Qualifications parser
│   ├── salary.py           # Salary range parser
│   └── skills.py           # Skills extraction
├── services/
│   ├── scraper_service.py  # Orchestrates scraper runs
│   ├── job_service.py      # Job CRUD operations
│   ├── parser_service.py   # Runs parsers on job text
│   └── application_service.py
└── utils/
    ├── config.py           # YAML config loading
    ├── dedup.py            # Deduplication logic
    ├── rate_limit.py       # Rate limiting for scrapers
    └── text_cleaning.py    # Text normalization utilities
```

## Requirements

- Python 3.10+
- See `requirements.txt` for dependencies
