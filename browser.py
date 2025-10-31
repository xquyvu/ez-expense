import platform
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from logging import getLogger
from pathlib import Path
from typing import Dict

from pydantic import BaseModel

from gui_dialogs import show_browser_confirmation_dialog

logger = getLogger(__name__)


class BrowserConfig(BaseModel):
    application_path: str
    process_name: str


class PlatformHandler(ABC):
    """Abstract base class for platform-specific browser operations"""

    @abstractmethod
    def get_browser_configs(self) -> Dict[str, BrowserConfig]:
        """Get browser configurations for this platform"""
        pass

    @abstractmethod
    def is_browser_running(self, process_name: str) -> bool:
        """Check if browser is running"""
        pass

    @abstractmethod
    def close_browser_gracefully(self, process_name: str) -> bool:
        """Gracefully close browser"""
        pass

    @abstractmethod
    def force_close_browser(self, process_name: str) -> None:
        """Force close browser"""
        pass


class MacOSHandler(PlatformHandler):
    """macOS-specific browser operations"""

    def get_browser_configs(self) -> Dict[str, BrowserConfig]:
        return {
            "edge": BrowserConfig(
                application_path="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                process_name="Microsoft Edge.app",
            ),
            "chrome": BrowserConfig(
                application_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                process_name="Google Chrome.app",
            ),
        }

    def is_browser_running(self, process_name: str) -> bool:
        result = subprocess.run(["pgrep", "-f", process_name], capture_output=True, text=True)
        return bool(result.stdout.strip())

    def close_browser_gracefully(self, process_name: str) -> bool:
        try:
            applescript = f'''
            tell application "{process_name}"
                if it is running then
                    quit
                end if
            end tell
            '''
            subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
            time.sleep(2)  # Give time for graceful shutdown
            return True
        except Exception as e:
            logger.warning(f"Failed to gracefully close browser: {e}")
            return False

    def force_close_browser(self, process_name: str) -> None:
        subprocess.run(["pkill", "-f", process_name], capture_output=True)


class WindowsHandler(PlatformHandler):
    """Windows-specific browser operations"""

    def get_browser_configs(self) -> Dict[str, BrowserConfig]:
        edge_paths = [
            "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
        chrome_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]

        config = {}

        # Find Edge
        for path in edge_paths:
            if Path(path).exists():
                config["edge"] = BrowserConfig(
                    application_path=path,
                    process_name="msedge.exe",
                )
                break

        # Find Chrome
        for path in chrome_paths:
            if Path(path).exists():
                config["chrome"] = BrowserConfig(
                    application_path=path,
                    process_name="chrome.exe",
                )
                break

        return config

    def is_browser_running(self, process_name: str) -> bool:
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-c",
                    f"Get-Process -Name '{process_name.replace('.exe', '')}' -ErrorAction SilentlyContinue",
                ],
                capture_output=True,
                text=True,
            )
            return bool(result.stdout.strip())
        except Exception:
            # Fallback to tasklist method
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"], capture_output=True, text=True
            )
            return process_name.lower() in result.stdout.lower()

    def close_browser_gracefully(self, process_name: str) -> bool:
        try:
            # Use PowerShell for more reliable process termination
            cmd = f"taskkill /IM {process_name} /T"
            subprocess.run(
                ["powershell", "-c", cmd],
                capture_output=True,
                text=True,
            )

            time.sleep(2)  # Give time for graceful shutdown

            # Verify processes are actually gone
            return not self.is_browser_running(process_name)
        except Exception as e:
            logger.warning(f"Failed to gracefully close browser: {e}")
            return False

    def force_close_browser(self, process_name: str) -> None:
        try:
            # Use PowerShell for more reliable force termination
            cmd = f"taskkill /F /IM {process_name}"
            subprocess.run(
                ["powershell", "-c", cmd],
                capture_output=True,
                text=True,
            )

            # Give processes time to terminate
            time.sleep(1)

            # If processes still exist, try more aggressive termination
            if self.is_browser_running(process_name):
                logger.warning(
                    "Processes still running after force close, trying alternative method"
                )
                # Try direct taskkill as fallback
                subprocess.run(["taskkill", "/F", "/IM", process_name], capture_output=True)

        except Exception as e:
            logger.warning(f"Failed to force close browser: {e}")
            # Final fallback to direct taskkill
            try:
                subprocess.run(["taskkill", "/F", "/IM", process_name], capture_output=True)
            except Exception:
                pass


