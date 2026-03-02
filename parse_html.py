"""
Parse Saved HTML - Extract Visa Allocation Data from Saved HTML File
Use this when browser automation doesn't work

Usage:
    python parse_html.py <html_file>
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from parse_saved_html import main

if __name__ == "__main__":
    main()
