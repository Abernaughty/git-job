# Job Search System - Testing Plan

## Overview

This document outlines the testing strategy for the Job Search System, covering:
1. **Unit Tests** - Testing individual components in isolation
2. **Integration Tests** - Testing components working together
3. **End-to-End Tests** - Testing complete workflows
4. **Manual Verification** - Human-verified checks
5. **Testing as We Go** - Incremental testing during development

---

## Testing Philosophy

- **Test Early**: Write tests alongside code, not after
- **Test Real Data**: Use actual API responses captured as fixtures
- **Test Edge Cases**: Handle missing data, malformed responses, rate limits
- **Test Incrementally**: Each phase has its own verification checkpoint

---

## Phase-by-Phase Testing

### Phase 1: Foundation (Database & Models)

#### Unit Tests

```python
# tests/test_database/test_schema.py
def test_companies_table_creation():
    """Verify companies table exists with correct columns."""
    
def test_postings_table_creation():
    """Verify postings table exists with correct columns and indexes."""

def test_foreign_key_constraints():
    """Verify CASCADE deletes work correctly."""

def test_unique_constraints():
    """Verify source_url uniqueness on postings."""
```

```python
# tests/test_database/test_queries.py
def test_insert_company():
    """Can insert a new company."""
    
def test_insert_duplicate_company_fails():
    """Inserting duplicate company name raises error."""
    
def test_get_active_companies():
    """Returns only companies with is_active=1."""
    
def test_update_last_scraped_at():
    """Updates timestamp correctly."""
```

```python
# tests/test_models/test_company.py
def test_company_from_dict():
    """Can create Company from dictionary."""
    
def test_company_to_dict():
    """Can serialize Company to dictionary."""
    
def test_company_greenhouse_url():
    """Generates correct Greenhouse URL from slug."""
```

#### Manual Verification Checkpoint
- [ ] SQLite database file created successfully
- [ ] Can view tables in DB browser (e.g., `sqlite3` CLI or DB Browser for SQLite)
- [ ] Seed script loads companies_seed.json without errors
- [ ] `SELECT COUNT(*) FROM companies` returns expected count

---

### Phase 2: Scraping

#### Test Fixtures

Create sample responses for offline testing:

```
tests/fixtures/
├── greenhouse/
│   ├── stripe_jobs_list.json      # Full job listing response
│   ├── stripe_job_detail.json     # Single job detail response
│   ├── empty_job_list.json        # Company with no jobs
│   └── invalid_response.json      # Malformed JSON
├── lever/
│   ├── netflix_jobs_list.html     # Full job listing page
│   ├── netflix_job_detail.html    # Single job page
│   ├── empty_job_list.html        # Company with no jobs
│   └── legacy_format.html         # Older Lever page format
```

#### Unit Tests

```python
# tests/test_scrapers/test_greenhouse.py
def test_parse_job_listing_response():
    """Correctly extracts job URLs from listing response."""
    
def test_parse_job_detail():
    """Correctly extracts all fields from job detail."""
    
def test_clean_html_description():
    """Strips HTML tags, preserves text structure."""
    
def test_parse_date_formats():
    """Handles various date formats in updated_at field."""
    
def test_handle_missing_location():
    """Gracefully handles jobs without location data."""
    
def test_handle_empty_job_list():
    """Returns empty list when company has no jobs."""
```

```python
# tests/test_scrapers/test_lever.py
def test_parse_job_listing_html():
    """Correctly extracts job URLs from listing page."""
    
def test_parse_job_detail_html():
    """Correctly extracts all fields from job page."""
    
def test_extract_team_and_location():
    """Parses team and location from posting metadata."""
    
def test_handle_legacy_format():
    """Works with older Lever page layouts."""
```

```python
# tests/test_scrapers/test_rate_limit.py
def test_rate_limit_delay():
    """Respects configured delay between requests."""
    
def test_retry_on_timeout():
    """Retries failed requests with backoff."""
    
def test_max_retries_exceeded():
    """Raises exception after max retries."""
```

#### Integration Tests (Live API)

```python
# tests/test_scrapers/test_live_greenhouse.py
@pytest.mark.live
def test_fetch_real_stripe_jobs():
    """Fetch actual jobs from Stripe's Greenhouse board."""
    scraper = GreenhouseScraper(config)
    jobs = await scraper.get_job_listings(stripe_company)
    assert len(jobs) > 0
    assert all(job.startswith('https://') for job in jobs)

@pytest.mark.live  
def test_fetch_real_job_detail():
    """Fetch actual job detail from Greenhouse."""
    # Use a known job URL that's likely to exist
```

