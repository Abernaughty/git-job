# Job Search & Analytics System - Implementation Guide

## Project Overview

A personal job search and analytics tool that aggregates job postings from multiple sources, extracts structured data using LLMs, scores postings against your profile, and provides analytics dashboards to identify trends and opportunities.

### Key Constraints
- **Personal use only** (single user, no auth needed)
- **Daily batch processing** (no real-time requirements)
- **90-day data retention** for raw postings (aggregates kept indefinitely)
- **US and Remote roles only**
- **Clearance**: Open to sponsored clearances, not requiring existing

### Tech Stack
- **Database**: SQLite (simple, portable, sufficient for personal use)
- **Backend**: Python 3.11+
- **LLM**: Claude API (or local model via Ollama as fallback)
- **GUI**: Streamlit
- **Scraping**: httpx + BeautifulSoup (async-capable)
- **Scheduling**: cron or APScheduler

---

## Data Sources

### Strategy: Company-First Monitoring

Rather than scraping job aggregators (Indeed, LinkedIn, ZipRecruiter), this system takes a **company-first approach**:

1. **Build a curated list** of target companies you'd want to work for
2. **Monitor their job boards** directly via Greenhouse and Lever APIs/pages
3. **See new roles immediately** (no aggregator indexing delay)
4. **Get full, original job descriptions** (not truncated)

This approach is:
- ✅ Legally clean (no robots.txt violations)
- ✅ Technically reliable (stable APIs, no anti-scraping measures)
- ✅ Higher quality data (original postings, not aggregated copies)

### 1. Greenhouse Boards (Primary)
- **URL Pattern**: `https://boards.greenhouse.io/{company_slug}`
- **API Endpoint**: `https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs` (JSON, no auth required)
- **Job Detail**: `https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs/{job_id}`
- **Approach**: Use the JSON API directly—no HTML scraping needed
- **Rate Limiting**: Generous, but still add 1-second delays
- **Data Available**: Title, location, department, description (HTML), job ID, updated_at

### 2. Lever (Secondary)
- **URL Pattern**: `https://jobs.lever.co/{company_slug}`
- **API Endpoint**: None public; scrape the HTML listing page
- **Job Detail**: `https://jobs.lever.co/{company_slug}/{job_id}`
- **Approach**: Parse listing page for job links, fetch each detail page
- **Rate Limiting**: Minimal concerns, but add 1-second delays for politeness
- **Data Available**: Title, location, team, commitment (full-time/part-time), description

### Future: Manual URL Input (Optional)
- **Approach**: Paste any job URL, system fetches page and uses LLM to extract data
- **Use Case**: Jobs from companies not using Greenhouse/Lever
- **Benefit**: No scraping needed—you're accessing as a user would

### Future: Custom Company Pages (Optional)
- **Approach**: Store custom CSS selectors or XPath per company for non-ATS pages
- **Use Case**: Large companies with custom career sites (Workday, Taleo, etc.)
- **Storage**: `companies.custom_scrape_config` JSON field for selector patterns

---

## Database Schema

### Core Tables

