"""
cx_Freeze setup script for BUTT Controller Bridge with System Tray
Creates Windows MSI installer
Reads configuration from .env file
"""
from cx_Freeze import setup, Executable
import sys
import os
from pathlib import Path

# Load environment variables from .env file
def load_env_file(env_path=".env"):
    """Load environment variables from .env file"""
    env_vars = {}
    env_file = Path(env_path)
    
    if not env_file.exists():
        print(f"Warning: {env_path} file not found. Using default values.")
        return env_vars
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE pairs
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value
    
    return env_vars

# Load environment variables
env_vars = load_env_file()

# Get configuration from .env or use defaults
AUTHOR = env_vars.get('AUTHOR')
UPGRADE_CODE = env_vars.get('UPGRADE_CODE')
APP_URL = env_vars.get('APP_URL')

print(f"Building with configuration:")
print(f"  Author: {AUTHOR}")
print(f"  Upgrade Code: {UPGRADE_CODE}")
print(f"  App URL: {APP_URL}")

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
    "upgrade_code": UPGRADE_CODE,
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