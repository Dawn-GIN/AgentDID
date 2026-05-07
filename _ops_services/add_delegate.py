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

from infrastructure.utils import get_w3, REGISTRY_ADDRESS, REGISTRY_ABI

def add_delegate_with_contract(admin_role: str, op_role: str):
    """
    Authorize an Operator role as a Delegate for an Admin role
    by calling the setAttribute function of the ethr-did-registry contract.
    
    Args:
        admin_role (str): Role name of the Owner, e.g., 'agent_a_admin'
        op_role (str):    Role name of the Delegate, e.g., 'agent_a_op'
    """
    print("="*50)
    print(f"===  Add Delegate Authorization ===")
    print(f"  Owner:    {admin_role}")
    print(f"  Delegate: {op_role}")
    print("="*50)

    try:
        # 1. Initialize Web3 connection and configuration
        w3, config = get_w3()
        accounts = config.get("accounts", {})

        # 2. Check and retrieve account information
        if admin_role not in accounts or op_role not in accounts:
            print(f"[Error] Role '{admin_role}' or '{op_role}' not found in key.json.")
            return

        admin_info = accounts[admin_role]
        op_addr = accounts[op_role]["address"]
        
        admin_addr = admin_info["address"]
        admin_pk = admin_info["private_key"]
        
        print(f" Owner (Admin) Address: {admin_addr}")
        print(f" Delegate (Op) Address:  {op_addr}")

        # 3. Get contract instance
        registry_contract = w3.eth.contract(address=REGISTRY_ADDRESS, abi=REGISTRY_ABI)

        # 4. Construct contract call parameters
        key_name_str = "did/pub/Secp256k1/sigAuth/hex"
        key_name_bytes = key_name_str.encode('utf-8').ljust(32, b'\0')
        value_bytes = bytes.fromhex(op_addr[2:])
        validity = 365 * 24 * 60 * 60  # Validity: 1 year

        # 5. Build transaction
        nonce = w3.eth.get_transaction_count(admin_addr)
        
        transaction = registry_contract.functions.setAttribute(
            identity=admin_addr,    # Set identity for Admin itself
            name=key_name_bytes,    # Attribute name (Authorization type)
            value=value_bytes,      # Attribute value (Op address)
            validity=validity
        ).build_transaction({
            'from': admin_addr,
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 11155111 # Sepolia
        })
        
        # 6. Sign with Admin private key and send
        signed_tx = w3.eth.account.sign_transaction(transaction, admin_pk)
        
        print("\n Sending transaction to Sepolia network...")
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f" Transaction broadcasted, Hash: {w3.to_hex(tx_hash)}")
        print(" Waiting for transaction confirmation...")

        # 7. Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        # 8. Confirm result
        if receipt.status == 1:
            print("\n" + "-"*50)
            print(f" Success! '{op_role}' has been authorized as a Delegate for '{admin_role}'.")
            print(f"   Block Number: {receipt.blockNumber}")
            print(f"   Gas Used: {receipt.gasUsed}")
            print("-" * 50)
        else:
            print(f"\n[Failure] Transaction execution failed, check block explorer for details: {w3.to_hex(tx_hash)}")

    except Exception as e:
        print(f"\n[Error] Script execution exception: {e}")

if __name__ == "__main__":
    # Receive arguments from command line, e.g.: python _ops_services/add_delegate.py agent_a_admin agent_a_op
    if len(sys.argv) < 3:
        print("Usage: python _ops_services/add_delegate.py <admin_role> <op_role>")
        print("Example: python _ops_services/add_delegate.py agent_a_admin agent_a_op")
        sys.exit(1)
    
    admin_role_arg = sys.argv[1]
    op_role_arg = sys.argv[2]
    
    add_delegate_with_contract(admin_role_arg, op_role_arg)