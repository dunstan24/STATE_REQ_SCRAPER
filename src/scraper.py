"""
Australian Immigration - State and Territory Nominations Scraper
Scrapes data from the SkillSelect invitation rounds page
"""

import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Optional

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

import config


class ImmigrationDataScraper:
    """Scraper for Australian Immigration State and Territory Nominations"""
    
    def __init__(self):
        """Initialize the scraper with configuration"""
        self.setup_logging()
        self.driver = None
        self.data = []
        
    def setup_logging(self):
        """Configure logging"""
        log_filename = f"{config.LOG_DIR}/scraper_{datetime.now().strftime(config.TIMESTAMP_FORMAT)}.log"
        
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format=config.LOG_FORMAT,
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Immigration Data Scraper initialized")
    
    def setup_driver(self):
        """Setup Selenium WebDriver with Chrome"""
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
            service = Service(ChromeDriverManager().install())
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
            time.sleep(3)  # Wait for page to load
            self.logger.info("Page loaded successfully")
            
            # Save page source for debugging
            with open(f"{config.OUTPUT_DIR}/page_source.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            
            return True
        except TimeoutException:
            self.logger.error("Page load timeout")
            return False
        except Exception as e:
            self.logger.error(f"Navigation error: {str(e)}")
            return False
    
    def scroll_page(self):
        """Scroll through the page to load all dynamic content"""
        self.logger.info("Scrolling page to load dynamic content...")
        
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(config.SCROLL_PAUSE_TIME)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        self.logger.info("Page scrolling complete")
    
    def extract_data(self) -> List[Dict]:
        """Extract State and Territory nomination data from the page"""
        self.logger.info("Extracting data from page...")
        
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        extracted_data = []
        
        # Strategy 1: Look for tables with State/Territory data
        tables = soup.find_all('table')
        self.logger.info(f"Found {len(tables)} tables on the page")
        
        for idx, table in enumerate(tables):
            self.logger.debug(f"Processing table {idx + 1}")
            table_data = self.parse_table(table, idx)
            if table_data:
                extracted_data.extend(table_data)
        
        # Strategy 2: Look for accordion/expandable sections
        accordions = soup.find_all(['div', 'section'], class_=lambda x: x and ('accordion' in x.lower() or 'expand' in x.lower()))
        self.logger.info(f"Found {len(accordions)} accordion sections")
        
        for accordion in accordions:
            accordion_data = self.parse_accordion(accordion)
            if accordion_data:
                extracted_data.extend(accordion_data)
        
        # Strategy 3: Look for specific text patterns
        text_data = self.parse_text_content(soup)
        if text_data:
            extracted_data.extend(text_data)
        
        self.logger.info(f"Extracted {len(extracted_data)} data records")
        return extracted_data
    
    def parse_table(self, table, table_index: int) -> List[Dict]:
        """Parse data from HTML table"""
        data = []
        
        try:
            # Get headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            else:
                # Try first row as header
                first_row = table.find('tr')
                if first_row:
                    headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
            
            self.logger.debug(f"Table {table_index} headers: {headers}")
            
            # Check if this table contains State/Territory data
            header_text = ' '.join(headers).lower()
            if not any(keyword in header_text for keyword in ['state', 'territory', 'nomination', 'invitation']):
                self.logger.debug(f"Table {table_index} doesn't appear to contain relevant data")
                return data
            
            # Get rows
            rows = table.find_all('tr')[1:] if header_row else table.find_all('tr')[1:]
            
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                
                if len(cells) >= 2:  # At least state and count
                    record = {
                        'table_index': table_index,
                        'extraction_date': datetime.now().isoformat(),
                        'source_url': config.TARGET_URL
                    }
                    
                    # Map cells to headers or use generic names
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            record[headers[i]] = cell
                        else:
                            record[f'column_{i}'] = cell
                    
                    data.append(record)
            
            self.logger.info(f"Extracted {len(data)} records from table {table_index}")
            
        except Exception as e:
            self.logger.error(f"Error parsing table {table_index}: {str(e)}")
        
        return data
    
    def parse_accordion(self, accordion) -> List[Dict]:
        """Parse data from accordion/expandable sections"""
        data = []
        
        try:
            # Click to expand if needed (for Selenium interaction)
            # This would require finding the element again in Selenium
            
            # For now, parse visible content
            text = accordion.get_text(strip=True)
            
            # Look for patterns like "NSW: 100 nominations"
            # This is a placeholder - adjust based on actual page structure
            
        except Exception as e:
            self.logger.error(f"Error parsing accordion: {str(e)}")
        
        return data
    
    def parse_text_content(self, soup) -> List[Dict]:
        """Parse data from text content using patterns"""
        data = []
        
        try:
            # Look for specific sections mentioning State/Territory nominations
            sections = soup.find_all(['div', 'section', 'article'])
            
            for section in sections:
                text = section.get_text()
                
                # Look for keywords
                if 'state' in text.lower() and 'territory' in text.lower() and 'nomination' in text.lower():
                    # Extract relevant information
                    # This is a placeholder - implement specific parsing logic
                    pass
                    
        except Exception as e:
            self.logger.error(f"Error parsing text content: {str(e)}")
        
        return data
    
    def click_expandable_sections(self):
        """Click on expandable sections to reveal hidden content"""
        self.logger.info("Looking for expandable sections...")
        
        try:
            # Common selectors for expandable content
            selectors = [
                "//button[contains(@class, 'accordion')]",
                "//div[contains(@class, 'expand')]",
                "//summary",
                "//*[contains(text(), 'Show more')]",
                "//*[contains(text(), 'View details')]"
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    self.logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    
                    for element in elements:
                        try:
                            # Scroll to element
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.5)
                            
                            # Click element
                            element.click()
                            time.sleep(1)
                            self.logger.debug(f"Clicked expandable element")
                        except Exception as e:
                            self.logger.debug(f"Could not click element: {str(e)}")
                            
                except Exception as e:
                    self.logger.debug(f"No elements found for selector {selector}")
                    
        except Exception as e:
            self.logger.error(f"Error clicking expandable sections: {str(e)}")
    
    def export_data(self, data: List[Dict]):
        """Export data to configured formats"""
        if not data:
            self.logger.warning("No data to export")
            return
        
        df = pd.DataFrame(data)
        
        for format_type in config.EXPORT_FORMATS:
            try:
                if format_type == "csv":
                    filename = f"{config.OUTPUT_DIR}/{config.get_output_filename('csv')}"
                    df.to_csv(filename, index=False, encoding='utf-8-sig')
                    self.logger.info(f"Data exported to CSV: {filename}")
                
                elif format_type == "json":
                    filename = f"{config.OUTPUT_DIR}/{config.get_output_filename('json')}"
                    df.to_json(filename, orient='records', indent=2, force_ascii=False)
                    self.logger.info(f"Data exported to JSON: {filename}")
                
                elif format_type == "excel":
                    filename = f"{config.OUTPUT_DIR}/{config.get_output_filename('xlsx')}"
                    df.to_excel(filename, index=False, engine='openpyxl')
                    self.logger.info(f"Data exported to Excel: {filename}")
                    
            except Exception as e:
                self.logger.error(f"Error exporting to {format_type}: {str(e)}")
    
    def run(self):
        """Main execution method"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("Starting Immigration Data Scraper")
            self.logger.info("=" * 50)
            
            # Setup driver
            self.setup_driver()
            
            # Navigate to page
            if not self.navigate_to_page():
                raise Exception("Failed to navigate to target page")
            
            # Scroll to load dynamic content
            self.scroll_page()
            
            # Click expandable sections
            self.click_expandable_sections()
            
            # Extract data
            self.data = self.extract_data()
            
            # Export data
            self.export_data(self.data)
            
            self.logger.info("=" * 50)
            self.logger.info("Scraping completed successfully")
            self.logger.info(f"Total records extracted: {len(self.data)}")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {str(e)}", exc_info=True)
            raise
        
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("WebDriver closed")
    
    def get_data(self) -> List[Dict]:
        """Return extracted data"""
        return self.data


def main():
    """Main entry point"""
    scraper = ImmigrationDataScraper()
    scraper.run()


if __name__ == "__main__":
    main()
