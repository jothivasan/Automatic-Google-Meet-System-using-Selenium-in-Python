"""
Google Meet Automation Module
Handles joining, controlling, and leaving Google Meet meetings.

Cross-system compatibility: All mic/camera controls use multiple
fallback strategies (attribute check → aria-label → keyboard shortcut)
to work consistently regardless of Chrome version, OS language, hardware
availability, or system privacy settings.
"""

import time
import logging
import threading
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, InvalidSessionIdException,
    WebDriverException, StaleElementReferenceException,
)
from colorama import Fore, Style

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Selector banks — ordered from most to least reliable.
# Each entry is a (By, selector_string) tuple.
# Updated with current working Google Meet selectors as of 2026.
# ---------------------------------------------------------------------------

_MIC_SELECTORS = [
    # Most reliable: attribute-based (language-independent)
    (By.CSS_SELECTOR, "button[data-is-muted]"),
    (By.XPATH, "//button[@data-is-muted]"),
    # aria-label partial matches (case-insensitive)
    (By.CSS_SELECTOR, "button[aria-label*='microphone' i]"),
    (By.CSS_SELECTOR, "button[aria-label*='mic' i]"),
    # data-tooltip partial matches (case-insensitive)
    (By.CSS_SELECTOR, "button[data-tooltip*='microphone' i]"),
    # Explicit English text matches
    (By.XPATH, "//button[contains(@aria-label, 'microphone')]"),
    (By.XPATH, "//button[contains(@aria-label, 'mic')]"),
    (By.XPATH, "//button[@data-tooltip='Turn off microphone']"),
    (By.XPATH, "//button[@data-tooltip='Turn on microphone']"),
    # Internal jsname (may change with Google updates)
    (By.XPATH, "//button[@jsname='BOHk2e']"),
]

