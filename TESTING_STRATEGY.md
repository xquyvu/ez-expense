# Testing Strategy for EZ Expense Application

## Overview
This document outlines comprehensive testing strategies for applications that integrate:
- Browser automation (Playwright)
- External websites
- File processing
- Web APIs
- Frontend-backend communication

## 1. Testing Pyramid

### Unit Tests (70%)
**What to test:**
- Pure functions in isolation
- Data transformation logic
- Configuration loading
- Business logic

**Examples:**
```python
# Test expense data transformation
def test_expense_data_normalization():
    raw_data = {"Amount": "123.45", "Date": "12/31/2023"}
    result = normalize_expense_data(raw_data)
    assert result["amount"] == 123.45
    assert result["date"] == datetime(2023, 12, 31)

# Test configuration loading
def test_config_debug_mode():
    with patch.dict(os.environ, {"DEBUG": "true"}):
        reload(config)
        assert config.DEBUG is True
```

### Integration Tests (20%)
**What to test:**
- API endpoints with mocked dependencies
- Database operations
- File upload/download flows
- Component interactions

**Examples:**
```python
# Test API endpoints
def test_import_endpoint_debug_mode(client, mock_expense_data):
    with patch('config.DEBUG', True):
        response = client.post('/api/expenses/import')
        assert response.status_code == 200
        assert response.json['source'] == 'mock'

def test_import_endpoint_real_mode(client, mock_playwright_page):
    with patch('config.DEBUG', False):
        with patch('expense_importer.get_playwright_page', return_value=mock_playwright_page):
            response = client.post('/api/expenses/import')
            assert response.status_code == 200
            assert response.json['source'] == 'browser'
```

### End-to-End Tests (10%)
**What to test:**
- Complete user workflows
- Real browser automation (in controlled environment)
- Full system integration

## 2. Testing Strategies by Component

### A. Browser Automation Testing

#### ✅ **Recommended Approach:**
```python
# Mock Playwright for most tests
@pytest.fixture
def mock_playwright_page():
    page = Mock()
    page.click = Mock()
    page.fill = Mock()
    page.wait_for_load_state = Mock()
    # Mock specific website elements
    page.locator.return_value.text_content.return_value = "Test Expense"
    return page

# Test real browser automation in isolation
@pytest.mark.integration
@pytest.mark.slow
def test_real_browser_automation():
    """Test actual browser automation against a test website"""
    # Only run in CI/test environment with test data
    if not os.getenv('RUN_BROWSER_TESTS'):
        pytest.skip("Browser tests disabled")

    # Use test website or staging environment
    # NOT production MyExpense site
```

#### ❌ **Avoid:**
- Testing against production websites
- Running browser tests in every test run
- Hard-coding production URLs in tests

### B. API Testing

#### ✅ **Comprehensive API Test Suite:**
```python
class TestExpenseAPI:
    def test_import_success_debug_mode(self, client):
        """Test successful import in DEBUG mode"""

    def test_import_success_real_mode(self, client, mock_browser):
        """Test successful import with mocked browser"""

    def test_import_failure_no_browser(self, client):
        """Test failure when browser not available"""

    def test_import_explicit_mock(self, client):
        """Test explicit mock endpoint"""

    def test_import_explicit_real_failure(self, client):
        """Test explicit real endpoint without browser"""

    def test_debug_status_endpoint(self, client):
        """Test debug status reporting"""
```

### C. Configuration Testing

```python
def test_config_debug_modes():
    """Test all DEBUG configuration scenarios"""
    test_cases = [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("false", False),
        ("False", False),
        ("", False),  # Default case
    ]

    for env_value, expected in test_cases:
        with patch.dict(os.environ, {"DEBUG": env_value}):
            # Reload config module
            reload(config)
            assert config.DEBUG == expected
```

### D. Error Handling Testing

```python
def test_error_scenarios():
    """Test various error conditions"""
    # Browser connection failures
    # Malformed data from website
    # Network timeouts
    # Permission errors
    # Invalid file uploads
```

## 3. Test Environment Setup

### A. Test Configuration
```python
# conftest.py
@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['DEBUG'] = True
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state between tests"""
    # Clear Playwright page reference
    from expense_importer import set_playwright_page
    set_playwright_page(None)
    yield
    set_playwright_page(None)
```

### B. Mock Strategy
```python
# Use dependency injection for testability
class ExpenseImporter:
    def __init__(self, browser_adapter=None):
        self.browser = browser_adapter or RealBrowserAdapter()

    def import_expenses(self):
        return self.browser.extract_expenses()

# Test with mock adapter
def test_expense_import():
    mock_browser = MockBrowserAdapter()
    importer = ExpenseImporter(mock_browser)
    result = importer.import_expenses()
    assert len(result) > 0
```

## 4. CI/CD Testing Pipeline

### A. Test Stages
```yaml
# .github/workflows/test.yml
stages:
  - lint_and_format
  - unit_tests
  - integration_tests_with_mocks
  - security_tests
  - e2e_tests_staging  # Only on staging environment
```

### B. Environment-Specific Tests
- **Development**: All tests with mocks
- **Staging**: Integration tests with test website
- **Production**: Monitoring and health checks only

## 5. Testing Tools Recommendations

### A. Python Testing Stack
```bash
pytest                 # Test runner
pytest-cov           # Coverage reporting
pytest-mock          # Mocking utilities
pytest-asyncio       # Async test support
factory-boy           # Test data factories
responses             # HTTP mocking
```

### B. Browser Testing
```bash
playwright            # Browser automation
pytest-playwright     # Pytest integration
docker                # Containerized browser tests
```

### C. API Testing
```bash
httpx                 # HTTP client for testing
pytest-httpx         # HTTP mocking
```

## 6. Key Testing Principles

### ✅ **Do:**
- Test behavior, not implementation
- Use dependency injection for testability
- Mock external dependencies
- Test error conditions thoroughly
- Use factories for test data
- Keep tests fast and isolated
- Test at the right level (unit vs integration)

### ❌ **Don't:**
- Test against production systems
- Write brittle tests that break on UI changes
- Over-mock (mock only external dependencies)
- Ignore error cases
- Write tests that depend on each other
- Test framework code (like Flask routing)

## 7. Monitoring and Health Checks

```python
# Production monitoring endpoints
@app.route('/health')
def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.route('/health/detailed')
def detailed_health_check():
    """Detailed health check with dependencies"""
    checks = {
        "database": check_database_connection(),
        "browser": check_browser_availability(),
        "file_system": check_file_permissions(),
    }
    status = "healthy" if all(checks.values()) else "unhealthy"
    return {"status": status, "checks": checks}
```

This comprehensive testing strategy ensures reliability while maintaining development velocity and avoiding the pitfalls of testing browser automation applications.