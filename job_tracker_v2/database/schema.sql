-- Job Search System Database Schema
-- SQLite 3.x

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- ============================================================
-- COMPANIES
-- ============================================================
CREATE TABLE IF NOT EXISTS companies (
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

CREATE INDEX IF NOT EXISTS idx_companies_ats ON companies(ats_platform, ats_slug);
CREATE INDEX IF NOT EXISTS idx_companies_active ON companies(is_active);


-- ============================================================
-- TARGET ROLES (canonical job titles you're interested in)
-- ============================================================
CREATE TABLE IF NOT EXISTS target_roles (
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
CREATE TABLE IF NOT EXISTS postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES target_roles(id) ON DELETE SET NULL,
    
    -- Source tracking
    source_url TEXT NOT NULL UNIQUE,      -- dedupe key
    source_site TEXT NOT NULL,            -- greenhouse, lever, company_direct
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

CREATE INDEX IF NOT EXISTS idx_postings_company ON postings(company_id);
CREATE INDEX IF NOT EXISTS idx_postings_role ON postings(role_id);
CREATE INDEX IF NOT EXISTS idx_postings_status ON postings(status);
CREATE INDEX IF NOT EXISTS idx_postings_match ON postings(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_postings_date ON postings(posted_date DESC);
CREATE INDEX IF NOT EXISTS idx_postings_source ON postings(source_site, source_url);
CREATE INDEX IF NOT EXISTS idx_postings_first_seen ON postings(first_seen_at);


-- ============================================================
-- SKILLS (normalized skill dictionary)
-- ============================================================
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,            -- canonical name: "Python", "Kubernetes"
    aliases TEXT,                         -- JSON: ["python3", "py"]
    category TEXT,                        -- language, framework, database, cloud, tool, 
                                          -- methodology, soft_skill, certification, domain
    parent_skill_id INTEGER REFERENCES skills(id),  -- for hierarchies: React -> JavaScript
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);


-- ============================================================
-- POSTING SKILLS (many-to-many with requirement level)
-- ============================================================
CREATE TABLE IF NOT EXISTS posting_skills (
    posting_id INTEGER REFERENCES postings(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES skills(id) ON DELETE CASCADE,
    requirement_level TEXT,               -- required, preferred, nice_to_have
    years_requested INTEGER,              -- if specified: "5+ years Python"
    context TEXT,                         -- original phrase from posting
    PRIMARY KEY (posting_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_posting_skills_skill ON posting_skills(skill_id);


-- ============================================================
-- MY PROFILE (your skills and preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS my_skills (
    skill_id INTEGER PRIMARY KEY REFERENCES skills(id),
    proficiency TEXT,                     -- learning, familiar, competent, proficient, expert
    years_experience REAL,
    last_used_date DATE,                  -- for tracking skill freshness
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS my_preferences (
    key TEXT PRIMARY KEY,
    value TEXT,                           -- JSON for complex values
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- APPLICATION EVENTS (detailed tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS application_events (
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

CREATE INDEX IF NOT EXISTS idx_app_events_posting ON application_events(posting_id);
CREATE INDEX IF NOT EXISTS idx_app_events_date ON application_events(event_date DESC);
CREATE INDEX IF NOT EXISTS idx_app_events_next_action ON application_events(next_action_date);


-- ============================================================
-- WEEKLY SNAPSHOTS (aggregates, kept indefinitely)
-- ============================================================
CREATE TABLE IF NOT EXISTS weekly_snapshots (
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

CREATE INDEX IF NOT EXISTS idx_snapshots_week ON weekly_snapshots(week_start DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_role ON weekly_snapshots(role_id);


-- ============================================================
-- SCRAPE LOG (debugging and monitoring)
-- ============================================================
CREATE TABLE IF NOT EXISTS scrape_log (
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

CREATE INDEX IF NOT EXISTS idx_scrape_log_date ON scrape_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_log_company ON scrape_log(company_id);


-- ============================================================
-- LLM USAGE TRACKING (for cost management)
-- ============================================================
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    purpose TEXT,                         -- extraction, normalization, etc.
    posting_id INTEGER REFERENCES postings(id)
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_date ON llm_usage(timestamp DESC);
