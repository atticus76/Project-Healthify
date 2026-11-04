@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "CODE_DIR=%ROOT_DIR%code"
set "VENV_DIR=%ROOT_DIR%\.venv"
set "FRONTEND_DIR=%CODE_DIR%\frontend"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo ERROR: The root .venv was not found.
    echo Create it from the repository root with:
    echo   py -3.12 -m venv .venv
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo ERROR: The virtual environment Python executable was not found.
    pause
    exit /b 1
)

if not exist "%CODE_DIR%\requirements.txt" (
    echo ERROR: The code requirements.txt was not found.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Could not activate the virtual environment.
    pause
    exit /b 1
)

"%PYTHON%" -m pip install --disable-pip-version-check -r "%CODE_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

:run
echo.
echo Starting Healthify...
cd /d "%FRONTEND_DIR%"
"%PYTHON%" -m reflex run

echo.
echo Reflex has stopped.
choice /C RT /N /M "Press R to restart or T to terminate: "
if errorlevel 2 goto terminate
if errorlevel 1 goto run

:terminate
echo Healthify terminated.
