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
            ]
        )

    def close_browser_if_running(self):
        result = subprocess.run(
            ["pgrep", "-f", self.browser.process_name], capture_output=True, text=True
        )
        if result.stdout.strip():
            logger.info(f"Found existing {self.browser.process_name} process(es).")
            (
                input(
                    f"""{self.browser.process_name} needs to be closed for this to work.
                    Hit <Enter> to Close your browser or <Ctrl+C> to cancel"""
                )
                .strip()
                .lower()
            )
            print(f"Closing existing {self.browser.process_name} processes...")
            subprocess.run(["pkill", "-f", self.browser.process_name], capture_output=True)
            time.sleep(1)  # Give time for processes to close
        else:
            logger.info(f"No existing {self.browser.process_name} processes found.")