```sql
-- ============================================================
-- COMPANIES
-- ============================================================
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    website TEXT,
    careers_url TEXT,
    ats_platform TEXT,                    -- greenhouse, lever, workday, custom, unknown
    ats_slug TEXT,                        -- company identifier in ATS URL
    industry TEXT,
    size_bucket TEXT,                     -- startup (<50), small (50-200), medium (200-1000), 
                                          -- large (1000-10000), enterprise (10000+)
    headquarters_location TEXT,
    glassdoor_url TEXT,
    notes TEXT,
    is_active INTEGER DEFAULT 1,          -- 0 = stop scraping
    custom_scrape_config TEXT,            -- JSON: CSS selectors for custom pages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scraped_at TIMESTAMP
);

CREATE INDEX idx_companies_ats ON companies(ats_platform, ats_slug);
CREATE INDEX idx_companies_active ON companies(is_active);


-- ============================================================
-- TARGET ROLES (canonical job titles you're interested in)
-- ============================================================
CREATE TABLE target_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,           -- "Data Engineer", "Backend Developer"
    aliases TEXT,                         -- JSON array: ["Data Platform Engineer", "DE"]
    min_salary_target INTEGER,            -- your minimum acceptable salary
    max_salary_target INTEGER,            -- ideal salary ceiling for filtering
    priority INTEGER DEFAULT 5,           -- 1-10, higher = more interested
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- JOB POSTINGS (90-day retention)
-- ============================================================
CREATE TABLE postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES target_roles(id) ON DELETE SET NULL,
    
    -- Source tracking
    source_url TEXT NOT NULL UNIQUE,      -- dedupe key
    source_site TEXT NOT NULL,            -- indeed, greenhouse, lever, company_direct
    external_id TEXT,                     -- job ID from source system
    
    -- Raw data (preserved for re-parsing)
    raw_title TEXT NOT NULL,
    raw_description TEXT,                 -- full job description text
    raw_html TEXT,                        -- original HTML if needed
    posted_date DATE,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- LLM-extracted structured data
    normalized_title TEXT,
    seniority_level TEXT,                 -- junior, mid, senior, staff, principal, lead, 
                                          -- manager, director, vp, c_level
    salary_min INTEGER,
    salary_max INTEGER,
    salary_type TEXT,                     -- annual, hourly, contract
    salary_currency TEXT DEFAULT 'USD',
    experience_years_min INTEGER,
    experience_years_max INTEGER,
    education_requirement TEXT,           -- none, bachelors, masters, phd, or_equivalent
    
    -- Location & Remote
    location_raw TEXT,                    -- as listed
    location_city TEXT,
    location_state TEXT,
    remote_type TEXT,                     -- onsite, hybrid, remote_local, remote_us, remote_global
    
    -- Clearance
    clearance_required TEXT,              -- none, public_trust, secret, top_secret, ts_sci
    clearance_sponsorship TEXT,           -- yes, no, unknown
    
    -- Extracted metadata
    department TEXT,
    team TEXT,
    reports_to TEXT,
    travel_requirement TEXT,              -- none, occasional, frequent, extensive
    visa_sponsorship TEXT,                -- yes, no, unknown
    benefits_summary TEXT,                -- JSON array of notable benefits
    red_flags TEXT,                       -- JSON array of concerning phrases
    
    -- Scoring & Status
    match_score REAL,                     -- 0.0 to 1.0
    skill_match_details TEXT,             -- JSON: breakdown of matched/missing skills
    
    status TEXT DEFAULT 'new',            -- new, reviewing, saved, applied, phone_screen, 
                                          -- interview, offer, rejected, withdrawn, closed
    interest_level INTEGER,               -- 1-5 user rating after review
    notes TEXT,
    
    -- Application tracking
    applied_at TIMESTAMP,
    application_method TEXT,              -- direct, linkedin, referral, recruiter
    resume_version TEXT,                  -- which resume variant used
    cover_letter_notes TEXT,
    
    -- Processing metadata
    parse_version TEXT,                   -- track which prompt/model version parsed this
    parse_confidence REAL,                -- LLM's self-reported confidence
    needs_reparse INTEGER DEFAULT 0,      -- flag for re-extraction
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_postings_company ON postings(company_id);
CREATE INDEX idx_postings_role ON postings(role_id);
CREATE INDEX idx_postings_status ON postings(status);
CREATE INDEX idx_postings_match ON postings(match_score DESC);
CREATE INDEX idx_postings_date ON postings(posted_date DESC);
CREATE INDEX idx_postings_source ON postings(source_site, source_url);
CREATE INDEX idx_postings_first_seen ON postings(first_seen_at);


-- ============================================================
-- SKILLS (normalized skill dictionary)
-- ============================================================
CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,            -- canonical name: "Python", "Kubernetes"
    aliases TEXT,                         -- JSON: ["python3", "py"]
    category TEXT,                        -- language, framework, database, cloud, tool, 
                                          -- methodology, soft_skill, certification, domain
    parent_skill_id INTEGER REFERENCES skills(id),  -- for hierarchies: React -> JavaScript
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skills_category ON skills(category);


-- ============================================================
-- POSTING SKILLS (many-to-many with requirement level)
-- ============================================================
CREATE TABLE posting_skills (
    posting_id INTEGER REFERENCES postings(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES skills(id) ON DELETE CASCADE,
    requirement_level TEXT,               -- required, preferred, nice_to_have
    years_requested INTEGER,              -- if specified: "5+ years Python"
    context TEXT,                         -- original phrase from posting
    PRIMARY KEY (posting_id, skill_id)
);

CREATE INDEX idx_posting_skills_skill ON posting_skills(skill_id);


-- ============================================================
-- MY PROFILE (your skills and preferences)
-- ============================================================
CREATE TABLE my_skills (
    skill_id INTEGER PRIMARY KEY REFERENCES skills(id),
    proficiency TEXT,                     -- learning, familiar, competent, proficient, expert
    years_experience REAL,
    last_used_date DATE,                  -- for tracking skill freshness
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE my_preferences (
    key TEXT PRIMARY KEY,
    value TEXT,                           -- JSON for complex values
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Example preferences:
-- min_salary: 150000
-- preferred_remote_types: ["remote_us", "remote_global"]
-- excluded_industries: ["gambling", "tobacco"]
-- preferred_company_sizes: ["startup", "small", "medium"]
-- location_preferences: {"willing_to_relocate": ["Austin", "Denver"], "preferred": "remote"}


-- ============================================================
-- APPLICATION EVENTS (detailed tracking)
-- ============================================================
CREATE TABLE application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    posting_id INTEGER REFERENCES postings(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,             -- applied, phone_screen_scheduled, interview_scheduled,
                                          -- interview_completed, offer_received, rejected, 
                                          -- withdrew, follow_up_sent, response_received
    event_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    contact_name TEXT,
    contact_email TEXT,
    contact_title TEXT,
    next_action TEXT,
    next_action_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_app_events_posting ON application_events(posting_id);
CREATE INDEX idx_app_events_date ON application_events(event_date DESC);
CREATE INDEX idx_app_events_next_action ON application_events(next_action_date);


-- ============================================================
-- WEEKLY SNAPSHOTS (aggregates, kept indefinitely)
-- ============================================================
CREATE TABLE weekly_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,             -- Monday of the week
    role_id INTEGER REFERENCES target_roles(id),
    
    -- Volume metrics
    total_postings INTEGER,
    new_postings INTEGER,
    closed_postings INTEGER,
    unique_companies INTEGER,
    
    -- Salary metrics (from postings with salary data)
    salary_data_count INTEGER,
    avg_salary_min REAL,
    avg_salary_max REAL,
    median_salary_min REAL,
    median_salary_max REAL,
    
    -- Experience metrics
    avg_experience_min REAL,
    avg_experience_max REAL,
    
    -- Remote breakdown
    remote_count INTEGER,
    hybrid_count INTEGER,
    onsite_count INTEGER,
    
    -- Top skills (JSON array of {skill, count, pct})
    top_required_skills TEXT,
    top_preferred_skills TEXT,
    emerging_skills TEXT,                 -- skills growing vs previous weeks
    declining_skills TEXT,                -- skills shrinking vs previous weeks
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(week_start, role_id)
);

CREATE INDEX idx_snapshots_week ON weekly_snapshots(week_start DESC);
CREATE INDEX idx_snapshots_role ON weekly_snapshots(role_id);


-- ============================================================
-- SCRAPE LOG (debugging and monitoring)
-- ============================================================
CREATE TABLE scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_site TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT,                          -- success, partial, failed
    postings_found INTEGER,
    postings_new INTEGER,
    postings_updated INTEGER,
    error_message TEXT,
    duration_seconds REAL
);

CREATE INDEX idx_scrape_log_date ON scrape_log(started_at DESC);
CREATE INDEX idx_scrape_log_company ON scrape_log(company_id);
```

