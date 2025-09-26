#!/bin/bash

# Enhanced build script with code signing support for macOS
# Based on successful approaches from popular Electron apps

set -e

echo "🚀 Building EZ-Expense with macOS code signing..."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check for macOS
if [ "$(uname)" != "Darwin" ]; then
    echo -e "${RED}❌ Error: This script must be run on macOS for code signing${NC}"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "../main.py" ]; then
    echo -e "${RED}❌ Error: ../main.py not found. Please run this script from the deployment/ folder.${NC}"
    exit 1
fi

# Configuration
APP_NAME="EZ-Expense"
BUNDLE_ID="com.ez-expense.app"
DEVELOPER_ID_APPLICATION="${APPLE_DEVELOPER_ID_APPLICATION:-}"
DEVELOPER_ID_INSTALLER="${APPLE_DEVELOPER_ID_INSTALLER:-}"
TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_ID="${APPLE_ID:-}"
APPLE_PASSWORD="${APPLE_PASSWORD:-}"

# Check for code signing certificate
if [ -z "$DEVELOPER_ID_APPLICATION" ]; then
    echo -e "${YELLOW}⚠️  Warning: APPLE_DEVELOPER_ID_APPLICATION not set${NC}"
    echo -e "${YELLOW}   Code signing will be skipped. App may be blocked by macOS Gatekeeper.${NC}"
    echo -e "${BLUE}   To enable code signing, export these environment variables:${NC}"
    echo "   export APPLE_DEVELOPER_ID_APPLICATION='Developer ID Application: Your Name (TEAMID)'"
    echo "   export APPLE_TEAM_ID='YOUR_TEAM_ID'"
    echo "   export APPLE_ID='your-apple-id@example.com'"
    echo "   export APPLE_PASSWORD='app-specific-password'"
    read -p "Continue without code signing? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Use uv for dependency management
echo -e "${BLUE}📦 Installing/updating build dependencies...${NC}"
cd ..
uv sync --group build
cd deployment

echo -e "${BLUE}🔧 Installing Playwright browsers...${NC}"
cd ..
uv run playwright install chromium --with-deps
cd deployment

echo -e "${BLUE}🧹 Cleaning previous build artifacts...${NC}"
rm -rf build/ dist/ *.spec.backup

echo -e "${BLUE}🔨 Building executable with PyInstaller...${NC}"
cd ..
uv run pyinstaller deployment/ez-expense.spec --clean --noconfirm
cd deployment

# Check if .app bundle was created
if [ ! -d "../dist/${APP_NAME}.app" ]; then
    echo -e "${RED}❌ Error: App bundle not created${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build completed!${NC}"

# Code signing if certificate is available
if [ -n "$DEVELOPER_ID_APPLICATION" ]; then
    echo -e "${BLUE}🔐 Code signing the application...${NC}"

    # Sign all executables and libraries in the app bundle
    find "../dist/${APP_NAME}.app" -type f \( -name "*.dylib" -o -name "*.so" -o -perm +111 \) -exec codesign --sign "$DEVELOPER_ID_APPLICATION" --timestamp --options runtime {} \;

    # Sign the main executable
    codesign --sign "$DEVELOPER_ID_APPLICATION" --timestamp --options runtime "../dist/${APP_NAME}.app/Contents/MacOS/${APP_NAME}"

    # Sign the entire app bundle
    codesign --sign "$DEVELOPER_ID_APPLICATION" --timestamp --options runtime "../dist/${APP_NAME}.app"

    echo -e "${GREEN}✅ Code signing completed${NC}"

    # Verify code signing
    echo -e "${BLUE}🔍 Verifying code signature...${NC}"
    codesign --verify --verbose "../dist/${APP_NAME}.app"

    # Notarization if Apple ID is provided
    if [ -n "$APPLE_ID" ] && [ -n "$APPLE_PASSWORD" ]; then
        echo -e "${BLUE}📋 Creating ZIP for notarization...${NC}"
        cd "../dist"
        zip -r "${APP_NAME}-notarize.zip" "${APP_NAME}.app"

        echo -e "${BLUE}🚀 Submitting for notarization...${NC}"
        xcrun notarytool submit "${APP_NAME}-notarize.zip" \
            --apple-id "$APPLE_ID" \
            --password "$APPLE_PASSWORD" \
            --team-id "$TEAM_ID" \
            --wait

        echo -e "${BLUE}🎯 Stapling notarization ticket...${NC}"
        xcrun stapler staple "${APP_NAME}.app"

        # Clean up
        rm "${APP_NAME}-notarize.zip"

        echo -e "${GREEN}✅ Notarization completed${NC}"
        cd "../deployment"
    else
        echo -e "${YELLOW}⚠️  Notarization skipped (Apple ID/password not provided)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Code signing skipped${NC}"
fi

# Create DMG installer
echo -e "${BLUE}💿 Creating DMG installer...${NC}"
if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "../assets/icon.icns" \
        --window-pos 200 120 \
        --window-size 600 300 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 120 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 120 \
        "../dist/${APP_NAME}.dmg" \
        "../dist/${APP_NAME}.app"

    # Sign the DMG if we have certificates
    if [ -n "$DEVELOPER_ID_APPLICATION" ]; then
        codesign --sign "$DEVELOPER_ID_APPLICATION" --timestamp "../dist/${APP_NAME}.dmg"
        echo -e "${GREEN}✅ DMG signed${NC}"
    fi

    echo -e "${GREEN}✅ DMG created: ../dist/${APP_NAME}.dmg${NC}"
else
    echo -e "${YELLOW}⚠️  create-dmg not found. Install with: brew install create-dmg${NC}"
fi

echo -e "${BLUE}📋 Post-build information:${NC}"
if [ -d "../dist/${APP_NAME}.app" ]; then
    echo "   • macOS App Bundle: ../dist/${APP_NAME}.app"
    echo "   • App Bundle size: $(du -sh "../dist/${APP_NAME}.app" | cut -f1)"
fi

if [ -f "../dist/${APP_NAME}.dmg" ]; then
    echo "   • DMG Installer: ../dist/${APP_NAME}.dmg"
    echo "   • DMG size: $(du -sh "../dist/${APP_NAME}.dmg" | cut -f1)"
fi

echo -e "${GREEN}🎉 Build complete!${NC}"

echo -e "${YELLOW}📝 Next steps:${NC}"
echo "   1. Test the app bundle: open ../dist/${APP_NAME}.app"
echo "   2. Test the DMG installer (if created)"
echo "   3. Distribute via:"
echo "      - Direct download"
echo "      - Homebrew cask"
echo "      - Mac App Store (requires additional setup)"

if [ -z "$DEVELOPER_ID_APPLICATION" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Important: Without code signing, users will see a security warning.${NC}"
    echo "   Users can bypass it by:"
    echo "   1. Right-clicking the app and selecting 'Open'"
    echo "   2. Or running: xattr -cr '/path/to/${APP_NAME}.app'"
fi