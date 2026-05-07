import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
while not os.path.exists(os.path.join(project_root, "infrastructure")):
    parent = os.path.dirname(project_root)
    if parent == project_root: break 
    project_root = parent
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import subprocess
import time
import signal
import atexit

# === Configuration ===
KEY_FILE = os.path.join(project_root, "data", "holders_key.json")
RUNTIME_SCRIPT = os.path.join(project_root, "agents", "holder", "runtime.py")
MAX_HOLDERS = 1

# Process list, for cleanup
processes = []

def cleanup_processes():
    """Clean up all child processes"""
    print(f"\n[Manager] Stopping {len(processes)} holder processes...")
    for p in processes:
        if p.poll() is None:  # If the process is still running
            p.terminate()
    print("[Manager] All processes stopped.")

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    cleanup_processes()
    sys.exit(0)

def main():
    # Register exit cleanup
    atexit.register(cleanup_processes)
    signal.signal(signal.SIGINT, signal_handler)

    print("="*60)
    print("MASSIVE P2P HOLDER LAUNCHER")
    print("="*60)

    # 1. Read key file
    if not os.path.exists(KEY_FILE):
        print(f"[Error] Key file not found: {KEY_FILE}")
        return

    with open(KEY_FILE, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    accounts = config_data.get("accounts", {})
    
    # 2. Filter holder_X_op roles and sort numerically
    holder_roles = [k for k in accounts.keys() if "_op" in k and "holder" in k]
    try:
        holder_roles.sort(key=lambda x: int(x.split('_')[1]))
    except:
        holder_roles.sort()

    # Force slice the first MAX_HOLDERS
    holder_roles = holder_roles[:MAX_HOLDERS] 

    total_holders = len(holder_roles)
    print(f"[Manager] Found {total_holders} holder accounts to launch.")

    # 3. Batch launch
    for i, role in enumerate(holder_roles):
        port = 5000 + i
        
        # Command format: python runtime.py <PORT> <ROLE> <KEY_FILE_PATH>
        cmd = [
            sys.executable, 
            RUNTIME_SCRIPT, 
            str(port), 
            role, 
            KEY_FILE  # Pass key file path to trigger custom loading logic in runtime.py
        ]
        
        # Start process (set stdout/stderr to DEVNULL to reduce noise, or keep for debugging)
        # Suggest redirecting to file or setting to DEVNULL, otherwise logs from 100 processes will freeze the terminal
        try:
            p = subprocess.Popen(
                cmd, 
                cwd=project_root,
                # stdout=subprocess.DEVNULL, 
                # stderr=subprocess.DEVNULL
            )
            processes.append(p)
            print(f"[{i+1}/{total_holders}] Started {role} on port {port} (PID: {p.pid})")
        except Exception as e:
            print(f"[Error] Failed to start {role}: {e}")

        # Pause slightly to avoid instant CPU spikes
        if (i + 1) % 10 == 0:
            time.sleep(1)

    print("="*60)
    print(f"[Manager] All {len(processes)} holders are running.")
    print("[Manager] Press Ctrl+C to stop all agents.")
    
    # 4. Keep main process alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
