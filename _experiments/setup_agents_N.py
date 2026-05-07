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
# Create data directory (if not exists)
DATA_DIR = os.path.join(project_root, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

import time
import json
import csv
from web3 import Web3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infrastructure.utils import get_w3, REGISTRY_ADDRESS, REGISTRY_ABI

# === 1. Experiment Parameters & Config ===
# --- Adjustable Parameters ---
NUM_VERIFIERS = 100                 # Number of accounts to generate
START_INDEX = 1                     # Starting index (generates START_INDEX to START_INDEX+NUM_VERIFIERS-1)
FUND_AMOUNT = 0.005                 # Amount to transfer to each Admin (ETH)
FUNDER_ACCOUNT_KEY = "master"       # Master account in key.json used for funding
# --- Output Files ---
KEY_OUTPUT_FILE = os.path.join(DATA_DIR, "verifiers_key.json")
CSV_REPORT_FILE = os.path.join(DATA_DIR, "setup_verifiers.csv")
# --- Cost Estimation Constants ---
FIXED_MAINNET_GAS_GWEI = 4.88       # Annual average Gwei
ETH_PRICE_USD = 3121.34             # Annual average USD

# Initialize connection (Load original config)
w3, config = get_w3()


def generate_accounts(num):
    """Generate specified number of key pairs (Admin + Op)"""
    print(f"\n[Step 1] Generating {num} sets of Verifier accounts (index {START_INDEX} to {START_INDEX + num - 1})...")
    verifiers = []
    for i in range(START_INDEX, START_INDEX + num):
        # Use extra_entropy to increase randomness
        admin_acct = w3.eth.account.create(extra_entropy=f"admin_{i}_{time.time()}")
        op_acct = w3.eth.account.create(extra_entropy=f"op_{i}_{time.time()}")
        
        verifiers.append({
            "id": i, 
            "name": f"verifier_{i}",
            "admin": {"address": admin_acct.address, "private_key": admin_acct.key.hex()},
            "op": {"address": op_acct.address, "private_key": op_acct.key.hex()}
        })
    print(f"    Generation complete.")
    return verifiers

def fund_accounts(verifiers, funder_info):
    """Master account funds new accounts in batch"""
    funder_addr = funder_info["address"]
    funder_pk = funder_info["private_key"]
    
    print(f"\n[Step 2] Master account {funder_addr} is distributing ETH...")
    
    # Get initial Nonce of the master account
    start_nonce = w3.eth.get_transaction_count(funder_addr, 'pending')
    
    tx_hashes = []
    
    for i, v in enumerate(verifiers):
        target_address = v["admin"]["address"]
        
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
        print(f"    -> Transferring to Verifier {v['id']} Admin: {w3.to_hex(tx_hash)}")
    
    print("    Waiting for transfer confirmation...")
    for tx_hash in tx_hashes:
        w3.eth.wait_for_transaction_receipt(tx_hash)
    print("    All accounts funded!")

def register_dids_and_measure(verifiers):
    """Implicitly register DID via 0 ETH self-transfer and measure performance metrics."""
    print(f"\n[Step 3] Verifiers are implicitly registering (Self-transfer 0 ETH)...")
    results = []

    for v in verifiers:
        admin_addr, admin_pk = v["admin"]["address"], v["admin"]["private_key"]
        
        try:
            nonce = w3.eth.get_transaction_count(admin_addr, 'pending')
            
            tx = {
                'nonce': nonce,
                'to': admin_addr,        # To self
                'value': 0,              # Amount 0
                'gas': 100000,           # Gas Limit
                'gasPrice': w3.eth.gas_price,
                'chainId': 11155111
            }
            
            signed_tx = w3.eth.account.sign_transaction(tx, admin_pk)
            
            start_time = time.time()
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            end_time = time.time()
            
            # Calculate metrics
            latency = end_time - start_time
            gas_used = receipt['gasUsed']
            cost_eth = gas_used * FIXED_MAINNET_GAS_GWEI * (10**-9)
            cost_usd = cost_eth * ETH_PRICE_USD
            
            results.append({
                "id": v["id"],
                "latency": latency, "gas_used": gas_used, "cost_usd": cost_usd
            })
            print(f"    Verifier {v['id']} implicit registration successful (Time {latency:.2f}s, Gas: {gas_used})")

        except Exception as e:
            print(f"    Verifier {v['id']} registration failed: {e}")
            results.append({"id": v["id"], "latency": -1, "gas_used": -1, "cost_usd": -1})
            
    print("    Implicit DID registration complete.")
    return results

def add_delegates_and_measure(verifiers):
    """Add Delegate and measure performance metrics."""
    print(f"\n[Step 4] Adding Delegate and measuring...")
    results = []
    contract = w3.eth.contract(address=REGISTRY_ADDRESS, abi=REGISTRY_ABI)
    validity = 365 * 24 * 60 * 60
    key_name_bytes = "did/pub/Secp256k1/sigAuth/hex".encode('utf-8').ljust(32, b'\0')

    for v in verifiers:
        admin_addr, admin_pk = v["admin"]["address"], v["admin"]["private_key"]
        op_addr = v["op"]["address"]
        value_bytes = bytes.fromhex(op_addr[2:])

        try:
            nonce = w3.eth.get_transaction_count(admin_addr, 'pending')
            tx_func = contract.functions.setAttribute(admin_addr, key_name_bytes, value_bytes, validity)
            tx = tx_func.build_transaction({
                'chainId': 11155111, 'gas': 200000,
                'gasPrice': w3.eth.gas_price, 'nonce': nonce
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, admin_pk)

            start_time = time.time()
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            end_time = time.time()
            
            latency = end_time - start_time
            gas_used = receipt['gasUsed']
            cost_eth = gas_used * FIXED_MAINNET_GAS_GWEI * (10**-9)
            cost_usd = cost_eth * ETH_PRICE_USD

            results.append({
                "id": v["id"],
                "latency": latency, "gas_used": gas_used, "cost_usd": cost_usd
            })
            print(f"    Verifier {v['id']} authorization successful (Time: {latency:.2f}s, Gas: {gas_used})")

        except Exception as e:
            print(f"    Verifier {v['id']} authorization failed: {e}")
            results.append({"id": v["id"], "latency": -1, "gas_used": -1, "cost_usd": -1})

    print("    Delegate addition complete.")
    return results

def generate_report(reg_results, del_results):
    """Generate CSV report and print summary"""
    print(f"\n[Step 5] Generating experiment report...")

    # A. Merge data
    merged_data = []
    del_map = {res["id"]: res for res in del_results}
    for reg_res in reg_results:
        verifier_id = reg_res["id"]
        del_res = del_map.get(verifier_id, {})
        merged_data.append({
            "Verifier ID": verifier_id,
            "Register Latency (s)": reg_res.get("latency", -1),
            "Register Gas Used": reg_res.get("gas_used", -1),
            "Register Cost (USD)": reg_res.get("cost_usd", -1),
            "Delegate Latency (s)": del_res.get("latency", -1),
            "Delegate Gas Used": del_res.get("gas_used", -1),
            "Delegate Cost (USD)": del_res.get("cost_usd", -1),
        })

    # B. Write to CSV
    try:
        with open(CSV_REPORT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=merged_data[0].keys())
            writer.writeheader()
            writer.writerows(merged_data)
        print(f"    Detailed data saved to: {CSV_REPORT_FILE}")
    except Exception as e:
        print(f"    [Error] Failed to save CSV: {e}")

    # C. Calculate and print averages
    print("\n" + "="*80)
    print("=== Experiment Results Average Summary ===")
    
    valid_reg_results = [r for r in reg_results if r['latency'] != -1]
    valid_del_results = [r for r in del_results if r['latency'] != -1]
    
    if not valid_reg_results or not valid_del_results:
        print("Valid data insufficient, cannot calculate averages.")
        return
        
    avg_reg_latency = sum(r['latency'] for r in valid_reg_results) / len(valid_reg_results)
    avg_reg_gas = sum(r['gas_used'] for r in valid_reg_results) / len(valid_reg_results)
    avg_reg_cost = sum(r['cost_usd'] for r in valid_reg_results) / len(valid_reg_results)
    
    avg_del_latency = sum(r['latency'] for r in valid_del_results) / len(valid_del_results)
    avg_del_gas = sum(r['gas_used'] for r in valid_del_results) / len(valid_del_results)
    avg_del_cost = sum(r['cost_usd'] for r in valid_del_results) / len(valid_del_results)

    print(f"{'Metric':<25} | {'Register DID':<25} | {'Add Delegate'}")
    print("-" * 80)
    print(f"{'Avg. Latency (s)':<25} | {avg_reg_latency:<25.4f} | {avg_del_latency:.4f}")
    print(f"{'Avg. Gas Used':<25} | {avg_reg_gas:<25.0f} | {avg_del_gas:.0f}")
    print(f"{'Avg. Est. Cost (USD)':<25} | ${avg_reg_cost:<24.4f} | ${avg_del_cost:.4f}")
    print("="*80)

def save_keys_to_file(verifiers):
    """
    Save key info to file, format fully compatible with key.json structure
    (Includes api_url, qwq_api_key, accounts)
    """
    print(f"\n[Step 6] Saving account keys to {KEY_OUTPUT_FILE} ...")
    
    # 1. Inherit original global config
    output_data = {
        "api_url": config.get("api_url", "https://ethereum-sepolia.publicnode.com"),
        "qwq_api_key": config.get("qwq_api_key", ""),
        "accounts": {}
    }

    # 2. Flatten verifiers list into accounts dictionary
    for v in verifiers:
        # e.g. verifier_1
        base_name = f"verifier_{v['id']}"
        
        # Add Admin account
        # key: verifier_1_admin
        output_data["accounts"][f"{base_name}_admin"] = {
            "address": v["admin"]["address"],
            "private_key": v["admin"]["private_key"]
        }
        
        # Add Op account
        # key: verifier_1_op
        output_data["accounts"][f"{base_name}_op"] = {
            "address": v["op"]["address"],
            "private_key": v["op"]["private_key"]
        }

    # 3. Write to file
    with open(KEY_OUTPUT_FILE, "w", encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    print(f"    Save successful! File format adapted to key.json standard.")

def main():
    funder_info = config["accounts"].get(FUNDER_ACCOUNT_KEY)
    if not funder_info:
        print(f"Error: Master account '{FUNDER_ACCOUNT_KEY}' not found in key.json")
        return
    
    try:
        verifiers = generate_accounts(NUM_VERIFIERS)
        fund_accounts(verifiers, funder_info)
        time.sleep(3)
        
        registration_results = register_dids_and_measure(verifiers)
        time.sleep(3)
        delegation_results = add_delegates_and_measure(verifiers)

        generate_report(registration_results, delegation_results)

        # Save formatted keys
        save_keys_to_file(verifiers)
        
        print("\n=== All operations completed ===")
        
    except Exception as e:
        print(f"\n[Error] An error occurred during script execution: {e}")
        if 'verifiers' in locals():
            print("Attempting to save generated account info...")
            save_keys_to_file(verifiers)

if __name__ == "__main__":
    main()
