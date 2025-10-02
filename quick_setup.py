"""
Quick Setup Script for Hotel Itemizer Development
Run this tomorrow to get everything started quickly
"""
import subprocess
import sys
import time
import os

def run_command(command, background=False, description=""):
    """Run a command with proper error handling"""
    if description:
        print(f"🔧 {description}")
    
    try:
        if background:
            # Start in background and return immediately
            if sys.platform == "win32":
                subprocess.Popen(command, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(command, shell=True)
            print(f"✅ Started in background: {command}")
            return True
        else:
            # Run and wait for completion
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Success: {command}")
                return True
            else:
                print(f"❌ Failed: {command}")
                print(f"Error: {result.stderr}")
                return False
    except Exception as e:
        print(f"❌ Exception running {command}: {e}")
        return False

def main():
    print("🚀 HOTEL ITEMIZER - QUICK SETUP")
    print("=" * 50)
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("ms_expense_itemizer.py"):
        print("❌ Please run this from the ez-expense-pm directory")
        return
    
    print("✅ In correct directory")
    
    # 1. Install dependencies
    print("\n📦 Installing dependencies...")
    dependencies = [
        "playwright", "quart", "pydantic", "openai", "pdfplumber", 
        "pillow", "pandas", "openpyxl", "quart-cors", "numpy", "requests"
    ]
    
    for dep in dependencies:
        run_command(f"pip install {dep}", description=f"Installing {dep}")
    
    # 2. Start hotel itemizer web app
    print("\n🌐 Starting Hotel Itemizer Web App...")
    run_command("python -m front_end.app", background=True, description="Starting web app on http://localhost:5001")
    
    # Wait a moment for web app to start
    time.sleep(3)
    
    # 3. Start debug browser
    print("\n🔗 Starting Debug Browser...")
    run_command('python setup_debug_browser.py', background=True, description="Starting Edge with debug port 9222")
    
    print("\n" + "=" * 50)
    print("🎉 SETUP COMPLETE!")
    print("=" * 50)
    print()
    print("✅ Hotel Itemizer running at: http://localhost:5001/hotel-itemizer")
    print("✅ Debug browser started with MS Expense")
    print()
    print("📋 NEXT STEPS:")
    print("1. Navigate to MS Expense in the opened browser")
    print("2. Go to an expense report with hotel charges")
    print("3. Run the automation:")
    print("   python ms_expense_itemizer.py")
    print()
    print("🔧 DEBUG TOOLS:")
    print("   python debug_ms_expense_live.py  # Live element inspector")
    print("   python integrated_hotel_itemizer.py  # Full workflow test")
    print()
    print("📖 See PROJECT_STATUS.md for detailed progress and next steps")

if __name__ == "__main__":
    main()