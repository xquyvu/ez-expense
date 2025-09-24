#!/bin/bash

# Build script for ez-expense executable
# This script builds a standalone executable using PyInstaller

set -e  # Exit on any error

echo "🚀 Building EZ-Expense standalone executable..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "../main.py" ]; then
    echo -e "${RED}❌ Error: ../main.py not found. Please run this script from the deployment/ folder.${NC}"
    exit 1
fi

# Check if virtual environment is activated or if we should use uv
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  No virtual environment detected. Using uv to run commands...${NC}"
    PYTHON_CMD="uv run"
else
    echo -e "${GREEN}✅ Virtual environment detected: $VIRTUAL_ENV${NC}"
    PYTHON_CMD="python"
fi

echo -e "${BLUE}📦 Installing/updating build dependencies...${NC}"
if [ "$PYTHON_CMD" = "uv run" ]; then
    cd ..
    uv sync --group build
    cd deployment
else
    pip install pyinstaller
fi

echo -e "${BLUE}🔧 Installing Playwright browsers (required for the app)...${NC}"
if [ "$PYTHON_CMD" = "uv run" ]; then
    cd ..
    uv run playwright install chromium --with-deps
    cd deployment
else
    playwright install chromium --with-deps
fi

echo -e "${BLUE}🧹 Cleaning previous build artifacts...${NC}"
rm -rf build/ dist/ *.spec.backup

echo -e "${BLUE}🔨 Building executable with PyInstaller...${NC}"
if [ "$PYTHON_CMD" = "uv run" ]; then
    cd ..
    uv run pyinstaller deployment/ez-expense.spec --clean --noconfirm
    cd deployment
else
    cd ..
    pyinstaller deployment/ez-expense.spec --clean --noconfirm
    cd deployment
fi

echo -e "${GREEN}✅ Build completed!${NC}"
echo ""
echo -e "${BLUE}📁 Output location:${NC}"
if [ "$(uname)" == "Darwin" ]; then
    echo "   • macOS App Bundle: ../dist/EZ-Expense.app"
    echo "   • Executable: ../dist/ez-expense"
    echo ""
    echo -e "${YELLOW}💡 To test the app bundle:${NC}"
    echo "   open ../dist/EZ-Expense.app"
else
    echo "   • Executable: ../dist/ez-expense"
fi

echo ""
echo -e "${YELLOW}💡 To test the executable:${NC}"
echo "   ../dist/ez-expense"

echo ""
echo -e "${BLUE}📊 File sizes:${NC}"
if command -v du &> /dev/null; then
    if [ "$(uname)" == "Darwin" ]; then
        echo "   App Bundle: $(du -sh ../dist/EZ-Expense.app | cut -f1)"
    fi
    echo "   Executable: $(du -sh ../dist/ez-expense | cut -f1)"
fi

echo ""
echo -e "${GREEN}🎉 Your EZ-Expense standalone executable is ready!${NC}"
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "   1. Test the executable thoroughly"
echo "   2. Create a simple user guide"
echo "   3. Consider code signing (for macOS/Windows)"
echo "   4. Distribute to your users"