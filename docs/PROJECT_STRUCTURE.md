# 📁 Project Structure

## Clean, Professional Organization

```
STATE ALLOCATION 2026/
│
├── 📂 src/                                  # Python Source Code
│   ├── 📂 scrapers/                         # State-specific extractor logic
│   │   ├── __init__.py
│   │   ├── base_scraper.py                  # Base class for common scrape functions
│   │   ├── playwright_helper.py             # Playwright utilities
│   │   ├── act_scraper.py                   # ACT specific scraper
│   │   ├── nsw_scraper.py                   # NSW specific scraper
│   │   └── ...                              # Other state scrapers
│   ├── 📂 master_data/                      # ANZSCO reference lookup files
│   ├── __init__.py                          # Package initialization
│   ├── config.py                            # URL endpoints, wait times, formats
│   ├── normalizer.py                        # Maps arbitrary titles to ANZSCO standard
│   ├── n8n_integration.py                   # N8N webhook integration
│   ├── data_analyzer.py                     # Data analysis tools
│   ├── parse_saved_html.py                  # HTML parser (fallback method)
│   └── visa_allocation_scraper.py           # Generic/Legacy scraper
│
├── 📂 docs/                                 # Documentation
│   ├── README.md                            # General documentation
│   ├── PROJECT_STRUCTURE.md                 # Project component breakdown (you are here)
│   ├── N8N_CONNECTION_GUIDE.md              # Connecting the output to n8n
│   ├── MANUAL_EXTRACTION_GUIDE.md           # Manual extraction steps
│   ├── SETUP.md                             # Setup instructions
│   └── ARCHITECTURE.md                      # Technical architecture
│
├── 📂 output/                               # Generated Data (auto-created)
│   └── 📂 run_YYYYMMDD_HHMMSS/              # Single run directory grouping all results
│       ├── occupation_list_FINAL_*.csv      # Final Normalized CSV
│       ├── occupation_list_FINAL_*.xlsx     # Final Normalized XLSX
│       └── [STATE]_[list_type]_raw.csv      # Batch files for individual states
│
├── 📂 logs/                                 # Execution Logs (auto-created)
│   └── scraper_*.log                        # Timestamped execution run logs
│
├── 📄 run_scraper.py                        # Main complete scraping script
├── 🔧 start_scraper.bat                     # Windows quick start / Interactive Menu
│
├── 📋 requirements.txt                      # Python dependencies
├── 📖 README.md                             # Main entry point overview
├── 📝 CHANGELOG.md                          # Version history
├── 🚫 .gitignore                            # Git ignore rules
│
└── 📄 Scrapping Idea.txt                    # Original requirements
```

---

## 📂 Directory Details

### `src/` - Source Code
All Python modules organized logically. Unlike earlier versions, we utilize modular scrapers per state:
- **`scrapers/` submodule**: Contains `base_scraper.py`, `playwright_helper.py`, and individual scripts like `nsw_scraper.py` which are dynamically loaded. This makes it trivial to change behavior when one specific state changes its website.
- **`config.py`**: A strict manifest defining `TARGET_URLS` mapped by State and List Type.
- **`normalizer.py`**: Given raw data containing string descriptors of ANZSCO fields, it attempts a fuzzy/similarity lookup against `.csv` rules embedded in `master_data/`. 

### `docs/` - Documentation
Comprehensive documentation for all use cases:
- **User guides**: Step-by-step instructions
- **Technical docs**: Architecture and implementation details
- **Integration**: Connecting the pipelines to downstream tools like n8n.

### `output/` - Generated Data
Instead of populating a flat root folder, runs are separated:
- **`run_.../` Subfolders**: A unique folder per run prevents states colliding.
- **Intermediate Resiliency**: `*_raw.csv` dumps mean any crash after State A saves State A's data without State B deleting it.
- **Final Combined Merges**: The CSV & Excel files combine all raw datasets passed through the ANZSCO normalizer.

### `logs/` - Execution Logs
Detailed logs for debugging and monitoring:
- **Timestamped logs**: Track each execution
- **Crash Context**: Exception blocks catch Selenium/Playwright errors and write traceback to files.

---

## 🎯 Key Files

### Entry Points
| File | Purpose | Usage |
|------|---------|-------|
| `run_scraper.py` | Main robust multi-state scraper | `python run_scraper.py` |
| `start_scraper.bat` | Quick start interactive CLI menu | Double-click to run |
| `parse_html.py` | HTML parser | `python parse_html.py file.html` |

### Configuration
| File | Purpose |
|------|---------|
| `src/config.py` | All settings (URLs, timeouts, target lists) |
| `requirements.txt` | Python package dependencies for Selenium and Playwright |
| `.gitignore` | Files to exclude from version control |

### Documentation
| File | Content |
|------|---------|
| `README.md` | Primary Guide for the Scraper |
| `docs/README.md` | Secondary documentation index |
| `docs/PROJECT_STRUCTURE.md` | Breakdowns of components (this file) |

---

## 🔄 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INITIATES SCRAPER                   │
│         (run_scraper.py or start_scraper.bat)               │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                ITERATING OVER `TARGET_URLS`                 │
│  • src/config.py provides the list of lists                 │
│  • Each state loops one-by-one                              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   EXTRACT STATE (scrapers/)                 │
│  • Dynamically loads `[state]_scraper.py`                   │
│  • Selenium or Playwright extracts raw rows                 │
│  • Falls back to explicit waits/CAPTCHA waits               │
│  • Immediate Export -> `[STATE]_[list_type]_raw.csv`        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 MERGE AND NORMALIZE (normalizer.py)         │
│  • All raw CSVs are parsed together                         │
│  • Strings mapped strictly to ANZSCO `master_data/`         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   EXPORT FINALIZED DATA                     │
│  • output/run_YYYYMMDD_HHMM/occupation_list_FINAL_*.xlsx    │
│  • output/run_YYYYMMDD_HHMM/occupation_list_FINAL_*.csv     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Design Principles

### 1. **Fault Isolation via Modularity**
State websites change frequently. By putting all NSW parsing in `src/scrapers/nsw_scraper.py`, broken parsers won't affect ACT processing. 

### 2. **State-Level Crash Resiliency**
Results string together iteratively. In the old `visa_allocation_scraper.py`, breaking halfway through lost everything. The new system dumps straight to `_raw.csv` the second a state completes.

### 3. **Clean Imports**
```python
# From generic driver code
from src.scrapers import get_scraper
from src.normalizer import load_master, normalize
```

### 4. **Agnostic Downstream Data**
The normalizer ensures that whichever string NSW uses for a job matches the string SA uses, unifying the final datasets.

---

## 🚀 Quick Navigation

### I want to...

**Run all states:**
→ `python run_scraper.py`

**Change target URLs or Master paths:**
→ Edit `src/config.py`

**Modify a specific state website logic:**
→ Edit `src/scrapers/[state]_scraper.py`

**Diagnose why a state failed to get data:**
→ Check `logs/` for the error trace and run `python run_scraper.py --state [state] --no-headless`

**Review final compiled results:**
→ Check `output/run_[timestamp]/occupation_list_FINAL_*.xlsx`

---

## 📝 File Naming Conventions

### Batch Output Files
- **Per State Extraction**: `{STATE}_{list_type}_raw.csv` -> `QLD_onshore_raw.csv` 

### Final Output Files
- **Timestamped Combined**: `occupation_list_FINAL_{timestamp}.xlsx`

---

**This structure ensures maximum reliability when iterating over highly mutable government endpoints.** 🎉
