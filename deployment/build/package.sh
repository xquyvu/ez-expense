#!/bin/bash

# Universal packaging script for EZ-Expense releases
# Can be used by both GitHub Actions and local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PLATFORM=""
EXECUTABLE_NAME=""
PACKAGE_NAME=""
OUTPUT_DIR="release-package"
DIST_DIR="../../dist"
DEPLOYMENT_DIR=".."

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --executable-name)
            EXECUTABLE_NAME="$2"
            shift 2
            ;;
        --package-name)
            PACKAGE_NAME="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dist-dir)
            DIST_DIR="$2"
            shift 2
            ;;
        --deployment-dir)
            DEPLOYMENT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

# Auto-detect platform if not provided
if [ -z "$PLATFORM" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        PLATFORM="macos"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        PLATFORM="windows"
    else
        PLATFORM="linux"
    fi
fi

# Set defaults based on platform if not provided
if [ -z "$EXECUTABLE_NAME" ]; then
    if [ "$PLATFORM" = "windows" ]; then
        EXECUTABLE_NAME="ez-expense.exe"
    else
        EXECUTABLE_NAME="ez-expense"
    fi
fi

if [ -z "$PACKAGE_NAME" ]; then
    PACKAGE_NAME="ez-expense-$PLATFORM"
fi

echo -e "${BLUE}📦 Creating $PLATFORM release package...${NC}"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Platform-specific packaging
if [ "$PLATFORM" = "macos" ]; then
    # Executable
    cp "$DIST_DIR/$EXECUTABLE_NAME" "$OUTPUT_DIR/"
    echo -e "${GREEN}✅ Included command-line executable${NC}"

    # Copy macOS app bundle
    cp -r "$DIST_DIR/EZ-Expense.app" "$OUTPUT_DIR/"
    echo -e "${GREEN}✅ Included macOS app bundle${NC}"

    # Copy run script
    cp "$DEPLOYMENT_DIR/run/run-ez-expense.sh" "$OUTPUT_DIR/"
    chmod +x "$OUTPUT_DIR/run-ez-expense.sh"
    echo -e "${GREEN}✅ Included run script${NC}"

elif [ "$PLATFORM" = "windows" ]; then
    # Executable
    cp "$DIST_DIR/$EXECUTABLE_NAME" "$OUTPUT_DIR/"
    echo -e "${GREEN}✅ Included Windows executable${NC}"

    # Copy Windows launcher
    cp "$DEPLOYMENT_DIR/run/run-ez-expense.bat" "$OUTPUT_DIR/"
    echo -e "${GREEN}✅ Included Windows run script${NC}"

else
    # Linux
    # Executable
    cp "$DIST_DIR/$EXECUTABLE_NAME" "$OUTPUT_DIR/"
    chmod +x "$OUTPUT_DIR/$EXECUTABLE_NAME"
    echo -e "${GREEN}✅ Included Linux executable${NC}"
fi

# Copy common files for all platforms
cp "$DEPLOYMENT_DIR/USER_GUIDE.md" "$OUTPUT_DIR/"
echo -e "${GREEN}✅ Included user guide${NC}"

# Copy environment template
ENV_TEMPLATE_PATH="$DEPLOYMENT_DIR/../.env.template"
cp "$ENV_TEMPLATE_PATH" "$OUTPUT_DIR/"
echo -e "${GREEN}✅ Included .env template${NC}"

echo -e "${GREEN}📦 Release package created successfully in $OUTPUT_DIR/${NC}"