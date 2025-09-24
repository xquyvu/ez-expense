#!/bin/bash

# Package EZ-Expense for distribution
# This script creates a distributable package with all necessary files

set -e

echo "📦 Creating EZ-Expense distribution package..."

# Create distribution directory in root folder
DIST_DIR="../ez-expense-distribution"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Copy executable and app bundle
echo "📋 Copying executable files..."
cp -r ../dist/ez-expense "$DIST_DIR/"
if [ -d "../dist/EZ-Expense.app" ]; then
    cp -r "../dist/EZ-Expense.app" "$DIST_DIR/"
fi

# Copy assets folder (required by the application)
echo "📁 Copying assets folder..."
cp -r ../assets "$DIST_DIR/"

# Copy launcher script
cp run-ez-expense.sh "$DIST_DIR/"
chmod +x "$DIST_DIR/run-ez-expense.sh"

# Copy user guide
cp USER_GUIDE.md "$DIST_DIR/"

# Create .env template
cat > "$DIST_DIR/.env.template" << 'EOF'
# EZ-Expense Configuration File
# Rename this file as .env and fill in your API keys

# Choose your browser: chrome, edge
BROWSER=edge

# For extraction receipt details with AI (Optional)
# These details can be found in our Azure OpenAI deployment
AZURE_OPENAI_API_KEY=abcdefghi
AZURE_OPENAI_ENDPOINT=https://jklmnopq.openai.azure.com/

# These are reasonable defaults, but you can change them if needed
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
EOF

# Create a simple README for the distribution
cat > "$DIST_DIR/README.txt" << 'EOF'
EZ-Expense Standalone Application
==================================

QUICK START:
1. Copy .env.template to .env
2. Edit .env with your API keys (see USER_GUIDE.md for details)
3. Double-click run-ez-expense.sh (macOS/Linux) or ez-expense.exe (Windows)

WHAT'S INCLUDED:
- ez-expense: The main executable
- EZ-Expense.app: macOS application bundle (macOS only)
- run-ez-expense.sh: Easy launcher script
- USER_GUIDE.md: Complete user guide
- .env.template: Configuration template
- assets/: Required application data files

SYSTEM REQUIREMENTS:
- macOS 10.15+ / Windows 10+ / Linux Ubuntu 18.04+
- 4GB RAM available
- 500MB free disk space
- Internet connection (for AI services)

GETTING HELP:
See USER_GUIDE.md for detailed instructions and troubleshooting.

The app will open your web browser automatically at http://localhost:3000
Keep the terminal/command window open while using the app!
EOF

# Create Windows batch launcher
cat > "$DIST_DIR/run-ez-expense.bat" << 'EOF'
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
EOF

echo "✅ Distribution package created in: $DIST_DIR"
echo ""
echo "📊 Package contents:"
ls -la "$DIST_DIR"
echo ""
echo "📦 Package size:"
du -sh "$DIST_DIR"
echo ""
echo "🎉 Ready for distribution!"
echo ""
echo "💡 To create a zip archive:"
echo "   zip -r ez-expense-$(uname -s)-$(uname -m).zip $DIST_DIR"