```python
# tests/test_scrapers/test_live_lever.py
@pytest.mark.live
def test_fetch_real_netflix_jobs():
    """Fetch actual jobs from Netflix's Lever board."""
    
@pytest.mark.live
def test_fetch_real_lever_job_detail():
    """Fetch actual job detail from Lever."""
```

#### Manual Verification Checkpoint
- [ ] `python -m scripts.test_scraper --company stripe --platform greenhouse` returns jobs
- [ ] `python -m scripts.test_scraper --company netflix --platform lever` returns jobs
- [ ] Rate limiting visibly delays requests (observe 1-second gaps)
- [ ] Error handling works: test with invalid slug like `nonexistent12345`
- [ ] Scraped job descriptions are readable (not garbled HTML)

---

### Phase 3: LLM Extraction

#### Test Fixtures

```
tests/fixtures/llm/
├── sample_job_descriptions/
│   ├── senior_engineer_with_salary.txt
│   ├── junior_role_no_salary.txt
│   ├── remote_job_with_clearance.txt
│   ├── vague_requirements.txt
│   └── very_long_description.txt
├── expected_extractions/
│   ├── senior_engineer_with_salary.json
│   ├── junior_role_no_salary.json
│   └── ...
```

#### Unit Tests

```python
# tests/test_llm/test_extraction.py
def test_extraction_basic_fields():
    """Extracts title, location, salary correctly."""
    
def test_extraction_skills_parsing():
    """Correctly identifies required vs preferred skills."""
    
def test_extraction_salary_conversion():
    """Converts hourly to annual salary."""
    
def test_extraction_remote_type_detection():
    """Distinguishes remote_us, remote_global, hybrid, onsite."""
    
def test_extraction_handles_missing_data():
    """Returns null for missing fields, not made-up values."""

def test_extraction_red_flags():
    """Identifies concerning phrases like 'rockstar'."""
```

```python
# tests/test_llm/test_validation.py
def test_validate_salary_range():
    """Ensures salary_min <= salary_max."""
    
def test_validate_experience_range():
    """Ensures experience_min <= experience_max."""
    
def test_validate_enum_fields():
    """Ensures seniority_level is valid enum value."""
    
def test_clean_malformed_json():
    """Handles LLM returning JSON with trailing commas."""
```

```python
# tests/test_llm/test_skill_normalization.py
def test_normalize_python_aliases():
    """python3, py, Python → Python."""
    
def test_normalize_aws_aliases():
    """aws, Amazon AWS, Amazon Web Services → AWS."""
    
def test_preserve_unknown_skills():
    """Unknown skills kept as-is with title case."""
```

#### Golden File Tests

```python
# tests/test_llm/test_golden_files.py
@pytest.mark.parametrize("fixture_name", [
    "senior_engineer_with_salary",
    "junior_role_no_salary",
    "remote_job_with_clearance",
])
def test_extraction_matches_expected(fixture_name):
    """Compare actual extraction to pre-validated expected output."""
    input_text = load_fixture(f"sample_job_descriptions/{fixture_name}.txt")
    expected = load_fixture(f"expected_extractions/{fixture_name}.json")
    
    result = extract_posting_data(input_text)
    
    assert result['normalized_title'] == expected['normalized_title']
    assert result['salary_min'] == expected['salary_min']
    # ... etc
```

#### Manual Verification Checkpoint
- [ ] Run extraction on 5 real job postings, verify accuracy
- [ ] Check that skills are categorized correctly
- [ ] Verify salary extraction only happens when explicitly stated
- [ ] Confirm red flags are detected ("rockstar", "fast-paced", etc.)
- [ ] Test with a job description that has NO extractable data

---

### Phase 4: Scoring

#### Unit Tests

```python
# tests/test_processing/test_scoring.py
def test_full_skill_match():
    """100% skill match returns 1.0 for skill components."""
    
def test_partial_skill_match():
    """50% skill match returns 0.5 for skill components."""
    
def test_no_skill_match():
    """0% skill match returns 0.0 for required_skills."""
    
def test_salary_above_minimum():
    """Salary above min returns 1.0."""
    
def test_salary_below_minimum():
    """Salary below min returns proportional score."""
    
def test_unknown_salary():
    """Missing salary returns 0.5 (neutral)."""
    
def test_experience_fit_overqualified():
    """Much more experience than required returns 0.5."""
    
def test_clearance_sponsorship_available():
    """Clearance with sponsorship returns 0.9."""
    
def test_clearance_required_no_sponsorship():
    """Clearance required without sponsorship returns 0.0."""
    
def test_remote_fit_matches_preference():
    """Remote type matching preference returns 1.0."""
    
def test_overall_score_calculation():
    """Weighted combination produces expected score."""
```

