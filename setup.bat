@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher was not found. Install Python 3.11 or newer from https://www.python.org/downloads/
    pause
    exit /b 1
)

py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))"
if errorlevel 1 (
    echo Python 3.11 or newer is required.
    pause
    exit /b 1
)

where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama is required. Install it from https://ollama.com/download, start Ollama, then rerun setup.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto failed
".venv\Scripts\patchright.exe" install chromium
if errorlevel 1 goto failed
ollama pull hermes3:8b
if errorlevel 1 goto failed

if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo Setup complete. Double-click start.bat to launch Lioran.
pause
exit /b 0

:failed
echo.
echo Setup failed. Check the error above, ensure Ollama is running, and rerun setup.bat.
pause
exit /b 1
