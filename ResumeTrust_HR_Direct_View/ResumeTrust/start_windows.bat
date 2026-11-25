@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo       ResumeTrust - Windows Launcher
echo ==========================================
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% --version
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 goto failed
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r requirements.txt
if errorlevel 1 goto failed
if not exist "resumetrust.db" (
  echo Creating demo database for first run...
  python seed.py
  if errorlevel 1 goto failed
) else (
  echo Existing database found - preserving existing users and data.
  python -c "from database import init_db; init_db()"
  if errorlevel 1 goto failed
)
set PORT=8081
 echo Starting ResumeTrust at http://localhost:8081
python app.py
pause
exit /b 0
:failed
echo.
echo Startup failed. Read the error above and share it for troubleshooting.
pause
exit /b 1
