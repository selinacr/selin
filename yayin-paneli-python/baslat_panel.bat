@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Yerel servisi baslatir ve paneli varsayilan tarayicida acar.
rem Anaconda/Miniconda aranir; Microsoft Store kisayolu gercek Python olmadigi icin atlanir.
set "PY="
for %%D in (
  "%USERPROFILE%\anaconda3"
  "%USERPROFILE%\miniconda3"
  "%LOCALAPPDATA%\anaconda3"
  "%LOCALAPPDATA%\miniconda3"
  "C:\ProgramData\anaconda3"
  "C:\Anaconda3"
) do if not defined PY if exist "%%~D\python.exe" set "PY=%%~D\python.exe"

if not defined PY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PY=%CONDA_PREFIX%\python.exe"

if not defined PY (
  for %%K in (python.exe) do if not defined PY if not "%%~$PATH:K"=="" (
    echo %%~$PATH:K | find /i "WindowsApps" >nul || set "PY=%%~$PATH:K"
  )
)

if not defined PY (
  echo Python bulunamadi. Anaconda Prompt uzerinden su komutu calistirin:
  echo     python -m yayin_paneli.servis
  pause
  exit /b 1
)

echo Gerekli paketler denetleniyor...
"%PY%" -m pip install -q -r requirements.txt

start "" http://127.0.0.1:8787/
"%PY%" -m yayin_paneli.servis
pause
