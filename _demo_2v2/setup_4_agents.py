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

import time
import json
from web3 import Web3
from infrastructure.utils import REGISTRY_ADDRESS, REGISTRY_ABI

# === 1. Experiment Parameters & Config ===
AGENT_NAMES = ["agent_a", "agent_b", "agent_c", "agent_d"]
FUND_AMOUNT = 0.005                 # Amount to transfer to each Admin (ETH)
FUNDER_ACCOUNT_KEY = "master"       # Master account in key.json used for funding

# --- Output File Paths ---
# Script is in _demo_2v2 folder, output is in ../config folder
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config'))
KEY_OUTPUT_FILE = os.path.join(CONFIG_DIR, "agents_4_key.json")

# 1. Read config/key.json (Get Master funds and Issuer identity)
source_key_file = os.path.join(CONFIG_DIR, 'key.json')
with open(source_key_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 2. Manually establish Web3 connection
# Prefer url from key.json, otherwise use default
node_url = config.get("api_url", "https://ethereum-sepolia.publicnode.com")
w3 = Web3(Web3.HTTPProvider(node_url))

def generate_accounts(names):
    """Generate named key pairs (Admin + Op)"""
    print(f"\n[Step 1] Generating {len(names)} sets of Agent accounts...")
    agents = []
    for name in names:
        # Use extra_entropy to increase randomness
        admin_acct = w3.eth.account.create(extra_entropy=f"{name}_admin_{time.time()}")
        op_acct = w3.eth.account.create(extra_entropy=f"{name}_op_{time.time()}")
        
        agents.append({
            "name": name, # e.g., agent_a
            "admin": {"address": admin_acct.address, "private_key": admin_acct.key.hex()},
            "op": {"address": op_acct.address, "private_key": op_acct.key.hex()}
        })
        print(f"    Generated: {name}_admin / {name}_op")
    print(f"    Generation complete.")
    return agents

def fund_accounts(agents, funder_info):
    """Master account batch transfers ETH to Agent Admin accounts"""
    funder_addr = funder_info["address"]
    funder_pk = funder_info["private_key"]
    
    print(f"\n[Step 2] Master account {funder_addr} is distributing ETH...")
    
    # Get initial Nonce of the master account
    start_nonce = w3.eth.get_transaction_count(funder_addr, 'pending')
    
    tx_hashes = []
    
    for i, agent in enumerate(agents):
        target_address = agent["admin"]["address"]
        
        tx = {
            'nonce': start_nonce + i, # Key: Manually increment Nonce for concurrent broadcasting
            'to': target_address,
            'value': w3.to_wei(FUND_AMOUNT, 'ether'),
            'gas': 21000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'chainId': 11155111
        }
        
        signed_tx = w3.eth.account.sign_transaction(tx, funder_pk)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hashes.append(tx_hash)
        print(f"    -> Transferring to {agent['name']} Admin: {target_address[:6]}... (TxHash={w3.to_hex(tx_hash)})")
    
    print("    Waiting for transfer confirmations...")
    for tx_hash in tx_hashes:
        w3.eth.wait_for_transaction_receipt(tx_hash)
    print("    All accounts funded!")

def register_dids(agents):
    """Implicitly register DID via 0 ETH self-transfer"""
    print(f"\n[Step 3] Agents are implicitly registering DIDs (Self-transfer 0 ETH)...")
    for agent in agents:
        admin_addr, admin_pk = agent["admin"]["address"], agent["admin"]["private_key"]
        
        try:
            nonce = w3.eth.get_transaction_count(admin_addr, 'pending')
            
            # === Construct 0 ETH self-transfer transaction ===
            tx = {
                'nonce': nonce,
                'to': admin_addr,        # To self
                'value': 0,              # Amount 0
                'gas': 100000,           # Gas Limit
                'gasPrice': w3.eth.gas_price,
                'chainId': 11155111
            }
            
            signed_tx = w3.eth.account.sign_transaction(tx, admin_pk)
            
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            print(f"    {agent['name']} implicit registration successful")

        except Exception as e:
            print(f"    {agent['name']} registration failed: {e}")
            
    print("    DID registration complete.")

def add_delegates(agents):
    """Add Delegate (Op Key)"""
    print(f"\n[Step 4] Adding Delegate (Op Key)...")
    contract = w3.eth.contract(address=REGISTRY_ADDRESS, abi=REGISTRY_ABI)
    validity = 365 * 24 * 60 * 60
    key_name_bytes = "did/pub/Secp256k1/sigAuth/hex".encode('utf-8').ljust(32, b'\0')

    for agent in agents:
        admin_addr, admin_pk = agent["admin"]["address"], agent["admin"]["private_key"]
        op_addr = agent["op"]["address"]
        value_bytes = bytes.fromhex(op_addr[2:])

        try:
            nonce = w3.eth.get_transaction_count(admin_addr, 'pending')
            tx_func = contract.functions.setAttribute(admin_addr, key_name_bytes, value_bytes, validity)
            tx = tx_func.build_transaction({
                'chainId': 11155111, 'gas': 200000,
                'gasPrice': w3.eth.gas_price, 'nonce': nonce
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, admin_pk)

            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            print(f"    {agent['name']} OP authorization successful")

        except Exception as e:
            print(f"    {agent['name']} authorization failed: {e}")

    print("    Delegate addition complete.")

def save_keys_to_file(agents):
    """
    Save key info to config/agents_4_key.json
    """
    print(f"\n[Step 5] Saving account keys to {KEY_OUTPUT_FILE} ...")
    
    # 1. Construct fixed header info as required
    output_data = {
        "api_url": config.get("api_url", "https://ethereum-sepolia.publicnode.com"),
        "api_url_pool": config.get("api_url_pool", []),
        "qwq_api_key": config.get("qwq_api_key", ""),
        "accounts": {}
    }
    # Read issuer info from original config (key.json)
    # Note: config is the global variable loaded via get_w3() at script start
    if "issuer" in config["accounts"]:
        output_data["accounts"]["issuer"] = config["accounts"]["issuer"]
    else:
        print("    [Warning] 'issuer' account info not found in key.json")

    # 2. Write agents list into accounts dictionary sequentially
    for agent in agents:
        name = agent['name']
        
        # Add Admin account: agent_x_admin
        output_data["accounts"][f"{name}_admin"] = {
            "address": agent["admin"]["address"],
            "private_key": agent["admin"]["private_key"]
        }
        
        # Add Op account: agent_x_op
        output_data["accounts"][f"{name}_op"] = {
            "address": agent["op"]["address"],
            "private_key": agent["op"]["private_key"]
        }

    # 3. Ensure target directory exists
    os.makedirs(os.path.dirname(KEY_OUTPUT_FILE), exist_ok=True)

    # 4. Write to file
    with open(KEY_OUTPUT_FILE, "w", encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    print(f"    Save successful!")

def main():
    funder_info = config["accounts"].get(FUNDER_ACCOUNT_KEY)
    if not funder_info:
        print(f"Error: Master account '{FUNDER_ACCOUNT_KEY}' not found in key.json")
        return
    
    try:
        agents = generate_accounts(AGENT_NAMES)
        
        fund_accounts(agents, funder_info)
        time.sleep(2)
        
        register_dids(agents)
        time.sleep(2)
        
        add_delegates(agents)
        
        save_keys_to_file(agents)
        
        print("\n=== All operations completed ===")
        
    except Exception as e:
        print(f"\n[Error] An error occurred during script execution: {e}")
        if 'agents' in locals():
            print("Attempting to save generated account info...")
            save_keys_to_file(agents)

if __name__ == "__main__":
    main()