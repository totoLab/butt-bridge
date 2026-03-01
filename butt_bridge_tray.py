"""
BUTT Controller Bridge - System Tray Application
Provides a system tray icon with status and control
Supports both Windows (system tray) and Linux (systemd service)
"""

import sys
import threading
import webbrowser
from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import os
import time
import psutil
import platform
import signal
import argparse
import socket

# Try to import pystray and PIL (Windows system tray)
try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    if platform.system() != "Linux":
        print("Warning: pystray not available. Running without system tray.")

# Import the BUTT controller from original script
from butt_bridge import app, controller, ALLOWED_ORIGINS, BUTT_COMMAND_PORT

# Detect operating system
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        # Create a socket to determine the local IP
        # This doesn't actually connect, just determines which interface would be used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # Fallback method
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "Unable to detect"

class TrayApp:
    def __init__(self, headless=False):
        self.icon = None
        self.server_thread = None
        self.server_running = False
        self.headless = headless or IS_LINUX
        self.shutdown_event = threading.Event()
        self.local_ip = get_local_ip()
        
    def create_image(self, color="green"):
        """Create a simple colored circle icon"""
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color='white')
        dc = ImageDraw.Draw(image)
        
        # Draw a circle
        if color == "green":
            fill_color = (34, 139, 34)  # Forest green
        elif color == "red":
            fill_color = (220, 20, 60)  # Crimson
        elif color == "yellow":
            fill_color = (255, 215, 0)  # Gold
        else:
            fill_color = (128, 128, 128)  # Gray
            
        dc.ellipse([8, 8, width-8, height-8], fill=fill_color, outline='black')
        
        # Add "B" for BUTT
        dc.text((22, 18), "B", fill='white', font=None)
        
        return image
    
    def start_server(self):
        """Start Flask server in a separate thread"""
        if not self.server_running:
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            time.sleep(2)  # Wait for server to start
            self.server_running = True
            self.update_icon_status()
            
    def _run_server(self):
        """Run Flask server"""
        print("=" * 60)
        print("BUTT Controller Bridge Starting...")
        print("=" * 60)
        print(f"Platform: {platform.system()}")
        print(f"Local IP: {self.local_ip}")
        print(f"Server running on: http://0.0.0.0:5001")
        print(f"Access via localhost: http://localhost:5001")
        print(f"Access via network: http://{self.local_ip}:5001")
        if not self.headless:
            print(f"System tray icon active")
        print("=" * 60)
        app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False, ssl_context='adhoc')
    
    def stop_server(self):
        """Stop Flask server"""
        self.server_running = False
    
    def update_icon_status(self):
        """Update icon color based on server and BUTT status"""
        if not self.icon:
            return
            
        if not self.server_running:
            self.icon.icon = self.create_image("red")
            self.icon.title = f"BUTT Bridge - Server Stopped\nIP: {self.local_ip}"
        elif controller.is_butt_running():
            self.icon.icon = self.create_image("green")
            self.icon.title = f"BUTT Bridge - Running (BUTT Connected)\nIP: {self.local_ip}:5001"
        else:
            self.icon.icon = self.create_image("yellow")
            self.icon.title = f"BUTT Bridge - Running (BUTT Disconnected)\nIP: {self.local_ip}:5001"
    
    def open_browser(self):
        """Open web interface in browser"""
        webbrowser.open('http://localhost:5001')
    
    def open_api_status(self):
        """Open API status endpoint"""
        webbrowser.open('http://localhost:5001/api/status')
    
    def show_ip_info(self):
        """Show IP address information"""
        message = f"Local IP: {self.local_ip}\nPort: 5001\n\nAccess from network:\nhttp://{self.local_ip}:5001"
        
        if TRAY_AVAILABLE and self.icon:
            self.icon.notify(message, "BUTT Bridge - Network Info")
        else:
            print(f"\n[NETWORK INFO]\n{message}\n")
    
    def start_butt(self):
        """Start BUTT application"""
        success = controller.start_butt()
        time.sleep(1)
        self.update_icon_status()
        return success
    
    def stop_butt(self):
        """Stop BUTT application"""
        if controller.is_butt_running():
            controller.quit_butt()
            time.sleep(1)
            self.update_icon_status()
    
    def check_status(self):
        """Check and display status"""
        butt_running = controller.is_butt_running()
        status = f"Server: {'Running' if self.server_running else 'Stopped'}\n"
        status += f"BUTT: {'Running' if butt_running else 'Not Running'}\n"
        status += f"IP: {self.local_ip}:5001"
        
        # On Windows, we could show a notification
        if TRAY_AVAILABLE and self.icon:
            self.icon.notify(status, "BUTT Bridge Status")
        else:
            print(f"\n[STATUS] {status}")
    
    def quit_app(self, signum=None, frame=None):
        """Quit the application"""
        print("\nShutting down BUTT Bridge...")
        self.shutdown_event.set()
        if self.icon:
            self.icon.stop()
        sys.exit(0)
    
    def create_menu(self):
        """Create system tray menu"""
        return Menu(
            MenuItem(
                'Status',
                self.check_status
            ),
            MenuItem(
                f'IP: {self.local_ip}:5001',
                self.show_ip_info
            ),
            Menu.SEPARATOR,
            MenuItem(
                'Open Web Interface',
                self.open_browser
            ),
            MenuItem(
                'View API Status',
                self.open_api_status
            ),
            Menu.SEPARATOR,
            MenuItem(
                'Start BUTT',
                self.start_butt,
                enabled=lambda item: not controller.is_butt_running()
            ),
            MenuItem(
                'Stop BUTT',
                self.stop_butt,
                enabled=lambda item: controller.is_butt_running()
            ),
            Menu.SEPARATOR,
            MenuItem(
                'Refresh Status',
                self.update_icon_status
            ),
            Menu.SEPARATOR,
            MenuItem(
                'Quit',
                self.quit_app
            )
        )
    
    def run_headless(self):
        """Run in headless mode (for systemd service)"""
        print("Running in headless mode (systemd service)")
        print(f"Local IP: {self.local_ip}")
        print(f"Access via: http://{self.local_ip}:5001")
        print("Press Ctrl+C to quit")
        
        # Setup signal handlers for systemd
        signal.signal(signal.SIGTERM, self.quit_app)
        signal.signal(signal.SIGINT, self.quit_app)
        
        # Notify systemd that we're ready (if running under systemd)
        try:
            import systemd.daemon
            systemd.daemon.notify('READY=1')
            print("Notified systemd: READY")
        except ImportError:
            pass  # systemd module not available
        except Exception as e:
            print(f"Could not notify systemd: {e}")
        
        # Keep running until shutdown
        try:
            while not self.shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nReceived interrupt signal...")
            self.quit_app()
    
    def run(self):
        """Run the tray application"""
        # Start the Flask server
        self.start_server()
        
        if self.headless:
            self.run_headless()
        elif not TRAY_AVAILABLE:
            print("Running in console mode (no system tray)")
            print(f"Local IP: {self.local_ip}")
            print(f"Access via: http://{self.local_ip}:5001")
            print("Press Ctrl+C to quit")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                sys.exit(0)
        else:
            # Create and run system tray icon
            self.icon = Icon(
                "BUTT Bridge",
                self.create_image("yellow"),
                f"BUTT Bridge - Starting...\nIP: {self.local_ip}:5001",
                menu=self.create_menu()
            )
            
            # Update status after a moment
            threading.Timer(2.0, self.update_icon_status).start()
            
            # Run the icon (this blocks)
            self.icon.run()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='BUTT Controller Bridge')
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode (no GUI, suitable for systemd)')
    parser.add_argument('--systemd', action='store_true',
                       help='Run as systemd service (implies --headless)')
    args = parser.parse_args()
    
    # Determine if we should run headless
    headless = args.headless or args.systemd or IS_LINUX
    
    print("""
╔══════════════════════════════════════════════════════════╗
║         BUTT Controller Bridge - System Tray App         ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    print(f"Platform: {platform.system()}")
    local_ip = get_local_ip()
    print(f"Local IP: {local_ip}")
    
    if IS_LINUX:
        print("✓ Running on Linux")
        if args.systemd:
            print("✓ Systemd service mode enabled")
        else:
            print("✓ Headless mode (use --systemd for systemd integration)")
    elif IS_WINDOWS:
        if not TRAY_AVAILABLE and not headless:
            print("⚠ Warning: System tray not available")
            print("Install with: pip install pystray Pillow")
            print("Running in console mode...\n")
        elif TRAY_AVAILABLE and not headless:
            print("✓ System tray enabled")
            print("✓ Look for the icon in your system tray\n")
        elif headless:
            print("✓ Running in headless mode\n")
    
    app_instance = TrayApp(headless=headless)
    
    try:
        app_instance.run()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()