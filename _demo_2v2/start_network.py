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

def start_network():
    # 1. Read configuration
    json_path = os.path.join(project_root, 'config', 'network_config.json')

    try:
        with open(json_path, "r", encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {json_path}")
        return

    processes = []

    print("="*60)
    print("Initializing Decentralized Network Simulation")
    print("="*60)

    # 2. Start all Holders
    for h in config["holders"]:
        print(f"Starting [Holder] {h['name']} ({h['role']}) on port {h['port']}...")
        
        # Construct command: python agents/holder/runtime.py <port> <role>
        cmd = [
            sys.executable, 
            "agents/holder/runtime.py", 
            str(h["port"]), 
            h["role"]
        ]
        
        p = subprocess.Popen(cmd)
        processes.append(p)

    # Wait a few seconds to ensure Holders are fully started
    time.sleep(2) 

    # 3. Start all Verifiers
    for v in config["verifiers"]:
        print(f"Starting [Verifier] {v['name']} ({v['role']}) on port {v['port']} -> target {v['target_url']}...")
        
        # Construct command: python _demo_2v2/demo_verifier_server.py <port> <role> <target>
        cmd = [
            sys.executable, 
            "_demo_2v2/demo_verifier_server.py", 
            str(v["port"]), 
            v["role"],
            v["target_url"]
        ]
        
        p = subprocess.Popen(cmd)
        processes.append(p)

    print("\n✅ Network is running! (Press Ctrl+C in this terminal to stop all nodes)")
    
    try:
        # Keep main script running until user presses Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down network...")
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    start_network()