class LinuxHandler(PlatformHandler):
    """Linux and other Unix-like systems browser operations"""

    def get_browser_configs(self) -> Dict[str, BrowserConfig]:
        return {
            "edge": BrowserConfig(
                application_path="microsoft-edge",
                process_name="msedge",
            ),
            "chrome": BrowserConfig(
                application_path="google-chrome",
                process_name="chrome",
            ),
        }

    def is_browser_running(self, process_name: str) -> bool:
        result = subprocess.run(["pgrep", "-f", process_name], capture_output=True, text=True)
        return bool(result.stdout.strip())

    def close_browser_gracefully(self, process_name: str) -> bool:
        try:
            subprocess.run(["pkill", "-f", process_name], capture_output=True, text=True)
            time.sleep(2)  # Give time for graceful shutdown
            return True
        except Exception as e:
            logger.warning(f"Failed to gracefully close browser: {e}")
            return False

    def force_close_browser(self, process_name: str) -> None:
        subprocess.run(["pkill", "-9", "-f", process_name], capture_output=True)


class PlatformHandlerFactory:
    """Factory to create the appropriate platform handler"""

    @staticmethod
    def create_handler() -> PlatformHandler:
        system = platform.system().lower()

        if system == "darwin":
            return MacOSHandler()
        elif system == "windows":
            return WindowsHandler()
        else:  # Linux and other systems
            return LinuxHandler()


# Global platform handler instance
_platform_handler = PlatformHandlerFactory.create_handler()


def get_browser_config():
    """Get browser configuration based on the operating system"""
    return _platform_handler.get_browser_configs()


BROWSER_CONFIG = get_browser_config()


def get_available_browsers():
    """Get list of available browsers on the current system"""
    return list(BROWSER_CONFIG.keys())


def is_browser_available(browser_name: str) -> bool:
    """Check if a specific browser is available on the current system"""
    return browser_name in BROWSER_CONFIG


class BrowserProcess:
    def __init__(self, browser_name: str, port: int):
        self.port = port
        self.platform_handler = _platform_handler

        if browser_name not in BROWSER_CONFIG:
            available_browsers = list(BROWSER_CONFIG.keys())
            raise ValueError(
                f"Browser '{browser_name}' not available on this system. "
                f"Available browsers: {available_browsers}"
            )
        self.browser = BROWSER_CONFIG[browser_name]

    def start_browser_debug_mode(self):
        subprocess.Popen(
            [
                self.browser.application_path,
                f"--remote-debugging-port={self.port}",
                "--new",
                "--log-level=3",  # Only fatal errors (suppresses INFO/WARNING)
                "--disable-logging",  # Disable Chrome's internal logging
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def close_browser_gracefully(self):
        """Gracefully close the browser using platform-specific methods"""
        return self.platform_handler.close_browser_gracefully(self.browser.process_name)

    def close_browser_if_running(self):
        is_running = self.platform_handler.is_browser_running(self.browser.process_name)

        if is_running:
            logger.info(f"Found existing {self.browser.process_name} process(es).")

            # Check if we're running in a terminal
            try:
                if sys.stdin and sys.stdin.isatty():
                    # We have a terminal, use console input (traditional method)
                    print(f"Found existing {self.browser.process_name} process(es).")
                    input(
                        "Press Enter to continue. This will close and restart your browser, or Ctrl+C to cancel: "
                    )
                    user_confirmed = True
                else:
                    # No terminal (GUI app), use GUI dialog
                    user_confirmed = show_browser_confirmation_dialog()
            except Exception as e:
                logger.warning(f"Error checking terminal status: {e}")
                # Fallback to GUI dialog
                user_confirmed = show_browser_confirmation_dialog()

            if not user_confirmed:
                logger.info("User cancelled browser restart")
                print("❌ Browser restart cancelled by user")
                return False

            print(f"🔄 Gracefully closing {self.browser.process_name}...")
            if self.close_browser_gracefully():
                print("✅ Browser closed gracefully")
            else:
                print("⚠️ Graceful close failed, falling back to force close...")
                self.platform_handler.force_close_browser(self.browser.process_name)
                time.sleep(1)
        else:
            logger.info(f"No existing {self.browser.process_name} processes found.")

        return True
