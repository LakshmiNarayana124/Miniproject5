@echo off
title IntelliWatch — Startup
cd /d "%~dp0"

echo [1/4] Installing Python dependencies...
python -m pip install -r Backend\requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed. Make sure Python is in your PATH.
    pause & exit /b 1
)

echo [2/4] Checking secret key...
IF "%INTELLIWATCH_SECRET_KEY%"=="" (
    echo     Secret key not set - generating a temporary key for this session.
    FOR /F "tokens=*" %%i IN ('python -c "import secrets; print(secrets.token_hex(32))"') DO (
        SET INTELLIWATCH_SECRET_KEY=%%i
    )
)
echo     Secret key: OK

echo [3/4] Starting FastAPI backend on http://localhost:8000 ...
start "IntelliWatch Backend" cmd /k "cd /d %~dp0Backend && python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000"

echo [4/4] Starting React frontend on http://localhost:5173 ...
start "IntelliWatch Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo  IntelliWatch is starting up.
echo  Backend :  http://localhost:8000
echo  Frontend:  http://localhost:5173
echo  API docs:  http://localhost:8000/docs
echo.
echo  Press any key to exit this launcher (servers keep running in their own windows).
pause
