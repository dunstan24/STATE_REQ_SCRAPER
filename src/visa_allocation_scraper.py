"""
Specialized Scraper for Visa Subclass 190 and 491 State Allocations
Extracts data from the State and Territory nominations table
"""

import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd

try:
    import config
except ImportError:
    from src import config


class VisaAllocationScraper:
    """Scraper for Visa Subclass 190 and 491 State Allocations"""
    
    # States and territories
    STATES = ['ACT', 'NSW', 'NT', 'Qld', 'SA', 'Tas', 'Vic', 'WA']
    
    # Visa subclasses we're looking for
    VISA_190 = "Skilled Nominated visa (subclass 190)"
    VISA_491 = "Skilled Work Regional (Provisional) visa (subclass 491)"
    
    def __init__(self, enable_console_logging=True):
        """
        Initialize the scraper
        
        Args:
            enable_console_logging (bool): Whether to output logs to console
        """
        self.enable_console_logging = enable_console_logging
        self.setup_logging()
        self.driver = None
        self.data_190 = []
        self.data_491 = []
        
    def setup_logging(self):
        """Configure logging"""
        log_filename = f"{config.LOG_DIR}/visa_allocation_{datetime.now().strftime(config.TIMESTAMP_FORMAT)}.log"
        
        handlers = [logging.FileHandler(log_filename)]
        if self.enable_console_logging:
            handlers.append(logging.StreamHandler())
        
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format=config.LOG_FORMAT,
            handlers=handlers,
            force=True  # Ensure we reset any existing handlers
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Visa Allocation Scraper initialized")
    
    def setup_driver(self):
        """Setup Selenium WebDriver"""
        self.logger.info("Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        
        if config.HEADLESS_MODE:
            chrome_options.add_argument("--headless")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"user-agent={config.USER_AGENT}")
        chrome_options.add_argument("--window-size=1920,1080")
    
        try:
            driver_path = ChromeDriverManager().install()
            
            # PATCH: Fix for webdriver_manager bug where it selects THIRD_PARTY_NOTICES
            if "THIRD_PARTY_NOTICES" in driver_path:
                import os
                self.logger.warning(f"webdriver_manager returned incorrect path: {driver_path}")
                driver_dir = os.path.dirname(driver_path)
                for file_name in os.listdir(driver_dir):
                    if file_name.startswith("chromedriver") and "THIRD" not in file_name:
                        new_path = os.path.join(driver_dir, file_name)
                        if os.access(new_path, os.X_OK):  # Check if executable
                            driver_path = new_path
                            self.logger.info(f"Fixed driver path: {driver_path}")
                            break
            
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
            self.driver.implicitly_wait(config.IMPLICIT_WAIT)
            self.logger.info("WebDriver setup successful")
        except Exception as e:
            self.logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise
    
    def navigate_to_page(self):
        """Navigate to the target URL"""
        self.logger.info(f"Navigating to {config.TARGET_URL}")
        
        try:
            self.driver.get(config.TARGET_URL)
            time.sleep(5)  # Wait for page to load
            self.logger.info("Page loaded successfully")
            
            # Scroll to find the State and Territory nominations section
            self.scroll_to_section()
            
            # Save page source for debugging
            with open(f"{config.OUTPUT_DIR}/visa_allocation_page_source.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            
            return True
        except TimeoutException:
            self.logger.error("Page load timeout")
            return False
        except Exception as e:
            self.logger.error(f"Navigation error: {str(e)}")
            return False
    
    def scroll_to_section(self):
        """Scroll to the State and Territory nominations section"""
        self.logger.info("Scrolling to State and Territory nominations section...")
        
        try:
            # Try to find the section by text
            section_keywords = [
                "State and Territory nominations",
                "state and territory nominations",
                "State and territory nominations"
            ]
            
            for keyword in section_keywords:
                try:
                    element = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{keyword}')]")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(2)
                    self.logger.info(f"Found section with keyword: {keyword}")
                    return
                except NoSuchElementException:
                    continue
            
            # If not found, scroll through the page
            self.logger.info("Section not found by keyword, scrolling entire page...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while True:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                
        except Exception as e:
            self.logger.error(f"Error scrolling to section: {str(e)}")
    
    def extract_allocation_data(self) -> Dict:
        """Extract visa allocation data from the page"""
        self.logger.info("Extracting visa allocation data...")
        
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        
        # Find all tables
        tables = soup.find_all('table')
        self.logger.info(f"Found {len(tables)} tables on the page")
        
        allocation_data = {
            'program_year': None,
            'date_range': None,
            'visa_190': {},
            'visa_491': {},
            'extraction_timestamp': datetime.now().isoformat()
        }
        
        for idx, table in enumerate(tables):
            self.logger.info(f"Analyzing table {idx + 1}...")
            
            # Check if this table contains State and Territory nominations
            table_text = table.get_text().lower()
            
            if 'state and territory' in table_text or 'visa subclass' in table_text:
                self.logger.info(f"Table {idx + 1} appears to contain allocation data")
                
                # Extract program year and date range from surrounding text
                self.extract_metadata(table, allocation_data)
                
                # Parse the table
                self.parse_allocation_table(table, allocation_data)
        
        return allocation_data
    
    def extract_metadata(self, table, allocation_data):
        """Extract program year and date range"""
        try:
            # We need to look at text surrounding the table.
            # The structure often has a heading or paragraph before the table.
            
            # Gather text from multiple sources to ensure we catch the headers/paragraphs
            text_sources = []
            
            # Helper to add text if valid
            def add_text_from_element(elem):
                if elem:
                    txt = elem.get_text(" ", strip=True)
                    if len(txt) > 5: # Skip empty/tiny strings
                        text_sources.append(txt)

            # 1. Previous siblings of the table (e.g. if table is direct child of page)
            for prev in table.find_previous_siblings(limit=5):
                add_text_from_element(prev)
            
            # 2. Parent text (e.g. if table is inside a wrapper)
            if table.parent:
                add_text_from_element(table.parent)
                
                # 3. Parent's previous siblings (CRITICAL: simpler structure often puts header before the div wrapping the table)
                for prev in table.parent.find_previous_siblings(limit=5):
                    add_text_from_element(prev)
                
            # Combine all text
            combined_text = " ".join(text_sources)
            # self.logger.info(f"Metadata search text ({len(combined_text)} chars): {combined_text[:500]}...")
            
            # --- 1. Extract Program Year ---
            if not allocation_data['program_year']:
                # Matches "2025-26 program year" exactly as in screenshot
                year_match = re.search(r'(\d{4}-\d{2,4})\s+(?:program\s+)?year', combined_text, re.IGNORECASE)
                
                if year_match:
                    allocation_data['program_year'] = year_match.group(1)
                    self.logger.info(f"Found program year (regex): {allocation_data['program_year']}")
                else:
                    # Fallback pattern
                    year_match_simple = re.search(r'(\d{4}-\d{2})', combined_text)
                    if year_match_simple:
                        allocation_data['program_year'] = year_match_simple.group(1)
                        self.logger.info(f"Found program year (simple): {allocation_data['program_year']}")

            # --- 2. Extract Date Range ---
            # Text: "from 1 July 2025 to 31 December 2025"
            if not allocation_data['date_range']:
                # Robust regex for "from X to Y"
                # Matches: from 1 July 2025 to 31 December 2025
                date_pattern = r'from\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+to\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})'
                date_match = re.search(date_pattern, combined_text, re.IGNORECASE)
                
                if date_match:
                    allocation_data['date_range'] = {
                        'from': date_match.group(1),
                        'to': date_match.group(2)
                    }
                    self.logger.info(f"Found date range: {date_match.group(1)} to {date_match.group(2)}")

            # --- 3. Fallback for Program Year ---
            if not allocation_data['program_year']:
                # Calculate based on current date (Australian financial year starts July 1)
                now = datetime.now()
                if now.month >= 7: # July onwards
                    start_year = now.year
                else: # Jan - June
                    start_year = now.year - 1
                
                # Format as YYYY-YY (e.g., 2025-26)
                end_year_short = str(start_year + 1)[-2:]
                allocation_data['program_year'] = f"{start_year}-{end_year_short}"
                self.logger.warning(f"Program year not found in text, using calculated fallback: {allocation_data['program_year']}")

        except Exception as e:
            self.logger.error(f"Error extracting metadata: {str(e)}")
    
    def parse_allocation_table(self, table, allocation_data):
        """Parse the allocation table for visa 190 and 491 data"""
        try:
            # Get headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            else:
                first_row = table.find('tr')
                if first_row:
                    headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
            
            self.logger.info(f"Table headers: {headers}")
            
            # Get all rows
            rows = table.find_all('tr')
            
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                
                if not cells or len(cells) < 2:
                    continue
                
                # Check if this row is for visa 190
                if '190' in cells[0]:
                    self.logger.info("Found Visa 190 row")
                    self.extract_state_allocations(cells, headers, allocation_data['visa_190'])
                
                # Check if this row is for visa 491
                elif '491' in cells[0]:
                    self.logger.info("Found Visa 491 row")
                    self.extract_state_allocations(cells, headers, allocation_data['visa_491'])
                    
        except Exception as e:
            self.logger.error(f"Error parsing allocation table: {str(e)}")
    
    def extract_state_allocations(self, cells, headers, visa_data):
        """Extract state allocations from table cells"""
        try:
            # First cell is usually the visa name, rest are allocations
            # We only want to extract data for valid Australian states/territories
            for i in range(1, len(cells)):
                if i < len(headers):
                    column_name = headers[i]
                    allocation = cells[i]
                    
                    # Only process if this column is a valid state/territory
                    # This filters out month columns (Jul, Aug, etc.) and other data
                    if column_name in self.STATES:
                        # Clean the allocation number
                        allocation_clean = re.sub(r'[^\d]', '', allocation)
                        
                        if allocation_clean:
                            visa_data[column_name] = int(allocation_clean)
                            self.logger.info(f"  {column_name}: {allocation_clean}")
                        else:
                            visa_data[column_name] = 0
                    else:
                        # Skip non-state columns (like months, totals, etc.)
                        self.logger.debug(f"  Skipping non-state column: {column_name}")
                        
        except Exception as e:
            self.logger.error(f"Error extracting state allocations: {str(e)}")
    
    def format_for_excel(self, allocation_data) -> List[Dict]:
        """Format data for Excel export (matching your template)"""
        records = []
        
        # Get date range safely
        date_range = allocation_data.get('date_range') or {}
        date_from = date_range.get('from', '') if isinstance(date_range, dict) else ''
        date_to = date_range.get('to', '') if isinstance(date_range, dict) else ''
        
        # Create records for visa 190
        for state, allocation in allocation_data['visa_190'].items():
            records.append({
                'Program Year': allocation_data.get('program_year', ''),
                'Date From': date_from,
                'Date To': date_to,
                'Visa Subclass': '190',
                'Visa Name': 'Skilled Nominated visa (subclass 190)',
                'State/Territory': state,
                'Allocations': allocation,
                'Extraction Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Create records for visa 491
        for state, allocation in allocation_data['visa_491'].items():
            records.append({
                'Program Year': allocation_data.get('program_year', ''),
                'Date From': date_from,
                'Date To': date_to,
                'Visa Subclass': '491',
                'Visa Name': 'Skilled Work Regional (Provisional) visa (subclass 491)',
                'State/Territory': state,
                'Allocations': allocation,
                'Extraction Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return records
    
    def export_data(self, allocation_data):
        """Export data to various formats"""
        if not allocation_data['visa_190'] and not allocation_data['visa_491']:
            self.logger.warning("No allocation data to export")
            return
        
        # Format for Excel
        records = self.format_for_excel(allocation_data)
        df = pd.DataFrame(records)
        
        # Export to different formats
        timestamp = datetime.now().strftime(config.TIMESTAMP_FORMAT)
        
        # CSV
        csv_file = f"{config.OUTPUT_DIR}/visa_allocations_{timestamp}.csv"
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        self.logger.info(f"Data exported to CSV: {csv_file}")
        
        # Excel
        excel_file = f"{config.OUTPUT_DIR}/visa_allocations_{timestamp}.xlsx"
        df.to_excel(excel_file, index=False, engine='openpyxl', sheet_name='Allocations')
        self.logger.info(f"Data exported to Excel: {excel_file}")
        
        # JSON (full structure)
        json_file = f"{config.OUTPUT_DIR}/visa_allocations_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(allocation_data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Data exported to JSON: {json_file}")
        
        # Summary report
        self.generate_summary_report(allocation_data, timestamp)
    
    def generate_summary_report(self, allocation_data, timestamp):
        """Generate a summary report"""
        report_file = f"{config.OUTPUT_DIR}/allocation_summary_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("VISA ALLOCATION SUMMARY REPORT\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Program Year: {allocation_data.get('program_year', 'N/A')}\n")
            
            if allocation_data.get('date_range'):
                f.write(f"Date Range: {allocation_data['date_range'].get('from', 'N/A')} to {allocation_data['date_range'].get('to', 'N/A')}\n")
            
            f.write(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("-" * 70 + "\n")
            f.write("VISA SUBCLASS 190 - Skilled Nominated\n")
            f.write("-" * 70 + "\n")
            
            total_190 = 0
            for state in self.STATES:
                allocation = allocation_data['visa_190'].get(state, 0)
                f.write(f"{state:10s}: {allocation:>6,}\n")
                total_190 += allocation
            
            f.write(f"{'TOTAL':10s}: {total_190:>6,}\n\n")
            
            f.write("-" * 70 + "\n")
            f.write("VISA SUBCLASS 491 - Skilled Work Regional (Provisional)\n")
            f.write("-" * 70 + "\n")
            
            total_491 = 0
            for state in self.STATES:
                allocation = allocation_data['visa_491'].get(state, 0)
                f.write(f"{state:10s}: {allocation:>6,}\n")
                total_491 += allocation
            
            f.write(f"{'TOTAL':10s}: {total_491:>6,}\n\n")
            
            f.write("=" * 70 + "\n")
            f.write(f"GRAND TOTAL: {total_190 + total_491:,}\n")
            f.write("=" * 70 + "\n")
        
        self.logger.info(f"Summary report generated: {report_file}")
        
        # Also print to console
        with open(report_file, 'r', encoding='utf-8') as f:
            print("\n" + f.read())
    
    def run(self):
        """Main execution method"""
        try:
            self.logger.info("=" * 70)
            self.logger.info("Starting Visa Allocation Scraper")
            self.logger.info("=" * 70)
            
            # Setup driver
            self.setup_driver()
            
            # Navigate to page
            if not self.navigate_to_page():
                raise Exception("Failed to navigate to target page")
            
            # Extract allocation data
            allocation_data = self.extract_allocation_data()
            
            # Export data
            self.export_data(allocation_data)
            
            self.logger.info("=" * 70)
            self.logger.info("Scraping completed successfully")
            self.logger.info("=" * 70)
            
            return allocation_data
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {str(e)}", exc_info=True)
            raise
        
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("WebDriver closed")


def main():
    """Main entry point"""
    scraper = VisaAllocationScraper()
    scraper.run()


if __name__ == "__main__":
    main()
