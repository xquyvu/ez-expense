"""
Test script to verify Phase 1 implementation
"""

import sys

import requests

from config import FRONTEND_PORT

BASE_URL = f"http://127.0.0.1:{FRONTEND_PORT}"


def test_health_endpoint():
    """Test the health check endpoint"""

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check endpoint working")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_main_page_accessibility():
    """Test main page accessibility and UI elements"""

    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Main page accessible")
            print(f"   Content length: {len(response.text)} characters")

            # Check for key elements in the HTML
            html_content = response.text
            required_elements = [
                "EZ Expense",
                "Import Expenses",
                "Review and Edit Expenses",
                "Match Receipts",
            ]

            missing_elements = []
            for element in required_elements:
                if element not in html_content:
                    missing_elements.append(element)

            if missing_elements:
                print(f"⚠️  Missing elements: {missing_elements}")
                return False
            else:
                print("✅ All required UI elements found")
                return True

        else:
            print(f"❌ Main page failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Main page test failed: {e}")
        return False


def test_static_files():
    """Test static file serving (CSS/JS)"""

    try:
        css_response = requests.get(f"{BASE_URL}/static/css/style.css", timeout=5)
        js_response = requests.get(f"{BASE_URL}/static/js/app.js", timeout=5)

        if css_response.status_code == 200 and js_response.status_code == 200:
            print("✅ Static files (CSS/JS) accessible")
            print(f"   CSS size: {len(css_response.text)} characters")
            print(f"   JS size: {len(js_response.text)} characters")
            return True
        else:
            print(
                f"❌ Static files failed: CSS {css_response.status_code}, JS {js_response.status_code}"
            )
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Static files test failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 1 tests"""
    print("🧪 Testing EZ Expense Flask Application - Phase 1")
    print("=" * 50)

    tests = [
        ("Test 1: Health Check Endpoint", test_health_endpoint),
        ("Test 2: Main Page Accessibility", test_main_page_accessibility),
        ("Test 3: Static File Serving", test_static_files),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * len(test_name))
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 Phase 1 Tests Completed Successfully!")
        print("\nPhase 1 Checklist:")
        print("✅ Task 1.1: Flask web framework set up")
        print("✅ Task 1.2: Frontend dependencies (HTML/CSS/JavaScript) added")
        print("✅ Task 1.3: Project structure created under front_end/ folder")
        print("✅ Task 1.4: Static file serving configured")
        print("✅ Task 1.5: Basic HTML template structure created")
        return True
    else:
        print(f"\n❌ Phase 1 Tests Failed: {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
