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
import requests
import threading

# === Path Adaptation ===
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from infrastructure.wallet import IdentityWallet

CONFIG_PATH = os.path.join(project_root, "config", "network_config.json")

def get_did_by_role(role_name):
    """
    Calculate DID directly using local keys
    """
    try:
        wallet = IdentityWallet(role_name)
        return wallet.did
    except Exception as e:
        print(f"[Warning] Unable to calculate DID for role {role_name}: {e}")
        return None

def trigger_single_audit(verifier_name, verifier_port, target_holder_name, target_did):
    """
    Execution function for a single audit task
    """
    url = f"http://localhost:{verifier_port}/control/start_audit"
    payload = {
        "target_holder_did": target_did
    }
    
    print(f"{verifier_name} (Port {verifier_port}) ->  {target_holder_name} ({target_did[:8]}...)")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            res_json = response.json()
            status = res_json.get("status", "Unknown")
            print(f"✅ [{verifier_name}] Response: {status}")
        else:
            print(f"❌ [{verifier_name}] HTTP Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ [{verifier_name}] Request failed: {e}")

def main():
    print("="*60)
    print(" 2v2 Demo Scenario: Automatically trigger multi-role verification flow")
    print("="*60)

    # 1. Read configuration file
    if not os.path.exists(CONFIG_PATH):
        print(f"[Error] Config file not found: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. Pre-calculate Holder information mapping table
    # Structure: { "http://localhost:5000": {"did": "did:ethr:...", "name": "Holder-A"} }
    holder_map = {}
    
    print("[1/3] Parsing Holder identities...")
    for h in config["holders"]:
        port = h["port"]
        role = h["role"]
        name = h["name"]
        
        # Automatically calculate DID
        did = get_did_by_role(role)
        if not did:
            print(f"Unable to obtain DID for {name}, aborting.")
            return
            
        # Establish mapping key: Target URL (configured as http://localhost:PORT in Verifier config)
        key_url = f"http://localhost:{port}"
        holder_map[key_url] = {
            "did": did,
            "name": name
        }
        print(f"   -> {name} ({port}) = {did}")

    # 3. Prepare concurrent tasks
    print("\n[2/3] Matching Verifier targets...")
    threads = []
    
    for v in config["verifiers"]:
        v_name = v["name"]
        v_port = v["port"]
        target_url = v["target_url"] # E.g. http://localhost:5000
        
        # Automatic matching
        target_info = holder_map.get(target_url)
        
        if not target_info:
            print(f"   ⚠️  Skipping {v_name}: Its target {target_url} cannot be found in holders configuration.")
            continue
            
        target_did = target_info["did"]
        target_holder_name = target_info["name"]
        
        # Create thread
        t = threading.Thread(
            target=trigger_single_audit,
            args=(v_name, v_port, target_holder_name, target_did)
        )
        threads.append(t)

    # 4. Concurrent execution
    if not threads:
        print("[Error] No executable tasks.")
        return

    print(f"\n[3/3] Triggering {len(threads)} verification flows simultaneously...\n")
    
    # Start all threads
    for t in threads:
        t.start()
        
    # Wait for all threads to finish
    for t in threads:
        t.join()
        
    print("\n" + "="*60)
    print("All trigger commands sent. Please check individual terminal windows for detailed logs.")

if __name__ == "__main__":
    main()