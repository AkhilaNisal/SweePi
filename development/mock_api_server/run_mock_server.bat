@echo off
title SweePi Mock API Server

cd /d "%~dp0"

echo ==========================================
echo Starting SweePi Mock API Server
echo Folder: %cd%
echo ==========================================
echo.

if not exist app\main.py (
    echo ERROR: app\main.py not found.
    echo Make sure this .bat file is in the mock_api_server root folder.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not added to PATH.
    echo Install Python, then try again.
    pause
    exit /b 1
)

echo Checking required Python packages...

python -m pip show fastapi >nul 2>nul
if errorlevel 1 (
    echo Installing fastapi...
    python -m pip install fastapi
)

python -m pip show uvicorn >nul 2>nul
if errorlevel 1 (
    echo Installing uvicorn...
    python -m pip install uvicorn
)

echo.
echo Server starting on:
echo http://localhost:8080
echo.
echo API docs:
echo http://localhost:8080/docs
echo.
echo Test status endpoint:
echo http://localhost:8080/api/robot/status
echo.
echo Press CTRL + C to stop the server.
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

pause
