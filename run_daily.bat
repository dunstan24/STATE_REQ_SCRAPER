@echo off
:: ============================================================================
:: AUTOMATED VISA SCRAPER RUNNER
:: 
:: This script is designed to be run by the Windows Task Scheduler.
:: It runs the python scraper and pushes the data to your n8n Webhook.
:: ============================================================================

:: 1. Navigate to the project directory (Ensures paths are correct)
cd /d "c:\Users\Wiswacon\Documents\KAY\Interlace Studies\AUTOMATION LIBRARY\STATE ALLOCATION 2026"

:: 2. Run the Scraper
:: REPLACE 'YOUR_WEBHOOK_URL_HERE' below with your actual n8n production webhook URL!
:: You will get this URL from the n8n "Webhook" node.
python run_visa_scraper.py --n8n --webhook-url "https://kayika.app.n8n.cloud/webhook/visa-data"

:: Optional: Log the run time to a local file for your own reference
echo Run completed at %date% %time% >> logs\scheduler_history.log
