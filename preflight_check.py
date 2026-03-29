"""
Pre-flight System Check for Google Meet Automation
Run this before using the automation to verify your system is properly configured.

Usage:
    python preflight_check.py
"""

import os
import sys
import platform
import subprocess
import shutil

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def check_mark(ok):
    return "[OK]" if ok else "[FAIL]"


def check_python_version():
    """Check Python version is 3.8+."""
    major, minor = sys.version_info[:2]
    ok = major >= 3 and minor >= 8
    print(f"  [{check_mark(ok)}] Python version: {platform.python_version()} (need 3.8+)")
    return ok


def check_chrome_installed():
    """Check if Google Chrome is installed."""
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    found = any(os.path.exists(p) for p in chrome_paths)

    if found:
        # Try to get version
        try:
            result = subprocess.run(
                [next(p for p in chrome_paths if os.path.exists(p)), "--version"],
                capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip()
            print(f"  [{check_mark(True)}] Chrome installed: {version}")
        except Exception:
            print(f"  [{check_mark(True)}] Chrome installed (version unknown)")
    else:
        print(f"  [{check_mark(False)}] Chrome NOT found in standard locations")
    return found


def check_dependencies():
    """Check if required Python packages are installed."""
    required = ["selenium", "webdriver_manager", "dotenv", "schedule", "yaml", "colorama"]
    import_names = {
        "dotenv": "dotenv",
        "yaml": "yaml",
        "webdriver_manager": "webdriver_manager",
    }
    all_ok = True
    for pkg in required:
        try:
            __import__(import_names.get(pkg, pkg))
            print(f"  [{check_mark(True)}] {pkg}")
        except ImportError:
            print(f"  [{check_mark(False)}] {pkg} — NOT INSTALLED")
            all_ok = False

    # Optional
    try:
        __import__("selenium_stealth")
        print(f"  [{check_mark(True)}] selenium-stealth (optional, recommended)")
    except ImportError:
        print(f"  [~] selenium-stealth — not installed (optional but recommended)")

    return all_ok


def check_env_file():
    """Check .env file exists and has required fields."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        print(f"  [{check_mark(False)}] .env file NOT FOUND")
        return False

    with open(env_path, "r") as f:
        content = f.read()

    issues = []

    if "GOOGLE_EMAIL=" not in content:
        issues.append("Missing GOOGLE_EMAIL")

    # Check Chrome profile path format
    for line in content.splitlines():
        if line.startswith("CHROME_USER_DATA_DIR="):
            path = line.split("=", 1)[1].strip()
            if path:
                if path.endswith("\\Default") or path.endswith("/Default"):
                    issues.append(
                        f"CHROME_USER_DATA_DIR should NOT end with '\\Default' — "
                        f"the profile folder is set separately via CHROME_PROFILE_DIRECTORY.\n"
                        f"    Current:  {path}\n"
                        f"    Expected: {path.rsplit(os.sep, 1)[0] if os.sep in path else path}"
                    )
                if not os.path.isdir(path):
                    issues.append(f"CHROME_USER_DATA_DIR path does not exist: {path}")

    if issues:
        print(f"  [{check_mark(False)}] .env file has issues:")
        for issue in issues:
            print(f"      >> {issue}")
        return False

    print(f"  [{check_mark(True)}] .env file looks good")
    return True


def check_windows_privacy():
    """Check Windows camera/microphone privacy settings (best-effort)."""
    if platform.system() != "Windows":
        print("  [~] Not Windows — skipping privacy check")
        return True

    issues = []

    # Check camera access via registry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam",
        )
        value, _ = winreg.QueryValueEx(key, "Value")
        winreg.CloseKey(key)
        if value.lower() != "allow":
            issues.append(
                "Camera access is DISABLED in Windows Privacy Settings.\n"
                "      -> Go to Settings -> Privacy & Security -> Camera -> Enable 'Let desktop apps access your camera'"
            )
        else:
            print(f"  [{check_mark(True)}] Windows camera privacy: Allowed")
    except Exception:
        print(f"  [~] Could not check camera privacy setting (non-critical)")

    # Check microphone access via registry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone",
        )
        value, _ = winreg.QueryValueEx(key, "Value")
        winreg.CloseKey(key)
        if value.lower() != "allow":
            issues.append(
                "Microphone access is DISABLED in Windows Privacy Settings.\n"
                "      -> Go to Settings -> Privacy & Security -> Microphone -> Enable 'Let desktop apps access your microphone'"
            )
        else:
            print(f"  [{check_mark(True)}] Windows microphone privacy: Allowed")
    except Exception:
        print(f"  [~] Could not check microphone privacy setting (non-critical)")

    if issues:
        for issue in issues:
            print(f"  [{check_mark(False)}] {issue}")
        return False

    return True


def check_chrome_not_running():
    """Check if Chrome is currently running (which can cause profile conflicts)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        if "chrome.exe" in result.stdout.lower():
            print(
                f"  [{check_mark(False)}] Chrome is currently RUNNING.\n"
                f"      >> Close ALL Chrome windows before running the automation.\n"
                f"      >> Profile conflicts can silently break mic/camera controls."
            )
            return False
        print(f"  [{check_mark(True)}] Chrome is not running (good)")
        return True
    except Exception:
        print(f"  [~] Could not check Chrome process status")
        return True


def main():
    print("\n" + "=" * 60)
    print(" GOOGLE MEET AUTOMATION -- PRE-FLIGHT SYSTEM CHECK")
    print("=" * 60)

    results = {}

    print("\n--- Python Environment:")
    results["python"] = check_python_version()

    print("\n--- Dependencies:")
    results["deps"] = check_dependencies()

    print("\n--- Chrome Browser:")
    results["chrome"] = check_chrome_installed()
    results["chrome_running"] = check_chrome_not_running()

    print("\n--- Configuration:")
    results["env"] = check_env_file()

    print("\n--- Windows Privacy Settings:")
    results["privacy"] = check_windows_privacy()

    # Summary
    all_ok = all(results.values())
    print("\n" + "=" * 60)
    if all_ok:
        print(" ALL CHECKS PASSED -- System is ready!")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f" FAIL: {len(failed)} CHECK(S) FAILED: {', '.join(failed)}")
        print(" Fix the issues above before running the automation.")
    print("=" * 60 + "\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
