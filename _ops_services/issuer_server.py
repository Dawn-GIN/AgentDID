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
import time
import datetime
import traceback
from flask import Flask, request, jsonify
from web3 import Web3
from eth_account.messages import encode_defunct

# === 1. Import Project Components ===
from infrastructure.load_config import load_key_config
from infrastructure.validator import DIDValidator

app = Flask(__name__)

# === 2. Initialize Configuration ===
config = load_key_config() 
accounts = config["accounts"]
issuer_info = accounts["issuer"]
w3 = Web3()
validator = DIDValidator()

# Template directory
SCHEMA_DIR = os.path.join(project_root, "vc_schemas")

print("="*60)
print(f"Issuer Server Started (Port: 8000)")
print(f"Issuer DID: did:ethr:sepolia:{issuer_info['address']}")
print(f"Template Dir: {SCHEMA_DIR}")
print("="*60)

# === 3. Core Utility Functions ===

def sign_vc(vc_payload, private_key):
    """Sort JSON and sign"""
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
    
    # Auto-generate validity period if not in template
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

def generate_all_vcs(applicant_did):
    """
    Traverse vc_schemas directory, issue all VCs defined in templates for applicant
    """
    issued_vcs = []
    
    if not os.path.exists(SCHEMA_DIR):
        print(f"[Error] Schema dir not found: {SCHEMA_DIR}")
        return []

    # Get all JSON files and sort
    files = sorted([f for f in os.listdir(SCHEMA_DIR) if f.endswith(".json")])
    
    print(f"    [Process] Found {len(files)} templates. Processing...")

    for filename in files:
        file_path = os.path.join(SCHEMA_DIR, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
            
            # Process single template
            vc = process_single_template(template, applicant_did)
            issued_vcs.append(vc)

            vc_json_str = json.dumps(vc)
            vc_size_bytes = len(vc_json_str)
            vc_size_kb = vc_size_bytes / 1024
            
            vc_type = template.get("type", ["Unknown"])[-1]
            print(f"      - Issued: {filename} -> {vc_type} | Size: {vc_size_bytes} bytes ({vc_size_kb:.2f} KB)")
            
        except Exception as e:
            print(f"      - Error processing {filename}: {e}")

    return issued_vcs

# === 4. API Definitions ===

@app.route('/issue_vc', methods=['POST'])
def handle_issue_vc():
    """
    Receive application -> Verify signature -> Simulate delay -> Batch issuance
    """
    try:
        data = request.json
        applicant_did = data.get('applicant')
        signature = data.get('signature')
        
        print(f"\n>>> [Request] VC Application from: {applicant_did}")

        # --- A. Verify Identity ---
        if not applicant_did or not signature:
            return jsonify({"error": "Missing applicant or signature"}), 400
        
        # Reconstruct original message for signature verification
        payload_copy = data.copy()
        if 'signature' in payload_copy: del payload_copy['signature']
        serialized_payload = json.dumps(payload_copy, sort_keys=True, separators=(',', ':'))
        
        # Verify: Signer must be the legitimate controller of applicant DID
        is_valid, reason = validator.verify_request_signature(serialized_payload, signature, applicant_did)
        
        if not is_valid:
            print(f"    [Auth Fail] {reason}")
            return jsonify({"error": f"Signature verification failed: {reason}"}), 401

        print("    [Auth Success] Signature Verified")

        # --- B. Simulate Approval ---
        # Sleep for 2 seconds and print
        time.sleep(2)
        print("    [Process] Assuming applicant identity attributes verified, issuing VCs...")

        # --- C. Batch Issue All Certificates ---
        vc_list = generate_all_vcs(applicant_did)
        
        print(f"    [Issued] Successfully issued {len(vc_list)} VCs to {applicant_did}")
        
        # Return list
        return jsonify(vc_list)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, threaded=True)
