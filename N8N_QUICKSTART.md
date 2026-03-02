# 🚀 Quick Start: Connect to n8n

## 3 Simple Steps

### Step 1: Set Up n8n

**Option A - Cloud (Easiest):**
- Go to https://n8n.io/cloud/
- Sign up and create account

**Option B - Local:**
```powershell
# Using Docker
docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n

# OR using npm
npm install -g n8n
n8n start
```

Access at: http://localhost:5678

---

### Step 2: Create Webhook in n8n

1. **Create New Workflow** in n8n
2. **Add Webhook Node:**
   - Click "+" → Search "Webhook"
   - HTTP Method: `POST`
   - Path: `visa-data`
3. **Copy Webhook URL** (example):
   - Cloud: `https://your-instance.app.n8n.cloud/webhook/visa-data`
   - Local: `http://localhost:5678/webhook/visa-data`
4. **Activate Workflow** (toggle switch at top)

---

### Step 3: Run Python Scraper

**Method 1 - Easy Batch File:**
1. Edit `send_to_n8n.bat`
2. Update `WEBHOOK_URL` with your URL
3. Double-click to run!

**Method 2 - Command Line:**
```powershell
python run_visa_scraper.py --n8n --webhook-url "YOUR_WEBHOOK_URL"
```

**Method 3 - With Visible Browser (for testing):**
```powershell
python run_visa_scraper.py --no-headless --n8n --webhook-url "YOUR_WEBHOOK_URL"
```

---

## 📊 What Gets Sent to n8n?

```json
{
  "timestamp": "2026-01-26T12:47:18",
  "records_count": 16,
  "data": [
    {
      "program_year": "2025-26",
      "visa_subclass": "190",
      "state_territory": "NSW",
      "allocations": 700
    }
    // ... more records
  ]
}
```

---

## 🔄 Connection Flow

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Python Scraper │  HTTP   │   Webhook    │  Flow   │  Your Actions   │
│                 │ ──────> │              │ ──────> │  (Save, Email,  │
│ run_visa_       │  POST   │   n8n        │         │   Notify, etc.) │
│ scraper.py      │  JSON   │              │         │                 │
└─────────────────┘         └──────────────┘         └─────────────────┘
```

---

## ✅ Test Your Connection

1. In n8n: Click **"Listen for Test Event"** on webhook
2. Run: `python run_visa_scraper.py --n8n --webhook-url "YOUR_URL"`
3. Check n8n - data should appear!

---

## 📁 Files You Need

- **`send_to_n8n.bat`** - Easy one-click run
- **`n8n_workflow_template.json`** - Import this into n8n
- **`docs/N8N_CONNECTION_GUIDE.md`** - Full documentation

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | Make sure n8n is running |
| 404 Not Found | Activate workflow in n8n |
| No data appears | Click "Listen for Test Event" first |
| Timeout | Check webhook URL is correct |

---

## 📚 Next Steps

1. **Import Workflow Template:**
   - In n8n: Workflows → Import from File
   - Select: `n8n_workflow_template.json`

2. **Customize Workflow:**
   - Add Google Sheets node
   - Add Email notification
   - Add Database storage

3. **Schedule Automation:**
   - Add Cron node in n8n
   - Set schedule (e.g., daily at 9 AM)

---

## 🎯 Example Use Cases

### Save to Google Sheets
Add **Google Sheets** node after webhook → Append rows

### Send Email Alert
Add **Gmail** node → Send summary when data received

### Store in Database
Add **Postgres/MySQL** node → Insert records

### Slack Notification
Add **Slack** node → Post message to channel

---

**Need detailed help?** See `docs/N8N_CONNECTION_GUIDE.md`

**Ready to go?** Run `send_to_n8n.bat` now! 🚀
