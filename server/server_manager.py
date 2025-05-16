"""
Server Manager Module

This module provides a simple way to start both the extension API and dashboard API servers.
It can run them in separate processes, allowing both to run concurrently.
"""

import os
import sys
import argparse
import subprocess
import signal
import time
import logging
import socket
from contextlib import closing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("server_manager")

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

def is_port_in_use(port):
    """Check if a port is in use by attempting to bind to it."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port."""
    for port_offset in range(max_attempts):
        port = start_port + port_offset
        if not is_port_in_use(port):
            return port
    
    # If no port is found after max_attempts, return None
    return None

def kill_existing_server(port):
    """
    Attempt to kill any existing server process running on the specified port.
    
    Args:
        port: The port number to check
        
    Returns:
        bool: True if a process was killed, False otherwise
    """
    try:
        # This works on macOS and Linux, might need adjustment for other platforms
        if sys.platform == 'win32':
            # Windows command
            try:
                output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
                if output:
                    # Parse the PID from the output
                    lines = output.strip().split('\n')
                    for line in lines:
                        if f':{port}' in line and 'LISTENING' in line:
                            parts = line.strip().split()
                            pid = parts[-1]
                            try:
                                subprocess.call(f'taskkill /F /PID {pid}', shell=True)
                                logger.info(f"Killed existing process (PID: {pid}) on port {port}")
                                time.sleep(1)  # Wait for port to be released
                                return True
                            except Exception as e:
                                logger.error(f"Failed to kill process on port {port}: {e}")
                                return False
            except subprocess.CalledProcessError:
                # No processes found on that port
                return False
        else:
            # macOS/Linux command - simpler and more robust approach
            try:
                # First attempt with lsof
                cmd = f"lsof -i :{port} | grep LISTEN"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE).decode().strip()
                if output:
                    # Extract PIDs
                    pids = []
                    for line in output.split('\n'):
                        parts = line.split()
                        if len(parts) > 1:
                            pids.append(parts[1])
                    
                    # Kill all PIDs found
                    for pid in pids:
                        try:
                            logger.info(f"Attempting to kill process {pid} on port {port}")
                            os.kill(int(pid), signal.SIGTERM)
                            logger.info(f"Killed process (PID: {pid}) on port {port}")
                        except Exception as e:
                            logger.warning(f"Failed to kill PID {pid}: {e}")
                    
                    # Give it a moment to release the port
                    time.sleep(1)
                    
                    # Check if port is still in use
                    if not is_port_in_use(port):
                        return True
                    else:
                        # Try a more forceful approach
                        logger.warning(f"Port {port} still in use after SIGTERM, trying SIGKILL...")
                        for pid in pids:
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                            except:
                                pass
                        time.sleep(1)
                        return not is_port_in_use(port)
            except subprocess.CalledProcessError:
                # Try alternative method if lsof doesn't work
                try:
                    cmd = f"fuser -n tcp {port} 2>/dev/null"
                    output = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE).decode().strip()
                    if output:
                        # Kill process
                        kill_cmd = f"fuser -k -n tcp {port}"
                        subprocess.call(kill_cmd, shell=True)
                        logger.info(f"Killed process on port {port} using fuser")
                        time.sleep(1)
                        return not is_port_in_use(port)
                except subprocess.CalledProcessError:
                    # Both methods failed
                    return False
    except Exception as e:
        logger.error(f"Error checking for existing processes: {e}")
    
    return False

