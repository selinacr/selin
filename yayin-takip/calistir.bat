@echo off
REM Yedek yontem: kisayol yerine bu dosyayi da cift tiklayabilirsin.
cd /d "%~dp0"
start "" pythonw app.py || python app.py
