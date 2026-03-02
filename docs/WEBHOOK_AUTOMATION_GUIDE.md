# Webhook Automation Guide

Since you cannot use the "Execute Command" node (likely because you are on n8n Cloud or a restricted version), we will use the **Webhook Method**.

**Concept**: Instead of n8n "pulling" the data, your computer will "push" the data to n8n automatically.

## Step 1: Set up n8n

1.  **Import the Workflow**
    *   In n8n, Import from file: `docs/n8n_webhook_workflow.json`.
2.  **Get the URL**
    *   Open the **Webhook** node.
    *   Click usually on "Webhook URLs".
    *   Select **Production URL** (Test URL only works if you have the n8n tab open).
    *   **Copy this URL**.
3.  **Activate**
    *   Toggle the workflow to **Active** (top right).

## Step 2: Configure the Local Script

1.  Open the file `run_daily.bat` in this folder.
2.  Find the text `YOUR_WEBHOOK_URL_HERE`.
3.  **Replace it** with the n8n URL you just copied.
    *   Example: `python run_scraper.py --n8n --webhook-url "https://your-n8n.com/webhook/..."`
4.  Save the file.
5.  **Test it**: Double-click `run_daily.bat`. You should see a command window open briefly and close. Check n8n execution log to see if data arrived.

## Step 3: Automate with Windows Task Scheduler

Now we tell Windows to run `run_daily.bat` every day.

1.  Press `Windows Key` + `R`, type `taskschd.msc` and hit Enter.
2.  In the right panel, click **Create Basic Task**.
3.  **Name**: "Visa Scraper Daily".
4.  **Trigger**: Select **Daily**.
5.  **Time**: Set your preferred time (e.g., 09:00:00).
6.  **Action**: **Start a program**.
7.  **Program/Script**: Browse and select `c:\Users\Wiswacon\Documents\KAY\Interlace Studies\AUTOMATION LIBRARY\STATE ALLOCATION 2026\run_daily.bat`.
    *   **Start in (Optional)**: Paste the folder path: `c:\Users\Wiswacon\Documents\KAY\Interlace Studies\AUTOMATION LIBRARY\STATE ALLOCATION 2026` (Important!).
8.  **Finish**.

🎉 **Done!**
- Your computer will wake up the script daily.
- The script will scrape the data.
- The script will send the data to n8n.
- n8n will process it.