### Key Design Decisions

1. **Normalized skills table**: Allows consistent tracking across postings and enables skill trend analysis. The `aliases` field handles variations ("k8s" → "Kubernetes").

2. **Separate application_events**: Tracks the full timeline of each application, not just current status. Useful for understanding your pipeline and response rates.

3. **parse_version tracking**: When you improve your LLM extraction prompt, you can identify which postings were parsed with older versions and re-process them.

4. **weekly_snapshots with emerging/declining skills**: Pre-computed trend data makes dashboard rendering fast and enables "what's hot" analysis.

---

## Project Structure

```
job_search_system/
├── config/
│   ├── settings.py              # Environment vars, API keys, paths
│   ├── logging_config.py        # Structured logging setup
│   └── companies_seed.json      # Initial companies to track
│
├── database/
│   ├── connection.py            # SQLite connection management
│   ├── schema.sql               # Full schema (above)
│   ├── migrations/              # Schema version changes
│   │   └── 001_initial.sql
│   └── queries.py               # Common query functions
│
├── scrapers/
│   ├── base.py                  # Abstract base scraper class
│   ├── greenhouse.py            # Greenhouse API client
│   ├── lever.py                 # Lever HTML scraper
│   └── utils.py                 # Rate limiting, user agents, retry logic
│
├── llm/
│   ├── client.py                # Claude API wrapper with retry/fallback
│   ├── prompts/
│   │   ├── extract_posting.txt  # Main extraction prompt
│   │   ├── normalize_title.txt  # Title normalization prompt
│   │   └── find_careers_url.txt # Company research prompt
│   ├── extraction.py            # Parse posting → structured data
│   └── validation.py            # Validate/clean LLM outputs
│
├── processing/
│   ├── pipeline.py              # Main daily pipeline orchestration
│   ├── scoring.py               # Match score calculation
│   ├── deduplication.py         # Detect duplicate postings
│   ├── aggregation.py           # Weekly snapshot generation
│   └── cleanup.py               # 90-day retention enforcement
│
├── models/
│   ├── company.py               # Company dataclass/ORM
│   ├── posting.py               # Posting dataclass/ORM
│   ├── skill.py                 # Skill dataclass/ORM
│   └── profile.py               # User profile management
│
├── gui/
│   ├── app.py                   # Main Streamlit entry point
│   ├── pages/
│   │   ├── 01_dashboard.py      # Home / daily digest
│   │   ├── 02_search.py         # Search and filter postings
│   │   ├── 03_companies.py      # Company management
│   │   ├── 04_applications.py   # Application pipeline tracker
│   │   ├── 05_analytics.py      # Charts and trends
│   │   └── 06_settings.py       # Profile, preferences, config
│   ├── components/
│   │   ├── posting_card.py      # Reusable posting display
│   │   ├── filters.py           # Filter sidebar components
│   │   └── charts.py            # Chart builders
│   └── styles.css               # Custom styling
│
├── scripts/
│   ├── run_pipeline.py          # CLI to trigger daily processing
│   ├── add_company.py           # CLI to add a company
│   ├── reparse_postings.py      # Re-run LLM on old postings
│   └── export_data.py           # Export to CSV/Excel
│
├── tests/
│   ├── test_scrapers/
│   ├── test_extraction/
│   └── fixtures/                # Sample HTML/JSON for testing
│
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Daily Processing Pipeline

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: SCRAPE                                                             │
│ ─────────────────                                                           │
│ For each active company:                                                    │
│   1. Determine scraper type (greenhouse/lever)                              │
│   2. Fetch job listing page(s)                                              │
│   3. Extract job URLs and basic metadata                                    │
│   4. For new URLs not in DB:                                                │
│      - Fetch full job description                                           │
│      - Store raw data in postings table                                     │
│   5. For existing URLs:                                                     │
│      - Update last_seen_at timestamp                                        │
│   6. Log results to scrape_log                                              │
│                                                                             │
│ Parallelism: Run scrapers concurrently (max 3) but serialize per-domain     │
│ Error handling: Log failures, continue with other companies                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: EXTRACT (LLM)                                                      │
│ ──────────────────────                                                      │
│ For each posting with raw_description but no normalized_title:              │
│   1. Send to LLM with extraction prompt                                     │
│   2. Parse JSON response                                                    │
│   3. Validate and clean extracted fields                                    │
│   4. Match/create skills in skills table                                    │
│   5. Link skills via posting_skills                                         │
│   6. Map to target_role if title matches                                    │
│   7. Update posting with structured data                                    │
│                                                                             │
│ Batching: Process in batches of 10 to manage API costs                      │
│ Retry: 3 attempts with exponential backoff on API errors                    │
│ Fallback: Mark as needs_reparse=1 if extraction fails                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: SCORE                                                              │
│ ─────────────                                                               │
│ For each posting with match_score IS NULL:                                  │
│   1. Load posting skills and requirement levels                             │
│   2. Load my_skills profile                                                 │
│   3. Calculate component scores:                                            │
│      - required_skill_match (0-1): % of required skills you have            │
│      - preferred_skill_match (0-1): % of preferred skills you have          │
│      - salary_fit (0-1): how well salary matches your range                 │
│      - experience_fit (0-1): does your experience match requirements        │
│      - clearance_eligible (0 or 1): can you get the clearance               │
│      - remote_fit (0-1): matches your remote preference                     │
│   4. Weighted combination → final match_score                               │
│   5. Store component breakdown in skill_match_details JSON                  │
│                                                                             │
│ Weights (configurable):                                                     │
│   required_skills: 0.35                                                     │
│   preferred_skills: 0.15                                                    │
│   salary_fit: 0.20                                                          │
│   experience_fit: 0.10                                                      │
│   clearance_eligible: 0.10                                                  │
│   remote_fit: 0.10                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: AGGREGATE (weekly, on Sundays)                                     │
│ ─────────────────────────────────────────                                   │
│ For each target_role:                                                       │
│   1. Count postings from past week                                          │
│   2. Calculate salary statistics                                            │
│   3. Aggregate skill frequencies                                            │
│   4. Compare to previous week for emerging/declining skills                 │
│   5. Insert into weekly_snapshots                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: DETECT CLOSED                                                      │
│ ──────────────────────                                                      │
│ For each posting not seen in last 7 days:                                   │
│   - If status in ('new', 'reviewing', 'saved'):                             │
│       - Update status = 'closed'                                            │
│   - Preserves applied/interview/offer statuses                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 6: CLEANUP                                                            │
│ ──────────────────                                                          │
│ Delete from postings WHERE:                                                 │
│   - first_seen_at < (now - 90 days)                                         │
│   - AND status NOT IN ('applied', 'phone_screen', 'interview', 'offer')     │
│                                                                             │
│ Cascade deletes posting_skills automatically                                │
│ Note: Never delete postings you've applied to (historical record)           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 7: NOTIFY (optional)                                                  │
│ ──────────────────────────                                                  │
│ If high-match postings found (score > 0.8):                                 │
│   - Generate summary email/notification                                     │
│   - Include top 5-10 new matches with key details                           │
│   - Send via configured notification channel                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Configuration

```python
# config/pipeline_config.py

