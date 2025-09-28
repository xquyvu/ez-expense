#!/bin/bash

# EZ-Expense Launcher Script
# This script provides a user-friendly way to run EZ-Expense

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting EZ-Expense...${NC}"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found!${NC}"
    echo ""
    echo "Please create a .env file following the .env.template file for this to work properly"
    echo ""
    echo -e "${YELLOW}Would you like to continue anyway? (y/N)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Please set up your .env file and try again."
        exit 1
    fi
fi

# Check if executable exists
if [ ! -f "../dist/ez-expense" ]; then
    echo -e "${RED}❌ Executable not found!${NC}"
    echo "Please run ./build/build.sh first to create the executable."
    exit 1
fi

echo -e "${GREEN}✅ Starting EZ-Expense...${NC}"
echo -e "${BLUE}💡 The app will open your browser automatically at http://localhost:5001${NC}"
echo -e "${YELLOW}⚠️  Keep this terminal window open while using the app!${NC}"
echo ""
echo "Press Ctrl+C to stop the application."
echo ""

# Run the executable
../dist/ez-expense