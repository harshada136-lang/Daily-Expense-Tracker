@echo off
setlocal
cd /d "%~dp0"
title Daily Expense Tracker - Running

 echo ================================================
 echo       DAILY EXPENSE TRACKER - PYTHON
 echo ================================================
 echo.

set "PYEXE="
where py >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
  echo ERROR: Python 3 was not found.
  echo Install Python 3.10+ from python.org and select Add Python to PATH.
  echo Then restart this file.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PYEXE% -m venv .venv
  if errorlevel 1 goto setup_error
)

 echo Installing/checking packages. First run needs internet...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto setup_error

echo.
echo Starting server. Keep this black window OPEN.
echo Website: http://127.0.0.1:5000
echo Stop server with CTRL+C.
echo.
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py

echo.
echo Server has stopped.
pause
exit /b 0

:setup_error
echo.
echo SETUP ERROR: Python environment or package installation failed.
echo Check Python installation and internet connection, then run run.bat again.
pause
exit /b 1
