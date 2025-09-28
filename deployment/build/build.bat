@echo off
REM Build script for ez-expense executable on Windows
REM This script builds a standalone executable using PyInstaller

echo 🚀 Building EZ-Expense standalone executable...

REM Check if we're in the right directory
if not exist "..\..\main.py" (
    echo ❌ Error: ..\..\main.py not found. Please run this script from the deployment\build folder.
    pause
    exit /b 1
)

REM Check if uv is available, otherwise use pip
where uv >nul 2>nul
if %errorlevel% equ 0 (
    echo ✅ Using uv for package management...
    set PYTHON_CMD=uv run
    cd ..\..
    uv sync --group build
    cd deployment\build
) else (
    echo ⚠️  uv not found, using pip...
    set PYTHON_CMD=python
    pip install pyinstaller
)

echo 📦 Installing Playwright browsers...
if "%PYTHON_CMD%"=="uv run" (
    cd ..\..
    uv run playwright install chromium --with-deps
    cd deployment\build
) else (
    python -m playwright install chromium --with-deps
)

echo 🧹 Cleaning previous build artifacts...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo 🔨 Building executable with PyInstaller...
if "%PYTHON_CMD%"=="uv run" (
    cd ..\..
    uv run pyinstaller deployment\ez-expense.spec --clean --noconfirm
    cd deployment\build
) else (
    cd ..\..
    python -m PyInstaller deployment\ez-expense.spec --clean --noconfirm
    cd deployment\build
)

echo ✅ Build completed!
echo.
echo 📁 Output location: ..\..\dist\ez-expense.exe
echo.
echo 💡 To test the executable:
echo    ..\..\dist\ez-expense.exe
echo.
echo 🎉 Your EZ-Expense standalone executable is ready!
echo 📝 Next steps:
echo    1. Test the executable thoroughly
echo    2. Create a simple user guide
echo    3. Consider code signing
echo    4. Distribute to your users
pause