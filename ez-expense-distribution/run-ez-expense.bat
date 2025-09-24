@echo off
echo 🚀 Starting EZ-Expense...
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ⚠️  No .env file found!
    echo.
    echo EZ-Expense needs API keys to work properly.
    echo Please copy .env.template to .env and fill in your API keys.
    echo See USER_GUIDE.md for detailed instructions.
    echo.
    pause
    exit /b 1
)

echo ✅ Starting EZ-Expense...
echo 💡 The app will open your browser automatically at http://localhost:3000
echo ⚠️  Keep this command window open while using the app!
echo.
echo Press Ctrl+C to stop the application.
echo.

REM Run the executable
ez-expense.exe
pause
