"""
Browser Manager Module
Handles browser initialization, configuration, and cleanup for Google Meet automation.
"""

import os
import platform
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from colorama import Fore, Style

logger = logging.getLogger(__name__)

_CHROMEDRIVER_NAME = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"


class BrowserManager:
    """
    Manages browser instance lifecycle and configuration.
    Supports Chrome browser with customizable options.
    """

    def __init__(self, headless=False, browser_type="chrome",
                 user_data_dir=None, profile_directory=None):
        """
        Initialize the Browser Manager.

        Args:
            headless (bool): Run browser in headless mode (no GUI)
            browser_type (str): Type of browser to use (currently supports 'chrome')
            user_data_dir (str): Path to Chrome user data directory for saved profile login
            profile_directory (str): Chrome profile folder name (e.g. 'Default')
        """
        self.headless = headless
        self.browser_type = browser_type.lower()
        self.user_data_dir = user_data_dir
        self.profile_directory = profile_directory or "Default"
        self.driver = None
        logger.info(f"{Fore.CYAN}Initializing Browser Manager...{Style.RESET_ALL}")

    def setup_chrome_options(self):
        """
        Configure Chrome browser options for optimal Google Meet experience.

        Returns:
            Options: Configured Chrome options object
        """
        chrome_options = Options()

        # Performance optimizations
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Only disable extensions when NOT using a real Chrome profile —
        # a saved profile may rely on extensions for auth or session management.
        if not self.user_data_dir:
            chrome_options.add_argument("--disable-extensions")

        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # Prevent startup dialogs that can block automation
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-default-apps")

        # Auto-grant media permission dialogs so Chrome does not show the
        # "allow microphone / camera" popup.
        # NOTE: --use-fake-device-for-media-stream is intentionally omitted.
        # That flag replaces real mic/camera with test signals, which means
        # no real audio or video would be transmitted in the meeting.
        chrome_options.add_argument("--use-fake-ui-for-media-stream")

        # Set preferences
        prefs = {
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 1,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Saved Chrome profile — launches browser already logged in, bypassing 2FA
        if self.user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={self.user_data_dir}")
            chrome_options.add_argument(f"--profile-directory={self.profile_directory}")
            logger.info(
                f"{Fore.GREEN}Using Chrome profile: {self.user_data_dir} "
                f"[{self.profile_directory}]{Style.RESET_ALL}"
            )

        # Headless mode — use --headless=new for Chrome 112+ compatibility
        if self.headless:
            chrome_options.add_argument("--headless=new")
            logger.info(f"{Fore.YELLOW}Running in headless mode{Style.RESET_ALL}")

        return chrome_options

    def initialize_browser(self):
        """
        Initialize and return a configured browser instance.

        Returns:
            WebDriver: Configured Selenium WebDriver instance

        Raises:
            Exception: If browser initialization fails
        """
        try:
            if self.browser_type == "chrome":
                logger.info(f"{Fore.CYAN}Setting up Chrome browser...{Style.RESET_ALL}")
                chrome_options = self.setup_chrome_options()

                try:
                    driver_path = ChromeDriverManager().install()
                    logger.info(f"{Fore.CYAN}ChromeDriver manager returned: {driver_path}{Style.RESET_ALL}")
                except Exception as e:
                    raise Exception(f"Failed to download/install ChromeDriver: {str(e)}")

                # webdriver-manager can sometimes return a non-driver file path
                # (e.g. THIRD_PARTY_NOTICES). Resolve the real chromedriver
                # executable for the current platform.
                if not os.path.basename(driver_path).lower().startswith("chromedriver"):
                    candidate_dir = os.path.dirname(driver_path)
                    resolved_path = None

                    for root, _, files in os.walk(candidate_dir):
                        for file_name in files:
                            if file_name.lower() == _CHROMEDRIVER_NAME.lower():
                                resolved_path = os.path.join(root, file_name)
                                break
                        if resolved_path:
                            break

                    if resolved_path:
                        driver_path = resolved_path
                        logger.info(f"{Fore.CYAN}Resolved ChromeDriver path: {driver_path}{Style.RESET_ALL}")
                    else:
                        raise FileNotFoundError(
                            f"ChromeDriver executable '{_CHROMEDRIVER_NAME}' not found in or near: {candidate_dir}. "
                            f"Please ensure ChromeDriver is installed and accessible."
                        )

                # Verify the driver path exists and is executable
                if not os.path.exists(driver_path):
                    raise FileNotFoundError(f"ChromeDriver not found at: {driver_path}")

                try:
                    service = Service(driver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    raise Exception(
                        f"Failed to start Chrome browser. Error: {str(e)}. "
                        f"Please ensure Chrome browser is installed and ChromeDriver is compatible."
                    )

                # Maximize window for better element visibility
                if not self.headless:
                    self.driver.maximize_window()

                logger.info(f"{Fore.GREEN}✓ Browser initialized successfully{Style.RESET_ALL}")
                return self.driver
            else:
                raise ValueError(f"Unsupported browser type: {self.browser_type}")

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Failed to initialize browser: {str(e)}{Style.RESET_ALL}")
            raise

    def close_browser(self):
        """
        Safely close the browser and cleanup resources.
        """
        try:
            if self.driver:
                logger.info(f"{Fore.CYAN}Closing browser...{Style.RESET_ALL}")
                self.driver.quit()
                self.driver = None
                logger.info(f"{Fore.GREEN}✓ Browser closed successfully{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error closing browser: {str(e)}{Style.RESET_ALL}")

    def __enter__(self):
        """Context manager entry."""
        return self.initialize_browser()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_browser()
