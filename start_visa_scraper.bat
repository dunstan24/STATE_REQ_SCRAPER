@echo off
REM Quick Start Script for Visa Allocation Scraper (190 & 491)
REM Extracts State and Territory allocation data

echo ========================================
echo Visa Allocation Scraper
echo Subclass 190 and 491
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo Python found!
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created!
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
echo Checking dependencies...
pip show selenium >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo Dependencies installed!
    echo.
)

REM Run the visa allocation scraper
echo.
echo ========================================
echo Starting Visa Allocation Scraper...
echo ========================================
echo.

python run_visa_scraper.py --no-headless

REM Deactivate virtual environment
deactivate

echo.
echo ========================================
echo Scraping complete!
echo Check the 'output' folder for results
echo ========================================
echo.

pause
