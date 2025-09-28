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
    if [ -f "../run/run-ez-expense.sh" ]; then
        cp ../run/run-ez-expense.sh "$RELEASE_DIR/"
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
cp ../USER_GUIDE.md "$RELEASE_DIR/"
echo -e "${GREEN}✅ Included user guide${NC}"

# Copy .env.template if it exists
if [ -f "../.env.template" ]; then
    cp ../.env.template "$RELEASE_DIR/"
    echo -e "${GREEN}✅ Included .env.template${NC}"
else
    echo -e "${YELLOW}⚠️ .env.template not found${NC}"
fi

# Copy README template
echo -e "${BLUE}📝 Copying README template...${NC}"
cp ../readme-templates/README.txt "$RELEASE_DIR/"

# Create Windows launcher script if on Windows
if [ "$PLATFORM" = "windows" ]; then
    if [ -f "../run/run-ez-expense.bat" ]; then
        cp ../run/run-ez-expense.bat "$RELEASE_DIR/"
        echo -e "${GREEN}✅ Included Windows run script${NC}"
    fi
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
    echo "   Contents: $(unzip -l "$PACKAGE_NAME.zip" | grep -c '.*')"
else
    echo -e "${RED}❌ Error: Release directory $PACKAGE_NAME not found${NC}"
    exit 1
fi

cd ..

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