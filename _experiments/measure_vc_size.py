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
import datetime
from web3 import Web3
from eth_account.messages import encode_defunct

# Import project components
try:
    from infrastructure.load_config import load_key_config
except ImportError:
    print("❌ Error: Unable to import infrastructure.")
    sys.exit(1)

#  Initialize resources 
print("Loading configuration...")
try:
    config = load_key_config()
    accounts = config["accounts"]
    issuer_info = accounts["issuer"]
    w3 = Web3()
except Exception as e:
    print(f"❌ Config loading failed: {e}")
    print("Please check if config/key.json exists and is correctly formatted.")
    sys.exit(1)

# Template directory
SCHEMA_DIR = os.path.join(project_root, "vc_schemas")

# Core logic

def sign_vc(vc_payload, private_key):
    """
    Sort JSON and sign
    """
    serialized_data = json.dumps(vc_payload, sort_keys=True, separators=(',', ':'))
    message = encode_defunct(text=serialized_data)
    signed_message = w3.eth.account.sign_message(message, private_key=private_key)
    return signed_message.signature.hex()

def get_iso_time(offset_days=0):
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=offset_days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def process_single_template(template_data, applicant_did):
    """
    Process single template data: Replace ID -> Supplement info -> Sign
    """
    vc_payload = json.loads(json.dumps(template_data))

    # 1. Replace ID
    if "credentialSubject" in vc_payload:
        vc_payload["credentialSubject"]["id"] = applicant_did
    else:
        vc_payload["credentialSubject"] = {"id": applicant_did}

    # 2. Fill in Issuer and Time info
    issuer_did = f"did:ethr:sepolia:{issuer_info['address']}"
    vc_payload["issuer"] = issuer_did
    
    if "validFrom" not in vc_payload:
        vc_payload["validFrom"] = get_iso_time(0)
    if "validUntil" not in vc_payload:
        vc_payload["validUntil"] = get_iso_time(365)

    # 3. Sign
    signature = sign_vc(vc_payload, issuer_info["private_key"])

    # 4. Wrap Proof
    final_vc = vc_payload.copy()
    final_vc["proof"] = {
        "type": "EcdsaSecp256k1Signature2019",
        "created": get_iso_time(0),
        "proofPurpose": "assertionMethod",
        "verificationMethod": f"{issuer_did}#controller",
        "jws": signature
    }
    
    return final_vc

# Main experiment program

def run_measurement():
    print("="*60)
    print("VC Size Measurement Experiment (Based on Actual Issuer Logic)")
    print(f"Template Directory: {SCHEMA_DIR}")
    print(f"Issuer DID: did:ethr:sepolia:{issuer_info['address']}")
    print("="*60)

    if not os.path.exists(SCHEMA_DIR):
        print(f"❌ Error: Template directory {SCHEMA_DIR} not found")
        return

    files = sorted([f for f in os.listdir(SCHEMA_DIR) if f.endswith(".json")])
    if not files:
        print("❌ Error: No JSON files in directory")
        return
    
    # Test Applicant DID (Using agent_a_admin from config as example)
    if "agent_a_admin" in accounts:
        applicant_address = accounts["agent_a_admin"]["address"]
        test_applicant_did = f"did:ethr:sepolia:{applicant_address}"
        print(f"Test Applicant (agent_a_admin) DID: {test_applicant_did}")
    else:
        # If this role is not in key.json, randomly generate as a fallback
        print("⚠️ Warning: agent_a_admin not found in key.json, using random address.")
        dummy_account = w3.eth.account.create()
        test_applicant_did = f"did:ethr:sepolia:{dummy_account.address}"
    print(f"Test Applicant DID: {test_applicant_did}")
    print("-" * 80)
    print(f"{'Filename':<35} | {'Type':<30} | {'Size (Bytes)':<10}")
    print("-" * 80)

    total_size = 0
    
    for filename in files:
        file_path = os.path.join(SCHEMA_DIR, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template = json.load(f)

            # --- Core Step: Invoke real issuance logic ---
            vc = process_single_template(template, test_applicant_did)

            # --- Measure Size ---
            vc_json_str = json.dumps(vc, separators=(',', ':'))
            vc_size_bytes = len(vc_json_str.encode('utf-8'))
            vc_size_kb = vc_size_bytes / 1024  # KB
            
            # Get VC type name for display
            vc_type_list = template.get("type", ["Unknown"])
            vc_type_name = vc_type_list[-1] if isinstance(vc_type_list, list) else str(vc_type_list)

            # Modify print format, keep 2 decimal places
            print(f"{filename:<35} | {vc_type_name:<30} | {vc_size_kb:<10.2f} KB")
            total_size += vc_size_bytes

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print("-" * 80)
    avg_size_kb = (total_size / len(files)) / 1024
    print(f"Average VC Size: {avg_size_kb:.2f} KB")
    print("="*60)
    print("Measurement completed.")

if __name__ == "__main__":
    run_measurement()