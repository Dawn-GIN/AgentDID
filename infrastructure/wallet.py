import time
import json
import datetime
import os
import glob
from web3 import Web3
from eth_account.messages import encode_defunct
from infrastructure.load_config import load_key_config

class IdentityWallet:
    def __init__(self, agent_role_name, w3_provider=None, override_config=None):
        self.w3 = w3_provider if w3_provider else Web3()
        if override_config:
            self.config = override_config
        else:
            self.config = load_key_config()
        self.role_name = agent_role_name
        
        if agent_role_name not in self.config["accounts"]:
            raise ValueError(f"Role {agent_role_name} not found")
        account_info = self.config["accounts"][agent_role_name]
        self.private_key = account_info["private_key"]
        
        if agent_role_name.endswith("_op"):
            admin_role = f"{agent_role_name.replace('_op', '')}_admin"
        else:
            admin_role = agent_role_name
            
        if admin_role in self.config["accounts"]:
            self.did = f"did:ethr:sepolia:{self.config['accounts'][admin_role]['address']}"
        else:
            self.did = f"did:ethr:sepolia:{account_info['address']}"

        self.my_vcs = []
        
    def load_local_vcs(self, data_dir):
        """
        Load all VC files belonging to this DID from the specified data directory
        File pattern: vc_*.json
        """
        self.my_vcs = [] # Clear old ones
        
        # Find all JSON files starting with vc_
        pattern = os.path.join(data_dir, "vc_*.json")
        files = glob.glob(pattern)
        
        for f_path in files:
            try:
                with open(f_path, 'r', encoding='utf-8') as f:
                    vc_data = json.load(f)
                    
                    # Simple check: Is this VC issued to me?
                    # Check if credentialSubject.id equals my DID
                    subj = vc_data.get("credentialSubject", {})
                    if subj.get("id") == self.did:
                        self.my_vcs.append(vc_data)
            except Exception as e:
                print(f"[Wallet Error] Failed to load VC from {f_path}: {e}")
                
        # print(f"[Wallet] Loaded {len(self.my_vcs)} VCs from {data_dir}")

    def add_vc(self, vc_data):
        """Dynamically add a single VC (used when a VC has just been acquired)"""
        self.my_vcs.append(vc_data)

    def sign_message(self, text_payload):
        message = encode_defunct(text=text_payload)
        signed = self.w3.eth.account.sign_message(message, private_key=self.private_key)
        return signed.signature.hex()

    def create_vp(self, nonce):
        t_start = time.perf_counter()
        
        vp_payload = {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": self.my_vcs, # This will automatically include the content just loaded by load_local_vcs
            "holder": self.did,
        }
        
        serialized_vp = json.dumps(vp_payload, sort_keys=True, separators=(',', ':'))
        signature_hex = self.sign_message(serialized_vp)
        
        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        final_vp = vp_payload.copy()
        final_vp["proof"] = {
            "type": "EcdsaSecp256k1RecoverySignature2020",
            "created": now_utc,
            "verificationMethod": f"{self.did}#delegate",
            "proofPurpose": "authentication",
            "challenge": nonce,
            "jws": signature_hex
        }
        
        t_end = time.perf_counter()
        return final_vp, (t_end - t_start) * 1000