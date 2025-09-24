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
    "package")
        echo "📦 Creating distribution package..."
        cd deployment && ./package.sh
        ;;
    "distribute")
        echo "🏭 Building and creating distribution package..."
        echo "Step 1/2: Building executable..."
        cd deployment && ./build.sh
        echo "Step 2/2: Creating distribution package..."
        ./package.sh
        ;;
    "run")
        echo "🚀 Running EZ-Expense..."
        cd deployment && ./run-ez-expense.sh
        ;;
    *)
        echo "EZ-Expense Deployment Helper"
        echo ""
        echo "Usage: $0 {build|test|package|distribute|run}"
        echo ""
        echo "Commands:"
        echo "  build      - Build the standalone executable"
        echo "  test       - Test the executable"
        echo "  package    - Create distribution package"
        echo "  distribute - Build executable and create distribution package"
        echo "  run        - Run the application"
        echo ""
        echo "All deployment files are in the deployment/ folder"
        exit 1
        ;;
esac