#!/bin/bash
# EZ-Expense App Launcher
# This script opens Terminal and runs the EZ-Expense console application

# Get the directory where this script is located (inside the .app bundle)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to the console executable
EZ_EXPENSE_EXEC="$SCRIPT_DIR/ez-expense"

# Check if the executable exists
if [ ! -f "$EZ_EXPENSE_EXEC" ]; then
    osascript -e 'display dialog "EZ-Expense executable not found!" with title "Error" buttons {"OK"} default button "OK"'
    exit 1
fi

# Open Terminal and run the EZ-Expense application
osascript << EOF
tell application "Terminal"
    activate
    set newWindow to do script "cd '$SCRIPT_DIR' && ./ez-expense"
    set custom title of newWindow to "EZ-Expense"
end tell
EOF