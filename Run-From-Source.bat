@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3.12 -m venv .venv
    if errorlevel 1 goto :failure
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failure
.venv\Scripts\pythonw.exe -m applylocal
exit /b 0
:failure
echo Setup failed. Install Python 3.12 with the Python launcher from python.org, then try again.
pause
exit /b 1
