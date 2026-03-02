# N8N Automation Guide

This guide explains how to trigger the Visa Allocation Scraper automatically using ANY n8n instance running locally (e.g., `npx n8n` or Desktop app).

## 🚀 Quick Setup

1. **Open n8n**
   - If running locally: `npx n8n` or open your desktop app.

2. **Import Workflow**
   - Create a new workflow.
   - Click the **three dots** in the top right -> **Import from File**.
   - Select: `docs/n8n_local_workflow.json` (located in this project).

3. **Verify Path**
   - Click on the **Run Scraper** node (Execute Command).
   - Ensure the command points to the correct location of your script:
     ```bash
     python "c:\Users\Wiswacon\Documents\KAY\Interlace Studies\AUTOMATION LIBRARY\STATE ALLOCATION 2026\run_scraper.py" --json
     ```
   - Note the `--json` flag. This is CRITICAL. It ensures the script runs silently and outputs clean JSON for n8n to consume.

4. **Activate**
   - Toggle **Active** to true.
   - The workflow is set to run daily at 9:00 AM (you can change this in the Schedule Trigger node).

---

## 🔧 Technical Details

### The `--json` Flag
We updated `run_scraper.py` to accept a `--json` argument. When used:
1. **Headless Mode** is forced (no browser window).
2. **Console Logs** are suppressed (no "Navigating to..." text).
3. **JSON Output**: The final scraped data is printed to standard output (stdout) as a JSON string.

This allows the **Execute Command** node in n8n to capture the output directly.

### Data Flow
1. **Schedule Trigger**: Wake up n8n.
2. **Execute Command**: Runs python script.
   - Command: `python .../run_scraper.py --json`
   - Output: `{"visa_190": {...}, "visa_491": {...}}` (Raw string)
3. **Parse JSON**: Converts the raw string into an n8n JSON object.
   - You can now add nodes to save this to Google Sheets, Notion, Database, or Email.

### Troubleshooting
- **"Command not found"**: Ensure `python` is in your system PATH, or use the full path to python executable (e.g., `C:\Python39\python.exe`).
- **Timeout**: The scraper might take longer than n8n default timeout. Consider increasing timeout in the Execute Command node settings if needed.
