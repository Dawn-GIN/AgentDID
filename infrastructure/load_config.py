import os
import json
import sys

# Calculate project root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(current_dir)

# Add root directory to sys.path for easy module imports
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

def load_key_config():
    """
    Load config/key.json
    Uses ROOT_DIR to ensure the file can be found regardless of script location.
    """
    path = os.path.join(ROOT_DIR, "config", "agents_4_key.json") # Modify path/filename as needed. Daily debug uses config/key.json; 2v2 demo uses config/agents_4_key.json. Concurrent stress test scripts load files directly instead of using this function.
    if not os.path.exists(path):
        raise FileNotFoundError(f"[Config] Error: Key file not found, please check the path: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_resolve_script_path():
    """
    Get absolute path of real_resolve.js
    Location: infrastructure/real_resolve.js
    """
    path = os.path.join(current_dir, "real_resolve.js")
    
    if not os.path.exists(path):
        path_root = os.path.join(ROOT_DIR, "real_resolve.js")
        if os.path.exists(path_root):
            return path_root
            
        raise FileNotFoundError(
            f"[Config] Error: real_resolve.js not found.\n"
            f"Please ensure the file is located at {path} or the project root."
        )
    return path