```python
# tests/test_processing/test_disqualification.py
def test_disqualify_clearance_no_sponsorship():
    """Disqualifies when clearance required, no sponsorship."""
    
def test_disqualify_salary_too_low():
    """Disqualifies when salary < 70% of minimum."""
    
def test_disqualify_excluded_industry():
    """Disqualifies companies in excluded industries."""
    
def test_not_disqualified_valid_posting():
    """Valid posting passes disqualification check."""
```

#### Manual Verification Checkpoint
- [ ] Score a high-match posting (expect > 0.75)
- [ ] Score a low-match posting (expect < 0.50)
- [ ] Verify disqualification works for clearance requirement
- [ ] Check skill_match_details JSON shows breakdown correctly

---

### Phase 5: GUI (Streamlit)

#### Automated UI Tests (Optional)

Using `pytest` with `streamlit.testing`:

```python
# tests/test_gui/test_dashboard.py
def test_dashboard_loads():
    """Dashboard page renders without error."""
    
def test_dashboard_shows_new_postings():
    """New postings appear in 'Today's Top Matches'."""
    
def test_dashboard_shows_stats():
    """Stats cards display correct counts."""
```

#### Manual Testing Checklist

##### Dashboard Page
- [ ] Page loads without errors
- [ ] "Today's Top Matches" shows recent high-score postings
- [ ] "Needs Attention" shows pending follow-ups
- [ ] Stats cards show correct numbers
- [ ] Clicking a posting card expands details

##### Search Page
- [ ] All filters render correctly
- [ ] Filtering by company works
- [ ] Filtering by match score works
- [ ] Filtering by remote type works
- [ ] Full-text search returns relevant results
- [ ] Table view displays correctly
- [ ] Card view displays correctly
- [ ] Sorting works on all columns

##### Companies Page
- [ ] Company list loads
- [ ] Add company form works
- [ ] Company detail view shows postings
- [ ] ATS auto-detection works (enter URL, detect Greenhouse/Lever)
- [ ] Test scraper button works

##### Applications Page
- [ ] Kanban columns display correctly
- [ ] Cards can be dragged between columns (if implemented)
- [ ] Adding events works
- [ ] Timeline shows event history

##### Analytics Page
- [ ] Skill demand heatmap renders
- [ ] Salary trends chart renders
- [ ] Skill gaps chart renders

##### Settings Page
- [ ] Profile settings save correctly
- [ ] Scoring weights update
- [ ] Manual pipeline trigger works
- [ ] Export data works

---

### Phase 6: Pipeline & Scheduling

#### Unit Tests

```python
# tests/test_processing/test_pipeline.py
def test_pipeline_stage_order():
    """Stages execute in correct order."""
    
def test_pipeline_handles_scrape_failure():
    """Pipeline continues when one company fails."""
    
def test_pipeline_logs_results():
    """Scrape results logged to scrape_log table."""
```

```python
# tests/test_processing/test_cleanup.py
def test_cleanup_old_postings():
    """Removes postings older than retention period."""
    
def test_cleanup_preserves_applied():
    """Does not remove postings with applied status."""
    
def test_detect_closed_postings():
    """Marks postings not seen in 7 days as closed."""
```

#### Integration Tests

```python
# tests/test_integration/test_full_pipeline.py
@pytest.mark.integration
def test_pipeline_single_company():
    """Run full pipeline for one test company."""
    # 1. Scrape
    # 2. Extract (with mock LLM or real)
    # 3. Score
    # 4. Verify database state
    
@pytest.mark.integration
def test_pipeline_handles_duplicates():
    """Running pipeline twice doesn't create duplicate postings."""
```

#### Manual Verification Checkpoint
- [ ] `python -m scripts.run_pipeline` completes without errors
- [ ] Scrape log shows entries for each company
- [ ] New postings appear in database
- [ ] Existing postings have updated `last_seen_at`
- [ ] Closed detection marks old postings correctly

---

## End-to-End Test Scenarios

