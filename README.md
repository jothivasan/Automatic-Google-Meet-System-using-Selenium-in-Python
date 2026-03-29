# 🤖 Automatic Google Meet System using Selenium in Python

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-4.16.0-green.svg)](https://www.selenium.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive automation system that automatically joins, manages, and leaves Google Meet meetings without manual interaction. Perfect for students and professionals who attend regular online meetings.

## ✨ Features

### Core Functionality

- 🔐 **Automatic Google Account Login** - Secure authentication with your Google credentials
- 🎯 **Smart Meeting Join** - Automatically navigate to and join Google Meet sessions
- ⏰ **Intelligent Scheduling** - Schedule meetings with flexible time and day configurations
- 🎤 **Audio/Video Control** - Toggle microphone and camera ON/OFF before or during meetings
- ⏱️ **Auto-Leave** - Automatically exit meetings after a specified duration
- 🔄 **Repeated Usage** - Reliable automation for daily/weekly recurring meetings

### Advanced Features

- 📅 **YAML-based Configuration** - Easy-to-manage meeting schedules
- 🛡️ **Exception Handling** - Robust error handling for common issues
- 📊 **Detailed Logging** - Track all automation activities
- 🎨 **Colorful Console Output** - Easy-to-read status messages
- 🔒 **Secure Credentials** - Environment variable-based credential storage
- 🌐 **Headless Mode** - Run without visible browser window

## 📁 Project Structure

```
Automatic Google Meet System using Selenium in Python/
│
├── main.py                          # Main entry point
├── requirements.txt                 # Python dependencies
├── .env                             # Your credentials (never commit this)
├── .env.example                     # Environment variables template
├── README.md                        # This file
├── meet_automation.log              # Automation logs (generated)
│
├── venv/                            # Virtual environment (generated, not committed)
│
├── config/
│   └── meetings.yaml                # Meeting schedule configuration
│
└── src/
    ├── __init__.py                  # Package initialization
    ├── browser_manager.py           # Browser setup and management
    ├── google_auth.py               # Google authentication handler
    ├── meet_automation.py           # Google Meet automation logic
    ├── scheduler.py                 # Meeting scheduling system
    └── config_loader.py             # Configuration loader
```

## 🚀 Quick Start

### Prerequisites

### Prerequisites

- **OS:** Windows 10/11 (Primary), macOS, Linux
- **Python:** Version 3.8 or higher
- **Browser:** Google Chrome (Latest Version)
- **Account:** Google account credentials (using a saved Chrome Profile is highly recommended)
- **Permissions:** OS-level Microphone/Camera access enabled for desktop apps (Windows Privacy Settings)

### Installation

1. **Clone or download this project**

   ```bash
   cd "Automatic Google Meet System using Selenium in Python"
   ```

2. **Create and activate a virtual environment**

   **Windows (Command Prompt):**

   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

   **Windows (PowerShell):**

   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```

   **macOS / Linux:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   > You should see `(venv)` in your terminal prompt after activation.

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Verify your system with Pre-Flight Check**

   This system includes a diagnostic script to verify everything is set up correctly (Python version, dependencies, Chrome installation, `.env` structure, and OS privacy settings).

   ```bash
   python preflight_check.py
   ```

   **Do not proceed unless all checks pass!**

5. **Configure credentials**

   ```bash
   # Windows — copy the example environment file
   copy .env.example .env

   # macOS/Linux
   cp .env.example .env
   ```

   Then open `.env` and fill in your credentials:

   ```env
   GOOGLE_EMAIL=your-email@gmail.com
   GOOGLE_PASSWORD=your-password

   # Recommended: set your Chrome profile path to bypass 2FA
   # Find your path by visiting chrome://version/ in Chrome
   # IMPORTANT: Use the parent "User Data" directory, NOT the "Default" subfolder.
   # Windows example: C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data
   CHROME_USER_DATA_DIR=
   CHROME_PROFILE_DIRECTORY=Default

   # Hardware Compatibility Toggle
   USE_FAKE_MEDIA_DEVICE=True
   ```

6. **Configure meetings** (optional, for scheduled mode)

   ```bash
   # Windows
   notepad config\meetings.yaml

   # macOS/Linux
   nano config/meetings.yaml
   ```

### Basic Usage

> Make sure the virtual environment is activated (`(venv)` in your prompt) before running any command.

#### Join a Meeting Now

```bash
# Join a meeting immediately
python main.py --now https://meet.google.com/xxx-xxxx-xxx --duration 3600

# Join with microphone ON
python main.py --now https://meet.google.com/xxx-xxxx-xxx --mic-on

# Join with camera and microphone ON
python main.py --now https://meet.google.com/xxx-xxxx-xxx --mic-on --camera-on
```

#### Run with Scheduler

```bash
# Start the scheduler (uses config/meetings.yaml)
python main.py --schedule
```

#### Deactivate the virtual environment when done

```bash
deactivate
```

## 📋 Configuration

### Environment Variables (.env)

```env
# Google Account Credentials (used as fallback when Chrome profile isn't set)
GOOGLE_EMAIL=your-email@gmail.com
GOOGLE_PASSWORD=your-password

# Chrome Profile (RECOMMENDED — bypasses 2FA/CAPTCHA entirely)
# IMPORTANT: Point to the "User Data" parent directory, NOT the profile subfolder.
# Windows: C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data
# Mac:     ~/Library/Application Support/Google/Chrome
# Linux:   ~/.config/google-chrome
CHROME_USER_DATA_DIR=
CHROME_PROFILE_DIRECTORY=Default

# Browser Settings
HEADLESS_MODE=False          # Set to True for invisible browser
BROWSER_TYPE=chrome

# Hardware Compatibility
USE_FAKE_MEDIA_DEVICE=True   # Set to True if attending silently (cross-machine reliable).
                             # Set to False if you will speak/unmute during meetings.

# Meeting Settings
AUTO_LEAVE_DURATION=3600     # Default duration in seconds (1 hour)
MICROPHONE_ON=False          # Default microphone state
CAMERA_ON=False              # Default camera state
```

### Meeting Schedule (config/meetings.yaml)

```yaml
meetings:
  - name: "Daily Standup"
    link: "https://meet.google.com/xxx-xxxx-xxx"
    time: "09:00"
    days: [MON, TUE, WED, THU, FRI]
    duration: 30
    microphone: false
    camera: false

  - name: "Team Meeting"
    link: "https://meet.google.com/yyy-yyyy-yyy"
    time: "14:00"
    days: [WED]
    duration: 60
    microphone: true
    camera: false
```

## 🎯 Use Cases

### For Students

- Automatically join online classes at scheduled times
- Never miss a lecture due to forgetting the time
- Join with camera/mic off by default for privacy

### For Professionals

- Automate daily standup meetings
- Join recurring team meetings automatically
- Reduce manual effort in meeting attendance

### For Remote Workers

- Manage multiple daily meetings effortlessly
- Ensure punctual attendance
- Focus on work instead of watching the clock

## 🔧 Command Line Options

```
Options:
  --now LINK              Join a meeting immediately (provide Meet link)
  --duration SECONDS      Meeting duration in seconds (default: from config)
  --mic-on                Turn microphone ON
  --mic-off               Turn microphone OFF
  --camera-on             Turn camera ON
  --camera-off            Turn camera OFF
  --schedule              Run with scheduler
  --config PATH           Path to meetings config file
  -h, --help              Show help message
```

## 📊 Features Breakdown

### Browser Management

- Automatic ChromeDriver installation and updates
- Optimized browser settings for Google Meet
- Headless mode support for background operation
- Anti-detection measures

### Authentication

- Secure Google account login
- Session persistence
- Login verification
- Error handling for failed authentication

### Meeting Automation

- Smart meeting link validation
- Automatic join button detection
- Audio/video control before joining
- Meeting status detection
- Graceful leave functionality

### Scheduling

- Flexible day-based scheduling
- Multiple meetings per day support
- Individual meeting configurations
- Next meeting preview
- Continuous scheduler loop

### Error Handling

- Invalid meeting link detection
- Login failure recovery
- Meeting not started handling
- Network error management
- Graceful degradation

## 🔒 Security Considerations

1. **Credential Storage**: Never commit `.env` file to version control
2. **Password Security**: Use app-specific passwords if 2FA is enabled
3. **Headless Mode**: Use for unattended automation
4. **Logging**: Logs don't contain sensitive information

## 🐛 Troubleshooting

### Common Issues

**Issue**: Login fails with 2-factor authentication

- **Solution (Recommended)**: Set `CHROME_USER_DATA_DIR` in `.env` to your Chrome profile path — this loads your saved session and bypasses 2FA entirely. Make sure you point to the **User Data** folder, not the **Default** subfolder.

**Issue**: Automation hangs, freezes, or fails to click mic/camera

- **Solution**: Chrome's profile might be locked by another session. **Close ALL existing Chrome windows** before running the bot. The automation requires exclusive access to the browser profile.

**Issue**: Microphone/camera toggles fail or buttons don't appear

- **Solution 1 (The easy fix)**: Set `USE_FAKE_MEDIA_DEVICE=True` in your `.env`. This forces a synthetic audio/video device, ensuring the Meet buttons always render and click properly, even on PCs with strict privacy settings or no hardware. NOTE: You will not be able to manually unmute and talk with this enabled (the fake device will send a test tone).
- **Solution 2 (If you need real hardware)**: Check Windows Settings → Privacy & Security → Camera & Microphone. Ensure "Let desktop apps access your camera/microphone" is toggled **ON**.

**Issue**: `venv\Scripts\activate` is blocked on PowerShell

- **Solution**: Run once in an Admin PowerShell: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.

## 📝 Logging

All automation activities are logged to `meet_automation.log`:

- Browser initialization
- Login attempts
- Meeting join/leave events
- Errors and warnings
- Scheduling events

## 🔄 Updates and Maintenance

The system is designed to be resilient to minor Google Meet UI changes, but may require updates if Google makes significant changes to their interface.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for educational and personal productivity purposes. Use responsibly and in accordance with Google's Terms of Service. The authors are not responsible for any misuse of this software.

## 👨‍💻 Author

**Your Name**

- Version: 1.0.0
- Created: 2026

## 🙏 Acknowledgments

- Selenium WebDriver team
- Python community
- All contributors and users

## 📞 Support

For issues, questions, or suggestions:

1. Check the **Troubleshooting** section above
2. Review existing issues
3. Create a new issue with detailed information

---

**Made with ❤️ for automating the boring stuff**
Env

# Google Account Credentials

GOOGLE_EMAIL=
GOOGLE_PASSWORD=

# Browser Settings (chrome, firefox, edge)

BROWSER_TYPE=chrome
HEADLESS_MODE=False

# Chrome Profile Settings (optional, for reusing sessions)

# IMPORTANT: Point to the "User Data" parent directory, NOT the profile subfolder.

# The profile subfolder is set via CHROME_PROFILE_DIRECTORY below.

# Example (Windows): C:\Users\<YourUsername>\AppData\Local\Google\Chrome\User Data

CHROME_USER_DATA_DIR=
CHROME_PROFILE_DIRECTORY=Default

# Join recovery settings

JOIN_RETRIES=2
JOIN_RETRY_DELAY_SECONDS=3

# Meeting Defaults

AUTO_LEAVE_DURATION=3600
MICROPHONE_ON=False
CAMERA_ON=False

# Fake Media Device (cross-system compatibility)

# True = Uses a synthetic test device. Mic/camera buttons ALWAYS appear,

# even on PCs without hardware. But you CANNOT use real mic/camera.

# False = Uses your REAL microphone and camera. You can unmute and talk

# during the meeting. But on PCs without hardware, the mic/camera

# buttons may not appear and toggle will fail.

#

# Recommendation: Set to True if you just need silent attendance.

# Set to False if you need to speak/show video during meetings.

USE_FAKE_MEDIA_DEVICE=False
