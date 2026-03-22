"""
Google Authentication Module
Handles Google account login automation with error handling.
Checks for an existing saved session before attempting credential-based login.
"""

import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from colorama import Fore, Style

logger = logging.getLogger(__name__)


class GoogleAuthenticator:
    """
    Handles Google account authentication for accessing Google Meet.
    Prefers using a saved Chrome profile session; falls back to
    credential-based login only when not already authenticated.
    """

    def __init__(self, driver, email, password):
        """
        Initialize the Google Authenticator.

        Args:
            driver: Selenium WebDriver instance
            email (str): Google account email
            password (str): Google account password
        """
        self.driver = driver
        self.email = email
        self.password = password
        self.wait = WebDriverWait(driver, 20)

    def login(self):
        """
        Ensure the browser is logged in to Google.
        If a saved Chrome profile is in use the session will already be
        active — this method detects that and skips credential entry.

        Returns:
            bool: True if logged in (by any means), False otherwise
        """
        try:
            # Check if the profile is already authenticated
            if self.is_logged_in():
                logger.info(f"{Fore.GREEN}✓ Already logged in via Chrome profile{Style.RESET_ALL}")
                return True

            logger.info(f"{Fore.CYAN}Starting Google account login...{Style.RESET_ALL}")

            # Navigate to Google login page
            self.driver.get("https://accounts.google.com/")

            # Enter email
            logger.info(f"{Fore.CYAN}Entering email address...{Style.RESET_ALL}")
            email_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            email_field.clear()
            email_field.send_keys(self.email)

            # Click Next
            next_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "identifierNext"))
            )
            next_button.click()

            # Enter password
            logger.info(f"{Fore.CYAN}Entering password...{Style.RESET_ALL}")
            password_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "Passwd"))
            )
            password_field.clear()
            password_field.send_keys(self.password)

            # Click Next
            next_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "passwordNext"))
            )
            next_button.click()

            # Wait for navigation away from the sign-in page
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: not (
                        "accounts.google.com" in d.current_url
                        and "signin" in d.current_url
                    )
                )
            except TimeoutException:
                pass  # _verify_login will handle the final verdict

            if self._verify_login():
                logger.info(f"{Fore.GREEN}✓ Login successful{Style.RESET_ALL}")
                return True
            else:
                logger.error(f"{Fore.RED}✗ Login verification failed{Style.RESET_ALL}")
                return False

        except TimeoutException as e:
            logger.error(f"{Fore.RED}✗ Timeout during login: {str(e)}{Style.RESET_ALL}")
            return False
        except NoSuchElementException as e:
            logger.error(f"{Fore.RED}✗ Element not found during login: {str(e)}{Style.RESET_ALL}")
            return False
        except Exception as e:
            logger.error(f"{Fore.RED}✗ Login failed: {str(e)}{Style.RESET_ALL}")
            raise

    def _verify_login(self):
        """
        Verify login success by requiring a confirmed redirect to a known
        post-login Google domain.  Returns False when stuck on 2FA/challenge.

        Returns:
            bool: True if login successful, False otherwise
        """
        _SUCCESS_DOMAINS = (
            "myaccount.google.com", "mail.google.com",
            "calendar.google.com", "meet.google.com",
            "drive.google.com",
        )
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: any(domain in d.current_url for domain in _SUCCESS_DOMAINS)
            )
            return True

        except TimeoutException:
            current_url = self.driver.current_url
            # Still on a 2FA / challenge page → login NOT complete
            if "challenge" in current_url or "signin" in current_url:
                return False
            # Landed on some other Google page → treat as success
            return any(domain in current_url for domain in _SUCCESS_DOMAINS)
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Could not verify login: {str(e)}{Style.RESET_ALL}")
            return False

    def is_logged_in(self):
        """
        Check whether the browser is already logged in to a Google account.
        Uses a short timeout to avoid blocking when no session exists.

        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            self.driver.get("https://accounts.google.com/")

            # A logged-in session redirects to myaccount.google.com
            WebDriverWait(self.driver, 5).until(
                lambda d: "myaccount.google.com" in d.current_url
                or "/signin" in d.current_url
                or "/ServiceLogin" in d.current_url
            )

            if "myaccount.google.com" in self.driver.current_url:
                logger.info(f"{Fore.GREEN}✓ Already logged in{Style.RESET_ALL}")
                return True

            return False

        except TimeoutException:
            return False
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Could not check login status: {str(e)}{Style.RESET_ALL}")
            return False
