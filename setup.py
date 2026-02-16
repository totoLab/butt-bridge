from cx_Freeze import setup, Executable
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(".env")
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")
else:
    print(f"Warning: {env_path} file not found. Using default values or environment variables.")

# Get configuration from .env or environment variables
AUTHOR = os.getenv('AUTHOR', 'Unknown Author')
UPGRADE_CODE = os.getenv('UPGRADE_CODE', '{00000000-0000-0000-0000-000000000000}')
APP_URL = os.getenv('APP_URL', 'https://example.com')

print(f"\nBuilding with configuration:")
print(f"  Author: {AUTHOR}")
print(f"  Upgrade Code: {UPGRADE_CODE}")
print(f"  App URL: {APP_URL}")
print()

# Dependencies are automatically detected, but some modules need help
build_exe_options = {
    "packages": [
        "flask",
        "flask_cors",
        "subprocess",
        "psutil",
        "json",
        "time",
        "os",
        "sys",
        "threading",
        "webbrowser",
        "pystray",
        "PIL",
        "dotenv",  # Add python-dotenv
    ],
    "includes": [
        "flask.json",
        "werkzeug",
        "PIL.Image",
        "PIL.ImageDraw",
    ],
    "excludes": [
        "tkinter",
        "unittest",
        "email",
        "xml",
        "pydoc",
        "matplotlib",
        "numpy",
        "pandas",
    ],
    "include_files": [
        # Add any additional files here if needed
        ("butt_bridge.py", "butt_bridge.py"),  # Include the original module
        (".env", ".env"),  # Include .env file in the build
    ],
    "optimize": 2,
}

# MSI-specific options
bdist_msi_options = {
    "upgrade_code": f"{{{UPGRADE_CODE}}}",
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\BUTT Controller Bridge",
    "install_icon": None,  # Add path to .ico file if you have one
}

# Base for Windows GUI applications
# Use "Win32GUI" to hide console, or None to show console
base = None
if sys.platform == "win32":
    # Use "Win32GUI" to hide console window for tray app
    base = "gui"  # No console window

# Executable configuration
executables = [
    Executable(
        "butt_bridge_tray.py",
        base=base,
        target_name="BUTTBridge.exe",
        icon=None,  # Add path to .ico file if you have one
        shortcut_name="BUTT Controller Bridge",
        shortcut_dir="ProgramMenuFolder",
    )
]

setup(
    name="BUTT Controller Bridge",
    version="1.0.2",
    description="REST API Bridge for BUTT with System Tray Interface",
    author=AUTHOR,
    url=APP_URL,
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
