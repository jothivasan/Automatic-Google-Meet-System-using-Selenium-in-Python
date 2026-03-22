"""
Google Meet Automation Module
Handles joining, controlling, and leaving Google Meet meetings.
"""

import logging
import threading
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, InvalidSessionIdException,
    WebDriverException,
)
from colorama import Fore, Style

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Selector banks — ordered from most to least reliable.
# Each entry is a (By, selector_string) tuple.
# Updated with current working Google Meet selectors as of 2026.
# ---------------------------------------------------------------------------

_MIC_SELECTORS = [
    (By.XPATH, "//button[@data-is-muted]"),
    (By.XPATH, "//button[contains(@aria-label, 'microphone')]"),
    (By.XPATH, "//button[contains(@aria-label, 'mic')]"),
    (By.XPATH, "//button[@data-tooltip='Turn off microphone']"),
    (By.XPATH, "//button[@data-tooltip='Turn on microphone']"),
    (By.XPATH, "//button[@jsname='BOHk2e']"),
    (By.CSS_SELECTOR, "button[data-tooltip*='microphone' i]"),
    (By.CSS_SELECTOR, "button[aria-label*='microphone' i]"),
    (By.CSS_SELECTOR, "button[aria-label*='mic' i]"),
]

_CAMERA_SELECTORS = [
    (By.XPATH, "//button[contains(@aria-label, 'camera')]"),
    (By.XPATH, "//button[@data-tooltip='Turn off camera']"),
    (By.XPATH, "//button[@data-tooltip='Turn on camera']"),
    (By.XPATH, "//button[@jsname='R3Oird']"),
    (By.CSS_SELECTOR, "button[data-tooltip*='camera' i]"),
    (By.CSS_SELECTOR, "button[aria-label*='camera' i]"),
]

_JOIN_SELECTORS = [
    (By.XPATH, "//button[contains(@jsname, 'Qx7uuf')]"),
    (By.XPATH, "//button[.//span[contains(text(),'Join now')]]"),
    (By.XPATH, "//button[.//span[contains(text(),'Ask to join')]]"),
    (By.XPATH, "//div[@role='button'][contains(@aria-label,'Join')]"),
    (By.XPATH, "//button[contains(@aria-label,'join')]"),
    (By.XPATH, "//button[contains(@aria-label, 'Ask to join')]"),
    (By.XPATH, "//button[contains(@aria-label, 'Join now')]"),
    (By.XPATH, "//button[@jsname='Qx7uuf']"),
    (By.CSS_SELECTOR, "button[data-tooltip='Ask to join']"),
    (By.CSS_SELECTOR, "button[data-tooltip='Join now']"),
    (By.XPATH, "//span[contains(text(), 'Ask to join')]"),
    (By.XPATH, "//span[contains(text(), 'Join now')]"),
    (By.XPATH, "//button[normalize-space()='Join now']"),
]

_LEAVE_SELECTORS = [
    (By.XPATH, "//button[contains(@aria-label,'Leave call')]"),
    (By.XPATH, "//button[contains(@aria-label,'leave')]"),
    (By.XPATH, "//button[@jsname='CQylAd']"),
    (By.XPATH, "//div[@role='button'][contains(@aria-label,'Leave')]"),
    (By.XPATH, "//button[contains(@aria-label, 'End call')]"),
    (By.XPATH, "//button[@data-tooltip='Leave call']"),
    (By.CSS_SELECTOR, "button[data-tooltip='Leave call']"),
    (By.CSS_SELECTOR, "button[data-tooltip='End call']"),
    (By.XPATH, "//span[contains(text(), 'Leave call')]"),
]

# Combined selectors for pre-join screen detection
_PREJOIN_READY_SELECTORS = _MIC_SELECTORS + _CAMERA_SELECTORS + _JOIN_SELECTORS

# Post-leave indicators (goodbye / rejoin screen)
_GOODBYE_SELECTORS = [
    (By.XPATH, "//span[contains(text(), 'Return to home screen')]"),
    (By.XPATH, "//span[contains(text(), 'Rejoin')]"),
    (By.XPATH, "//button[contains(text(), 'Rejoin')]"),
    (By.XPATH, "//button[contains(text(), 'Return to home')]"),
]


