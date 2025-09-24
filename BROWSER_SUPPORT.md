# Browser Support Documentation

## Overview

The `browser.py` module supports cross-platform browser automation across macOS, Windows, and Linux systems using a clean, object-oriented architecture. The module uses platform-specific handler classes to encapsulate OS-specific operations, making it easy to maintain and extend.

## Architecture

The module uses a class-based approach with the following components:

- **`PlatformHandler`** (Abstract Base Class): Defines the interface for platform-specific operations
- **`MacOSHandler`**: Handles macOS-specific browser operations using AppleScript and `pgrep`
- **`WindowsHandler`**: Handles Windows-specific browser operations using `tasklist` and `taskkill`
- **`LinuxHandler`**: Handles Linux-specific browser operations using `pgrep` and `pkill`
- **`PlatformHandlerFactory`**: Creates the appropriate platform handler based on the current OS

## Supported Platforms

### macOS (Darwin)

- **Edge**: `/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge`
- **Chrome**: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- **Process management**: Uses AppleScript for graceful browser closure
- **Process detection**: Uses `pgrep` command

### Windows

- **Edge**: Searches common installation paths:
  - `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  - `C:\Program Files\Microsoft\Edge\Application\msedge.exe`
- **Chrome**: Searches common installation paths:
  - `C:\Program Files\Google\Chrome\Application\chrome.exe`
  - `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
- **Process management**: Uses `taskkill` for browser closure
- **Process detection**: Uses `tasklist` command

### Linux (and other systems)

- **Edge**: Uses system command `microsoft-edge`
- **Chrome**: Uses system command `google-chrome`
- **Process management**: Uses `pkill` for browser closure
- **Process detection**: Uses `pgrep` command

## Key Features

### Platform-Specific Handlers

Each platform has its own dedicated handler class that encapsulates OS-specific behavior:

```python
from browser import _platform_handler

# The platform handler is automatically selected based on your OS
print(f"Using: {type(_platform_handler).__name__}")

# Each handler provides consistent interface methods:
# - get_browser_configs(): Get available browser configurations
# - is_browser_running(process_name): Check if browser is running
# - close_browser_gracefully(process_name): Gracefully close browser
# - force_close_browser(process_name): Force close browser
```

### Automatic Browser Detection

The system automatically detects which browsers are available on the current platform:

```python
from browser import get_available_browsers, is_browser_available

# Get list of available browsers
browsers = get_available_browsers()
print(f"Available browsers: {browsers}")

# Check if a specific browser is available
if is_browser_available("chrome"):
    print("Chrome is available")
```

### Error Handling

The system provides clear error messages when requesting unsupported browsers:

```python
from browser import BrowserProcess

try:
    browser = BrowserProcess("unsupported_browser", 9222)
except ValueError as e:
    print(f"Error: {e}")
    # Output: Browser 'unsupported_browser' not available on this system. Available browsers: ['edge', 'chrome']
```

### Cross-Platform Process Management

The browser process management automatically uses the appropriate method for each platform through the handler classes:

- **macOS**: AppleScript for graceful closure, `pkill` for force closure
- **Windows**: `taskkill` for both graceful and force closure
- **Linux**: `pkill` with different signals for graceful vs force closure

## Usage Example

```python
import os
from browser import BrowserProcess

# Create a browser process (defaults to Edge, can be overridden with BROWSER env var)
browser_name = os.getenv("BROWSER", "edge")
browser_process = BrowserProcess(browser_name, 9222)

# Close any existing browser instances
browser_process.close_browser_if_running()

# Start browser in debug mode
browser_process.start_browser_debug_mode()
```

## Environment Variables

- `BROWSER`: Specify which browser to use (default: "edge")
  - Valid values: "edge", "chrome" (depending on what's available on your system)

## Testing

Run the included test script to verify browser support on your system:

```bash
uv run python test_browser_support.py
```

This will show:

- Current operating system
- Available browsers on your system
- Whether browser executables exist
- Error handling for unsupported browsers

## Troubleshooting

### Windows-Specific Issues

1. **Browser not found**: If a browser is installed but not detected, it may be in a non-standard location. The module checks common installation paths.

2. **Permission errors**: On Windows, you may need to run the application with appropriate permissions to manage browser processes.

### Cross-Platform Issues

1. **Missing browsers**: If a browser is not available, use `get_available_browsers()` to see what's supported on your system.

2. **Process management fails**: The module falls back to force closure if graceful closure fails.