PIPELINE_CONFIG = {
    "scraping": {
        "max_concurrent_scrapers": 3,
        "request_delay_seconds": 2.0,
        "request_timeout_seconds": 30,
        "max_retries": 3,
        "user_agent_rotation": True,
    },
    "extraction": {
        "batch_size": 10,
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "retry_attempts": 3,
        "cost_limit_daily_usd": 5.00,  # stop if exceeded
    },
    "scoring": {
        "weights": {
            "required_skills": 0.35,
            "preferred_skills": 0.15,
            "salary_fit": 0.20,
            "experience_fit": 0.10,
            "clearance_eligible": 0.10,
            "remote_fit": 0.10,
        },
        "high_match_threshold": 0.75,
    },
    "retention": {
        "days_to_keep": 90,
        "protected_statuses": ["applied", "phone_screen", "interview", "offer"],
    },
    "aggregation": {
        "run_day": "sunday",
        "skill_top_n": 20,
    },
    "notifications": {
        "enabled": False,
        "min_score_to_notify": 0.80,
        "max_notifications_per_day": 10,
        "channel": "email",  # or "slack", "pushover"
    },
}
```

---

## LLM Integration

### Extraction Prompt

```
You are extracting structured data from a job posting. Be precise and conservative—if information isn't clearly stated, use null rather than guessing.

