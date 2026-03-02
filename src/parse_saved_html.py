"""
Parse Saved HTML - Extract Visa Allocation Data from Saved HTML File
Use this when browser automation doesn't work
"""

import sys
import re
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
import json


# Valid Australian states and territories
STATES = ['ACT', 'NSW', 'NT', 'Qld', 'SA', 'Tas', 'Vic', 'WA']


def parse_html_file(filename):
    """Parse saved HTML file for visa allocation data"""
    
    print("=" * 70)
    print("HTML PARSER - Visa Allocation Data")
    print("=" * 70)
    print(f"Reading file: {filename}")
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filename}")
        print("\nTo save the HTML:")
        print("1. Visit: https://immi.homeaffairs.gov.au/visas/working-in-australia/skillselect/invitation-rounds")
        print("2. Right-click → Save As → Save as HTML")
        print("3. Run: python parse_saved_html.py <filename.html>")
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    allocation_data = {
        'program_year': None,
        'date_range': None,
        'visa_190': {},
        'visa_491': {},
        'extraction_timestamp': datetime.now().isoformat()
    }
    
    # Find all tables
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables in the HTML")
    
    for idx, table in enumerate(tables):
        table_text = table.get_text().lower()
        
        # Check if this table contains visa allocation data
        if 'state and territory' in table_text or 'visa subclass' in table_text:
            print(f"\nTable {idx + 1} appears to contain allocation data")
            
            # Extract metadata
            parent = table.parent
            if parent:
                text = parent.get_text()
                
                # Extract program year
                year_match = re.search(r'(\d{4}-\d{2})\s+program year', text, re.IGNORECASE)
                if year_match:
                    allocation_data['program_year'] = year_match.group(1)
                    print(f"Program Year: {allocation_data['program_year']}")
                
                # Extract date range
                date_match = re.search(r'from\s+(\d+\s+\w+\s+\d{4})\s+to\s+(\d+\s+\w+\s+\d{4})', text, re.IGNORECASE)
                if date_match:
                    allocation_data['date_range'] = {
                        'from': date_match.group(1),
                        'to': date_match.group(2)
                    }
                    print(f"Date Range: {date_match.group(1)} to {date_match.group(2)}")
            
            # Parse table
            parse_table(table, allocation_data)
    
    return allocation_data


def parse_table(table, allocation_data):
    """Parse the allocation table"""
    
    # Get headers
    headers = []
    header_row = table.find('thead')
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
    else:
        first_row = table.find('tr')
        if first_row:
            headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
    
    print(f"Headers: {headers}")
    
    # Get all rows
    rows = table.find_all('tr')
    
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
        
        if not cells or len(cells) < 2:
            continue
        
        # Check if this row is for visa 190
        if '190' in cells[0]:
            print("\nFound Visa 190 row:")
            extract_allocations(cells, headers, allocation_data['visa_190'])
        
        # Check if this row is for visa 491
        elif '491' in cells[0]:
            print("\nFound Visa 491 row:")
            extract_allocations(cells, headers, allocation_data['visa_491'])


def extract_allocations(cells, headers, visa_data):
    """Extract state allocations from cells"""
    
    for i in range(1, len(cells)):
        if i < len(headers):
            column_name = headers[i]
            allocation = cells[i]
            
            # Only process if this column is a valid state/territory
            # This filters out month columns (Jul, Aug, etc.) and other data
            if column_name in STATES:
                # Clean the allocation number
                allocation_clean = re.sub(r'[^\d]', '', allocation)
                
                if allocation_clean:
                    visa_data[column_name] = int(allocation_clean)
                    print(f"  {column_name}: {allocation_clean}")
                else:
                    visa_data[column_name] = 0


def format_for_excel(allocation_data):
    """Format data for Excel export"""
    
    records = []
    
    # Create records for visa 190
    for state, allocation in allocation_data['visa_190'].items():
        records.append({
            'Program Year': allocation_data.get('program_year', ''),
            'Date From': allocation_data.get('date_range', {}).get('from', ''),
            'Date To': allocation_data.get('date_range', {}).get('to', ''),
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
            'Date From': allocation_data.get('date_range', {}).get('from', ''),
            'Date To': allocation_data.get('date_range', {}).get('to', ''),
            'Visa Subclass': '491',
            'Visa Name': 'Skilled Work Regional (Provisional) visa (subclass 491)',
            'State/Territory': state,
            'Allocations': allocation,
            'Extraction Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return records


def export_data(allocation_data):
    """Export data to files"""
    
    if not allocation_data['visa_190'] and not allocation_data['visa_491']:
        print("\nWARNING: No allocation data found!")
        return
    
    records = format_for_excel(allocation_data)
    df = pd.DataFrame(records)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # CSV
    csv_file = f"output/visa_allocations_{timestamp}.csv"
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ Data exported to CSV: {csv_file}")
    
    # Excel
    excel_file = f"output/visa_allocations_{timestamp}.xlsx"
    df.to_excel(excel_file, index=False, engine='openpyxl', sheet_name='Allocations')
    print(f"✅ Data exported to Excel: {excel_file}")
    
    # JSON
    json_file = f"output/visa_allocations_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(allocation_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Data exported to JSON: {json_file}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Program Year: {allocation_data.get('program_year', 'N/A')}")
    
    if allocation_data.get('date_range'):
        print(f"Date Range: {allocation_data['date_range'].get('from', 'N/A')} to {allocation_data['date_range'].get('to', 'N/A')}")
    
    print(f"\nVisa 190 States: {len(allocation_data['visa_190'])}")
    total_190 = sum(allocation_data['visa_190'].values())
    print(f"Visa 190 Total: {total_190:,}")
    
    print(f"\nVisa 491 States: {len(allocation_data['visa_491'])}")
    total_491 = sum(allocation_data['visa_491'].values())
    print(f"Visa 491 Total: {total_491:,}")
    
    print(f"\nGrand Total: {total_190 + total_491:,}")
    print("=" * 70)


def main():
    """Main entry point"""
    
    if len(sys.argv) < 2:
        print("Usage: python parse_saved_html.py <html_file>")
        print("\nExample:")
        print("  python parse_saved_html.py invitation_rounds.html")
        print("\nHow to save HTML:")
        print("1. Visit: https://immi.homeaffairs.gov.au/visas/working-in-australia/skillselect/invitation-rounds")
        print("2. Right-click → Save As → Save as 'invitation_rounds.html'")
        print("3. Run this script with the filename")
        sys.exit(1)
    
    filename = sys.argv[1]
    allocation_data = parse_html_file(filename)
    
    if allocation_data:
        export_data(allocation_data)
        print("\n✅ SUCCESS! Check the output folder for your data.")
    else:
        print("\n❌ FAILED! Could not extract data from HTML file.")


if __name__ == "__main__":
    main()
