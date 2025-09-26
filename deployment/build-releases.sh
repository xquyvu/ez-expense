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

# Detect what was built
HAS_MACOS_APP=false
HAS_WINDOWS_EXE=false

if [ -d "../dist/EZ-Expense.app" ]; then
    HAS_MACOS_APP=true
    echo -e "${GREEN}✅ Found macOS app bundle${NC}"
fi

if [ -f "../dist/ez-expense.exe" ] || [ -f "../dist/ez-expense" ]; then
    HAS_WINDOWS_EXE=true
    echo -e "${GREEN}✅ Found Windows/Linux executable${NC}"
fi

# Create macOS release only if we have the app bundle
if [ "$HAS_MACOS_APP" = true ]; then
    echo -e "${BLUE}📱 Creating macOS release package...${NC}"
    MACOS_DIR="../releases/ez-expense-macos"
    mkdir -p "$MACOS_DIR"

    # Copy macOS app bundle
    cp -r ../dist/EZ-Expense.app "$MACOS_DIR/"
    cp USER_GUIDE.md "$MACOS_DIR/"
else
    echo -e "${YELLOW}⚠️ Skipping macOS release - no app bundle found${NC}"
fi

# Copy .env template from root
if [ -f "../.env.template" ]; then
    if [ "$HAS_MACOS_APP" = true ]; then
        cp "../.env.template" "$MACOS_DIR/"
    fi
else
    echo "⚠️ Warning: .env.template not found in root directory"
fi

# Create macOS README only if we have the app
if [ "$HAS_MACOS_APP" = true ]; then
    cat > "$MACOS_DIR/README.txt" << 'EOF'
EZ-Expense for macOS
===================

QUICK START:
1. Rename the `.env.template` file to `.env`
2. Edit .env with your API keys (see USER_GUIDE.md)
3. Double-click EZ-Expense.app

SYSTEM REQUIREMENTS:
- macOS 10.15 or later
- 4GB RAM available
- 500MB free disk space
- Internet connection (for AI services)

GETTING HELP:
See USER_GUIDE.md for detailed instructions and troubleshooting.

The app will open your browser automatically at http://localhost:3000
EOF
fi

# Create Windows release if we have executable
if [ "$HAS_WINDOWS_EXE" = true ]; then
    echo -e "${BLUE}💻 Creating Windows release package...${NC}"
    WINDOWS_DIR="../releases/ez-expense-windows"
    mkdir -p "$WINDOWS_DIR"

    # Copy executable - handle both .exe and non-.exe names
    if [ -f "../dist/ez-expense.exe" ]; then
        cp "../dist/ez-expense.exe" "$WINDOWS_DIR/"
    elif [ -f "../dist/ez-expense" ]; then
        cp "../dist/ez-expense" "$WINDOWS_DIR/ez-expense.exe"
    fi

    cp USER_GUIDE.md "$WINDOWS_DIR/"

    # Copy .env template from root
    if [ -f "../.env.template" ]; then
        cp "../.env.template" "$WINDOWS_DIR/"
    fi
else
    echo -e "${YELLOW}⚠️ Skipping Windows release - no executable found${NC}"
fi

# Create Windows launcher and README only if we have the executable
if [ "$HAS_WINDOWS_EXE" = true ]; then
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
- Internet connection (for AI services)

GETTING HELP:
See USER_GUIDE.md for detailed instructions and troubleshooting.

The app will open your browser automatically at http://localhost:3000
Keep the command window open while using the app!
EOF
fi

# Create ZIP files for releases
echo -e "${BLUE}📦 Creating release archives...${NC}"
cd ../releases

# Check if zip command is available
if ! command -v zip &> /dev/null; then
    echo -e "${RED}❌ zip command not found. Please install zip utility.${NC}"
    echo "zip is required to create release archives."
    exit 1
fi

# Create macOS archive if we have it
if [ "$HAS_MACOS_APP" = true ]; then
    zip -r "ez-expense-macos.zip" "ez-expense-macos/"
    echo -e "${GREEN}✅ Created: ez-expense-macos.zip${NC}"
fi

# Create Windows archive if we have it
if [ "$HAS_WINDOWS_EXE" = true ]; then
    zip -r "ez-expense-windows.zip" "ez-expense-windows/"
    echo -e "${GREEN}✅ Created: ez-expense-windows.zip${NC}"
fi

# Show results
echo ""
echo -e "${GREEN}🎉 GitHub releases ready!${NC}"
echo ""

if [ -f "ez-expense-macos.zip" ] || [ -f "ez-expense-windows.zip" ]; then
    echo -e "${BLUE}📁 Release files:${NC}"
    ls -la *.zip 2>/dev/null || true
    echo ""
    echo -e "${BLUE}📊 File sizes:${NC}"
    du -sh *.zip 2>/dev/null || true
    echo ""
    echo -e "${YELLOW}📋 Next steps:${NC}"
    echo "1. Go to https://github.com/xquyvu/ez-expense/releases"
    echo "2. Click 'Create a new release'"
    echo "3. Upload the archive file(s):"
    if [ -f "ez-expense-macos.zip" ]; then
        echo "   • ez-expense-macos.zip"
    fi
    if [ -f "ez-expense-windows.zip" ]; then
        echo "   • ez-expense-windows.zip"
    fi
    echo "4. Add release notes and publish"
else
    echo -e "${RED}❌ No release packages were created${NC}"
    echo "Make sure you have built executables in ../dist/"
fi