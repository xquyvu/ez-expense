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
    echo "EZ-Expense needs API keys to work properly."
    echo "Please create a .env file with the following content:"
    echo ""
    echo -e "${GREEN}# Required: Azure AI Vision (for receipt text extraction)"
    echo "AZURE_AI_VISION_ENDPOINT=your_endpoint_here"
    echo "AZURE_AI_VISION_KEY=your_key_here"
    echo ""
    echo "# Required: OpenAI (for intelligent matching)"
    echo "OPENAI_API_KEY=your_openai_key_here"
    echo ""
    echo "# Optional: Browser automation settings"
    echo "BROWSER_PORT=9222"
    echo "FRONTEND_PORT=3000${NC}"
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
    echo "Please run ./build.sh first to create the executable."
    exit 1
fi

echo -e "${GREEN}✅ Starting EZ-Expense...${NC}"
echo -e "${BLUE}💡 The app will open your browser automatically at http://localhost:3000${NC}"
echo -e "${YELLOW}⚠️  Keep this terminal window open while using the app!${NC}"
echo ""
echo "Press Ctrl+C to stop the application."
echo ""

# Run the executable
../dist/ez-expense