_CAMERA_SELECTORS = [
    # aria-label partial matches (case-insensitive, language-resilient)
    (By.CSS_SELECTOR, "button[aria-label*='camera' i]"),
    (By.CSS_SELECTOR, "button[data-tooltip*='camera' i]"),
    # Explicit English text matches
    (By.XPATH, "//button[contains(@aria-label, 'camera')]"),
    (By.XPATH, "//button[@data-tooltip='Turn off camera']"),
    (By.XPATH, "//button[@data-tooltip='Turn on camera']"),
    # Internal jsname
    (By.XPATH, "//button[@jsname='R3Oird']"),
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

# Maximum retries for toggling mic/camera
_TOGGLE_MAX_RETRIES = 3


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
        Scan ALL selectors in parallel within a single WebDriverWait.
        Returns the first matching element found within timeout seconds.
        Much faster than sequential per-selector waits.

        Args:
            selectors: list of (By, selector_string) tuples
            timeout (int): total wait in seconds across ALL selectors

        Returns:
            WebElement or None
        """
        def any_present(driver):
            for by, selector in selectors:
                try:
                    els = driver.find_elements(by, selector)
                    if els:
                        return els[0]
                except Exception:
                    continue
            return None

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: any_present(d) is not None
            )
            return any_present(self.driver)
        except TimeoutException:
            return None

    def _find_clickable(self, selectors, timeout=10):
        """
        Scan ALL selectors in parallel within a single WebDriverWait.
        Returns the first visible and enabled element found within timeout seconds.
        Much faster than sequential per-selector waits.

        Args:
            selectors: list of (By, selector_string) tuples
            timeout (int): total wait in seconds across ALL selectors

        Returns:
            WebElement or None
        """
        def any_clickable(driver):
            for by, selector in selectors:
                try:
                    els = driver.find_elements(by, selector)
                    if els and els[0].is_displayed() and els[0].is_enabled():
                        return els[0]
                except Exception:
                    continue
            return None

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: any_clickable(d) is not None
            )
            return any_clickable(self.driver)
        except TimeoutException:
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

    def _wait_for_buttons_interactive(self, timeout=20):
        """
        Wait until BOTH mic and camera buttons are:
        - Present in the DOM
        - Visible on screen
        - Enabled (not disabled)
        Returns True if ready, False if timed out.
        """
        def both_buttons_ready(driver):
            try:
                # Check mic button
                mic_btn = None
                for by, selector in _MIC_SELECTORS:
                    try:
                        els = driver.find_elements(by, selector)
                        if els:
                            mic_btn = els[0]
                            break
                    except Exception:
                        continue

                # Check camera button
                cam_btn = None
                for by, selector in _CAMERA_SELECTORS:
                    try:
                        els = driver.find_elements(by, selector)
                        if els:
                            cam_btn = els[0]
                            break
                    except Exception:
                        continue

                if not mic_btn or not cam_btn:
                    return False

                # Both must be visible and enabled
                return (
                    mic_btn.is_displayed()
                    and mic_btn.is_enabled()
                    and cam_btn.is_displayed()
                    and cam_btn.is_enabled()
                )
            except Exception:
                return False

        try:
            WebDriverWait(self.driver, timeout).until(both_buttons_ready)
            logger.info(f"{Fore.GREEN}✓ Mic and camera buttons are ready{Style.RESET_ALL}")
            return True
        except TimeoutException:
            logger.warning(f"{Fore.YELLOW}⚠ Buttons did not become interactive in time{Style.RESET_ALL}")
            self._save_debug_screenshot("buttons_not_ready")
            return False

    def _wait_for_prejoin_screen(self, timeout=30):
        """
        Wait until the pre-join screen is fully stable —
        any pre-join element is visible AND the page stops changing.
        """
        def any_visible(driver):
            for by, selector in _PREJOIN_READY_SELECTORS:
                try:
                    el = driver.find_element(by, selector)
                    if el.is_displayed():
                        return True
                except Exception:
                    continue
            return False

        def page_is_stable(driver):
            """Check DOM is stable by comparing page source length twice."""
            try:
                first = driver.execute_script("return document.body.innerHTML.length")
                time.sleep(0.5)
                second = driver.execute_script("return document.body.innerHTML.length")
                return first == second
            except Exception:
                return False

        try:
            # Step 1: Wait for any pre-join element to appear
            WebDriverWait(self.driver, timeout).until(any_visible)
            logger.info(f"{Fore.GREEN}✓ Pre-join screen detected{Style.RESET_ALL}")

            # Step 2: Wait for DOM to stop changing (page fully rendered)
            WebDriverWait(self.driver, 10).until(page_is_stable)
            logger.info(f"{Fore.GREEN}✓ Pre-join screen stable{Style.RESET_ALL}")
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

    def _safe_click(self, element):
        """
        Click an element with fallback to JS click if a normal click is
        intercepted by an overlay or animation.
        """
        try:
            element.click()
        except (WebDriverException, StaleElementReferenceException):
            try:
                self.driver.execute_script("arguments[0].click()", element)
            except Exception:
                pass

    def _save_debug_screenshot(self, name):
        """Save a screenshot for debugging cross-machine issues."""
        try:
            import os
            screenshots_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "screenshots"
            )
            os.makedirs(screenshots_dir, exist_ok=True)
            path = os.path.join(screenshots_dir, f"{name}.png")
            self.driver.save_screenshot(path)
            logger.info(f"{Fore.CYAN}Debug screenshot saved: {path}{Style.RESET_ALL}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Mic / Camera status detection (multi-strategy, language-agnostic)
    # ------------------------------------------------------------------

    def _get_mic_status(self):
        """
        Return True if mic is currently ON, False if muted.

        Uses multiple detection strategies for cross-system reliability:
        1. data-is-muted attribute (language-independent, most reliable)
        2. aria-label substring check (works for English UIs)
        3. data-tooltip substring check
        """
        try:
            btn = self._find_element(_MIC_SELECTORS, timeout=5)
            if btn is None:
                logger.warning(f"{Fore.YELLOW}Mic button not found in DOM{Style.RESET_ALL}")
                return None

            # Strategy 1: data-is-muted attribute (best — language-independent)
            data_is_muted = btn.get_attribute("data-is-muted")
            if data_is_muted is not None:
                is_on = data_is_muted.lower() == "false"
                logger.debug(f"Mic status via data-is-muted: {'ON' if is_on else 'OFF'}")
                return is_on

            # Strategy 2: aria-label
            aria_label = (btn.get_attribute("aria-label") or "").lower()
            if "turn on" in aria_label or "unmute" in aria_label:
                return False
            if "turn off" in aria_label or "mute" in aria_label:
                return True

            # Strategy 3: data-tooltip
            data_tooltip = (btn.get_attribute("data-tooltip") or "").lower()
            if "turn on" in data_tooltip:
                return False
            if "turn off" in data_tooltip:
                return True

            # Fallback: assume mic is ON (safer — will attempt to mute)
            logger.warning(f"{Fore.YELLOW}Could not determine mic state, assuming ON{Style.RESET_ALL}")
            return True

        except (StaleElementReferenceException, WebDriverException):
            return None
        except Exception:
            return None

    def _get_camera_status(self):
        """
        Return True if camera is currently ON, False if off.

        Uses multiple detection strategies for cross-system reliability:
        1. data-is-muted attribute (language-independent, most reliable)
        2. aria-label substring check
        3. data-tooltip substring check
        """
        try:
            btn = self._find_element(_CAMERA_SELECTORS, timeout=5)
            if btn is None:
                return None

            # Strategy 1: data-is-muted attribute (most reliable)
            data_is_muted = btn.get_attribute("data-is-muted")
            if data_is_muted is not None:
                return data_is_muted.lower() == "false"

            # Strategy 2: aria-label
            aria_label = (btn.get_attribute("aria-label") or "").lower()
            if "turn on" in aria_label:
                return False
            if "turn off" in aria_label:
                return True

            # Strategy 3: data-tooltip
            data_tooltip = (btn.get_attribute("data-tooltip") or "").lower()
            if "turn on" in data_tooltip:
                return False
            if "turn off" in data_tooltip:
                return True

            logger.warning("Could not determine camera state, assuming ON")
            return True
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Mic / Camera toggling (multi-fallback with verification)
    # ------------------------------------------------------------------

    def _toggle_microphone(self):
        """
        Toggle the microphone button.
        Falls back to keyboard shortcut (Ctrl+D) if button click fails.
        Waits for state change confirmation after each strategy.
        """
        state_before = self._get_mic_status()

        # Strategy 1: Click the button
        btn = self._find_clickable(_MIC_SELECTORS, timeout=5)
        if btn:
            self._safe_click(btn)
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: self._get_mic_status() != state_before
                )
            except TimeoutException:
                pass
            return True

        # Strategy 2: Keyboard shortcut Ctrl+D
        logger.info(f"{Fore.YELLOW}Mic button not clickable, trying Ctrl+D shortcut{Style.RESET_ALL}")
        try:
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('d').key_up(Keys.CONTROL).perform()
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: self._get_mic_status() != state_before
                )
            except TimeoutException:
                pass
            return True
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Keyboard shortcut failed: {e}{Style.RESET_ALL}")

        # Strategy 3: JavaScript click
        logger.info(f"{Fore.YELLOW}Trying JS-based mic toggle{Style.RESET_ALL}")
        try:
            script = """
            var btns = document.querySelectorAll('button[data-is-muted], button[aria-label*="microphone" i], button[aria-label*="mic" i]');
            if (btns.length > 0) { btns[0].click(); return true; }
            return false;
            """
            result = self.driver.execute_script(script)
            if result:
                try:
                    WebDriverWait(self.driver, 3).until(
                        lambda d: self._get_mic_status() != state_before
                    )
                except TimeoutException:
                    pass
                return True
        except Exception:
            pass

        logger.warning(f"{Fore.YELLOW}Could not toggle microphone by any method{Style.RESET_ALL}")
        return False

    def _toggle_camera(self):
        """
        Toggle the camera button.
        Falls back to keyboard shortcut (Ctrl+E) if button click fails.
        Waits for state change confirmation after each strategy.
        """
        state_before = self._get_camera_status()

        # Strategy 1: Click the button
        btn = self._find_clickable(_CAMERA_SELECTORS, timeout=5)
        if btn:
            self._safe_click(btn)
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: self._get_camera_status() != state_before
                )
            except TimeoutException:
                pass
            return True

        # Strategy 2: Keyboard shortcut Ctrl+E
        logger.info(f"{Fore.YELLOW}Camera button not clickable, trying Ctrl+E shortcut{Style.RESET_ALL}")
        try:
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('e').key_up(Keys.CONTROL).perform()
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: self._get_camera_status() != state_before
                )
            except TimeoutException:
                pass
            return True
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Keyboard shortcut failed: {e}{Style.RESET_ALL}")

        # Strategy 3: JavaScript click
        logger.info(f"{Fore.YELLOW}Trying JS-based camera toggle{Style.RESET_ALL}")
        try:
            script = """
            var btns = document.querySelectorAll('button[aria-label*="camera" i], button[data-tooltip*="camera" i]');
            if (btns.length > 0) { btns[0].click(); return true; }
            return false;
            """
            result = self.driver.execute_script(script)
            if result:
                try:
                    WebDriverWait(self.driver, 3).until(
                        lambda d: self._get_camera_status() != state_before
                    )
                except TimeoutException:
                    pass
                return True
        except Exception:
            pass

        logger.warning(f"{Fore.YELLOW}Could not toggle camera by any method{Style.RESET_ALL}")
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def join_meeting(self, meet_link, microphone_on=False, camera_on=False):
        """
        Join a Google Meet meeting with specified audio/video settings.
        Retries up to 2 times if the first attempt fails.

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

            # Retry joining up to 2 times if first attempt fails
            for join_attempt in range(1, 3):
                logger.info(f"{Fore.CYAN}Join attempt {join_attempt}/2...{Style.RESET_ALL}")

                self.driver.get(meet_link)

                if not self._wait_for_prejoin_screen():
                    logger.warning(f"{Fore.YELLOW}⚠ Pre-join screen took too long{Style.RESET_ALL}")
                    self._save_debug_screenshot(f"prejoin_timeout_attempt{join_attempt}")
                    continue  # retry

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

                logger.warning(f"{Fore.YELLOW}⚠ Join attempt {join_attempt} failed, retrying...{Style.RESET_ALL}")
                self._save_debug_screenshot(f"join_failed_attempt{join_attempt}")

            logger.error(f"{Fore.RED}✗ Failed to join after 2 attempts{Style.RESET_ALL}")
            return False

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error joining meeting: {str(e)}{Style.RESET_ALL}")
            self._save_debug_screenshot("join_error")
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
        Uses multi-strategy detection and toggling with verification.
        """
        try:
            # Wait for at least one media control to appear
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: self._any_element_present(_MIC_SELECTORS)
                    or self._any_element_present(_CAMERA_SELECTORS)
                )
            except TimeoutException:
                logger.warning(f"{Fore.YELLOW}⚠ Media controls did not appear in time{Style.RESET_ALL}")
                self._save_debug_screenshot("no_media_controls")

            # Wait for buttons to be truly interactive
            if not self._wait_for_buttons_interactive(timeout=20):
                logger.warning(f"{Fore.YELLOW}⚠ Proceeding despite buttons not confirmed ready{Style.RESET_ALL}")

            # --- Microphone ---
            self._set_mic_state(microphone_on)

            # --- Camera ---
            self._set_camera_state(camera_on)

        except (InvalidSessionIdException, WebDriverException):
            raise
        except Exception as e:
            logger.warning(f"{Fore.YELLOW}Could not set audio/video: {str(e)}{Style.RESET_ALL}")

    def _set_mic_state(self, desired_on):
        """
        Ensure the microphone matches the desired state, with retry.

        Args:
            desired_on (bool): True = microphone should be ON, False = should be muted
        """
        for attempt in range(1, _TOGGLE_MAX_RETRIES + 1):
            current = self._get_mic_status()

            if current is None:
                logger.warning(f"Mic status unknown on attempt {attempt}, skipping toggle")
                try:
                    WebDriverWait(self.driver, 5).until(
                        lambda d: self._get_mic_status() is not None
                    )
                except TimeoutException:
                    pass
                continue

            if current == desired_on:
                state_label = "ON" if desired_on else "OFF"
                logger.info(f"{Fore.GREEN}✓ Microphone already {state_label}{Style.RESET_ALL}")
                return True

            logger.info(
                f"{Fore.CYAN}Toggling microphone from "
                f"{'ON' if current else 'OFF'} → {'ON' if desired_on else 'OFF'} "
                f"(attempt {attempt}/{_TOGGLE_MAX_RETRIES}){Style.RESET_ALL}"
            )
            self._toggle_microphone()

            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: self._get_mic_status() != current
                )
            except TimeoutException:
                pass

            new_status = self._get_mic_status()
            if new_status == desired_on:
                logger.info(f"{Fore.GREEN}✓ Microphone set to {'ON' if desired_on else 'OFF'}{Style.RESET_ALL}")
                return True

            logger.warning(f"{Fore.YELLOW}Mic toggle verification failed (attempt {attempt}){Style.RESET_ALL}")

        logger.error(f"{Fore.RED}✗ Failed to set microphone state after {_TOGGLE_MAX_RETRIES} attempts{Style.RESET_ALL}")
        self._save_debug_screenshot("mic_toggle_failed")
        return False

    def _set_camera_state(self, desired_on):
        """
        Ensure the camera matches the desired state, with retry.

        Args:
            desired_on (bool): True = camera should be ON, False = should be off
        """
        for attempt in range(1, _TOGGLE_MAX_RETRIES + 1):
            current = self._get_camera_status()

            if current is None:
                logger.warning(f"Camera status unknown on attempt {attempt}, skipping toggle")
                try:
                    WebDriverWait(self.driver, 5).until(
                        lambda d: self._get_camera_status() is not None
                    )
                except TimeoutException:
                    pass
                continue

            if current == desired_on:
                state_label = "ON" if desired_on else "OFF"
                logger.info(f"{Fore.GREEN}✓ Camera already {state_label}{Style.RESET_ALL}")
                return True

            logger.info(
                f"{Fore.CYAN}Toggling camera from "
                f"{'ON' if current else 'OFF'} → {'ON' if desired_on else 'OFF'} "
                f"(attempt {attempt}/{_TOGGLE_MAX_RETRIES}){Style.RESET_ALL}"
            )
            self._toggle_camera()

            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: self._get_camera_status() != current
                )
            except TimeoutException:
                pass

            new_status = self._get_camera_status()
            if new_status == desired_on:
                logger.info(f"{Fore.GREEN}✓ Camera set to {'ON' if desired_on else 'OFF'}{Style.RESET_ALL}")
                return True

            logger.warning(f"{Fore.YELLOW}Camera toggle verification failed (attempt {attempt}){Style.RESET_ALL}")

        logger.error(f"{Fore.RED}✗ Failed to set camera state after {_TOGGLE_MAX_RETRIES} attempts{Style.RESET_ALL}")
        self._save_debug_screenshot("camera_toggle_failed")
        return False

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
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => (b.innerText || '').trim() === label);
            if (btn) return btn;
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
        Scans ALL selectors in parallel (single WebDriverWait),
        then confirms entry by waiting for the leave button to appear.

        Returns:
            bool: True if button found, clicked, AND entry confirmed
        """
        try:
            def any_join_button_ready(driver):
                for by, selector in _JOIN_SELECTORS:
                    try:
                        els = driver.find_elements(by, selector)
                        if els and els[0].is_displayed() and els[0].is_enabled():
                            return els[0]
                    except Exception:
                        continue
                return None

            btn = None
            try:
                # Wait up to 10s total for ANY join button to become ready
                WebDriverWait(self.driver, 10).until(
                    lambda d: any_join_button_ready(d) is not None
                )
                btn = any_join_button_ready(self.driver)
            except TimeoutException:
                logger.warning(f"{Fore.YELLOW}Join button not found via selectors{Style.RESET_ALL}")

            # Fallback: JS text search
            if btn is None:
                btn = self._find_join_button_js()
                if btn is None:
                    logger.error(f"{Fore.RED}✗ Could not find join button{Style.RESET_ALL}")
                    return False

            self._safe_click(btn)
            logger.info(f"{Fore.GREEN}✓ Join button clicked{Style.RESET_ALL}")

            # Confirm we actually entered the meeting by waiting for leave button
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: self._any_element_present(_LEAVE_SELECTORS)
                )
                logger.info(f"{Fore.GREEN}✓ Confirmed inside meeting{Style.RESET_ALL}")
            except TimeoutException:
                logger.error(f"{Fore.RED}✗ Join clicked but never entered meeting{Style.RESET_ALL}")
                self._save_debug_screenshot("join_not_confirmed")
                return False

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

            # Use parallel scan for leave button (fast, not sequential)
            btn = self._find_clickable(_LEAVE_SELECTORS, timeout=10)
            if btn:
                self._safe_click(btn)
                logger.info(f"{Fore.GREEN}✓ Successfully left the meeting{Style.RESET_ALL}")
                with self._joined_lock:
                    self.meeting_joined = False
                # Wait for post-leave indicators
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