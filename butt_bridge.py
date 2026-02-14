"""
Flask Bridge for BUTT (Broadcast Using This Tool) Control
Provides REST API to control streaming and recording functions
Corrected version using command-line interface with proper CORS configuration
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import subprocess
import os
import time
import psutil
import sys

app = Flask(__name__)

# Configure CORS to allow requests from your production domain
# Add your production domain(s) to the origins list
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
BUTT_EXECUTABLE = "butt"  # or full path like /usr/bin/butt
BUTT_CONFIG = os.path.expanduser("~/.buttrc")  # Default BUTT config location
BUTT_COMMAND_PORT = 1256

class BUTTController:
    def __init__(self):
        self.process = None
        self.butt_executable = BUTT_EXECUTABLE
        self.command_port = BUTT_COMMAND_PORT
    
    def is_butt_running(self):
        """Check if BUTT process is running"""
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if 'butt' in proc.info['name'].lower():
                    self.process = proc
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False
    
    def start_butt(self):
        """Start BUTT application with command server enabled as a detached process"""
        try:
            if not self.is_butt_running():
                # Start BUTT as a detached process
                if sys.platform == 'win32':
                    # Windows: Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS flags
                    DETACHED_PROCESS = 0x00000008
                    subprocess.Popen(
                        [self.butt_executable, '-p', str(self.command_port)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        creationflags=DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                        close_fds=True
                    )
                else:
                    # Unix/Linux/Mac: Use start_new_session
                    subprocess.Popen(
                        [self.butt_executable, '-p', str(self.command_port)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        start_new_session=True,
                        close_fds=True
                    )
                
                time.sleep(3)  # Wait for BUTT to initialize
                return self.is_butt_running()
            return True
        except FileNotFoundError:
            print(f"Error: BUTT executable not found at '{self.butt_executable}'")
            return False
        except Exception as e:
            print(f"Error starting BUTT: {e}")
            return False
    
    def send_command(self, command_args):
        """
        Send command to running BUTT instance via command-line interface
        
        Args:
            command_args: List of command arguments (e.g., ['-s'] for start streaming)
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Build command to control running BUTT instance
            cmd = [
                self.butt_executable,
                '-a', '127.0.0.1',  # Address of BUTT instance
                '-p', str(self.command_port)  # Port of BUTT instance
            ] + command_args
            
            print(f"[BUTT] Executing command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            print(f"[BUTT] Return code: {result.returncode}")
            print(f"[BUTT] Stdout: '{result.stdout}'")
            print(f"[BUTT] Stderr: '{result.stderr}'")
            
            # Check if command was successful
            if result.returncode == 0:
                return True, result.stdout.strip() or "Command executed successfully"
            else:
                error_msg = result.stderr.strip() or "Command failed"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, f"BUTT executable not found: {self.butt_executable}"
        except Exception as e:
            return False, f"Error executing command: {str(e)}"
    
    def get_detailed_status(self):
        """
        Get detailed status by parsing BUTT's status output.
        Returns dict with streaming and recording states.
        """
        success, msg = self.send_command(['-S'])
        
        status = {
            'streaming': False,
            'recording': False,
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
        # connecting: 1 means streaming is active
        # connecting: 0 means not streaming
        if 'connected' in status_dict:
            status['streaming'] = status_dict['connected'] == '1'

        # Check recording status
        # recording: 1 means recording is active
        # recording: 0 means not recording
        if 'recording' in status_dict:
            status['recording'] = status_dict['recording'] == '1'
        
        print(f"[BUTT] Parsed - Streaming: {status['streaming']}, Recording: {status['recording']}")
        
        return status
    
    def get_status(self):
        """Request status from BUTT - returns raw output"""
        return self.send_command(['-S'])
    
    def start_streaming(self):
        """Start streaming to default server"""
        return self.send_command(['-s'])
    
    def stop_streaming(self):
        """Disconnect from streaming server"""
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
        """Update song name metadata"""
        return self.send_command(['-u', song_name])
    
    def quit_butt(self):
        """Quit BUTT application"""
        return self.send_command(['-q'])

controller = BUTTController()

@app.route('/')
def index():
    """Serve the control interface"""
    return jsonify({
        'status': 'BUTT Bridge API Server',
        'version': '1.0',
        'endpoints': {
            'status': '/api/status',
            'debug': '/api/debug/butt-status',
            'butt_start': '/api/butt/start',
            'butt_quit': '/api/butt/quit',
            'stream_start': '/api/stream/start',
            'stream_stop': '/api/stream/stop',
            'record_start': '/api/record/start',
            'record_stop': '/api/record/stop',
            'record_split': '/api/record/split',
            'song_update': '/api/song/update'
        }
    })

@app.route('/api/debug/butt-status', methods=['GET'])
def debug_butt_status():
    """Debug endpoint to see raw BUTT status output"""
    if not controller.is_butt_running():
        return jsonify({
            'running': False,
            'message': 'BUTT is not running'
        })
    
    success, status_msg = controller.get_status()
    return jsonify({
        'running': True,
        'command_success': success,
        'raw_output': status_msg,
        'raw_output_repr': repr(status_msg),
        'raw_output_bytes': [ord(c) for c in status_msg[:50]] if status_msg else [],
        'lowercase': status_msg.lower() if status_msg else '',
        'stripped': status_msg.strip() if status_msg else ''
    })

@app.route('/api/status', methods=['GET', 'OPTIONS'])
def get_status():
    """Get current status of BUTT"""
    if request.method == 'OPTIONS':
        return '', 204
    
    is_running = controller.is_butt_running()
    
    status_info = {
        'butt_running': is_running,
        'streaming': False,
        'recording': False,
        'capabilities': {
            'streaming': True,
            'recording': True,
            'split_recording': True,
            'control_method': 'command_line'
        }
    }
    
    if is_running:
        # Get detailed status by parsing BUTT's output
        detailed_status = controller.get_detailed_status()
        
        status_info['streaming'] = detailed_status['streaming']
        status_info['recording'] = detailed_status['recording']
        status_info['status_message'] = detailed_status['raw_message']
        status_info['command_success'] = detailed_status['command_success']
    
    return jsonify(status_info)

@app.route('/api/butt/start', methods=['POST', 'OPTIONS'])
def start_butt():
    """Start BUTT application"""
    if request.method == 'OPTIONS':
        return '', 204
    
    success = controller.start_butt()
    return jsonify({
        'success': success,
        'message': 'BUTT started successfully' if success else 'Failed to start BUTT. Make sure it is installed.'
    })

@app.route('/api/butt/quit', methods=['POST', 'OPTIONS'])
def quit_butt():
    """Quit BUTT application"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.quit_butt()
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/stream/start', methods=['POST', 'OPTIONS'])
def start_stream():
    """Start streaming"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.start_streaming()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/stream/stop', methods=['POST', 'OPTIONS'])
def stop_stream():
    """Stop streaming"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.stop_streaming()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/record/start', methods=['POST', 'OPTIONS'])
def start_record():
    """Start recording"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.start_recording()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/record/stop', methods=['POST', 'OPTIONS'])
def stop_record():
    """Stop recording"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.stop_recording()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/record/split', methods=['POST', 'OPTIONS'])
def split_record():
    """Split current recording"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.split_recording()
    
    return jsonify({
        'success': success,
        'message': message
    })

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
    
    return jsonify({
        'success': success,
        'message': message
    })

if __name__ == '__main__':
    print("=" * 60)
    print("BUTT Controller Bridge Starting...")
    print("=" * 60)
    print(f"Server running on: http://0.0.0.0:5000")
    print(f"Access via localhost: http://localhost:5000")
    print(f"Access via network: http://<your-ip>:5000")
    print(f"API endpoints available at /api/*")
    print(f"BUTT executable: {BUTT_EXECUTABLE}")
    print(f"Command port: {BUTT_COMMAND_PORT}")
    print("=" * 60)
    print("\nCORS Configuration:")
    print("- Allowing ALL origins (safe for local development)")
    print("- Credentials: NOT required")
    print("- This allows cross-network requests")
    print("=" * 60)
    print("\nMake sure BUTT is installed and accessible in your PATH")
    print("On Ubuntu/Debian: sudo apt-get install butt")
    print("On macOS: Download from https://danielnoethen.de/butt")
    print("=" * 60)
    print("\nIMPORTANT: If your Vue app is on a different machine or IP,")
    print("make sure to access this server using the same network IP")
    print("that your Vue app uses (not localhost).")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)