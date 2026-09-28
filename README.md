# Automatic Google Meet System using Selenium in Python

A configurable Selenium automation tool for scheduled Google Meet sessions. It demonstrates browser management, environment-based authentication, meeting scheduling, audio/video controls, structured logging, and automatic leave behavior.

## Features

- YAML-defined meeting schedules
- Selenium browser lifecycle and robust element handling
- Optional saved Chrome profile or environment-based authentication
- Microphone and camera controls
- Scheduled auto-join and auto-leave behavior
- Preflight validation and structured logging

## Safety and responsible use

Use this project only for meetings you are authorized to automate and in accordance with Google’s terms, your organization’s policies, and participant consent. Do not commit passwords, session cookies, browser profiles, or private meeting links.

## Setup

Requirements: Python 3.8+, Google Chrome, and a test account or approved Chrome profile.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python preflight_check.py
python main.py
```

Edit `config/meetings.yaml` with authorized test meeting details. The committed configuration contains placeholders only; keep real links in a local, ignored file. Prefer a saved Chrome profile over storing a password in an environment file.

## Project layout

- `main.py` – application entry point
- `src/` – configuration, browser, authentication, scheduling, and Meet automation modules
- `config/` – local schedule template
- `preflight_check.py` – configuration validation

## License

Released under the MIT License. See [LICENSE](LICENSE).
