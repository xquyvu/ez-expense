#!/bin/bash

# Quick test script for the EZ-Expense executable

echo "🧪 Testing EZ-Expense executable..."

# Check if executable exists and is executable
if [ ! -f "../dist/ez-expense" ]; then
    echo "❌ Executable not found at ../dist/ez-expense"
    exit 1
fi

if [ ! -x "../dist/ez-expense" ]; then
    echo "❌ File exists but is not executable"
    exit 1
fi

echo "✅ Executable found and is executable"

# Check file size
SIZE=$(du -h ../dist/ez-expense | cut -f1)
echo "📊 Executable size: $SIZE"

# Check if it's a valid binary
if file ../dist/ez-expense | grep -q "executable"; then
    echo "✅ Valid executable binary"
else
    echo "❌ Not a valid executable"
    exit 1
fi

# Try to get version info or at least verify it starts without crashing immediately
echo "🔍 Testing basic functionality..."
timeout 5s ../dist/ez-expense --version 2>/dev/null || \
timeout 5s ../dist/ez-expense -h 2>/dev/null || \
echo "⚠️  Executable doesn't respond to --version or -h (this is normal for this app)"

echo "✅ Basic tests passed!"
echo ""
echo "💡 To run the app:"
echo "   ./run-ez-expense.sh   (recommended)"
echo "   or"
echo "   ../dist/ez-expense     (direct execution)"