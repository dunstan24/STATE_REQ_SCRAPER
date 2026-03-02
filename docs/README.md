# Australian Immigration Data Scraper (Occupation List Multi-State Scraper)

A professional Python web scraping tool designed to extract State and Territory occupation list data from 8 Australian states and territories, normalizing it against the ANZSCO master list.

## 🎯 Purpose

This tool automatically scrapes immigration data regarding State and Territory occupation lists. It is engineered to handle differing website structures, CAPTCHAs, and dynamic content across ACT, NSW, NT, QLD, SA, TAS, VIC, and WA.

## ✨ Features

- **Automated Web Scraping**: Uses Selenium and Playwright for dynamic content handling.
- **Data Normalization**: Automatically maps extracted and loosely formatted occupations against a Master ANZSCO list to produce standardized codes and names.
- **Crash Resiliency**: Sub-results are saved instantly as batch CSVs per-state, ensuring partial data is preserved even if another state scraper fails.
- **Multiple Export Formats**: CSV and Excel.
- **Robust Error Handling**: Comprehensive logging and error recovery.
- **N8N Integration Ready**: Built-in support for n8n automation workflows.

## 📋 Requirements

- Python 3.8 or higher
- Chrome browser (for Selenium/Playwright)
- Internet connection

## 🚀 Installation

### Step 1: Install Python Dependencies

```powershell
pip install -r requirements.txt
playwright install
```

## 📖 Usage

### Basic Usage

Run the scraper through the main entry point:

```powershell
python run_scraper.py
```

### Configuration

Edit `src/config.py` to customize settings like `TARGET_URLS` and configuration options. 
Note: The `--no-headless` flag defaults to False, but some states like ACT might inherently run non-headless due to protections.

### Output

The scraper creates the following directories and files:

```
output/run_YYYYMMDD_HHMMSS/
├── occupation_list_FINAL_YYYYMMDD_HHMMSS.csv
├── occupation_list_FINAL_YYYYMMDD_HHMMSS.xlsx
└── [STATE]_[list_type]_raw.csv (for each state)

logs/
└── scraper_YYYYMMDD_HHMMSS.log
```

## 🔄 N8N Integration

The project has robust integration capabilities with n8n described in `N8N_CONNECTION_GUIDE.md`.

## 🏗️ Project Structure

```
STATE ALLOCATION 2026/
├── run_scraper.py          # Main complete scraping script
├── src/
│   ├── scrapers/           # Submodules detailing extraction per state
│   ├── config.py           # Configuration settings
│   ├── normalizer.py       # Maps arbitrary titles to ANZSCO standard
│   ├── n8n_integration.py  # N8N integration utilities
│   └── data_analyzer.py    # Data analysis tools
├── requirements.txt        # Python dependencies
├── README.md               # Main repository file
├── output/                 # Scraped data output
└── logs/                   # Execution logs
```

## 🔧 Advanced Usage

### Specific State extraction

To debug or run just one state simply pass it as a flag parameter:
```powershell
python run_scraper.py --state QLD --no-headless
```

### Skipping Normalization

If the ANZSCO master file isn't needed, you can export raw records identically to how they appear on the target websites:
```powershell
python run_scraper.py --skip-normalize
```

## 🐛 Troubleshooting

### Page Not Loading

- Check your internet connection
- The site structure might have changed. Visit the URL directly and compare it to the specific state scraper defined in `src/scrapers/[state]_scraper.py`
- Try utilizing the `--no-headless` flag to verify if a CAPTCHA blocks the headless browser instance

### Import Errors

Make sure all dependencies are installed:

```powershell
pip install -r requirements.txt --upgrade
```

## 📝 Logging

Logs are saved in the `logs/` directory with timestamps. Log levels:

- **INFO**: Normal operation
- **WARNING**: Potential issues
- **ERROR**: Errors that don't stop execution
- **CRITICAL**: Fatal errors

## 🔒 Best Practices

1. **Respect Rate Limits**: Don't run the scraper too frequently
2. **Monitor Logs**: Check logs regularly for errors
3. **Update Regularly**: Website structures change - update extraction logic in the `scrapers/` subfolder as needed
4. **Test First**: Run a single state with `--no-headless` when writing a revised script before running the full batch.
