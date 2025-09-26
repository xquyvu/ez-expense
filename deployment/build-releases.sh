#!/bin/bash

# Build EZ-Expense releases for GitHub
# Creates separate packages based on current platform

set -e

echo "🚀 Building EZ-Expense release for current platform..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect current platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
    EXECUTABLE_NAME="ez-expense"
    PACKAGE_NAME="ez-expense-macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PLATFORM="windows"
    EXECUTABLE_NAME="ez-expense.exe"
    PACKAGE_NAME="ez-expense-windows"
else
    PLATFORM="linux"
    EXECUTABLE_NAME="ez-expense"
    PACKAGE_NAME="ez-expense-linux"
fi

echo -e "${BLUE}📱 Detected platform: $PLATFORM${NC}"

# Clean previous releases
echo -e "${BLUE}🧹 Cleaning previous release artifacts...${NC}"
rm -rf ../releases
mkdir -p ../releases

# Build the executable first
echo -e "${BLUE}🔨 Building executable...${NC}"
./build.sh

# Create platform-specific release package
echo -e "${BLUE}📦 Creating $PLATFORM release package...${NC}"
RELEASE_DIR="../releases/$PACKAGE_NAME"
mkdir -p "$RELEASE_DIR"

if [ "$PLATFORM" = "macos" ]; then
    # Copy macOS app bundle if it exists
    if [ -d "../dist/EZ-Expense.app" ]; then
        cp -r ../dist/EZ-Expense.app "$RELEASE_DIR/"
        echo -e "${GREEN}✅ Included macOS app bundle${NC}"
    fi

    # Always copy the command-line executable
    if [ -f "../dist/$EXECUTABLE_NAME" ]; then
        cp ../dist/$EXECUTABLE_NAME "$RELEASE_DIR/"
        echo -e "${GREEN}✅ Included command-line executable${NC}"
    fi

    # Copy run script
    if [ -f "run-ez-expense.sh" ]; then
        cp run-ez-expense.sh "$RELEASE_DIR/"
        chmod +x "$RELEASE_DIR/run-ez-expense.sh"
        echo -e "${GREEN}✅ Included run script${NC}"
    fi
else
    # Copy executable for other platforms
    if [ -f "../dist/$EXECUTABLE_NAME" ]; then
        cp ../dist/$EXECUTABLE_NAME "$RELEASE_DIR/"
        chmod +x "$RELEASE_DIR/$EXECUTABLE_NAME"
        echo -e "${GREEN}✅ Included $PLATFORM executable${NC}"
    else
        echo -e "${RED}❌ Error: Expected executable ../dist/$EXECUTABLE_NAME not found${NC}"
        exit 1
    fi
fi

# Copy common files
cp USER_GUIDE.md "$RELEASE_DIR/"
echo -e "${GREEN}✅ Included user guide${NC}"

# Copy .env.template if it exists
if [ -f "../.env.template" ]; then
    cp ../.env.template "$RELEASE_DIR/"
    echo -e "${GREEN}✅ Included .env.template${NC}"
else
    echo -e "${YELLOW}⚠️ .env.template not found${NC}"
fi

# Create platform-specific README
echo -e "${BLUE}📝 Creating platform-specific README...${NC}"
if [ "$PLATFORM" = "macos" ]; then
    cat > "$RELEASE_DIR/README.txt" << 'EOF'
EZ-Expense for macOS
===================

QUICK START:
1. Rename the `.env.template` file to `.env`
2. Edit .env with your API keys (see USER_GUIDE.md)
3. For app bundle: Double-click EZ-Expense.app
   For command line: Run ./ez-expense in Terminal

SYSTEM REQUIREMENTS:
- macOS 10.15 or later (supports both Intel and Apple Silicon)
- 4GB RAM available
- 500MB free disk space
- Internet connection (for AI services)

GETTING HELP:
See USER_GUIDE.md for detailed instructions and troubleshooting.

The app will open your browser automatically at http://localhost:3000
EOF

elif [ "$PLATFORM" = "windows" ]; then
    cat > "$RELEASE_DIR/README.txt" << 'EOF'
EZ-Expense for Windows
=====================

QUICK START:
1. Copy .env.template to .env
2. Edit .env with your API keys (see USER_GUIDE.md)
3. Double-click ez-expense.exe

SYSTEM REQUIREMENTS:
- Windows 10 or later (64-bit)
- 4GB RAM available
- 500MB free disk space
- Internet connection (for AI services)

GETTING HELP:
See USER_GUIDE.md for detailed instructions and troubleshooting.

The app will open your browser automatically at http://localhost:3000
Keep the command window open while using the app!
EOF

    # Create Windows launcher script
    cat > "$RELEASE_DIR/run-ez-expense.bat" << 'EOF'
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

else
    # Linux README
    cat > "$RELEASE_DIR/README.txt" << 'EOF'
EZ-Expense for Linux
===================

QUICK START:
1. Copy .env.template to .env
2. Edit .env with your API keys (see USER_GUIDE.md)
3. Run ./ez-expense in terminal

SYSTEM REQUIREMENTS:
- Linux (64-bit) with glibc 2.17 or later
- 4GB RAM available
- 500MB free disk space
- Internet connection (for AI services)

GETTING HELP:
See USER_GUIDE.md for detailed instructions and troubleshooting.

The app will open your browser automatically at http://localhost:3000
Keep the terminal open while using the app!
EOF
fi
# Create ZIP archive
echo -e "${BLUE}📦 Creating release archive...${NC}"
cd ../releases

# Check if zip command is available
if ! command -v zip &> /dev/null; then
    echo -e "${RED}❌ zip command not found. Please install zip utility.${NC}"
    echo "zip is required to create release archives."
    exit 1
fi

# Create platform-specific archive
if [ -d "$PACKAGE_NAME" ]; then
    cd "$PACKAGE_NAME"
    zip -r "../$PACKAGE_NAME.zip" .
    cd ..
    echo -e "${GREEN}✅ Created $PACKAGE_NAME.zip${NC}"

    # Show file sizes
    echo ""
    echo -e "${BLUE}📊 Release package info:${NC}"
    echo "   Archive: $(du -sh $PACKAGE_NAME.zip | cut -f1)"
    echo "   Contents:"
    unzip -l "$PACKAGE_NAME.zip" | tail -n +4 | head -n -2 | awk '{print "   - " $4}'
else
    echo -e "${RED}❌ Error: Release directory $PACKAGE_NAME not found${NC}"
    exit 1
fi

cd ../deployment

echo ""
echo -e "${GREEN}🎉 Release package created successfully!${NC}"
echo -e "${BLUE}📁 Location: releases/$PACKAGE_NAME.zip${NC}"
echo ""
echo -e "${YELLOW}� Next steps for distribution:${NC}"
echo "   1. Test the release package thoroughly"
echo "   2. Upload to GitHub Releases"
echo "   3. Update release notes with setup instructions"
echo "   4. Consider code signing (for enhanced security)"
echo ""
echo -e "${YELLOW}⚠️  Important reminders:${NC}"
echo "   • Users must create their own .env file"
echo "   • API keys should never be bundled in releases"
echo "   • Test on target platform before distributing"
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