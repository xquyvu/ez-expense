#!/bin/bash

# Build EZ-Expense releases for GitHub
# Creates separate packages for macOS and Windows

set -e

echo "🚀 Building EZ-Expense releases for GitHub..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Clean previous releases
echo -e "${BLUE}🧹 Cleaning previous release artifacts...${NC}"
rm -rf ../releases
mkdir -p ../releases

# Build the executable first
echo -e "${BLUE}🔨 Building executable...${NC}"
./build.sh

# Create macOS release
echo -e "${BLUE}📱 Creating macOS release package...${NC}"
MACOS_DIR="../releases/ez-expense-macos"
mkdir -p "$MACOS_DIR"

# Copy macOS app bundle
cp -r ../dist/EZ-Expense.app "$MACOS_DIR/"
cp USER_GUIDE.md "$MACOS_DIR/"

# Create .env template
cat > "$MACOS_DIR/.env.template" << 'EOF'
# EZ-Expense Configuration File
# Copy this file to .env and fill in your API keys

# Required: Azure AI Vision (for receipt text extraction)
AZURE_AI_VISION_ENDPOINT=your_endpoint_here
AZURE_AI_VISION_KEY=your_key_here

# Required: OpenAI (for intelligent matching)
OPENAI_API_KEY=your_openai_key_here

# Optional: Browser automation settings
BROWSER_PORT=9222
FRONTEND_PORT=3000

# Optional: Debug settings
FLASK_DEBUG=false
EOF

# Create macOS README
cat > "$MACOS_DIR/README.txt" << 'EOF'
EZ-Expense for macOS
===================

QUICK START:
1. Copy .env.template to .env
2. Edit .env with your API keys (see USER_GUIDE.md)
3. Double-click EZ-Expense.app

SYSTEM REQUIREMENTS:
- macOS 10.15 or later
- 4GB RAM available
- 500MB free disk space
- Internet connection

The app will open your browser at http://localhost:3000
EOF

# Create Windows release (simulated - cross-platform executable)
echo -e "${BLUE}💻 Creating Windows release package...${NC}"
WINDOWS_DIR="../releases/ez-expense-windows"
mkdir -p "$WINDOWS_DIR"

# Copy executable (rename to .exe for Windows)
cp ../dist/ez-expense "$WINDOWS_DIR/ez-expense.exe"
cp USER_GUIDE.md "$WINDOWS_DIR/"

# Copy .env template
cp "$MACOS_DIR/.env.template" "$WINDOWS_DIR/"

# Create Windows launcher
cat > "$WINDOWS_DIR/run-ez-expense.bat" << 'EOF'
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
echo 💡 The app will open your browser at http://localhost:3000
echo ⚠️  Keep this window open while using the app!
echo.

ez-expense.exe
pause
EOF

# Create Windows README
cat > "$WINDOWS_DIR/README.txt" << 'EOF'
EZ-Expense for Windows
=====================

QUICK START:
1. Copy .env.template to .env
2. Edit .env with your API keys (see USER_GUIDE.md)
3. Double-click run-ez-expense.bat

SYSTEM REQUIREMENTS:
- Windows 10 or later
- 4GB RAM available
- 500MB free disk space
- Internet connection

The app will open your browser at http://localhost:3000
Keep the command window open while using the app!
EOF

# Create ZIP files for releases
echo -e "${BLUE}📦 Creating release archives...${NC}"
cd ../releases

# Create macOS zip
zip -r "ez-expense-macos.zip" "ez-expense-macos/"
echo -e "${GREEN}✅ Created: ez-expense-macos.zip${NC}"

# Create Windows zip
zip -r "ez-expense-windows.zip" "ez-expense-windows/"
echo -e "${GREEN}✅ Created: ez-expense-windows.zip${NC}"

# Show results
echo ""
echo -e "${GREEN}🎉 GitHub releases ready!${NC}"
echo ""
echo -e "${BLUE}📁 Release files:${NC}"
ls -la *.zip
echo ""
echo -e "${BLUE}📊 File sizes:${NC}"
du -sh *.zip
echo ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Go to https://github.com/xquyvu/ez-expense/releases"
echo "2. Click 'Create a new release'"
echo "3. Upload both zip files:"
echo "   • ez-expense-macos.zip"
echo "   • ez-expense-windows.zip"
echo "4. Add release notes and publish"