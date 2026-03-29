"""
Configuration Loader Module
Handles loading and validation of configuration files.
"""

import os
import re
import yaml
import logging
from dotenv import load_dotenv
from colorama import Fore, Style

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Loads and validates configuration from environment variables and YAML files.
    """

    def __init__(self, env_path=None, meetings_config_path=None):
        """
        Initialize the Configuration Loader.

        Args:
            env_path (str): Path to .env file
            meetings_config_path (str): Path to meetings YAML config
        """
        self.env_path = env_path or '.env'
        self.meetings_config_path = meetings_config_path or 'config/meetings.yaml'
        self.config = {}

    def load_environment(self):
        """
        Load environment variables from .env file.

        Returns:
            dict: Environment configuration
        """
        try:
            # Load .env file
            if os.path.exists(self.env_path):
                load_dotenv(self.env_path)
                logger.info(f"{Fore.GREEN}✓ Environment variables loaded{Style.RESET_ALL}")
            else:
                logger.warning(f"{Fore.YELLOW}⚠ .env file not found, using defaults{Style.RESET_ALL}")

            # Extract configuration
            self.config['email'] = os.getenv('GOOGLE_EMAIL', '')
            self.config['password'] = os.getenv('GOOGLE_PASSWORD', '')
            self.config['chrome_user_data_dir'] = os.getenv('CHROME_USER_DATA_DIR', '').strip() or None
            self.config['chrome_profile_directory'] = os.getenv('CHROME_PROFILE_DIRECTORY', 'Default').strip()
            self.config['headless'] = os.getenv('HEADLESS_MODE', 'False').lower() == 'true'
            self.config['browser_type'] = os.getenv('BROWSER_TYPE', 'chrome')
            try:
                self.config['auto_leave_duration'] = int(os.getenv('AUTO_LEAVE_DURATION', '3600'))
            except ValueError:
                logger.warning(
                    f"{Fore.YELLOW}⚠ Invalid AUTO_LEAVE_DURATION; defaulting to 3600s{Style.RESET_ALL}"
                )
                self.config['auto_leave_duration'] = 3600
            self.config['microphone_on'] = os.getenv('MICROPHONE_ON', 'False').lower() == 'true'
            self.config['camera_on'] = os.getenv('CAMERA_ON', 'False').lower() == 'true'
            self.config['use_fake_media_device'] = os.getenv('USE_FAKE_MEDIA_DEVICE', 'True').lower() == 'true'

            return self.config

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error loading environment: {str(e)}{Style.RESET_ALL}")
            raise

    def load_meetings_config(self):
        """
        Load meetings configuration from YAML file with validation.

        Returns:
            list: List of valid meeting configurations
        """
        try:
            if not os.path.exists(self.meetings_config_path):
                logger.warning(f"{Fore.YELLOW}⚠ Meetings config not found: {self.meetings_config_path}{Style.RESET_ALL}")
                return []

            with open(self.meetings_config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file) or {}
                meetings = config_data.get('meetings', [])

                valid_meetings = []
                for i, meeting in enumerate(meetings):
                    if self._validate_meeting_config(meeting, i + 1):
                        valid_meetings.append(meeting)
                    else:
                        logger.warning(f"{Fore.YELLOW}⚠ Skipping invalid meeting #{i + 1}{Style.RESET_ALL}")

                logger.info(f"{Fore.GREEN}✓ Loaded {len(valid_meetings)} valid meeting(s) from config (skipped {len(meetings) - len(valid_meetings)}){Style.RESET_ALL}")
                return valid_meetings

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error loading meetings config: {str(e)}{Style.RESET_ALL}")
            raise

    def _validate_meeting_config(self, meeting, meeting_number):
        """
        Validate a single meeting configuration.

        Args:
            meeting (dict): Meeting configuration to validate
            meeting_number (int): Meeting number for error reporting

        Returns:
            bool: True if valid, False otherwise
        """
        errors = []

        # Validate meeting link
        link = meeting.get('link', '').strip()
        if not link:
            errors.append("Missing meeting link")
        elif not link.startswith('https://meet.google.com/'):
            errors.append(f"Invalid meeting link: must start with 'https://meet.google.com/'")

        # Validate time format (HH:MM)
        time_str = meeting.get('time', '').strip()
        if not time_str:
            errors.append("Missing meeting time")
        elif not re.match(r'^\d{2}:\d{2}$', time_str):
            errors.append(f"Invalid time format '{time_str}': must be HH:MM (e.g., '09:30')")
        else:
            # Validate time range
            try:
                hours, minutes = map(int, time_str.split(':'))
                if hours > 23 or minutes > 59:
                    errors.append(f"Invalid time '{time_str}': hours must be 0-23, minutes 0-59")
            except ValueError:
                errors.append(f"Invalid time format '{time_str}': must be numeric HH:MM")

        # Validate duration
        duration = meeting.get('duration')
        if duration is None:
            errors.append("Missing meeting duration")
        elif not isinstance(duration, int) or duration <= 0:
            errors.append(f"Invalid duration '{duration}': must be a positive integer (minutes)")

        # Validate days
        days = meeting.get('days', [])
        if not days:
            errors.append("Missing meeting days")
        elif not isinstance(days, list):
            errors.append("Days must be a list")
        else:
            valid_days = {'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
                         'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'}
            for day in days:
                if day.upper() not in valid_days:
                    errors.append(f"Invalid day '{day}': must be one of {', '.join(sorted(valid_days))}")

        # Report errors
        if errors:
            logger.error(f"{Fore.RED}✗ Meeting #{meeting_number} validation failed:{Style.RESET_ALL}")
            for error in errors:
                logger.error(f"  - {error}")
            return False

        return True

    def validate_config(self):
        """
        Validate that required configuration is present.

        Returns:
            bool: True if valid, False otherwise
        """
        errors = []

        # Check email (also catch the default placeholder)
        email = self.config.get('email', '')
        if not email or email == 'your_email@gmail.com':
            errors.append("GOOGLE_EMAIL is not configured (replace the placeholder in .env)")

        # Password only required when no Chrome profile is configured
        using_profile = bool(self.config.get('chrome_user_data_dir'))
        if not using_profile and not self.config.get('password'):
            errors.append(
                "GOOGLE_PASSWORD is required (or set CHROME_USER_DATA_DIR to use saved profile)"
            )

        # Display errors
        if errors:
            logger.error(f"{Fore.RED}✗ Configuration validation failed:{Style.RESET_ALL}")
            for error in errors:
                logger.error(f"  - {error}")
            return False

        logger.info(f"{Fore.GREEN}✓ Configuration validated{Style.RESET_ALL}")
        return True

    def get_config(self):
        """
        Get the loaded configuration.

        Returns:
            dict: Configuration dictionary
        """
        return self.config

    def display_config(self):
        """Display current configuration (hiding sensitive data)."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}CURRENT CONFIGURATION{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

        # Mask sensitive data
        email = self.config.get('email', 'Not set')
        masked_email = email[:3] + '***' + email[email.find('@'):] if email and '@' in email else 'Not set'
        
        print(f"Email: {masked_email}")
        print(f"Password: {'***' if self.config.get('password') else 'Not set'}")
        print(f"Browser: {self.config.get('browser_type', 'chrome')}")
        print(f"Headless Mode: {self.config.get('headless', False)}")
        print(f"Auto Leave Duration: {self.config.get('auto_leave_duration', 3600)} seconds")
        print(f"Default Microphone: {'ON' if self.config.get('microphone_on') else 'OFF'}")
        print(f"Default Camera: {'ON' if self.config.get('camera_on') else 'OFF'}")

        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
