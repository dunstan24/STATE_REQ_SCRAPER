@echo off
REM ================================================
REM Visa Scraper - n8n Integration
REM ================================================

echo.
echo ================================================
echo VISA ALLOCATION SCRAPER - N8N INTEGRATION
echo ================================================
echo.

REM ------------------------------------------------
REM CONFIGURATION - UPDATE YOUR WEBHOOK URL HERE
REM ------------------------------------------------

REM Option 1: n8n Cloud
REM set WEBHOOK_URL=https://your-instance.app.n8n.cloud/webhook/visa-data

REM Option 2: Local n8n
set WEBHOOK_URL=http://localhost:5678/webhook/visa-data

REM Option 3: Custom domain
REM set WEBHOOK_URL=https://your-domain.com/webhook/visa-data

REM ------------------------------------------------
REM CHECK IF WEBHOOK URL IS SET
REM ------------------------------------------------

if "%WEBHOOK_URL%"=="http://localhost:5678/webhook/visa-data" (
    echo WARNING: Using default local webhook URL
    echo Make sure n8n is running on http://localhost:5678
    echo.
    echo To change the webhook URL, edit this file: send_to_n8n.bat
    echo.
)

echo Webhook URL: %WEBHOOK_URL%
echo.

REM ------------------------------------------------
REM RUN OPTIONS
REM ------------------------------------------------

echo Select run mode:
echo [1] Headless mode (browser hidden)
echo [2] Visible browser (for debugging)
echo.
set /p MODE="Enter choice (1 or 2): "

echo.
echo ================================================
echo STARTING SCRAPER...
echo ================================================
echo.

if "%MODE%"=="2" (
    echo Running with VISIBLE browser...
    python run_visa_scraper.py --no-headless --n8n --webhook-url "%WEBHOOK_URL%"
) else (
    echo Running in HEADLESS mode...
    python run_visa_scraper.py --n8n --webhook-url "%WEBHOOK_URL%"
)

echo.
echo ================================================
echo DONE!
echo ================================================
echo.
echo Check your n8n workflow to see the received data.
echo.

pause
