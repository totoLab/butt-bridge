"""
Flask Bridge for BUTT (Broadcast Using This Tool) Control
Provides REST API to control streaming and recording functions
Cross-platform: Windows and Linux support
WITH CACHING TO AVOID RATE LIMITING
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
from threading import Lock
from datetime import datetime, timedelta

app = Flask(__name__)

# Configure CORS to allow requests from your production domain
ALLOWED_ORIGINS = [
    "http://localhost:*",
    "http://127.0.0.1:*",
    "http://192.168.1.25:*",
    "http://192.168.1.168:*",
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

# Cache configuration
STATUS_CACHE_DURATION = 2.0  # Cache status for 2 seconds
COMMAND_MIN_INTERVAL = 0.5   # Minimum 500ms between commands


class StatusCache:
    """Thread-safe cache for BUTT status to avoid rate limiting"""
    
    def __init__(self, ttl_seconds=STATUS_CACHE_DURATION):
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.lock = Lock()
        self.last_command_time = {}
        self.command_lock = Lock()
    
    def get(self, key):
        """Get cached value if not expired"""
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                    print(f"[CACHE] HIT for {key} (age: {(datetime.now() - timestamp).total_seconds():.2f}s)")
                    return value
                else:
                    print(f"[CACHE] EXPIRED for {key}")
                    del self.cache[key]
            else:
                print(f"[CACHE] MISS for {key}")
            return None
    
    def set(self, key, value):
        """Set cached value with current timestamp"""
        with self.lock:
            self.cache[key] = (value, datetime.now())
            print(f"[CACHE] SET for {key}")
    
    def invalidate(self, key=None):
        """Invalidate cache entry or all entries"""
        with self.lock:
            if key:
                if key in self.cache:
                    del self.cache[key]
                    print(f"[CACHE] INVALIDATED {key}")
            else:
                self.cache.clear()
                print(f"[CACHE] INVALIDATED ALL")
    
    def can_send_command(self, command_type):
        """Check if enough time has passed since last command of this type"""
        with self.command_lock:
            now = datetime.now()
            if command_type in self.last_command_time:
                elapsed = (now - self.last_command_time[command_type]).total_seconds()
                if elapsed < COMMAND_MIN_INTERVAL:
                    print(f"[THROTTLE] Command {command_type} blocked (only {elapsed:.2f}s since last)")
                    return False
            self.last_command_time[command_type] = now
            return True
    
    def clear_old_entries(self):
        """Remove expired cache entries"""
        with self.lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, timestamp) in self.cache.items()
                if now - timestamp >= timedelta(seconds=self.ttl_seconds)
            ]
            for key in expired_keys:
                del self.cache[key]
            if expired_keys:
                print(f"[CACHE] Cleared {len(expired_keys)} expired entries")


class BUTTController:
    def __init__(self):
        self.process = None
        self.butt_executable = self._find_butt_executable()
        self.command_port = BUTT_COMMAND_PORT
        self.cache = StatusCache()
        print(f"[BUTT] Executable path: {self.butt_executable}")
        print(f"[BUTT] Platform: {platform.system()}")
        print(f"[BUTT] Cache enabled: Status TTL={STATUS_CACHE_DURATION}s, Command interval={COMMAND_MIN_INTERVAL}s")
    
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
    
    def is_butt_running(self, use_cache=True):
        """Check if BUTT process is running (with optional caching)"""
        if use_cache:
            cached = self.cache.get('butt_running')
            if cached is not None:
                return cached
        
        is_running = False
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                if 'butt.exe' in proc_name or proc_name == 'butt':
                    self.process = proc
                    print(f"[BUTT] Found running process: PID {proc.info['pid']}")
                    is_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if use_cache:
            self.cache.set('butt_running', is_running)
        
        return is_running
    
    def start_butt(self):
        """Start BUTT application with command server enabled"""
        try:
            if not self.is_butt_running(use_cache=False):
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
                        if self.is_butt_running(use_cache=False):
                            print(f"[BUTT] Successfully started after {elapsed} seconds")
                            self.cache.invalidate()  # Clear cache after starting
                            return True
                        print(f"[BUTT] Waiting for BUTT to start... ({elapsed}s)")
                    
                    print("[BUTT] WARNING: BUTT process started but not detected as running")
                    self.cache.invalidate()  # Clear cache
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
    
    def send_command(self, command_args, command_type=None):
        """
        Send command to running BUTT instance via command-line interface
        WITH THROTTLING to avoid rate limiting
        
        Args:
            command_args: List of command arguments (e.g., ['-s'] for start streaming)
            command_type: String identifier for throttling (e.g., 'start_stream', 'status')
        
        Returns:
            tuple: (success: bool, message: str)
        """
        # Apply throttling if command_type is specified
        if command_type and not self.cache.can_send_command(command_type):
            return False, f"Command throttled - please wait {COMMAND_MIN_INTERVAL}s between {command_type} commands"
        
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
            
            # Invalidate status cache after state-changing commands
            if command_type and command_type != 'status':
                self.cache.invalidate('detailed_status')
                print(f"[BUTT] Cache invalidated after {command_type}")
            
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
        return self.send_command(['-s'], command_type='start_stream')
    
    def stop_streaming(self):
        """Stop streaming"""
        return self.send_command(['-d'], command_type='stop_stream')
    
    def start_recording(self):
        """Start recording"""
        return self.send_command(['-r'], command_type='start_record')
    
    def stop_recording(self):
        """Stop recording"""
        return self.send_command(['-t'], command_type='stop_record')
    
    def split_recording(self):
        """Split current recording"""
        return self.send_command(['-n'], command_type='split_record')
    
    def update_song_name(self, song_name):
        """Update song metadata"""
        return self.send_command(['-u', song_name], command_type='update_song')
    
    def quit_butt(self):
        """Quit BUTT application"""
        success, message = self.send_command(['-q'], command_type='quit_butt')
        if success:
            self.cache.invalidate()  # Clear all cache when quitting
        return success, message
    
    def get_detailed_status(self, use_cache=True):
        """
        Get detailed status by parsing BUTT's status output.
        Returns dict with streaming and recording states.
        WITH CACHING to avoid rate limiting
        """
        # Check cache first
        if use_cache:
            cached_status = self.cache.get('detailed_status')
            if cached_status is not None:
                return cached_status
        
        success, msg = self.send_command(['-S'], command_type='status')
        
        status = {
            'streaming': False,
            'recording': False,
            'connected': False,
            'connecting': False,
            'signal_present': False,
            'raw_message': msg if success else None,
            'command_success': success,
            'cached': False
        }
        
        if not success or not msg:
            # Cache even failed requests briefly to avoid hammering
            if use_cache:
                self.cache.set('detailed_status', status)
            return status
        
        # Clean up the message
        msg_clean = msg.strip()
        print(f"[BUTT] Status message: '{msg_clean}'")
        
        # Parse the key:value format from BUTT
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
        
        # Check connecting status first (before connected)
        if 'connecting' in status_dict:
            status['connecting'] = status_dict['connecting'] == '1'
        
        # Check streaming status
        if 'connected' in status_dict:
            status['connected'] = status_dict['connected'] == '1'
            # Only mark as streaming if connected and not in connecting state
            status['streaming'] = status_dict['connected'] == '1' and not status['connecting']
        
        # Check recording status
        if 'recording' in status_dict:
            status['recording'] = status_dict['recording'] == '1'
        
        # Check signal present
        if 'signal present' in status_dict:
            status['signal_present'] = status_dict['signal present'] == '1'
        
        print(f"[BUTT] Parsed - Streaming: {status['streaming']}, Connecting: {status['connecting']}, Recording: {status['recording']}")
        
        # Cache the result
        if use_cache:
            self.cache.set('detailed_status', status)
        
        return status

# Create global controller instance
controller = BUTTController()

# API Routes
@app.route('/', methods=['GET'])
def home():
    """Welcome endpoint"""
    return jsonify({
        'name': 'BUTT Controller Bridge',
        'version': '2.1',
        'platform': platform.system(),
        'cache_enabled': True,
        'cache_ttl': STATUS_CACHE_DURATION,
        'command_throttle': COMMAND_MIN_INTERVAL,
        'endpoints': {
            'status': '/api/status',
            'start_butt': '/api/butt/start',
            'quit_butt': '/api/butt/quit',
            'start_stream': '/api/stream/start',
            'stop_stream': '/api/stream/stop',
            'start_record': '/api/record/start',
            'stop_record': '/api/record/stop',
            'split_record': '/api/record/split',
            'update_song': '/api/song/update',
            'cache_clear': '/api/cache/clear'
        }
    })

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    """Get current status of BUTT (with caching)"""
    if request.method == 'OPTIONS':
        return '', 204
    
    # Check for force refresh parameter
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    use_cache = not force_refresh
    
    is_running = controller.is_butt_running(use_cache=use_cache)
    
    status_info = {
        'butt_running': is_running,
        'butt_executable': controller.butt_executable,
        'butt_found': os.path.exists(controller.butt_executable),
        'streaming': False,
        'recording': False,
        'platform': platform.system(),
        'cached': False,
        'capabilities': {
            'streaming': True,
            'recording': True,
            'split_recording': True,
            'control_method': 'command_line',
            'platform': platform.system().lower(),
            'cache_enabled': True
        }
    }
    
    if is_running:
        detailed_status = controller.get_detailed_status(use_cache=use_cache)
        status_info.update({
            'streaming': detailed_status['streaming'],
            'recording': detailed_status['recording'],
            'connected': detailed_status['connected'],
            'connecting': detailed_status['connecting'],
            'signal_present': detailed_status['signal_present'],
            'status_message': detailed_status['raw_message'],
            'command_success': detailed_status['command_success'],
            'cached': detailed_status.get('cached', False)
        })
    
    return jsonify(status_info)

@app.route('/api/cache/clear', methods=['POST', 'OPTIONS'])
def clear_cache():
    """Manually clear the status cache"""
    if request.method == 'OPTIONS':
        return '', 204
    
    controller.cache.invalidate()
    return jsonify({
        'success': True,
        'message': 'Cache cleared successfully'
    })

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
    
    if not controller.is_butt_running(use_cache=False):
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
    print(f"CACHING ENABLED:")
    print(f"  - Status cache TTL: {STATUS_CACHE_DURATION}s")
    print(f"  - Command throttle: {COMMAND_MIN_INTERVAL}s")
    print(f"  - Add ?refresh=true to /api/status to bypass cache")
    print(f"  - POST /api/cache/clear to manually clear cache")
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