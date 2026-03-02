# 🔗 Connecting Python Scraper to n8n

This guide shows you how to connect your visa allocation scraper to n8n for automated workflows.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Setting Up n8n](#setting-up-n8n)
3. [Creating a Webhook in n8n](#creating-a-webhook-in-n8n)
4. [Connecting Python to n8n](#connecting-python-to-n8n)
5. [Testing the Connection](#testing-the-connection)
6. [Advanced Workflows](#advanced-workflows)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Method 1: Direct Webhook Integration

```powershell
# Run scraper and send data to n8n
python run_scraper.py --n8n --webhook-url "https://your-n8n-instance.com/webhook/visa-data"
```

### Method 2: Save JSON and Import to n8n

```powershell
# Run scraper (saves JSON automatically)
python run_scraper.py

# JSON file will be in: output/visa_allocations_YYYYMMDD_HHMMSS.json
# Import this file into n8n using "Read Binary File" node
```

---

## 🛠️ Setting Up n8n

### Option 1: Cloud (Easiest)

1. **Sign up for n8n Cloud**: https://n8n.io/cloud/
2. Create a new workflow
3. Skip to [Creating a Webhook](#creating-a-webhook-in-n8n)

### Option 2: Self-Hosted (Docker)

```powershell
# Install n8n using Docker
docker run -it --rm `
  --name n8n `
  -p 5678:5678 `
  -v ${PWD}/.n8n:/home/node/.n8n `
  n8nio/n8n

# Access n8n at: http://localhost:5678
```

### Option 3: Self-Hosted (npm)

```powershell
# Install n8n globally
npm install -g n8n

# Start n8n
n8n start

# Access n8n at: http://localhost:5678
```

---

## 📡 Creating a Webhook in n8n

### Step 1: Create New Workflow

1. Open n8n interface
2. Click **"New Workflow"**
3. Name it: `Immigration Data Processor`

### Step 2: Add Webhook Node

1. Click **"+"** to add a node
2. Search for **"Webhook"**
3. Select **"Webhook"** node
4. Configure:
   - **HTTP Method**: `POST`
   - **Path**: `visa-data` (or any name you want)
   - **Response Mode**: `Respond to Webhook`

5. **Copy the Webhook URL** (looks like):
   - Cloud: `https://your-instance.app.n8n.cloud/webhook/visa-data`
   - Local: `http://localhost:5678/webhook/visa-data`

### Step 3: Test Webhook (Optional)

Click **"Listen for Test Event"** in the webhook node to test.

---

## 🐍 Connecting Python to n8n

### Method 1: Command Line (Recommended)

```powershell
# Basic usage
python run_scraper.py --n8n --webhook-url "YOUR_WEBHOOK_URL"

# With visible browser (for debugging)
python run_scraper.py --no-headless --n8n --webhook-url "YOUR_WEBHOOK_URL"
```

### Method 2: Programmatic Integration

Create a custom script:

```python
# custom_n8n_scraper.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from visa_allocation_scraper import VisaAllocationScraper
from n8n_integration import N8NIntegration

# Your n8n webhook URL
WEBHOOK_URL = "https://your-n8n-instance.com/webhook/visa-data"

# Run scraper
scraper = VisaAllocationScraper()
allocation_data = scraper.run()

# Send to n8n
if allocation_data:
    records = scraper.format_for_excel(allocation_data)
    n8n = N8NIntegration(WEBHOOK_URL)
    success = n8n.send_data(records)
    
    if success:
        print("✅ Data sent to n8n successfully!")
    else:
        print("❌ Failed to send data to n8n")
```

Run it:
```powershell
python custom_n8n_scraper.py
```

### Method 3: Batch File (Windows)

Create `send_to_n8n.bat`:

```batch
@echo off
echo ================================================
echo Visa Scraper - n8n Integration
echo ================================================

set WEBHOOK_URL=https://your-n8n-instance.com/webhook/visa-data

python run_scraper.py --n8n --webhook-url %WEBHOOK_URL%

pause
```

Double-click to run!

---

## 📊 Data Format Sent to n8n

Your Python scraper sends data in this format:

```json
{
  "timestamp": "2026-01-26T12:47:18.123456",
  "batch_number": 1,
  "total_batches": 1,
  "records_count": 16,
  "data": [
    {
      "program_year": "2025-26",
      "date_from": "1 July 2025",
      "date_to": "31 December 2025",
      "visa_subclass": "190",
      "state_territory": "NSW",
      "allocations": 700
    },
    {
      "program_year": "2025-26",
      "date_from": "1 July 2025",
      "date_to": "31 December 2025",
      "visa_subclass": "190",
      "state_territory": "VIC",
      "allocations": 839
    }
    // ... more records
  ]
}
```

---

## 🧪 Testing the Connection

### Step 1: Test Webhook in n8n

1. In n8n, click **"Listen for Test Event"** on webhook node
2. Run your Python scraper:
   ```powershell
   python run_scraper.py --n8n --webhook-url "YOUR_WEBHOOK_URL"
   ```
3. Check n8n - you should see data appear!

### Step 2: Verify Data

In n8n, add a **"Code"** node after webhook:

```javascript
// Check received data
const data = $input.item.json;

console.log('Received records:', data.records_count);
console.log('First record:', data.data[0]);

return $input.all();
```

---

## 🔄 Advanced Workflows

### Example 1: Save to Google Sheets

**n8n Workflow:**
1. **Webhook** (receive data)
2. **Code** (process data)
3. **Google Sheets** (append rows)

**Code Node:**
```javascript
// Transform data for Google Sheets
const records = $input.item.json.data;

return records.map(record => ({
  json: {
    'Program Year': record.program_year,
    'Date From': record.date_from,
    'Date To': record.date_to,
    'Visa': record.visa_subclass,
    'State': record.state_territory,
    'Allocations': record.allocations,
    'Scraped At': $input.item.json.timestamp
  }
}));
```

### Example 2: Send Email Notification

**n8n Workflow:**
1. **Webhook** (receive data)
2. **Code** (calculate totals)
3. **Gmail** (send summary email)

**Code Node:**
```javascript
// Calculate summary
const records = $input.item.json.data;
const visa190 = records.filter(r => r.visa_subclass === '190');
const visa491 = records.filter(r => r.visa_subclass === '491');

const total190 = visa190.reduce((sum, r) => sum + r.allocations, 0);
const total491 = visa491.reduce((sum, r) => sum + r.allocations, 0);

return [{
  json: {
    subject: 'Visa Allocation Data Updated',
    body: `
      New visa allocation data received:
      
      Visa 190: ${total190} allocations across ${visa190.length} states
      Visa 491: ${total491} allocations across ${visa491.length} states
      Total: ${total190 + total491} allocations
      
      Scraped at: ${$input.item.json.timestamp}
    `
  }
}];
```

### Example 3: Save to Database

**n8n Workflow:**
1. **Webhook** (receive data)
2. **Split In Batches** (process in chunks)
3. **Postgres/MySQL** (insert records)

**Postgres Node Configuration:**
- **Operation**: `Insert`
- **Table**: `visa_allocations`
- **Columns**: Map from incoming data

### Example 4: Conditional Processing

**n8n Workflow:**
1. **Webhook** (receive data)
2. **IF** (check if allocations > 500)
3. **Slack** (send alert for high allocations)
4. **Google Sheets** (save all data)

---

## 🔐 Security Best Practices

### 1. Use Authentication

In n8n webhook node:
- Enable **"Authentication"**
- Choose **"Header Auth"**
- Set header name: `X-API-Key`
- Set header value: `your-secret-key`

Update Python code:

```python
# In src/n8n_integration.py, modify send_data method:
response = requests.post(
    self.webhook_url,
    json=payload,
    headers={
        "Content-Type": "application/json",
        "X-API-Key": "your-secret-key"  # Add this
    },
    timeout=30
)
```

### 2. Use Environment Variables

```powershell
# Set environment variable
$env:N8N_WEBHOOK_URL = "https://your-webhook-url"
$env:N8N_API_KEY = "your-secret-key"

# Use in Python
import os
webhook_url = os.getenv('N8N_WEBHOOK_URL')
```

### 3. Use HTTPS

Always use HTTPS webhooks in production:
- ✅ `https://your-n8n.com/webhook/visa-data`
- ❌ `http://your-n8n.com/webhook/visa-data`

---

## 🐛 Troubleshooting

### Issue 1: Connection Refused

**Error:** `Connection refused` or `Failed to connect`

**Solutions:**
1. Check if n8n is running: `http://localhost:5678`
2. Verify webhook URL is correct
3. Check firewall settings
4. For local n8n, use `http://localhost:5678/webhook/...`

### Issue 2: 404 Not Found

**Error:** `404 Not Found`

**Solutions:**
1. Verify webhook path matches in n8n
2. Ensure workflow is **activated** (toggle switch in n8n)
3. Check webhook URL format

### Issue 3: Timeout

**Error:** `Request timeout`

**Solutions:**
1. Increase timeout in Python:
   ```python
   # In src/n8n_integration.py
   response = requests.post(
       self.webhook_url,
       json=payload,
       headers={"Content-Type": "application/json"},
       timeout=60  # Increase from 30 to 60
   )
   ```
2. Reduce batch size:
   ```python
   n8n.send_data(records, batch_size=50)  # Default is 100
   ```

### Issue 4: Data Not Appearing

**Solutions:**
1. Click **"Listen for Test Event"** in n8n before running scraper
2. Check n8n execution logs
3. Add debug logging in Python:
   ```powershell
   python run_scraper.py --n8n --webhook-url "URL" --no-headless
   ```

### Issue 5: SSL Certificate Error

**Error:** `SSL: CERTIFICATE_VERIFY_FAILED`

**Temporary fix (not recommended for production):**
```python
# In src/n8n_integration.py
response = requests.post(
    self.webhook_url,
    json=payload,
    headers={"Content-Type": "application/json"},
    timeout=30,
    verify=False  # Add this (use only for testing!)
)
```

---

## 📅 Scheduling Automated Runs

### Option 1: Windows Task Scheduler

1. Open **Task Scheduler**
2. Create **New Task**
3. **Trigger**: Daily at 9:00 AM
4. **Action**: Run `send_to_n8n.bat`

### Option 2: n8n Cron Trigger

Instead of Python calling n8n, have n8n trigger Python:

**n8n Workflow:**
1. **Cron** (schedule: daily at 9:00 AM)
2. **Execute Command** (run Python script)
3. **Webhook** (receive results)

**Execute Command Node:**
```bash
cd "C:/Users/Wiswacon/Documents/KAY/Interlace Studies/AUTOMATION LIBRARY/STATE ALLOCATION 2026"
python run_scraper.py --n8n --webhook-url "http://localhost:5678/webhook/visa-data"
```

### Option 3: Python Scheduler

```python
# scheduled_scraper.py
import schedule
import time
from run_visa_scraper import run_visa_scraper

WEBHOOK_URL = "https://your-n8n.com/webhook/visa-data"

def job():
    print("Running scheduled scrape...")
    run_visa_scraper(headless=True, send_to_n8n=True, webhook_url=WEBHOOK_URL)

# Run every day at 9:00 AM
schedule.every().day.at("09:00").do(job)

print("Scheduler started. Waiting for scheduled time...")
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 📚 Additional Resources

- **n8n Documentation**: https://docs.n8n.io/
- **n8n Webhook Guide**: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- **n8n Community**: https://community.n8n.io/
- **Python Requests**: https://requests.readthedocs.io/

---

## ✅ Quick Reference

### Run Scraper with n8n

```powershell
# Basic
python run_scraper.py --n8n --webhook-url "YOUR_URL"

# With visible browser
python run_scraper.py --no-headless --n8n --webhook-url "YOUR_URL"

# Just scrape (no n8n)
python run_scraper.py
```

### n8n Webhook URL Format

- **Cloud**: `https://your-instance.app.n8n.cloud/webhook/visa-data`
- **Local**: `http://localhost:5678/webhook/visa-data`
- **Custom**: `https://your-domain.com/webhook/visa-data`

### Data Flow

```
Python Scraper → Webhook → n8n Workflow → Your Destination
                                          (Sheets, DB, Email, etc.)
```

---

**Need help?** Check the logs in `logs/` directory or run with `--no-headless` to see what's happening!
