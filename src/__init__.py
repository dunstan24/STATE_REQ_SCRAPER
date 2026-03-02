"""
Australian Immigration Visa Allocation Scraper
Extract State and Territory nomination data for Visa 190 and 491
"""

__version__ = "1.0.0"
__author__ = "Immigration Data Automation"

from .visa_allocation_scraper import VisaAllocationScraper
from .parse_saved_html import parse_html_file
from .n8n_integration import N8NIntegration
from .data_analyzer import DataAnalyzer

__all__ = [
    'VisaAllocationScraper',
    'parse_html_file',
    'N8NIntegration',
    'DataAnalyzer',
]
