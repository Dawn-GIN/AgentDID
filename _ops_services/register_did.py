import sys
import os
import time
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
while not os.path.exists(os.path.join(project_root, "infrastructure")):
    parent = os.path.dirname(project_root)
    if parent == project_root: break 
    project_root = parent
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infrastructure.utils import get_w3

def register_did_implicit(role_name: str):
    """
    Complete implicit DID registration by sending a 0 ETH transaction to self.
    
    Args:
        role_name (str): Target role name defined in key.json.
    """
    print("="*50)
    print(f"===  Implicit DID Registration (Self-transfer 0 ETH): {role_name} ===")
    print("="*50)

    try:
        # 1. Initialize Web3 connection and configuration
        w3, config = get_w3()
        accounts = config.get("accounts", {})

        # 2. Check and retrieve account information
        if role_name not in accounts:
            print(f"[Error] Role '{role_name}' not found in key.json.")
            return

        account_info = accounts[role_name]
        address = account_info["address"]
        private_key = account_info["private_key"]
        print(f" Target Address: {address}")

        # 3. Check balance
        balance = w3.eth.get_balance(address)
        if balance == 0:
            print(f"[Error] Account balance is 0, cannot pay Gas fees. Please fund with Sepolia testnet ETH.")
            return

        # 4. Construct implicit registration transaction
        nonce = w3.eth.get_transaction_count(address, 'pending')
        
        tx = {
            'nonce': nonce,
            'to': address,           # To self
            'value': 0,              # Amount 0
            'gas': 21000,            # Gas Limit 
            'gasPrice': w3.eth.gas_price,
            'chainId': 11155111      # Sepolia Chain ID
        }

        # 5. Sign and send transaction
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        
        print("\n Sending implicit registration transaction to Sepolia network...")
        start_time = time.time()
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f" Transaction broadcasted, Hash: {w3.to_hex(tx_hash)}")
        print(" Waiting for transaction confirmation...")

        # 6. Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        end_time = time.time()
        
        # 7. Confirm result
        if receipt.status == 1:
            latency = end_time - start_time
            print("\n" + "-"*50)
            print(f" Success! DID '{role_name}' registered implicitly.")
            print(f"   Block Number: {receipt.blockNumber}")
            print(f"   Gas Used: {receipt.gasUsed}")
            print(f"   Latency: {latency:.2f}s")
            print("-" * 50)
        else:
            print(f"\n[Failure] Transaction execution failed, check block explorer for details: {w3.to_hex(tx_hash)}")

    except Exception as e:
        print(f"\n[Error] Script execution exception: {e}")

if __name__ == "__main__":
    # Receive arguments from command line, e.g.: python _ops_services/register_did.py agent_a_admin
    if len(sys.argv) < 2:
        print("Usage: python _ops_services/register_did.py <role_name>")
        print("Example: python _ops_services/register_did.py agent_a_admin")
        sys.exit(1)
    
    target_role = sys.argv[1]
    register_did_implicit(target_role)