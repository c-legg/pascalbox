@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0main.py" %*
    exit /b 0
)
where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0main.py" %*
    exit /b %errorlevel%
)
echo Python 3 was not found on PATH.
echo Install Python 3.10+ or edit run.bat to point at your python.exe.
pause
exit /b 1
