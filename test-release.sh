#!/bin/bash

# Test release package locally
# Creates full release structure with .env for testing

set -e

echo "🚀 Building test release package..."

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
    PACKAGE_NAME="ez-expense-macos-test"
    IS_MACOS=true
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PLATFORM="windows"
    EXECUTABLE_NAME="ez-expense.exe"
    PACKAGE_NAME="ez-expense-windows-test"
    IS_MACOS=false
else
    PLATFORM="linux"
    EXECUTABLE_NAME="ez-expense"
    PACKAGE_NAME="ez-expense-linux-test"
    IS_MACOS=false
fi

echo -e "${BLUE}📱 Detected platform: $PLATFORM${NC}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RELEASE_DIR="$SCRIPT_DIR/releases/$PACKAGE_NAME"

# Clean previous test release
echo -e "${BLUE}🧹 Cleaning previous test release...${NC}"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Build the executable
echo -e "${BLUE}🔨 Building executable...${NC}"
cd "$SCRIPT_DIR/deployment/build"
bash build.sh
cd "$SCRIPT_DIR"

# Package the release
echo -e "${BLUE}📦 Creating release package...${NC}"
cd "$SCRIPT_DIR/deployment/build"
bash package.sh \
    --platform "$PLATFORM" \
    --executable-name "$EXECUTABLE_NAME" \
    --package-name "$PACKAGE_NAME" \
    --output-dir "$RELEASE_DIR" \
    --dist-dir "$SCRIPT_DIR/dist" \
    --deployment-dir "$SCRIPT_DIR/deployment"
cd "$SCRIPT_DIR"

# Copy .env for testing
echo -e "${BLUE}📋 Copying .env for testing...${NC}"
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$RELEASE_DIR/.env"
    echo -e "${GREEN}✅ Copied .env${NC}"
else
    echo -e "${RED}❌ No .env file found. Please create one first.${NC}"
    exit 1
fi

# Remove macOS quarantine
echo -e "${BLUE}🔐 Removing macOS quarantine attributes...${NC}"
xattr -cr "$RELEASE_DIR"
echo -e "${GREEN}✅ Quarantine removed${NC}"

# Create ZIP to simulate user download
echo -e "${BLUE}📦 Creating ZIP archive...${NC}"
cd "$RELEASE_DIR"
zip -r "../$PACKAGE_NAME.zip" . > /dev/null
cd "$SCRIPT_DIR"
echo -e "${GREEN}✅ Created ZIP${NC}"

# Extract ZIP to simulate user experience
echo -e "${BLUE}📂 Extracting ZIP to test location...${NC}"
TEST_EXTRACT_DIR="$SCRIPT_DIR/releases/extracted-test"
rm -rf "$TEST_EXTRACT_DIR"
mkdir -p "$TEST_EXTRACT_DIR"
unzip -q "$SCRIPT_DIR/releases/$PACKAGE_NAME.zip" -d "$TEST_EXTRACT_DIR"
echo -e "${GREEN}✅ Extracted${NC}"

# Copy .env to extracted package
echo -e "${BLUE}📋 Copying .env to extracted package...${NC}"
cp "$SCRIPT_DIR/.env" "$TEST_EXTRACT_DIR/.env"
echo -e "${GREEN}✅ Copied .env${NC}"

# Remove macOS quarantine from extracted package (macOS only)
if [ "$IS_MACOS" = true ]; then
    echo -e "${BLUE}🔐 Removing macOS quarantine attributes...${NC}"
    xattr -cr "$TEST_EXTRACT_DIR"
    echo -e "${GREEN}✅ Quarantine removed${NC}"
fi

# Ensure executables are executable
chmod +x "$TEST_EXTRACT_DIR/$EXECUTABLE_NAME"
chmod +x "$TEST_EXTRACT_DIR/run-ez-expense.sh" 2>/dev/null || true
if [ -d "$TEST_EXTRACT_DIR/EZ-Expense.app" ]; then
    chmod +x "$TEST_EXTRACT_DIR/EZ-Expense.app/Contents/MacOS/"* 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}🎉 Test release ready to run!${NC}"
echo -e "${BLUE}📁 Extracted to: releases/extracted-test/${NC}"
echo ""
echo -e "${YELLOW}🚀 Click to test:${NC}"
echo "   open $TEST_EXTRACT_DIR/EZ-Expense.app"
echo ""
echo -e "${BLUE}📦 Files created:${NC}"
echo "   • releases/$PACKAGE_NAME.zip (release archive)"
echo "   • releases/$PACKAGE_NAME/ (build artifacts)"
echo "   • releases/extracted-test/ (ready to test)"
echo ""
echo -e "${YELLOW}⚠️  Remember: .env is included for testing only${NC}"
echo "   Remove it before creating actual releases!"
