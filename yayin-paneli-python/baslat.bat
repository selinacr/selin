@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Gerekli paketler kontrol ediliyor...
pip install -q -r requirements.txt
echo Panel aciliyor: http://localhost:8501
streamlit run app.py
pause
