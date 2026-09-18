@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem Python'u once PATH'te, sonra bilinen Anaconda/Miniconda klasorlerinde arar.
set "PY="
for %%K in (python.exe) do if not defined PY if not "%%~$PATH:K"=="" set "PY=%%~$PATH:K"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\anaconda3\python.exe" set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Continuum\anaconda3\python.exe" set "PY=%LOCALAPPDATA%\Continuum\anaconda3\python.exe"
if not defined PY if exist "C:\ProgramData\anaconda3\python.exe" set "PY=C:\ProgramData\anaconda3\python.exe"
if not defined PY if exist "C:\Anaconda3\python.exe" set "PY=C:\Anaconda3\python.exe"

if not defined PY (
  echo Python bulunamadi.
  echo Anaconda Prompt'u acip su iki komutu calistirin:
  echo    cd /d "%~dp0"
  echo    python -m pip install -r requirements.txt ^&^& python -m streamlit run app.py
  pause
  exit /b 1
)

echo Python: %PY%
echo Gerekli paketler kontrol ediliyor, ilk acilista birkac dakika surebilir...
"%PY%" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Paket kurulumu basarisiz oldu. Internet baglantisini kontrol edin.
  pause
  exit /b 1
)
echo Panel aciliyor: http://localhost:8501
echo Bu pencereyi kapatirsaniz panel de kapanir.
"%PY%" -m streamlit run app.py
pause
