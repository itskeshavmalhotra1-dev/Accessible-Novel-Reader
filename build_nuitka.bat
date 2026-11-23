@echo off
setlocal
cd /d "%~dp0"
echo ========================================================
echo Compiling Accessible Novel Reader with Nuitka
echo ========================================================
python scripts\build_nuitka.py
if errorlevel 1 (
    echo.
    echo [ERROR] Compilation failed.
    pause
    exit /b %errorlevel%
)
echo.
echo [SUCCESS] Compilation and packaging finished.
pause
