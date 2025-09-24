import subprocess
import time
from logging import getLogger

from pydantic import BaseModel

logger = getLogger(__name__)


class BrowserConfig(BaseModel):
    application_path: str
    process_name: str


BROWSER_CONFIG = {
    "edge": BrowserConfig(
        application_path="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        process_name="Microsoft Edge",
    ),
}


class BrowserProcess:
    def __init__(self, browser_name: str, port: int):
        self.port = port
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
        """Gracefully close the browser using AppleScript (macOS specific)"""
        try:
            # Use AppleScript to gracefully quit the browser
            applescript = f'''
            tell application "{self.browser.process_name}"
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

    def close_browser_if_running(self):
        result = subprocess.run(
            ["pgrep", "-f", self.browser.process_name], capture_output=True, text=True
        )

        if result.stdout.strip():
            logger.info(f"Found existing {self.browser.process_name} process(es).")

            input(
                "Press Enter to continue. This will close and restart your browser, or Ctrl+C to cancel"
            )

            print(f"Gracefully closing {self.browser.process_name}...")
            if self.close_browser_gracefully():
                print("✅ Browser closed gracefully")
            else:
                print("⚠️ Graceful close failed, falling back to force close...")
                subprocess.run(["pkill", "-f", self.browser.process_name], capture_output=True)
                time.sleep(1)

        else:
            logger.info(f"No existing {self.browser.process_name} processes found.")

        return True
