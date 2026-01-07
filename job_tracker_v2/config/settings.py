"""
Application settings and configuration.
Uses pydantic-settings for environment variable loading.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Database
    database_path: Path = Field(
        default=DATA_DIR / "job_search.db",
        description="Path to SQLite database file"
    )
    
    # Anthropic API
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude"
    )
    
    # Scraping settings
    scrape_user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent string for HTTP requests"
    )
    scrape_delay_seconds: float = Field(
        default=1.5,
        description="Delay between requests to same domain"
    )
    scrape_timeout_seconds: int = Field(
        default=30,
        description="HTTP request timeout"
    )
    scrape_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed requests"
    )
    scrape_max_concurrent: int = Field(
        default=3,
        description="Maximum concurrent scrapers"
    )
    
    # LLM settings
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for extraction"
    )
    llm_max_tokens: int = Field(
        default=2000,
        description="Maximum tokens in LLM response"
    )
    llm_cost_limit_daily_usd: float = Field(
        default=5.00,
        description="Daily cost limit for LLM API"
    )
    llm_batch_size: int = Field(
        default=10,
        description="Number of postings to extract in one batch"
    )
    
    # Scoring weights
    score_weight_required_skills: float = Field(default=0.35)
    score_weight_preferred_skills: float = Field(default=0.15)
    score_weight_salary_fit: float = Field(default=0.20)
    score_weight_experience_fit: float = Field(default=0.10)
    score_weight_clearance_eligible: float = Field(default=0.10)
    score_weight_remote_fit: float = Field(default=0.10)
    score_high_match_threshold: float = Field(default=0.75)
    
    # Retention settings
    retention_days: int = Field(
        default=90,
        description="Days to keep postings before cleanup"
    )
    retention_protected_statuses: list[str] = Field(
        default=["applied", "phone_screen", "interview", "offer"],
        description="Statuses that prevent deletion"
    )
    
    # Notification settings
    notifications_enabled: bool = Field(default=False)
    notification_min_score: float = Field(default=0.80)
    notification_max_per_day: int = Field(default=10)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    @property
    def scoring_weights(self) -> dict[str, float]:
        """Return scoring weights as a dictionary."""
        return {
            "required_skills": self.score_weight_required_skills,
            "preferred_skills": self.score_weight_preferred_skills,
            "salary_fit": self.score_weight_salary_fit,
            "experience_fit": self.score_weight_experience_fit,
            "clearance_eligible": self.score_weight_clearance_eligible,
            "remote_fit": self.score_weight_remote_fit,
        }


# Global settings instance
settings = Settings()


# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
