"""
Flask Bridge for BUTT (Broadcast Using This Tool) Control
Provides REST API to control streaming and recording functions
Cross-platform: Windows and Linux support
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import os
import time
import psutil
import sys
import platform
from pathlib import Path

app = Flask(__name__)

# Configure CORS to allow requests from your production domain
ALLOWED_ORIGINS = [
    "http://localhost:*",
    "http://127.0.0.1:*",
    "http://192.168.1.25:*",
    "https://evangelo.org",
    "http://evangelo.org",
    "https://www.evangelo.org",
    "http://www.evangelo.org",
]

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": False
    }
})

# Configuration
BUTT_COMMAND_PORT = 1256
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

class BUTTController:
    def __init__(self):
        self.process = None
        self.butt_executable = self._find_butt_executable()
        self.command_port = BUTT_COMMAND_PORT
        print(f"[BUTT] Executable path: {self.butt_executable}")
        print(f"[BUTT] Platform: {platform.system()}")
    
    def _find_butt_executable(self):
        """
        Find BUTT executable on Windows or Linux
        Returns the full path to butt.exe (Windows) or butt (Linux)
        """
        if IS_WINDOWS:
            return self._find_butt_windows()
        elif IS_LINUX:
            return self._find_butt_linux()
        else:
            print(f"[BUTT] WARNING: Unsupported platform: {platform.system()}")
            return "butt"
    
    def _find_butt_windows(self):
        """Find BUTT executable on Windows"""
        # Import Windows-specific modules
        try:
            import winreg
        except ImportError:
            print("[BUTT] winreg not available (not on Windows)")
            return "butt.exe"
        
        # Common installation paths for BUTT on Windows
        possible_paths = [
            r"C:\Program Files\butt\butt.exe",
            r"C:\Program Files (x86)\butt\butt.exe",
            r"C:\butt\butt.exe",
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'butt', 'butt.exe'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'butt', 'butt.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'butt', 'butt.exe'),
        ]
        
        # Check if butt.exe is in PATH
        try:
            result = subprocess.run(['where', 'butt.exe'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if os.path.exists(path):
                    print(f"[BUTT] Found in PATH: {path}")
                    return path
        except Exception as e:
            print(f"[BUTT] PATH search failed: {e}")
        
        # Try to find in registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if "butt" in display_name.lower():
                                    install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                    exe_path = os.path.join(install_location, "butt.exe")
                                    if os.path.exists(exe_path):
                                        print(f"[BUTT] Found in registry: {exe_path}")
                                        return exe_path
                            except:
                                pass
                        i += 1
                    except WindowsError:
                        break
        except Exception as e:
            print(f"[BUTT] Registry search failed: {e}")
        
        # Check common paths
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[BUTT] Found at: {path}")
                return path
        
        # Check user's home directory
        home = Path.home()
        user_paths = [
            home / "butt" / "butt.exe",
            home / "Desktop" / "butt" / "butt.exe",
            home / "Downloads" / "butt" / "butt.exe",
        ]
        
        for path in user_paths:
            if path.exists():
                print(f"[BUTT] Found at: {path}")
                return str(path)
        
        print("[BUTT] WARNING: Could not find butt.exe automatically")
        return "butt.exe"
    
    def _find_butt_linux(self):
        """Find BUTT executable on Linux"""
        # Common installation paths for BUTT on Linux
        possible_paths = [
            "/usr/bin/butt",
            "/usr/local/bin/butt",
            "/opt/butt/butt",
            "/snap/bin/butt",
            str(Path.home() / ".local/bin/butt"),
            str(Path.home() / "bin/butt"),
        ]
        
        # Check if butt is in PATH
        try:
            result = subprocess.run(['which', 'butt'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                path = result.stdout.strip()
                if os.path.exists(path):
                    print(f"[BUTT] Found in PATH: {path}")
                    return path
        except Exception as e:
            print(f"[BUTT] PATH search failed: {e}")
        
        # Check common paths
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[BUTT] Found at: {path}")
                return path
        
        print("[BUTT] WARNING: Could not find butt automatically")
        print("[BUTT] Install BUTT with: sudo apt install butt")
        return "butt"
    
    def is_butt_running(self):
        """Check if BUTT process is running"""
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                if 'butt.exe' in proc_name or proc_name == 'butt':
                    self.process = proc
                    print(f"[BUTT] Found running process: PID {proc.info['pid']}")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    
    def start_butt(self):
        """Start BUTT application with command server enabled"""
        try:
            if not self.is_butt_running():
                if not os.path.exists(self.butt_executable):
                    print(f"[BUTT] ERROR: Executable not found at: {self.butt_executable}")
                    return False
                
                print(f"[BUTT] Starting BUTT from: {self.butt_executable}")
                print(f"[BUTT] Command port: {self.command_port}")
                
                if IS_WINDOWS:
                    process = self._start_butt_windows()
                else:
                    process = self._start_butt_linux()
                
                if process:
                    print(f"[BUTT] Process started with PID: {process.pid}")
                    
                    # Wait for BUTT to initialize
                    max_wait = 10  # seconds
                    wait_interval = 0.5
                    elapsed = 0
                    
                    while elapsed < max_wait:
                        time.sleep(wait_interval)
                        elapsed += wait_interval
                        if self.is_butt_running():
                            print(f"[BUTT] Successfully started after {elapsed} seconds")
                            return True
                        print(f"[BUTT] Waiting for BUTT to start... ({elapsed}s)")
                    
                    print("[BUTT] WARNING: BUTT process started but not detected as running")
                    return True
                else:
                    return False
            else:
                print("[BUTT] BUTT is already running")
                return True
                
        except FileNotFoundError:
            print(f"[BUTT] ERROR: BUTT executable not found at '{self.butt_executable}'")
            return False
        except Exception as e:
            print(f"[BUTT] ERROR starting BUTT: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _start_butt_windows(self):
        """Start BUTT on Windows with proper process handling"""
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        return subprocess.Popen(
            [self.butt_executable, '-p', str(self.command_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            close_fds=False,
            startupinfo=startupinfo,
            cwd=os.path.dirname(self.butt_executable) if os.path.dirname(self.butt_executable) else None
        )
    
    def _start_butt_linux(self):
        """Start BUTT on Linux with proper process handling"""
        return subprocess.Popen(
            [self.butt_executable, '-p', str(self.command_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent
            cwd=os.path.dirname(self.butt_executable) if os.path.dirname(self.butt_executable) else None
        )
    
    def send_command(self, command_args):
        """
        Send command to running BUTT instance via command-line interface
        
        Args:
            command_args: List of command arguments (e.g., ['-s'] for start streaming)
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not os.path.exists(self.butt_executable):
                return False, f"BUTT executable not found: {self.butt_executable}"
            
            # Build command
            cmd = [
                self.butt_executable,
                '-p', str(self.command_port)
            ] + command_args
            
            print(f"[BUTT] Sending command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.path.dirname(self.butt_executable) if os.path.dirname(self.butt_executable) else None
            )
            
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            print(f"[BUTT] Return code: {result.returncode}")
            if stdout:
                print(f"[BUTT] Output: {stdout}")
            if stderr:
                print(f"[BUTT] Error: {stderr}")
            
            success = result.returncode == 0
            message = stdout if stdout else (stderr if stderr else "Command executed")
            
            return success, message
            
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            error_msg = f"Error sending command: {str(e)}"
            print(f"[BUTT] {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg
    
    def start_streaming(self):
        """Start streaming"""
        return self.send_command(['-s'])
    
    def stop_streaming(self):
        """Stop streaming"""
        return self.send_command(['-d'])
    
    def start_recording(self):
        """Start recording"""
        return self.send_command(['-r'])
    
    def stop_recording(self):
        """Stop recording"""
        return self.send_command(['-t'])
    
    def split_recording(self):
        """Split current recording"""
        return self.send_command(['-n'])
    
    def update_song_name(self, song_name):
        """Update song metadata"""
        return self.send_command(['-u', song_name])
    
    def quit_butt(self):
        """Quit BUTT application"""
        return self.send_command(['-q'])
    
    def get_detailed_status(self):
        """
        Get detailed status by parsing BUTT's status output.
        Returns dict with streaming and recording states.
        """
        success, msg = self.send_command(['-S'])
        
        status = {
            'streaming': False,
            'recording': False,
            'connected': False,
            'connecting': False,
            'signal_present': False,
            'raw_message': msg if success else None,
            'command_success': success
        }
        
        if not success or not msg:
            return status
        
        # Clean up the message
        msg_clean = msg.strip()
        print(f"[BUTT] Status message: '{msg_clean}'")
        
        # Parse the key:value format from BUTT
        # BUTT returns status in format like:
        # connecting: 0
        # recording: 0
        # signal present: 1
        # connected: 1
        # etc.
        lines = msg_clean.split('\n')
        status_dict = {}
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                status_dict[key] = value
        
        print(f"[BUTT] Parsed dict: {status_dict}")
        
        # Check streaming status
        # connected: 1 means streaming is active
        # connected: 0 means not streaming
        if 'connected' in status_dict:
            status['connected'] = status_dict['connected'] == '1'
            status['streaming'] = status_dict['connected'] == '1'
        
        # Check connecting status
        if 'connecting' in status_dict:
            status['connecting'] = status_dict['connecting'] == '1'
        
        # Check recording status
        # recording: 1 means recording is active
        # recording: 0 means not recording
        if 'recording' in status_dict:
            status['recording'] = status_dict['recording'] == '1'
        
        # Check signal present
        if 'signal present' in status_dict:
            status['signal_present'] = status_dict['signal present'] == '1'
        
        print(f"[BUTT] Parsed - Streaming: {status['streaming']}, Recording: {status['recording']}")
        
        return status

# Create global controller instance
controller = BUTTController()

# API Routes
@app.route('/', methods=['GET'])
def home():
    """Welcome endpoint"""
    return jsonify({
        'name': 'BUTT Controller Bridge',
        'version': '2.0',
        'platform': platform.system(),
        'endpoints': {
            'status': '/api/status',
            'start_butt': '/api/butt/start',
            'quit_butt': '/api/butt/quit',
            'start_stream': '/api/stream/start',
            'stop_stream': '/api/stream/stop',
            'start_record': '/api/record/start',
            'stop_record': '/api/record/stop',
            'split_record': '/api/record/split',
            'update_song': '/api/song/update'
        }
    })

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    """Get current status of BUTT"""
    if request.method == 'OPTIONS':
        return '', 204
    
    is_running = controller.is_butt_running()
    
    status_info = {
        'butt_running': is_running,
        'butt_executable': controller.butt_executable,
        'butt_found': os.path.exists(controller.butt_executable),
        'streaming': False,
        'recording': False,
        'platform': platform.system(),
        'capabilities': {
            'streaming': True,
            'recording': True,
            'split_recording': True,
            'control_method': 'command_line',
            'platform': platform.system().lower()
        }
    }
    
    if is_running:
        detailed_status = controller.get_detailed_status()
        status_info.update({
            'streaming': detailed_status['streaming'],
            'recording': detailed_status['recording'],
            'connected': detailed_status['connected'],
            'connecting': detailed_status['connecting'],
            'signal_present': detailed_status['signal_present'],
            'status_message': detailed_status['raw_message'],
            'command_success': detailed_status['command_success']
        })
    
    return jsonify(status_info)

@app.route('/api/butt/start', methods=['POST', 'OPTIONS'])
def start_butt():
    """Start BUTT application"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not os.path.exists(controller.butt_executable):
        return jsonify({
            'success': False,
            'message': f'BUTT executable not found at: {controller.butt_executable}',
            'help': 'Please install BUTT from https://danielnoethen.de/butt/'
        }), 404
    
    success = controller.start_butt()
    return jsonify({
        'success': success,
        'message': 'BUTT started successfully' if success else 'Failed to start BUTT',
        'executable_path': controller.butt_executable
    })

@app.route('/api/butt/quit', methods=['POST', 'OPTIONS'])
def quit_butt():
    """Quit BUTT application"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.quit_butt()
    return jsonify({'success': success, 'message': message})

@app.route('/api/stream/start', methods=['POST', 'OPTIONS'])
def start_stream():
    """Start streaming"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.start_streaming()
    return jsonify({'success': success, 'message': message})

@app.route('/api/stream/stop', methods=['POST', 'OPTIONS'])
def stop_stream():
    """Stop streaming"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.stop_streaming()
    return jsonify({'success': success, 'message': message})

@app.route('/api/record/start', methods=['POST', 'OPTIONS'])
def start_record():
    """Start recording"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.start_recording()
    return jsonify({'success': success, 'message': message})

@app.route('/api/record/stop', methods=['POST', 'OPTIONS'])
def stop_record():
    """Stop recording"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.stop_recording()
    return jsonify({'success': success, 'message': message})

@app.route('/api/record/split', methods=['POST', 'OPTIONS'])
def split_record():
    """Split current recording"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.split_recording()
    return jsonify({'success': success, 'message': message})

@app.route('/api/song/update', methods=['POST', 'OPTIONS'])
def update_song():
    """Update song name metadata"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    data = request.json or {}
    song_name = data.get('song_name', '')
    
    if not song_name:
        return jsonify({'success': False, 'message': 'Song name is required'}), 400
    
    success, message = controller.update_song_name(song_name)
    return jsonify({'success': success, 'message': message})

if __name__ == '__main__':
    print("=" * 70)
    print(f"BUTT Controller Bridge - Starting on {platform.system()}...")
    print("=" * 70)
    print(f"Server running on: http://0.0.0.0:5000")
    print(f"Access via localhost: http://localhost:5000")
    print(f"Access via network: http://<your-ip>:5000")
    print(f"API endpoints available at /api/*")
    print("=" * 70)
    print(f"BUTT executable path: {controller.butt_executable}")
    print(f"BUTT executable found: {os.path.exists(controller.butt_executable)}")
    print(f"Command port: {BUTT_COMMAND_PORT}")
    print("=" * 70)
    
    if not os.path.exists(controller.butt_executable):
        print("\n" + "!" * 70)
        print("WARNING: BUTT executable not found!")
        print("!" * 70)
        print("\nPlease install BUTT from:")
        print("https://danielnoethen.de/butt/")
        if IS_LINUX:
            print("Or: sudo apt install butt")
        print("!" * 70 + "\n")
    else:
        print("\n✓ BUTT executable found and ready!")
        print("=" * 70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)