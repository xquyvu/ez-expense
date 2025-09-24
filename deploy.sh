#!/bin/bash

# Convenience script to run deployment commands from the project root

case "$1" in
    "build")
        echo "🔨 Building EZ-Expense executable..."
        cd deployment && ./build.sh
        ;;
    "test")
        echo "🧪 Testing EZ-Expense executable..."
        cd deployment && ./test-executable.sh
        ;;
    "releases")
        echo "🚀 Building GitHub releases..."
        cd deployment && ./build-releases.sh
        ;;
    "run")
        echo "🚀 Running EZ-Expense..."
        cd deployment && ./run-ez-expense.sh
        ;;
    *)
        echo "EZ-Expense Deployment Helper"
        echo ""
        echo "Usage: $0 {build|test|releases|run}"
        echo ""
        echo "Commands:"
        echo "  build      - Build the standalone executable"
        echo "  test       - Test the executable"
        echo "  releases   - Build GitHub release packages (macOS + Windows)"
        echo "  run        - Run the application"
        echo ""
        echo "All deployment files are in the deployment/ folder"
        exit 1
        ;;
esac