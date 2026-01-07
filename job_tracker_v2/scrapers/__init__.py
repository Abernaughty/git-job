"""
Job posting scrapers for Greenhouse and Lever ATS platforms.
"""

from scrapers.base import BaseScraper, ScraperResult
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper

__all__ = ["BaseScraper", "ScraperResult", "GreenhouseScraper", "LeverScraper"]
