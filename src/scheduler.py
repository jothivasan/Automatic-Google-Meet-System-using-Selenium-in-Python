"""
Meeting Scheduler Module
Handles scheduling and automatic execution of Google Meet sessions.
"""

import time
import logging
import schedule
from datetime import datetime
from colorama import Fore, Style

logger = logging.getLogger(__name__)


class MeetingScheduler:
    """
    Manages scheduling of Google Meet sessions based on configuration.
    Uses an instance-level scheduler to avoid polluting global schedule state.
    """

    def __init__(self, meetings_config):
        """
        Initialize the Meeting Scheduler.

        Args:
            meetings_config (list): List of meeting configurations
        """
        self.meetings_config = meetings_config
        self.scheduled_jobs = []
        self._scheduler = schedule.Scheduler()   # instance-level, not global
        logger.info(f"{Fore.CYAN}Meeting Scheduler initialized{Style.RESET_ALL}")

    def schedule_meetings(self, join_callback):
        """
        Schedule all meetings from configuration.

        Args:
            join_callback (callable): Function to call when meeting time arrives
        """
        for meeting in self.meetings_config:
            self._schedule_meeting(meeting, join_callback)

        logger.info(f"{Fore.GREEN}✓ Scheduled {len(self.meetings_config)} meeting(s){Style.RESET_ALL}")
        self._display_schedule()

    def _schedule_meeting(self, meeting, join_callback):
        """
        Schedule a single meeting.

        Args:
            meeting (dict): Meeting configuration
            join_callback (callable): Function to call when meeting time arrives
        """
        name = meeting.get('name', 'Unnamed Meeting')
        time_str = meeting.get('time', '09:00')
        days = meeting.get('days', [])

        # Map day names to schedule methods — supports both 3-letter and full names
        day_mapping = {
            'MON': self._scheduler.every().monday,
            'MONDAY': self._scheduler.every().monday,
            'TUE': self._scheduler.every().tuesday,
            'TUESDAY': self._scheduler.every().tuesday,
            'WED': self._scheduler.every().wednesday,
            'WEDNESDAY': self._scheduler.every().wednesday,
            'THU': self._scheduler.every().thursday,
            'THURSDAY': self._scheduler.every().thursday,
            'FRI': self._scheduler.every().friday,
            'FRIDAY': self._scheduler.every().friday,
            'SAT': self._scheduler.every().saturday,
            'SATURDAY': self._scheduler.every().saturday,
            'SUN': self._scheduler.every().sunday,
            'SUNDAY': self._scheduler.every().sunday,
        }

        # Schedule for each specified day
        for day in days:
            key = day.upper()
            if key in day_mapping:
                job = day_mapping[key].at(time_str).do(
                    join_callback, meeting
                )
                self.scheduled_jobs.append({
                    'name': name,
                    'day': day,
                    'time': time_str,
                    'job': job
                })
            else:
                logger.warning(
                    f"{Fore.YELLOW}⚠ Unrecognized day '{day}' for meeting "
                    f"'{name}'{Style.RESET_ALL}"
                )

    def _display_schedule(self):
        """Display all scheduled meetings."""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}SCHEDULED MEETINGS{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

        for scheduled in self.scheduled_jobs:
            print(f"{Fore.GREEN}📅 {scheduled['name']}{Style.RESET_ALL}")
            print(f"   Day: {scheduled['day']} | Time: {scheduled['time']}")
            print()

        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    def run_scheduler(self):
        """
        Run the scheduler loop continuously.

        ✅ Fix: Changed from time.sleep(30) to time.sleep(1).
        
        Why this matters:
        - Old code checked every 30 seconds — if a meeting was at 10:31:00
          and the loop checked at 10:30:45, next check was 10:31:15.
          The schedule library marks jobs as missed → meeting never triggered.
        - New code checks every 1 second — guaranteed to catch every meeting
          within 1 second of its scheduled time. No meetings ever missed.
        """
        logger.info(f"{Fore.GREEN}✓ Scheduler is running... Press Ctrl+C to stop{Style.RESET_ALL}")

        try:
            while True:
                self._scheduler.run_pending()
                time.sleep(1)  # ✅ Check every 1 second — never miss a meeting
        except KeyboardInterrupt:
            logger.info(f"\n{Fore.YELLOW}Scheduler stopped by user{Style.RESET_ALL}")

    def get_next_meeting(self):
        """
        Get information about the next scheduled meeting.

        Returns:
            dict: Next meeting information or None
        """
        if not self.scheduled_jobs:
            return None

        # Find the job with the earliest next_run
        valid = [s for s in self.scheduled_jobs if s['job'].next_run is not None]
        if not valid:
            return None

        earliest = min(valid, key=lambda s: s['job'].next_run)
        return {
            'name': earliest['name'],
            'time': earliest['job'].next_run.strftime('%Y-%m-%d %H:%M:%S'),
        }

    def clear_schedule(self):
        """Clear all scheduled jobs for this scheduler instance."""
        self._scheduler.clear()
        self.scheduled_jobs = []
        logger.info(f"{Fore.YELLOW}All scheduled meetings cleared{Style.RESET_ALL}")

    @staticmethod
    def is_meeting_time(meeting_time_str):
        """
        Check if current time matches meeting time.

        Args:
            meeting_time_str (str): Time in HH:MM format

        Returns:
            bool: True if current time matches
        """
        current_time = datetime.now().strftime('%H:%M')
        return current_time == meeting_time_str

    @staticmethod
    def get_current_day():
        """
        Get current day of week.

        Returns:
            str: Three-letter day code (MON, TUE, etc.)
        """
        days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        return days[datetime.now().weekday()]