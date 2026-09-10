@echo off
REM Windows'ta cift tiklayarak calistirmak icin
cd /d "%~dp0"
python -m pip install -r requirements.txt
python app.py
pause
