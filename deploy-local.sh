#!/bin/bash

# Local deployment script for ez-expense
# Builds, copies .env, removes quarantine, and prepares for click-to-run

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"

# Step 1: Build
echo -e "${BLUE}🔨 Building...${NC}"
bash "$SCRIPT_DIR/deploy.sh" build

# Step 2: Copy .env
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$DIST_DIR/.env"
    echo -e "${GREEN}✅ Copied .env to dist/${NC}"
else
    echo -e "${RED}❌ No .env file found in project root. Please create one first.${NC}"
    exit 1
fi

# Step 3: Remove macOS quarantine
echo -e "${BLUE}🔐 Removing macOS quarantine attributes...${NC}"
xattr -cr "$DIST_DIR/EZ-Expense.app"
xattr -cr "$DIST_DIR/ez-expense"
xattr -cr "$DIST_DIR/EZ-Expense-Launcher" 2>/dev/null || true
echo -e "${GREEN}✅ Quarantine removed${NC}"

# Step 4: Ensure executables are executable
chmod +x "$DIST_DIR/ez-expense"
chmod +x "$DIST_DIR/EZ-Expense-Launcher" 2>/dev/null || true

echo ""
echo -e "${GREEN}🎉 Local deployment ready!${NC}"
echo -e "   Open ${BLUE}dist/${NC} in Finder and double-click ${BLUE}EZ-Expense.app${NC} to run."
echo -e "   Or run: ${BLUE}open $DIST_DIR/EZ-Expense.app${NC}"
