#!/bin/bash

# Create a Homebrew tap for EZ-Expense
# This allows users to install via: brew install --cask your-tap/ez-expense

set -e

echo "🍺 Creating Homebrew Cask for EZ-Expense..."

# Configuration
GITHUB_USER="xquyvu"
REPO_NAME="ez-expense"
TAP_NAME="homebrew-ez-expense"
VERSION="${1:-1.0.0}"

# Create tap directory structure
mkdir -p "../${TAP_NAME}/Casks"

# Create the cask file
cat > "../${TAP_NAME}/Casks/ez-expense.rb" << EOF
cask "ez-expense" do
  version "$VERSION"

  url "https://github.com/${GITHUB_USER}/${REPO_NAME}/releases/download/v#{version}/ez-expense-macos.zip"
  name "EZ Expense"
  desc "Expense management and receipt processing application"
  homepage "https://github.com/${GITHUB_USER}/${REPO_NAME}"

  livecheck do
    url :url
    strategy :github_latest
  end

  app "EZ-Expense.app"

  # Handle unsigned app
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-cr", "#{appdir}/EZ-Expense.app"],
                   sudo: false
  end

  zap trash: [
    "~/Library/Application Support/EZ-Expense",
    "~/Library/Preferences/com.ez-expense.app.plist",
    "~/Library/Caches/com.ez-expense.app",
    "~/Library/Logs/EZ-Expense",
  ]
end
EOF

echo "✅ Homebrew cask created at ../${TAP_NAME}/Casks/ez-expense.rb"

# Create tap README
cat > "../${TAP_NAME}/README.md" << EOF
# EZ-Expense Homebrew Tap

This tap provides easy installation of EZ-Expense via Homebrew.

## Installation

\`\`\`bash
# Add the tap
brew tap ${GITHUB_USER}/ez-expense

# Install the app
brew install --cask ez-expense
\`\`\`

## About

EZ-Expense is an expense management and receipt processing application.

- **Repository**: https://github.com/${GITHUB_USER}/${REPO_NAME}
- **Issues**: https://github.com/${GITHUB_USER}/${REPO_NAME}/issues

## Note on Security

This app is not code signed. The cask automatically removes the quarantine attribute
to prevent macOS security warnings.
EOF

echo "✅ Tap README created"
echo ""
echo "🚀 Next steps:"
echo "1. Create a new repository: ${GITHUB_USER}/${TAP_NAME}"
echo "2. Push the tap contents to that repository"
echo "3. Users can install with: brew tap ${GITHUB_USER}/ez-expense && brew install --cask ez-expense"