IMPORTANT GUIDELINES:
- Salary: Only extract if explicitly stated. Convert hourly to annual (×2080). Ignore "competitive" or "DOE".
- Experience: Look for patterns like "5+ years", "3-5 years", "senior level" (implies 5+).
- Remote: Distinguish between "remote within US", "fully remote", "hybrid", "remote [city] only".
- Clearance: Note both requirement level AND whether sponsorship is mentioned.
- Skills: Separate truly required ("must have", "required") from preferred ("nice to have", "bonus").

JOB POSTING:
---
Title: {raw_title}
Company: {company_name}
Location: {location_raw}

{raw_description}
---

Extract as JSON with this exact structure:
{
  "normalized_title": "string - standardized title without company-specific prefixes/levels",
  "seniority_level": "junior|mid|senior|staff|principal|lead|manager|director|vp|c_level|null",
  
  "salary_min": "integer or null",
  "salary_max": "integer or null", 
  "salary_type": "annual|hourly|null",
  
  "experience_years_min": "integer or null",
  "experience_years_max": "integer or null",
  "education_requirement": "none|bachelors|masters|phd|or_equivalent|null",
  
  "location_city": "string or null",
  "location_state": "2-letter code or null",
  "remote_type": "onsite|hybrid|remote_local|remote_us|remote_global|null",
  
  "clearance_required": "none|public_trust|secret|top_secret|ts_sci|null",
  "clearance_sponsorship": "yes|no|unknown",
  
  "department": "string or null",
  "team": "string or null",
  "reports_to": "string or null",
  "travel_requirement": "none|occasional|frequent|extensive|null",
  "visa_sponsorship": "yes|no|unknown",
  
  "skills": [
    {
      "name": "canonical skill name",
      "category": "language|framework|database|cloud|tool|methodology|soft_skill|certification|domain",
      "level": "required|preferred|nice_to_have",
      "years": "integer or null if specific years mentioned"
    }
  ],
  
  "benefits_highlights": ["array of notable benefits worth tracking"],
  "red_flags": ["array of concerning phrases - e.g., 'rockstar', 'wear many hats', 'fast-paced']",
  
  "parse_confidence": "0.0-1.0 - your confidence in this extraction"
}

Return ONLY valid JSON, no commentary.
```

### Title Normalization Logic

The LLM handles most normalization, but apply these post-processing rules:

1. **Remove company prefixes**: "Acme Corp - Software Engineer" → "Software Engineer"
2. **Standardize levels**: "SDE II", "Software Engineer 2", "Mid-Level SWE" → "Software Engineer" with seniority_level="mid"
3. **Map to target_roles**: Fuzzy match normalized_title against target_roles.title and aliases

### Skill Normalization

```python
# Common aliases to handle
SKILL_ALIASES = {
    "python": ["python3", "py", "python 3.x"],
    "javascript": ["js", "es6", "ecmascript"],
    "typescript": ["ts"],
    "kubernetes": ["k8s", "kube"],
    "postgresql": ["postgres", "psql", "pg"],
    "amazon web services": ["aws", "amazon aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    # ... expand as you encounter variations
}

def normalize_skill(raw_skill: str) -> str:
    """Return canonical skill name."""
    lower = raw_skill.lower().strip()
    for canonical, aliases in SKILL_ALIASES.items():
        if lower == canonical or lower in aliases:
            return canonical.title()
    return raw_skill.title()
```

### Cost Management

With Claude API, a typical job posting extraction costs ~$0.01-0.02. For 100 postings/day:
- Daily cost: ~$1-2
- Monthly cost: ~$30-60

Implement a daily cost limit check that pauses extraction if exceeded.

---

## Match Scoring Algorithm

### Component Scores

```python
def calculate_match_score(posting, my_skills, my_preferences):
    """
    Returns (final_score, component_breakdown_dict)
    """
    components = {}
    
    # 1. Required Skills Match
    required = get_posting_skills(posting.id, level='required')
    if required:
        matched = sum(1 for s in required if s.skill_id in my_skills)
        components['required_skills'] = matched / len(required)
    else:
        components['required_skills'] = 1.0  # No requirements = full match
    
    # 2. Preferred Skills Match
    preferred = get_posting_skills(posting.id, level='preferred')
    if preferred:
        matched = sum(1 for s in preferred if s.skill_id in my_skills)
        components['preferred_skills'] = matched / len(preferred)
    else:
        components['preferred_skills'] = 0.5  # Neutral if none listed
    
    # 3. Salary Fit
    min_salary = my_preferences.get('min_salary', 0)
    if posting.salary_max and posting.salary_max < min_salary:
        components['salary_fit'] = posting.salary_max / min_salary  # Partial credit
    elif posting.salary_min and posting.salary_min >= min_salary:
        components['salary_fit'] = 1.0
    elif posting.salary_min is None and posting.salary_max is None:
        components['salary_fit'] = 0.5  # Unknown = neutral
    else:
        components['salary_fit'] = 0.7  # Overlapping range
    
    # 4. Experience Fit
    my_years = my_preferences.get('years_experience', 5)
    if posting.experience_years_max and my_years > posting.experience_years_max + 3:
        components['experience_fit'] = 0.5  # Likely overqualified
    elif posting.experience_years_min and my_years < posting.experience_years_min:
        # How close are you?
        gap = posting.experience_years_min - my_years
        components['experience_fit'] = max(0, 1 - (gap * 0.2))
    else:
        components['experience_fit'] = 1.0
    
    # 5. Clearance Eligibility
    if posting.clearance_required == 'none':
        components['clearance_eligible'] = 1.0
    elif posting.clearance_sponsorship == 'yes':
        components['clearance_eligible'] = 0.9  # Sponsorship available
    elif posting.clearance_sponsorship == 'unknown':
        components['clearance_eligible'] = 0.5  # Uncertain
    else:
        components['clearance_eligible'] = 0.0  # Required but no sponsorship
    
    # 6. Remote Fit
    preferred_remote = my_preferences.get('remote_types', ['remote_us', 'remote_global'])
    if posting.remote_type in preferred_remote:
        components['remote_fit'] = 1.0
    elif posting.remote_type == 'hybrid':
        components['remote_fit'] = 0.6
    elif posting.remote_type == 'onsite':
        components['remote_fit'] = 0.2
    else:
        components['remote_fit'] = 0.5  # Unknown
    
    # Weighted combination
    weights = PIPELINE_CONFIG['scoring']['weights']
    final_score = sum(
        components[k] * weights[k] 
        for k in weights.keys()
    )
    
    return final_score, components
```

### Disqualifying Conditions

Some conditions should zero out the score entirely:

```python
# Hard disqualifiers (before scoring)
def is_disqualified(posting, my_preferences):
    # Clearance required without sponsorship
    if (posting.clearance_required not in ('none', None) and 
        posting.clearance_sponsorship == 'no'):
        return True, "Clearance required, no sponsorship"
    
    # Salary way below minimum
    min_salary = my_preferences.get('min_salary')
    if min_salary and posting.salary_max and posting.salary_max < min_salary * 0.7:
        return True, "Salary below threshold"
    
    # Excluded industries
    excluded = my_preferences.get('excluded_industries', [])
    if posting.company.industry in excluded:
        return True, f"Excluded industry: {posting.company.industry}"
    
    return False, None
```

---

## Streamlit GUI

### Page Structure

#### 1. Dashboard (Home)

**Purpose**: Daily digest view—what's new and actionable.

**Sections**:
- **Today's Top Matches**: New postings (last 24h) with score > 0.75, sorted by score
- **Needs Attention**: Applications awaiting follow-up, upcoming interviews
- **Quick Stats Card**:
  - New postings today / this week
  - Active applications in pipeline
  - Companies actively hiring
  - Average match score trend

**Key Components**:
- Posting cards with: Title, Company, Salary range, Match score badge, Quick actions (Save, Apply, Dismiss)
- Mini calendar showing interview/follow-up dates

#### 2. Search & Filter

**Purpose**: Full posting explorer with powerful filtering.

**Filters (Sidebar)**:
- Target roles (multi-select from target_roles)
- Companies (multi-select with search)
- Match score range (slider: 0-100%)
- Salary range (dual slider)
- Remote type (checkboxes)
- Status (new, saved, applied, etc.)
- Posted date range
- Clearance (none only / include sponsored / all)
- Skills (include/exclude specific skills)
- Full-text search on title + description

**Results Area**:
- Sortable table or card view (toggle)
- Columns: Title, Company, Location, Salary, Remote, Score, Status, Posted
- Click to expand full details inline
- Bulk actions: Save selected, Mark as reviewed, Export

**Detail View (Expanded)**:
- Full job description (rendered markdown)
- Skill match breakdown (visual: green=have, yellow=learning, red=missing)
- Company info sidebar
- Action buttons: Apply, Save, Add Note, Mark Closed

#### 3. Companies

**Purpose**: Manage tracked companies and see per-company insights.

**List View**:
- All companies with: Name, Industry, Size, ATS type, Last scraped, Open postings count
- Filters: Industry, Size, ATS platform, Has open postings
- Sort: Name, Posting count, Last scraped

**Add Company Form**:
- Name (required)
- Website URL → Auto-detect careers page and ATS platform
- Manual override for careers_url and ats_slug
- Industry, Size (dropdowns)
- Notes

**Company Detail View**:
- Basic info + edit form
- Current open postings list
- Historical posting count chart
- Common skills requested (from their postings)
- Salary ranges by role
- Your application history with this company

#### 4. Applications

**Purpose**: Kanban-style application pipeline tracker.

**Pipeline Columns**:
```
┌──────────┐  ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌──────────┐
│  Saved   │→ │ Applied  │→ │Phone Screen│→ │ Interview │→ │  Offer   │
│   (12)   │  │   (5)    │  │    (2)     │  │    (1)    │  │   (0)    │
├──────────┤  ├──────────┤  ├────────────┤  ├───────────┤  ├──────────┤
│ Card 1   │  │ Card A   │  │  Card X    │  │  Card Z   │  │          │
│ Card 2   │  │ Card B   │  │  Card Y    │  │           │  │          │
│ ...      │  │ ...      │  │            │  │           │  │          │
└──────────┘  └──────────┘  └────────────┘  └───────────┘  └──────────┘
```

**Card Info**:
- Company logo/name
- Job title
- Days in current stage
- Next action/date (if set)
- Click to expand: full timeline, notes, contacts

**Separate Sections**:
- **Rejected/Withdrawn**: Collapsed archive
- **Closed**: Jobs that disappeared before you applied

**Timeline Detail (Per Application)**:
- Event list: Applied → Response → Interview Scheduled → etc.
- Add event form: Type, Date, Notes, Contact info
- Set next action reminder
- Rich notes field (markdown supported)

#### 5. Analytics

**Purpose**: Trends and insights to inform your job search strategy.

**Dashboard Sections**:

a) **Skill Demand Heatmap**
   - X-axis: Weeks, Y-axis: Top 20 skills
   - Color intensity: Frequency of appearance
   - Filter by target role

b) **Salary Trends**
   - Line chart: Average min/max salary over time
   - Filter by role, location, remote type
   - Benchmark lines: Your target salary, market median

c) **Your Skill Gaps**
   - Bar chart: Most-requested skills you don't have
   - Weighted by: How often required vs preferred, match score impact
   - Actionable: "Learning Python would increase match scores by ~15%"

d) **Market Overview**
   - Posting volume by role (bar chart)
   - Company hiring activity (who's posting most)
   - Remote vs onsite trend

e) **Your Funnel Metrics**
   - Applications sent → Responses → Interviews → Offers
   - Response rate by company size, role type
   - Average time in each pipeline stage

#### 6. Settings

**Sections**:

a) **My Profile**
   - Skills inventory (add/edit/remove, with proficiency levels)
   - Experience summary (years, key highlights)
   - Preferences: Min salary, preferred remote types, excluded industries

b) **Target Roles**
   - CRUD for roles you're tracking
   - Set aliases, salary targets, priority

c) **Data Sources**
   - Toggle Greenhouse, Lever scrapers on/off
   - Manage company list (bulk import/export)
   - Add new company (auto-detect ATS platform)
   - Test scraper on a specific company

d) **Pipeline Settings**
   - Scoring weights (sliders that sum to 1.0)
   - Notification preferences
   - Data retention (view/edit 90-day default)

e) **System**
   - View scrape logs
   - Trigger manual pipeline run
   - Export all data (SQLite file or CSV bundle)
   - Reset/clear database

---

## Scraper Implementation Notes

### Base Scraper Class

```python
# scrapers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import httpx
from datetime import datetime

@dataclass
class ScrapedPosting:
    """Raw posting data before LLM processing."""
    source_url: str
    source_site: str
    external_id: Optional[str]
    raw_title: str
    raw_description: str
    raw_html: Optional[str]
    company_name: str
    location_raw: Optional[str]
    posted_date: Optional[datetime]

class BaseScraper(ABC):
    """Abstract base for all scrapers."""
    
    def __init__(self, config: dict):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.get('request_timeout_seconds', 30),
            follow_redirects=True,
            headers=self._get_headers()
        )
    
    def _get_headers(self) -> dict:
        """Return randomized but realistic headers."""
        # Rotate user agents, set accept headers, etc.
        pass
    
    @abstractmethod
    async def get_job_listings(self, company) -> List[str]:
        """Return list of job posting URLs for a company."""
        pass
    
    @abstractmethod
    async def get_job_details(self, url: str, company) -> ScrapedPosting:
        """Fetch and parse a single job posting."""
        pass
    
    async def scrape_company(self, company) -> List[ScrapedPosting]:
        """Full scrape flow for one company."""
        urls = await self.get_job_listings(company)
        postings = []
        for url in urls:
            await self._rate_limit_delay()
            posting = await self.get_job_details(url, company)
            if posting:
                postings.append(posting)
        return postings
    
    async def _rate_limit_delay(self):
        """Respectful delay between requests."""
        import asyncio
        delay = self.config.get('request_delay_seconds', 2.0)
        await asyncio.sleep(delay)
```

### Greenhouse Scraper (Simplest)

```python
# scrapers/greenhouse.py

class GreenhouseScraper(BaseScraper):
    """Greenhouse has a public JSON API - no HTML parsing needed."""
    
    async def get_job_listings(self, company) -> List[str]:
        """Fetch all jobs from Greenhouse API."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{company.ats_slug}/jobs"
        response = await self.client.get(url)
        response.raise_for_status()
        
        data = response.json()
        return [
            f"https://boards-api.greenhouse.io/v1/boards/{company.ats_slug}/jobs/{job['id']}"
            for job in data.get('jobs', [])
        ]
    
    async def get_job_details(self, url: str, company) -> ScrapedPosting:
        """Fetch individual job details."""
        response = await self.client.get(url)
        response.raise_for_status()
        
        job = response.json()
        
        return ScrapedPosting(
            source_url=job['absolute_url'],  # The human-readable URL
            source_site='greenhouse',
            external_id=str(job['id']),
            raw_title=job['title'],
            raw_description=self._clean_html(job.get('content', '')),
            raw_html=job.get('content'),
            company_name=company.name,
            location_raw=job.get('location', {}).get('name'),
            posted_date=self._parse_date(job.get('updated_at'))
        )
    
    def _clean_html(self, html: str) -> str:
        """Strip HTML tags for plain text description."""
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, 'html.parser').get_text(separator='\n')
```

### Lever Scraper

Lever doesn't have a public API, so scrape the HTML:

1. Fetch `https://jobs.lever.co/{company_slug}`
2. Parse listing page for job links (CSS: `a.posting-title`)
3. Fetch each job page
4. Extract description (CSS: `div.section-wrapper.page-full-width`)

---

## Scheduling

### Cron Approach (Simple)

```bash
# /etc/cron.d/job-search-pipeline
# Run daily at 6 AM
0 6 * * * /path/to/venv/bin/python /path/to/scripts/run_pipeline.py >> /var/log/job-search.log 2>&1
```

### APScheduler Approach (Python-Native)

```python
# scripts/scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from processing.pipeline import run_full_pipeline

scheduler = BlockingScheduler()

@scheduler.scheduled_job(CronTrigger(hour=6, minute=0))
def daily_job():
    """Run the full pipeline daily at 6 AM."""
    run_full_pipeline()

@scheduler.scheduled_job(CronTrigger(day_of_week='sun', hour=7, minute=0))
def weekly_aggregation():
    """Run weekly aggregation on Sundays."""
    from processing.aggregation import generate_weekly_snapshots
    generate_weekly_snapshots()

if __name__ == '__main__':
    scheduler.start()
```

Run as a service via systemd or similar.

---

## Key Dependencies

```
# requirements.txt

# Core
python-dotenv>=1.0.0
pydantic>=2.0
pydantic-settings>=2.0

# Database
# (sqlite3 is built-in)

# HTTP / Scraping
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# LLM
anthropic>=0.30.0

# GUI
streamlit>=1.30.0
plotly>=5.18.0
altair>=5.0

# Scheduling
apscheduler>=3.10.0

# Utilities
tenacity>=8.2.0    # Retry logic
structlog>=23.0    # Structured logging
python-dateutil>=2.8.0

# Development
pytest>=7.0
pytest-asyncio>=0.21.0
black
ruff
```

---

## Getting Started Checklist

### Phase 1: Foundation (Days 1-3)
- [ ] Set up project structure
- [ ] Create SQLite database with schema
- [ ] Implement database connection and basic queries
- [ ] Create dataclasses/models for Company, Posting, Skill
- [ ] Write seed data script with 5-10 initial companies

### Phase 2: Scraping (Days 4-5)
- [ ] Implement base scraper class
- [ ] Build Greenhouse scraper (JSON API - easiest, test with it)
- [ ] Build Lever scraper (HTML parsing)
- [ ] Test scraping pipeline end-to-end with seed companies

### Phase 3: LLM Extraction (Days 7-9)
- [ ] Set up Anthropic client with retry logic
- [ ] Create extraction prompt
- [ ] Build extraction pipeline
- [ ] Implement skill normalization
- [ ] Add validation and error handling

### Phase 4: Scoring (Day 10)
- [ ] Implement scoring algorithm
- [ ] Create my_skills management functions
- [ ] Test scoring with sample data

### Phase 5: Basic GUI (Days 11-14)
- [ ] Streamlit app skeleton
- [ ] Dashboard page (basic)
- [ ] Search & filter page (core functionality)
- [ ] Company management page
- [ ] Settings page (profile, preferences)

### Phase 6: Pipeline & Scheduling (Days 15-16)
- [ ] Wire up full pipeline stages
- [ ] Add logging throughout
- [ ] Set up cron/scheduler
- [ ] Test full daily run

### Phase 7: Polish (Days 17-21)
- [ ] Application tracking (kanban board)
- [ ] Analytics dashboards
- [ ] Notifications (optional)
- [ ] Error handling improvements
- [ ] Documentation

---

## Future Enhancements (Post-MVP)

1. **Browser extension**: Clip jobs from any site to your database
2. **Resume tailoring**: Generate customized resume bullet points per application
3. **Interview prep**: Pull in company info, Glassdoor reviews, prep questions
4. **Networking tracker**: Track contacts at target companies
5. **Salary negotiation data**: Aggregate Glassdoor/Levels.fyi data
6. **ML-based scoring**: Train on your actual application outcomes
7. **Calendar integration**: Sync interviews to Google Calendar
8. **Mobile app**: React Native companion for on-the-go updates

---

## Appendix: Environment Variables

```bash
# .env

# Database
DATABASE_PATH=./data/job_search.db

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Scraping
SCRAPE_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
SCRAPE_DELAY_SECONDS=2.5
SCRAPE_MAX_RETRIES=3

# Notifications (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-specific-password
NOTIFICATION_EMAIL=your-email@gmail.com

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```
