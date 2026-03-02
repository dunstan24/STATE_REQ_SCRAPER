@echo off
echo ================================================
echo   Occupation List Multi-State Scraper
echo ================================================
echo.

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [INFO] Virtual environment activated.
) else (
    echo [WARN] No virtual environment found. Using system Python.
)

echo.
echo [1] Run ALL states (headless)
echo [2] Run ALL states (visible browser)
echo [3] Run specific state (headless)
echo [4] Run specific state (visible browser)
echo [5] Run ALL states, skip normalization (raw output)
echo.
set /p CHOICE="Enter choice (1-5): "

if "%CHOICE%"=="1" (
    python run_scraper.py
    goto :done
)

if "%CHOICE%"=="2" (
    python run_scraper.py --no-headless
    goto :done
)

if "%CHOICE%"=="3" (
    set /p STATE="Enter state code (e.g. QLD, SA, NSW): "
    python run_scraper.py --state %STATE%
    goto :done
)

if "%CHOICE%"=="4" (
    set /p STATE="Enter state code (e.g. QLD, SA, NSW): "
    python run_scraper.py --state %STATE% --no-headless
    goto :done
)

if "%CHOICE%"=="5" (
    python run_scraper.py --skip-normalize
    goto :done
)

echo Invalid choice. Exiting.

:done
echo.
pause
