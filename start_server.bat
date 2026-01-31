@echo off
cd /d "%~dp0"
echo Starting PDF Tools Server...
echo.
echo Server will be available at: http://127.0.0.1:5000/tools
echo.
echo Press Ctrl+C to stop the server
echo.
python app_full.py
pause
