import random
import json
import hashlib
import itertools
from web3 import Web3
from .load_config import load_key_config

_RPC_CYCLE = None

ETH_PRICE_USD = 3121.34 

def get_rpc_url():
    """
    Get RPC node from the configuration pool via round-robin.
    Strategy: Random-Start Round-Robin
    Ensures load balancing within a single process and prevents the 'thundering herd' effect when multiple processes start.
    """
    global _RPC_CYCLE
    config = load_key_config()
    
    # First, check for a node pool
    if "api_url_pool" in config and isinstance(config["api_url_pool"], list) and len(config["api_url_pool"]) > 0:
        pool = config["api_url_pool"]
        
        # If this is the first call (or a new process starts), initialize the iterator
        if _RPC_CYCLE is None:
            # 1. To prevent multiple processes from hitting the first node simultaneously on startup,
            #    we randomize the order or pick a random starting point during initialization.
            start_index = random.randint(0, len(pool) - 1)
            
            # 2. Create an infinitely cycling iterator
            # e.g., for pool=[A, B, C] and start_index=1, the sequence is B -> C -> A -> B ...
            rotated_pool = pool[start_index:] + pool[:start_index]
            _RPC_CYCLE = itertools.cycle(rotated_pool)
            
        # 3. Get the next node
        selected_url = next(_RPC_CYCLE)
        return selected_url, config
    
    # Fallback to single-point configuration
    return config["api_url"], config
 
def get_w3():
    """
    Initialize Web3 connection.
    Now gets configuration via the unified load_key_config, which is more robust.
    """
    try:
        rpc_url, config = get_rpc_url()
        
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            print(f"[Network] Connection failed, please check API URL: {rpc_url}")
            exit(1)
        return w3, config
    except Exception as e:
        print(f"[Network] Initialization exception: {e}")
        exit(1)

# ethr:did registry address (Sepolia)
REGISTRY_ADDRESS = "0x03d5003bf0e79C5F5223588F347ebA39AfbC3818"

# ===  Contract ABI ===
REGISTRY_ABI = [
    {
        "constant": False,
        "inputs": [
            {"internalType": "address", "name": "identity", "type": "address"},
            {"internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "changeOwner",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"internalType": "address", "name": "identity", "type": "address"}],
        "name": "identityOwner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"internalType": "address", "name": "identity", "type": "address"},
            {"internalType": "bytes32", "name": "name", "type": "bytes32"},
            {"internalType": "bytes", "name": "value", "type": "bytes"},
            {"internalType": "uint256", "name": "validity", "type": "uint256"}
        ],
        "name": "setAttribute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "identity", "type": "address"},
            {"indexed": False, "internalType": "address", "name": "owner", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "previousChange", "type": "uint256"}
        ],
        "name": "DIDOwnerChanged",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "identity", "type": "address"},
            {"indexed": False, "internalType": "bytes32", "name": "name", "type": "bytes32"},
            {"indexed": False, "internalType": "bytes", "name": "value", "type": "bytes"},
            {"indexed": False, "internalType": "uint256", "name": "validTo", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "previousChange", "type": "uint256"}
        ],
        "name": "DIDAttributeChanged",
        "type": "event"
    },
    {
        "constant": True,
        "inputs": [
            {"internalType": "address", "name": "identity", "type": "address"},
            {"internalType": "bytes32", "name": "delegateType", "type": "bytes32"},
            {"internalType": "address", "name": "delegate", "type": "address"}
        ],
        "name": "validDelegate",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# === Generic Memory Management Functions ===

def load_memory(file_path):
    """Safely load a JSON file, return an empty list if it doesn't exist"""
    import os # Local import to keep things clean
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] Failed to load memory from {file_path}: {e}")
        return []

def save_memory(file_path, memory_data):
    """Save data to a JSON file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Error] Failed to save memory to {file_path}: {e}")

def calculate_memory_hash(memory_data):
    """Calculate a hash, used for signing and verification"""
    serialized = json.dumps(
        memory_data, 
        sort_keys=True, 
        separators=(',', ':'), 
        ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
