"""
Google Meet Automation System - Main Entry Point
Automates joining and leaving Google Meet meetings with scheduling support.

Author: Your Name
Version: 1.0.0
"""

import os
import sys
import time
import logging
import argparse
from colorama import init, Fore, Style

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from browser_manager import BrowserManager
from google_auth import GoogleAuthenticator
from meet_automation import MeetAutomation
from scheduler import MeetingScheduler
from config_loader import ConfigLoader

# Initialize colorama for Windows
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meet_automation.log'),
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GoogleMeetAutomation:
    """
    Main automation system for Google Meet.
    Coordinates all components to automate meeting attendance.
    """

    def __init__(self, config_loader):
        """
        Initialize the automation system.

        Args:
            config_loader (ConfigLoader): Configuration loader instance
        """
        self.config = config_loader.get_config()
        self.browser_manager = None
        self.driver = None
        self.authenticator = None
        self.meet_automation = None

    def initialize(self):
        """Initialize browser and authenticate."""
        try:
            logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            logger.info(f"{Fore.CYAN}GOOGLE MEET AUTOMATION SYSTEM{Style.RESET_ALL}")
            logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

            # Initialize browser — pass saved profile to launch already logged in
            self.browser_manager = BrowserManager(
                headless=self.config.get('headless', False),
                browser_type=self.config.get('browser_type', 'chrome'),
                user_data_dir=self.config.get('chrome_user_data_dir'),
                profile_directory=self.config.get('chrome_profile_directory', 'Default'),
                use_fake_media_device=self.config.get('use_fake_media_device', True),
            )
            self.driver = self.browser_manager.initialize_browser()

            # Authenticate
            self.authenticator = GoogleAuthenticator(
                self.driver,
                self.config.get('email', ''),
                self.config.get('password', '')
            )

            if not self.authenticator.login():
                raise Exception("Authentication failed")

            # Initialize meet automation
            self.meet_automation = MeetAutomation(self.driver)

            logger.info(f"{Fore.GREEN}✓ System initialized successfully{Style.RESET_ALL}\n")
            return True

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Initialization failed: {str(e)}{Style.RESET_ALL}")
            self.cleanup()
            return False

    def join_meeting_now(self, meet_link, duration=None, microphone=None, camera=None):
        """
        Join a meeting immediately.

        Args:
            meet_link (str): Google Meet URL
            duration (int): Meeting duration in seconds
            microphone (bool): Microphone state
            camera (bool): Camera state
        """
        try:
            # Use config defaults if not specified
            mic_on = microphone if microphone is not None else self.config.get('microphone_on', False)
            cam_on = camera if camera is not None else self.config.get('camera_on', False)
            meet_duration = duration if duration is not None else self.config.get('auto_leave_duration', 3600)

            # Join meeting
            if self.meet_automation.join_meeting(meet_link, mic_on, cam_on):
                logger.info(f"{Fore.GREEN}✓ In meeting. Will leave after {meet_duration} seconds{Style.RESET_ALL}")
                
                # Wait for specified duration
                time.sleep(meet_duration)
                
                # Leave meeting
                self.meet_automation.leave_meeting()
                return True
            else:
                logger.error(f"{Fore.RED}✗ Failed to join meeting{Style.RESET_ALL}")
                return False

        except KeyboardInterrupt:
            logger.info(f"\n{Fore.YELLOW}Meeting interrupted by user{Style.RESET_ALL}")
            if self.meet_automation:
                self.meet_automation.leave_meeting()
            return False
        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error during meeting: {str(e)}{Style.RESET_ALL}")
            return False

    def scheduled_meeting_handler(self, meeting_config):
        """
        Handler for scheduled meetings.

        Args:
            meeting_config (dict): Meeting configuration
        """
        try:
            logger.info(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            logger.info(f"{Fore.GREEN}⏰ Time for: {meeting_config.get('name', 'Unnamed Meeting')}{Style.RESET_ALL}")
            logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

            # Always start with a fresh browser session for each scheduled meeting
            self.cleanup()
            if not self.initialize():
                return

            # Join meeting with config settings
            duration = meeting_config.get('duration', 60) * 60  # Convert minutes to seconds
            microphone = meeting_config.get('microphone', False)
            camera = meeting_config.get('camera', False)

            link = meeting_config.get('link', '').strip()
            if not link:
                logger.error(f"{Fore.RED}✗ Meeting has no link configured{Style.RESET_ALL}")
                self.cleanup()
                return

            self.join_meeting_now(
                link,
                duration=duration,
                microphone=microphone,
                camera=camera
            )

        except Exception as e:
            logger.error(f"{Fore.RED}✗ Error in scheduled meeting: {str(e)}{Style.RESET_ALL}")

    def run_scheduler(self, meetings_config):
        """
        Run the meeting scheduler.

        Args:
            meetings_config (list): List of meeting configurations
        """
        try:
            scheduler = MeetingScheduler(meetings_config)
            scheduler.schedule_meetings(self.scheduled_meeting_handler)
            
            # Display next meeting
            next_meeting = scheduler.get_next_meeting()
            if next_meeting:
                logger.info(f"{Fore.CYAN}Next meeting: {next_meeting['name']} at {next_meeting['time']}{Style.RESET_ALL}\n")

            # Run scheduler loop
            scheduler.run_scheduler()

        except KeyboardInterrupt:
            logger.info(f"\n{Fore.YELLOW}Scheduler stopped{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"{Fore.RED}✗ Scheduler error: {str(e)}{Style.RESET_ALL}")

    def cleanup(self):
        """Cleanup resources and reset all component references."""
        try:
            if self.browser_manager:
                self.browser_manager.close_browser()
            logger.info(f"{Fore.GREEN}✓ Cleanup completed{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"{Fore.RED}✗ Cleanup error: {str(e)}{Style.RESET_ALL}")
        finally:
            self.browser_manager = None
            self.driver = None
            self.authenticator = None
            self.meet_automation = None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Google Meet Automation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Join a meeting now
  python main.py --now https://meet.google.com/xxx-xxxx-xxx --duration 3600

  # Run with scheduler
  python main.py --schedule

  # Join with custom audio/video settings
  python main.py --now https://meet.google.com/xxx-xxxx-xxx --mic-on --camera-on
        """
    )

    parser.add_argument('--now', type=str, help='Join a meeting immediately (provide Meet link)')
    parser.add_argument('--duration', type=int, help='Meeting duration in seconds (default: from config)')
    parser.add_argument('--mic-on', action='store_true', help='Turn microphone ON')
    parser.add_argument('--mic-off', action='store_true', help='Turn microphone OFF')
    parser.add_argument('--camera-on', action='store_true', help='Turn camera ON')
    parser.add_argument('--camera-off', action='store_true', help='Turn camera OFF')
    parser.add_argument('--schedule', action='store_true', help='Run with scheduler')
    parser.add_argument('--config', type=str, help='Path to meetings config file')

    args = parser.parse_args()

    try:
        # Load configuration
        config_loader = ConfigLoader(
            meetings_config_path=args.config if args.config else 'config/meetings.yaml'
        )
        config_loader.load_environment()
        
        if not config_loader.validate_config():
            logger.error(f"{Fore.RED}Please configure your credentials in .env file{Style.RESET_ALL}")
            return

        config_loader.display_config()

        # Initialize automation system
        automation = GoogleMeetAutomation(config_loader)

        # Handle immediate join
        if args.now:
            if not automation.initialize():
                return

            # Determine mic/camera settings
            mic = True if args.mic_on else (False if args.mic_off else None)
            cam = True if args.camera_on else (False if args.camera_off else None)

            automation.join_meeting_now(
                args.now,
                duration=args.duration,
                microphone=mic,
                camera=cam
            )
            automation.cleanup()

        # Handle scheduler
        elif args.schedule:
            meetings = config_loader.load_meetings_config()
            if not meetings:
                logger.error(f"{Fore.RED}No meetings configured in {config_loader.meetings_config_path}{Style.RESET_ALL}")
                return

            automation.run_scheduler(meetings)
            automation.cleanup()

        else:
            parser.print_help()

    except KeyboardInterrupt:
        logger.info(f"\n{Fore.YELLOW}Program terminated by user{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"{Fore.RED}✗ Fatal error: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
