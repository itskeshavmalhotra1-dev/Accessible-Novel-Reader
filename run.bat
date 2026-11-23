@echo off
setlocal
cd /d "%~dp0"

:: 1. Try launching with pythonw (Zero terminal / pure GUI)
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0main.py"
    exit /b 0
)

:: 2. Try launching with python
where python >nul 2>&1
if %errorlevel% equ 0 (
    start "" python "%~dp0main.py"
    exit /b 0
)

:: 3. Check default user Python install path
if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "%~dp0main.py"
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%~dp0main.py"
    exit /b 0
)

echo [ERROR] Python was not found in your system PATH.
echo Please verify that Python 3 is installed.
pause
exit /b 1
