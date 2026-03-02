# Occupation List Multi-State Scraper

Extract **State and Territory Occupation List data** from 8 Australian states and territories, and normalize the results against the ANZSCO master list.

## 🎯 Purpose

This tool automatically scrapes State and Territory occupation lists for migration programs from:
**ACT, NSW, NT, QLD, SA, TAS, VIC, WA**

It unifies the diverse formats from each state's website and maps the occupations to standardized ANZSCO codes.

## 🚀 Quick Start

### Option 1: Interactive Menu (Easiest)

Double-click or run: **`start_scraper.bat`**

### Option 2: Command Line

```powershell
# Install dependencies first
pip install -r requirements.txt

# Run ALL states (headless)
python run_scraper.py

# Run ALL states (visible browser)
python run_scraper.py --no-headless

# Run specific state (e.g. QLD)
python run_scraper.py --state QLD

# Run specific state with visible browser
python run_scraper.py --state SA --no-headless

# Run ALL states, skip normalization (raw output)
python run_scraper.py --skip-normalize
```

## 📁 Project Structure

```
STATE ALLOCATION 2026/
├── src/                          # Python source code
│   ├── scrapers/                 # State-specific scrapers
│   ├── config.py                 # Configuration
│   ├── normalizer.py             # ANZSCO mapping
│   ├── n8n_integration.py        # N8N integration
│   └── data_analyzer.py          # Data analysis tools
│
├── docs/                         # Documentation
├── output/                       # Scraped data (auto-generated per run)
├── logs/                         # Execution logs (auto-generated)
├── src/master_data/              # Master ANZSCO data files
│
├── run_scraper.py               # Main execution script
├── start_scraper.bat            # Windows interactive starter
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 📄 Output Files

After running, check the `output/run_YYYYMMDD_HHMMSS/` folder:

1. **`occupation_list_FINAL_YYYYMMDD_HHMMSS.xlsx`** - Excel format (normalized)
2. **`occupation_list_FINAL_YYYYMMDD_HHMMSS.csv`** - CSV format (normalized)
3. **`[STATE]_[list_type]_raw.csv`** - Raw extraction files per state
4. **`scraper_YYYYMMDD_HHMMSS.log`** - Exection logs (in the `logs/` directory)

### Excel Output Format

| state_code | anzsco_unit_group_code | unit_group_name | anzsco_occupation_code | occupation_name | 190 | 491 |
|------------|------------------------|-----------------|------------------------|-----------------|-----|-----|
| NSW        | 2611                   | ICT Business... | 261111                 | ICT Business... | Y   | Y   |

## 📚 Documentation

- **[Project Structure](docs/PROJECT_STRUCTURE.md)** - Documentation of folders
- **[N8N Connection Guide](docs/N8N_CONNECTION_GUIDE.md)** - N8N Integration Guide
- **[Manual Guide](docs/MANUAL_EXTRACTION_GUIDE.md)** - Manual extraction steps
- **[Setup Guide](docs/SETUP.md)** - Installation and setup
- **[Architecture](docs/ARCHITECTURE.md)** - Technical details

## 🔧 Configuration

Edit `src/config.py` to customize global constants such as URLs or Master Data paths.

## 🔄 N8N Integration

Send data directly to n8n automation workflows!

### Quick Start

```powershell
# Easy way - use the batch file
.\send_to_n8n.bat
```

## 🐛 Troubleshooting

### Chrome Driver / Playwright Issues?
→ Some scrapers use Selenium and others use Playwright. Make sure your browsers are installed, e.g., `playwright install`.

### No Data Extracted?
→ Run with `--no-headless` to see if the website structure has changed or if there is a CAPTCHA.

### Website Changed?
→ If an error occurs during scrape, check the state script in `src/scrapers/` for updates to the CSS selectors.

## 📞 Quick Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Run scraper (visible browser)
python run_scraper.py --no-headless

# Run scraper (headless)
python run_scraper.py

# One-click wizard
.\start_scraper.bat
```

## 📝 Requirements

- Python 3.8+
- Active Internet connection
- Necessary browser drivers (Selenium/Playwright)

## 🎉 Features

- ✅ Automated browser scraping (Selenium & Playwright)
- ✅ Master Data Normalization (ANZSCO)
- ✅ Multiple export formats (Excel, CSV)
- ✅ N8N integration ready
- ✅ Comprehensive logging & crash resiliency (saves partial states)

---

**Ready to extract your occupation list data!** 🚀
