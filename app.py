"""
Flask Bridge for BUTT (Broadcast Using This Tool) Control
Provides REST API to control streaming and recording functions
Corrected version using command-line interface
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import subprocess
import os
import time
import psutil

app = Flask(__name__)
CORS(app)

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
        """Start BUTT application with command server enabled"""
        try:
            if not self.is_butt_running():
                # Start BUTT with command server on default port
                subprocess.Popen(
                    [self.butt_executable, '-p', str(self.command_port)],
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
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
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
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
    
    def get_status(self):
        """Request status from BUTT"""
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
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current status of BUTT"""
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
        # Try to get status from BUTT
        success, status_msg = controller.get_status()
        if success and status_msg:
            # Parse status message to determine streaming/recording state
            # BUTT status format may vary, adjust parsing as needed
            status_lower = status_msg.lower()
            status_info['streaming'] = 'streaming' in status_lower or 'connected' in status_lower
            status_info['recording'] = 'recording' in status_lower
            status_info['status_message'] = status_msg
    
    return jsonify(status_info)

@app.route('/api/butt/start', methods=['POST'])
def start_butt():
    """Start BUTT application"""
    success = controller.start_butt()
    return jsonify({
        'success': success,
        'message': 'BUTT started successfully' if success else 'Failed to start BUTT. Make sure it is installed.'
    })

@app.route('/api/butt/quit', methods=['POST'])
def quit_butt():
    """Quit BUTT application"""
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.quit_butt()
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/stream/start', methods=['POST'])
def start_stream():
    """Start streaming"""
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.start_streaming()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/stream/stop', methods=['POST'])
def stop_stream():
    """Stop streaming"""
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.stop_streaming()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/record/start', methods=['POST'])
def start_record():
    """Start recording"""
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.start_recording()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/record/stop', methods=['POST'])
def stop_record():
    """Stop recording"""
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.stop_recording()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/record/split', methods=['POST'])
def split_record():
    """Split current recording"""
    if not controller.is_butt_running():
        return jsonify({'success': False, 'message': 'BUTT is not running'}), 400
    
    success, message = controller.split_recording()
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/song/update', methods=['POST'])
def update_song():
    """Update song name metadata"""
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
    print(f"Web interface: http://localhost:5000")
    print(f"API endpoints available at /api/*")
    print(f"BUTT executable: {BUTT_EXECUTABLE}")
    print(f"Command port: {BUTT_COMMAND_PORT}")
    print("=" * 60)
    print("\nMake sure BUTT is installed and accessible in your PATH")
    print("On Ubuntu/Debian: sudo apt-get install butt")
    print("On macOS: Download from https://danielnoethen.de/butt")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)