### Scenario 1: New User Setup

```
1. Create fresh database
2. Load seed companies
3. Run first pipeline
4. Open Streamlit GUI
5. Verify dashboard shows new postings
6. Search for a specific role
7. Save a posting
8. Verify saved posting appears in Applications
```

**Expected Results:**
- [ ] Database created with schema
- [ ] 67 companies loaded from seed
- [ ] At least 50 new postings scraped
- [ ] Dashboard shows top matches
- [ ] Search returns relevant results
- [ ] Saved posting moves to "Saved" column

### Scenario 2: Daily Pipeline Run

```
1. Start with populated database
2. Run pipeline
3. Check for new postings
4. Check for closed postings
5. Verify no duplicates created
```

**Expected Results:**
- [ ] Pipeline completes in < 10 minutes
- [ ] Some new postings found
- [ ] Some postings marked as closed
- [ ] Posting count reasonable (no explosion of duplicates)

### Scenario 3: Application Tracking

```
1. Find a posting
2. Change status to "Applied"
3. Add application event
4. Change status to "Phone Screen"
5. Add interview event
6. View application timeline
```

**Expected Results:**
- [ ] Status changes persist
- [ ] Events saved to application_events
- [ ] Timeline displays chronologically

### Scenario 4: Analytics Accuracy

```
1. Run pipeline for 1 week (or simulate data)
2. View skill demand heatmap
3. Check top skills match actual postings
4. Verify salary trends data
```

**Expected Results:**
- [ ] Heatmap shows realistic skill distribution
- [ ] Top skills match manual spot-check
- [ ] Salary ranges are plausible

### Scenario 5: Error Recovery

```
1. Corrupt a company's ATS slug
2. Run pipeline
3. Verify error logged but pipeline continues
4. Fix slug
5. Re-run pipeline
6. Verify company now scraped successfully
```

**Expected Results:**
- [ ] Pipeline doesn't crash on single failure
- [ ] Error logged with helpful message
- [ ] Other companies scraped successfully
- [ ] Fixed company works on next run

---

## Test Data Management

### Creating Test Fixtures

```bash
# Capture real Greenhouse response for fixture
curl "https://boards-api.greenhouse.io/v1/boards/stripe/jobs" > tests/fixtures/greenhouse/stripe_jobs_list.json

# Capture real Lever page for fixture
curl "https://jobs.lever.co/netflix" > tests/fixtures/lever/netflix_jobs_list.html
```

### Test Database

```python
# conftest.py
@pytest.fixture
def test_db():
    """Create temporary test database."""
    db_path = tempfile.mktemp(suffix='.db')
    conn = create_database(db_path)
    yield conn
    os.unlink(db_path)

@pytest.fixture
def seeded_db(test_db):
    """Test database with seed data."""
    load_seed_companies(test_db, 'tests/fixtures/test_companies.json')
    return test_db
```

---

## Running Tests

### Commands

```bash
# Run all unit tests
pytest tests/ -v

# Run only unit tests (fast)
pytest tests/ -v -m "not live and not integration"

# Run integration tests (uses real APIs)
pytest tests/ -v -m integration

# Run live API tests (makes real requests)
pytest tests/ -v -m live

# Run with coverage
pytest tests/ --cov=job_search_system --cov-report=html

# Run specific test file
pytest tests/test_scrapers/test_greenhouse.py -v

# Run tests matching pattern
pytest tests/ -v -k "test_extraction"
```

### CI/CD Configuration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio pytest-cov
      - run: pytest tests/ -v -m "not live" --cov
```

---

## Test Metrics & Goals

| Metric | Target |
|--------|--------|
| Unit test coverage | > 80% |
| Integration test coverage | > 60% |
| All critical paths tested | 100% |
| Zero flaky tests | 0 |
| Test run time (unit only) | < 30 seconds |
| Test run time (full suite) | < 5 minutes |

---

## Summary: Testing as We Go

| Phase | Test Before Proceeding |
|-------|------------------------|
| Phase 1: Foundation | Database creates, seed loads, queries work |
| Phase 2: Scraping | Both Greenhouse and Lever return real jobs |
| Phase 3: LLM | Golden file tests pass, real job extracts correctly |
| Phase 4: Scoring | Score calculations match expected values |
| Phase 5: GUI | All pages render, basic interactions work |
| Phase 6: Pipeline | Full pipeline completes, no duplicates |
| **Final** | All E2E scenarios pass |
