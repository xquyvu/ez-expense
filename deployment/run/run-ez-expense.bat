@echo off
echo 🚀 Starting EZ-Expense...
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ⚠️  No .env file found!
    echo.
    echo Please copy .env.template to .env and fill in your API keys.
    echo See USER_GUIDE.md for detailed instructions.
    echo.
    pause
    exit /b 1
)

echo ✅ Starting EZ-Expense...
echo 💡 The app will open your browser at http://localhost:5001
echo ⚠️  Keep this window open while using the app!
echo.

ez-expense.exe
pause