def start_server(server_type):
    """
    Start the specified server type.
    
    Args:
        server_type: Either 'extension', 'dashboard', or 'both'
    """
    # Always clean up existing servers first
    logger.info("Checking for existing server processes...")
    
    # Try to kill any existing processes on the default ports
    default_extension_port = 8000
    default_dashboard_port = 8001
    
    # Attempt to kill any servers on default ports
    killed_extension = kill_existing_server(default_extension_port)
    killed_dashboard = kill_existing_server(default_dashboard_port)
    
    if killed_extension or killed_dashboard:
        # Wait for ports to be released if any servers were killed
        logger.info("Waiting for ports to be released...")
        time.sleep(2)
    
    extension_process = None
    dashboard_process = None
    
    try:
        # Determine which server(s) to start
        if server_type in ['extension', 'both']:
            # Make sure the default port is free
            if is_port_in_use(default_extension_port):
                logger.error(f"Port {default_extension_port} is still in use despite cleanup attempt!")
                logger.error("Please manually kill the process using this port and try again.")
                sys.exit(1)
                
            logger.info(f"Starting Extension API server on port {default_extension_port}...")
            extension_cmd = [
                sys.executable, "-m", "uvicorn", 
                "server.extension_api:app", 
                "--reload", "--host", "0.0.0.0", "--port", str(default_extension_port),
                "--log-level", "info"
            ]
            logger.info(f"Running command: {' '.join(extension_cmd)}")
            extension_process = subprocess.Popen(extension_cmd)
            logger.info(f"Extension API server started with PID: {extension_process.pid}")
        
        if server_type in ['dashboard', 'both']:
            # Make sure the default port is free
            if is_port_in_use(default_dashboard_port):
                logger.error(f"Port {default_dashboard_port} is still in use despite cleanup attempt!")
                logger.error("Please manually kill the process using this port and try again.")
                # Clean up extension process if it was started
                if extension_process:
                    extension_process.terminate()
                sys.exit(1)
                
            logger.info(f"Starting Dashboard API server on port {default_dashboard_port}...")
            dashboard_cmd = [
                sys.executable, "-m", "uvicorn", 
                "server.dashboard_api:app", 
                "--reload", "--host", "0.0.0.0", "--port", str(default_dashboard_port),
                "--log-level", "info"
            ]
            logger.info(f"Running command: {' '.join(dashboard_cmd)}")
            dashboard_process = subprocess.Popen(dashboard_cmd)
            logger.info(f"Dashboard API server started with PID: {dashboard_process.pid}")
        
        # Set up signal handling for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("\nShutting down servers...")
            if extension_process:
                logger.info(f"Terminating Extension API server (PID: {extension_process.pid})")
                extension_process.terminate()
            if dashboard_process:
                logger.info(f"Terminating Dashboard API server (PID: {dashboard_process.pid})")
                dashboard_process.terminate()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # Wait for processes
        logger.info("Servers are running. Press Ctrl+C to stop.")
        if server_type in ['extension', 'both']:
            logger.info(f"Extension API: http://localhost:{default_extension_port}")
        if server_type in ['dashboard', 'both']:
            logger.info(f"Dashboard API: http://localhost:{default_dashboard_port}")
        
        while True:
            # Check if processes are still running
            if extension_process and extension_process.poll() is not None:
                logger.error(f"Extension API server exited with code: {extension_process.returncode}")
                extension_process = None
            
            if dashboard_process and dashboard_process.poll() is not None:
                logger.error(f"Dashboard API server exited with code: {dashboard_process.returncode}")
                dashboard_process = None
            
            # If both processes have exited, exit the manager
            if server_type == 'both' and extension_process is None and dashboard_process is None:
                logger.error("Both servers have exited. Shutting down.")
                break
            elif server_type == 'extension' and extension_process is None:
                logger.error("Extension API server has exited. Shutting down.")
                break
            elif server_type == 'dashboard' and dashboard_process is None:
                logger.error("Dashboard API server has exited. Shutting down.")
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\nShutting down servers...")
        if extension_process:
            logger.info(f"Terminating Extension API server (PID: {extension_process.pid})")
            extension_process.terminate()
        if dashboard_process:
            logger.info(f"Terminating Dashboard API server (PID: {dashboard_process.pid})")
            dashboard_process.terminate()
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if extension_process:
            logger.info(f"Terminating Extension API server (PID: {extension_process.pid})")
            extension_process.terminate()
        if dashboard_process:
            logger.info(f"Terminating Dashboard API server (PID: {dashboard_process.pid})")
            dashboard_process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the News Bias Analyzer servers")
    parser.add_argument(
        "--type", 
        choices=["extension", "dashboard", "both"],
        default="both",
        help="Which server to start (default: both)"
    )
    
    args = parser.parse_args()
    
    # Start the servers (cleanup is now built into the start_server function)
    start_server(args.type)