class MeetAutomation:
    """
    Automates Google Meet meeting operations including joining,
    controlling audio/video, and leaving meetings.
    """

    def __init__(self, driver):
        """
        Initialize the Meet Automation handler.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, 20)
        self.meeting_joined = False
        self._joined_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_element(self, selectors, timeout=5):
        """
        Try each (By, selector) pair in order and return the first element found.

        Args:
            selectors: list of (By, selector_string) tuples
            timeout (int): per-selector wait in seconds

        Returns:
            WebElement or None
        """
        for by, selector in selectors:
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
            except (TimeoutException, NoSuchElementException):
                continue
        return None

    def _find_clickable(self, selectors, timeout=10):
        """
        Try each (By, selector) pair and return the first clickable element.

        Args:
            selectors: list of (By, selector_string) tuples
            timeout (int): per-selector wait in seconds

        Returns:
            WebElement or None
        """
        for by, selector in selectors:
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((by, selector))
                )
            except (TimeoutException, NoSuchElementException):
                continue
        return None

    def _any_element_present(self, selectors):
        """Non-blocking check: return True if any selector matches in the DOM."""
        for by, selector in selectors:
            try:
                if self.driver.find_elements(by, selector):
                    return True
            except Exception:
                continue
        return False

    def _wait_for_prejoin_screen(self, timeout=20):
        """Wait until any pre-join element becomes visible — single combined wait."""
        def any_visible(driver):
            for by, selector in _PREJOIN_READY_SELECTORS:
                try:
                    el = driver.find_element(by, selector)
                    if el.is_displayed():
                        return True
                except Exception:
                    continue
            return False

        try:
            WebDriverWait(self.driver, timeout).until(any_visible)
            return True
        except TimeoutException:
            return False

    def _is_session_alive(self):
        """Return True if the WebDriver session is still active."""
        try:
            _ = self.driver.current_url
            return True
        except (InvalidSessionIdException, WebDriverException):
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def join_meeting(self, meet_link, microphone_on=False, camera_on=False):
        """
        Join a Google Meet meeting with specified audio/video settings.

        Args:
            meet_link (str): Google Meet URL
            microphone_on (bool): Enable microphone before joining
            camera_on (bool): Enable camera before joining

        Returns:
            bool: True if successfully joined, False otherwise
        """
        try:
            logger.info(f"{Fore.CYAN}Navigating to meeting: {meet_link}{Style.RESET_ALL}")

            if not self._validate_meet_link(meet_link):
                logger.error(f"{Fore.RED}✗ Invalid Google Meet link{Style.RESET_ALL}")
                return False

            self.driver.get(meet_link)

            # Wait for the pre-join lobby to render instead of a blind sleep
            if not self._wait_for_prejoin_screen():
                logger.warning(f"{Fore.YELLOW}⚠ Pre-join screen took too long to load{Style.RESET_ALL}")

            self._check_meeting_status()
            self._dismiss_popups()
            self._set_audio_video(microphone_on, camera_on)

            if not self._is_session_alive():
                logger.error(
                    f"{Fore.RED}✗ Chrome session died (likely caused by profile conflict — "
                    f"close all Chrome windows before running){Style.RESET_ALL}"
                )
                return False

            if self._click_join_button():
                with self._joined_lock:
                    self.meeting_joined = True
                logger.info(f"{Fore.GREEN}✓ Successfully joined the meeting{Style.RESET_ALL}")
                return True

            logger.error(f"{Fore.RED}✗ Failed to join the meeting{Style.RESET_ALL}")
            return False

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error joining meeting: {str(e)}{Style.RESET_ALL}")
            return False

    def _validate_meet_link(self, link):
        """Validate that the link is a genuine Google Meet URL."""
        try:
            parsed = urlparse(link)
            return (
                parsed.scheme in ("https", "http")
                and parsed.netloc == "meet.google.com"
                and bool(parsed.path.strip("/"))
            )
        except Exception:
            return False

    def _check_meeting_status(self):
        """Log a warning if the meeting lobby shows a waiting message."""
        try:
            waiting_indicators = [
                "//span[contains(text(), 'waiting')]",
                "//span[contains(text(), 'hasn\\'t started')]",
                "//div[contains(text(), 'waiting room')]",
            ]
            for indicator in waiting_indicators:
                try:
                    self.driver.find_element(By.XPATH, indicator)
                    logger.warning(f"{Fore.YELLOW}⚠ Waiting for meeting to start{Style.RESET_ALL}")
                    return False
                except NoSuchElementException:
                    continue
            return True
        except Exception:
            return True

    def _set_audio_video(self, microphone_on, camera_on):
        """
        Set microphone and camera state before joining.
        Waits for the controls to appear before interacting.
        """
        try:
            # Non-blocking poll inside WebDriverWait — no nested waits
            WebDriverWait(self.driver, 10).until(
                lambda d: self._any_element_present(_MIC_SELECTORS)
                or self._any_element_present(_CAMERA_SELECTORS)
            )

            mic_status = self._get_mic_status()
            if mic_status != microphone_on:
                self._toggle_microphone()
                logger.info(f"{Fore.CYAN}Microphone: {'ON' if microphone_on else 'OFF'}{Style.RESET_ALL}")

            camera_status = self._get_camera_status()
            if camera_status != camera_on:
                self._toggle_camera()
                logger.info(f"{Fore.CYAN}Camera: {'ON' if camera_on else 'OFF'}{Style.RESET_ALL}")

        except (InvalidSessionIdException, WebDriverException) as e:
            # Session is unrecoverable — propagate so join_meeting can abort cleanly
            raise
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Could not set audio/video: {str(e)}{Style.RESET_ALL}")

    def _get_mic_status(self):
        """Return True if mic is currently on, False if muted."""
        try:
            btn = self._find_element(_MIC_SELECTORS, timeout=3)
            if btn is None:
                return False
            aria_label = btn.get_attribute("aria-label") or ""
            data_tooltip = btn.get_attribute("data-tooltip") or ""
            return "Turn on" not in aria_label and "Turn on" not in data_tooltip
        except Exception:
            return False

    def _get_camera_status(self):
        """Return True if camera is currently on, False if off."""
        try:
            btn = self._find_element(_CAMERA_SELECTORS, timeout=3)
            if btn is None:
                return False
            aria_label = btn.get_attribute("aria-label") or ""
            data_tooltip = btn.get_attribute("data-tooltip") or ""
            return "Turn on" not in aria_label and "Turn on" not in data_tooltip
        except Exception:
            return False

    def _toggle_microphone(self):
        """Click the microphone toggle button."""
        try:
            btn = self._find_clickable(_MIC_SELECTORS, timeout=5)
            if btn:
                btn.click()
                # Wait for the button to become clickable again (state has updated)
                self._find_clickable(_MIC_SELECTORS, timeout=3)
            else:
                logger.warning(f"{Fore.YELLOW}Could not find microphone button{Style.RESET_ALL}")
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Could not toggle microphone: {str(e)}{Style.RESET_ALL}")

    def _toggle_camera(self):
        """Click the camera toggle button."""
        try:
            btn = self._find_clickable(_CAMERA_SELECTORS, timeout=5)
            if btn:
                btn.click()
                self._find_clickable(_CAMERA_SELECTORS, timeout=3)
            else:
                logger.warning(f"{Fore.YELLOW}Could not find camera button{Style.RESET_ALL}")
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Could not toggle camera: {str(e)}{Style.RESET_ALL}")

    def _dismiss_popups(self):
        """Dismiss any popups or permission dialogs."""
        dismiss_selectors = [
            (By.XPATH, "//button[contains(text(), 'Got it')]"),
            (By.XPATH, "//button[contains(text(), 'Dismiss')]"),
            (By.XPATH, "//button[contains(text(), 'Close')]"),
            (By.XPATH, "//span[contains(text(), 'Got it')]"),
        ]
        for by, selector in dismiss_selectors:
            try:
                btn = self.driver.find_element(by, selector)
                btn.click()
                # Brief wait for the dialog to close before checking the next one
                WebDriverWait(self.driver, 2).until(EC.staleness_of(btn))
            except (NoSuchElementException, TimeoutException):
                continue
            except Exception:
                continue

    def _find_join_button_js(self):
        """
        Last-resort: use JavaScript to find the join button by visible text.
        Returns the button WebElement or None.
        """
        script = """
        const labels = ['Join now', 'Ask to join', 'Join'];
        for (const label of labels) {
            // Direct button text match
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => (b.innerText || '').trim() === label);
            if (btn) return btn;
            // Button containing a span with that text
            const spans = Array.from(document.querySelectorAll('button span'));
            const span = spans.find(s => (s.innerText || '').trim() === label);
            if (span) return span.closest('button');
        }
        return null;
        """
        try:
            return self.driver.execute_script(script)
        except Exception:
            return None

    def _click_join_button(self):
        """
        Click the join / ask-to-join button.

        Returns:
            bool: True if button found and clicked
        """
        try:
            # Use a short per-selector timeout (2 s) so we cycle through all
            # candidates quickly rather than blocking for 10 s on each one.
            btn = self._find_clickable(_JOIN_SELECTORS, timeout=2)

            if btn is None:
                # Selector bank missed — try JS text search as last resort
                btn = self._find_join_button_js()
                if btn is None:
                    logger.error(f"{Fore.RED}✗ Could not find join button{Style.RESET_ALL}")
                    return False

            # Try a normal click first; fall back to JS click if an overlay
            # or animation intercepts the event.
            try:
                btn.click()
            except WebDriverException:
                self.driver.execute_script("arguments[0].click()", btn)

            logger.info(f"{Fore.GREEN}✓ Join button clicked{Style.RESET_ALL}")
            # Wait for the leave button to appear (confirms we entered the meeting)
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: self._any_element_present(_LEAVE_SELECTORS)
                )
            except TimeoutException:
                pass  # proceed anyway — join was clicked successfully
            return True

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error clicking join button: {str(e)}{Style.RESET_ALL}")
            return False

    def leave_meeting(self):
        """
        Leave the current Google Meet meeting.

        Returns:
            bool: True if successfully left, False otherwise
        """
        try:
            with self._joined_lock:
                if not self.meeting_joined:
                    logger.warning(f"{Fore.YELLOW}⚠ Not currently in a meeting{Style.RESET_ALL}")
                    return False

            logger.info(f"{Fore.CYAN}Leaving the meeting...{Style.RESET_ALL}")

            btn = self._find_clickable(_LEAVE_SELECTORS, timeout=10)
            if btn:
                btn.click()
                logger.info(f"{Fore.GREEN}✓ Successfully left the meeting{Style.RESET_ALL}")
                with self._joined_lock:
                    self.meeting_joined = False
                # Wait for post-leave indicators (goodbye / rejoin screen)
                try:
                    WebDriverWait(self.driver, 5).until(
                        lambda d: self._any_element_present(_GOODBYE_SELECTORS)
                    )
                except TimeoutException:
                    pass
                return True

            logger.error(f"{Fore.RED}✗ Could not find leave button{Style.RESET_ALL}")
            return False

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error leaving meeting: {str(e)}{Style.RESET_ALL}")
            return False

    def toggle_microphone_during_meeting(self):
        """Toggle microphone during an active meeting."""
        with self._joined_lock:
            if not self.meeting_joined:
                logger.warning(f"{Fore.YELLOW}⚠ Not in a meeting{Style.RESET_ALL}")
                return False
        self._toggle_microphone()
        return True

    def toggle_camera_during_meeting(self):
        """Toggle camera during an active meeting."""
        with self._joined_lock:
            if not self.meeting_joined:
                logger.warning(f"{Fore.YELLOW}⚠ Not in a meeting{Style.RESET_ALL}")
                return False
        self._toggle_camera()
        return True
