#!/usr/bin/env python3
"""
Debug script to test the macOS app executable directly
"""

import os
import subprocess
from pathlib import Path


def test_executable_directly():
    """Test running the executable directly from command line"""
    app_path = Path("/Users/quyvu/code/ez-expense/releases/ez-expense-macos/EZ-Expense.app")
    executable_path = app_path / "Contents/MacOS/ez-expense"

    print("🔍 Debugging macOS App Executable")
    print("=" * 50)

    # Check if the app bundle exists
    if not app_path.exists():
        print("❌ App bundle not found at expected path")
        return

    print(f"✅ App bundle exists: {app_path}")

    # Check if executable exists
    if not executable_path.exists():
        print("❌ Executable not found in app bundle")
        return

    print(f"✅ Executable exists: {executable_path}")

    # Check executable permissions
    permissions = oct(os.stat(executable_path).st_mode)[-3:]
    print(f"📝 Executable permissions: {permissions}")

    if not os.access(executable_path, os.X_OK):
        print("❌ Executable is not executable")
        print("🔧 Try running: chmod +x " + str(executable_path))
        return

    print("✅ Executable has proper permissions")

    # Test running the executable directly
    print("\n🚀 Testing direct execution...")
    print("Note: This will start the app - press Ctrl+C to stop it")

    try:
        # Change to the app directory for proper resource loading
        os.chdir(app_path.parent)

        # Run the executable and capture output
        result = subprocess.run(
            [str(executable_path)],
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout
        )

        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)

    except subprocess.TimeoutExpired:
        print("⏰ Process is running (timed out after 10 seconds) - this is actually good!")
        print("💡 The app seems to start correctly")
    except Exception as e:
        print(f"❌ Error running executable: {e}")


def test_console_log():
    """Check macOS Console for app launch logs"""
    print("\n📋 Checking macOS Console logs...")
    print("💡 You can also check Console.app for 'EZ-Expense' or 'ez-expense' entries")

    try:
        # Look for recent log entries related to our app
        result = subprocess.run(
            [
                "log",
                "show",
                "--predicate",
                "processImagePath CONTAINS 'ez-expense'",
                "--last",
                "5m",
                "--style",
                "syslog",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.stdout.strip():
            print("Recent logs:")
            print(result.stdout)
        else:
            print("No recent logs found for ez-expense")

    except Exception as e:
        print(f"Could not check logs: {e}")


def check_app_bundle_integrity():
    """Check the app bundle structure"""
    print("\n🔍 Checking App Bundle Structure...")
    app_path = Path("/Users/quyvu/code/ez-expense/releases/ez-expense-macos/EZ-Expense.app")

    required_paths = [
        "Contents/Info.plist",
        "Contents/MacOS/ez-expense",
        "Contents/Resources",
        "Contents/Frameworks",
    ]

    for path in required_paths:
        full_path = app_path / path
        if full_path.exists():
            print(f"✅ {path}")
        else:
            print(f"❌ {path} (missing)")


def suggest_fixes():
    """Suggest potential fixes"""
    print("\n🔧 Potential Fixes:")
    print(
        "1. The Info.plist has 'LSBackgroundOnly' set to true - this makes the app run in background"
    )
    print("2. Try running from Terminal to see error messages:")
    print("   cd /Users/quyvu/code/ez-expense/releases/ez-expense-macos")
    print("   ./EZ-Expense.app/Contents/MacOS/ez-expense")
    print("3. Check Console.app for crash logs or error messages")
    print("4. The app might be starting but not showing a visible window")
    print("5. Check Activity Monitor for 'ez-expense' process")


if __name__ == "__main__":
    test_executable_directly()
    test_console_log()
    check_app_bundle_integrity()
    suggest_fixes()
