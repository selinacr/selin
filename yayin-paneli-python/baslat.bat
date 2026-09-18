@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Once Anaconda/Miniconda kurulumlarina bakilir; Microsoft Store kisayolu
rem (WindowsApps\python.exe) gercek Python olmadigi icin atlanir.
set "PY="
for %%D in (
  "%USERPROFILE%\anaconda3"
  "%USERPROFILE%\miniconda3"
  "%USERPROFILE%\Anaconda"
  "%LOCALAPPDATA%\anaconda3"
  "%LOCALAPPDATA%\miniconda3"
  "%LOCALAPPDATA%\Continuum\anaconda3"
  "C:\ProgramData\anaconda3"
  "C:\ProgramData\Miniconda3"
  "C:\Anaconda3"
  "C:\Miniconda3"
) do if not defined PY if exist "%%~D\python.exe" set "PY=%%~D\python.exe"

if not defined PY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PY=%CONDA_PREFIX%\python.exe"

if not defined PY (
  for %%K in (python.exe) do if not defined PY if not "%%~$PATH:K"=="" (
    echo %%~$PATH:K | find /i "WindowsApps" >nul || set "PY=%%~$PATH:K"
  )
)

if not defined PY (
  echo Python bulunamadi.
  echo.
  echo Baslat menusunden "Anaconda Prompt" acip su iki satiri calistirin:
  echo    cd /d "%~dp0"
  echo    python -m pip install -r requirements.txt ^&^& python -m streamlit run app.py
  echo.
  pause
  exit /b 1
)

echo Python: %PY%
echo Gerekli paketler kontrol ediliyor, ilk acilista birkac dakika surebilir...
"%PY%" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo Paket kurulumu basarisiz oldu. Yukaridaki hata mesajini kontrol edin.
  pause
  exit /b 1
)
echo Panel aciliyor: http://localhost:8501
echo Bu pencereyi kapatirsaniz panel de kapanir.
"%PY%" -m streamlit run app.py
pause
