import sys
import os
# Locate project root to ensure infrastructure can be imported
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
import requests
import uuid
import re
import datetime
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify

# === Import Project Components ===
from infrastructure.wallet import IdentityWallet
from infrastructure.validator import DIDValidator
from agents.verifier.definition import create_verifier_resources

app = Flask(__name__)

# === Global Configuration ===
HOLDER_API_URL = "http://localhost:5000"
DEFAULT_ROLE = "agent_b_op"
ISSUER_URL = "http://localhost:8000"

# Thread pool: allows concurrent processing of background audit tasks
executor = ThreadPoolExecutor(max_workers=10)

class VerifierServerLogic:
    """
    Core business logic class for the Verifier Server.
    """
    def __init__(self, role_name):
        self.role_name = role_name
        self.name = f"Server-{role_name}"
        
        # Data directory setup
        self.data_dir = os.path.join(current_dir, "data")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.probe_templates_file = os.path.join(self.data_dir, "probe_templates.json")
        self.probe_inputs_file = os.path.join(self.data_dir, "probe_inputs.json")
        
        # Component initialization
        self._init_components()

    def _init_components(self):
        try:
            self.wallet = IdentityWallet(self.role_name)
            # Load local VCs upon Server startup
            self.wallet.load_local_vcs(self.data_dir)
            self.validator = DIDValidator()
            print(f"[{self.name}] Wallet Ready: {self.wallet.did}")
        except Exception as e:
            print(f"[{self.name}] [Fatal] Infrastructure init failed: {e}")
            sys.exit(1)

        # Initialize AI resources
        self.agent_chain, self.judge_chain = create_verifier_resources(self.wallet.did)

    # === Helper Methods ===

    def _get_memory_file(self, target_did):
        my_did = self.wallet.did
        safe_my = my_did.replace(":", "_")
        safe_target = (target_did or "unknown").replace(":", "_")
        return os.path.join(self.data_dir, f"memory_{safe_my}_to_{safe_target}.json")

    def _append_interaction(self, target_did, req, res):
        file_path = self._get_memory_file(target_did)
        existing_data = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except: pass
        existing_data.append(req)
        existing_data.append(res)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

    def _get_local_snapshot_hash(self, target_did):
        file_path = self._get_memory_file(target_did)
        if not os.path.exists(file_path):
            return hashlib.sha256(json.dumps([]).encode('utf-8')).hexdigest()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            serialized = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        except:
            return hashlib.sha256(json.dumps([]).encode('utf-8')).hexdigest()

    def _save_vc_to_wallet(self, vc_data_or_list):
        items = vc_data_or_list if isinstance(vc_data_or_list, list) else [vc_data_or_list]
        for vc_data in items:
            safe_did = self.wallet.did.replace(":", "_")
            vc_types = vc_data.get("type", ["UnknownCredential"])
            vc_type_name = vc_types[-1] if isinstance(vc_types, list) else str(vc_types)
            filename = f"vc_{safe_did}_{vc_type_name}.json"
            vc_file = os.path.join(self.data_dir, filename)
            try:
                with open(vc_file, 'w', encoding='utf-8') as f:
                    json.dump(vc_data, f, indent=2, ensure_ascii=False)
                self.wallet.add_vc(vc_data)
            except Exception as e:
                print(f"[{self.name}] Failed to save VC: {e}")

    def _load_probe_config(self):
        # Create default files if missing
        if not os.path.exists(self.probe_templates_file):
            default_tpl = [{"template_id": "tpl_01", "template_str": "Calculate SHA256 of '{{input_text}}'."}]
            with open(self.probe_templates_file, 'w', encoding='utf-8') as f: json.dump(default_tpl, f)
        if not os.path.exists(self.probe_inputs_file):
            default_inp = [{"text": "Hello World", "category": "basic"}]
            with open(self.probe_inputs_file, 'w', encoding='utf-8') as f: json.dump(default_inp, f)

        try:
            with open(self.probe_templates_file, 'r', encoding='utf-8') as f: tpls = json.load(f)
            with open(self.probe_inputs_file, 'r', encoding='utf-8') as f: inps = json.load(f)
            return tpls, inps
        except:
            return [], []

    def _construct_probe_payload(self):
        templates, inputs = self._load_probe_config()
        if not templates or not inputs:
            # Fallback
            templates = [{"template_str": "Echo '{{input_text}}'"}]
            inputs = [{"text": "Test"}]

        template_data = random.choice(templates)
        input_data = random.choice(inputs)
        
        input_text = input_data["text"]
        raw_template = template_data["template_str"]
        final_prompt = raw_template.replace("{{input_text}}", input_text)
        
        # Handle tool placeholders
        required_tools = template_data.get("required_tool_names", [])
        for i, tool_name in enumerate(required_tools):
            final_prompt = final_prompt.replace(f"{{{{required_tools[{i}]}}}}", tool_name)
        
        # Dynamic timeout calculation
        dynamic_timeout = 5000 + (len(input_text) * 50) + (2000 if required_tools else 0)
        dynamic_timeout = max(3000, min(dynamic_timeout, 100000))

        task_id = f"task-{uuid.uuid4()}"
        payload = {
            "task_id": task_id,
            "prompt": final_prompt,
            "verifier_did": self.wallet.did,
            "timestamp": time.time(),
            "timeout_ms": int(dynamic_timeout)
        }
        
        expected_hash = hashlib.sha256(input_text.encode('utf-8')).hexdigest()
        
        # Return raw_input_text for AI audit
        return payload, expected_hash, final_prompt, input_text, int(dynamic_timeout)

    def _verify_tool_outputs(self, response_text, expected_hash):
        details = []
        passed = True
        
        # Hash Check
        if expected_hash in response_text:
            details.append("Hash Match")
        else:
            passed = False
            details.append(f"Hash Mismatch (Exp: {expected_hash[:6]}...)")
            
        # Time Check (120s tolerance)
        match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", response_text)
        if match:
            try:
                dt_str = match.group(1)
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                now = datetime.datetime.now(datetime.timezone.utc)
                if abs((now - dt).total_seconds()) <= 120:
                    details.append("Time Fresh")
                else:
                    passed = False
                    details.append("Time Stale")
            except:
                details.append("Time Parse Err")
        else:
            passed = False
            details.append("No Time Found")
            
        return passed, "; ".join(details)

    # === Server-Specific Control Methods ===

    def perform_startup_check(self):
        """VC check at Server startup"""
        if len(self.wallet.my_vcs) > 0:
            print(f"[{self.name}] ✅ VC loaded from storage.")
            return
        
        print(f"[{self.name}] ⚠️ No VC found. Requesting from Issuer...")
        self.execute_request_vc(ISSUER_URL, "Audit_License")

    def execute_request_vc(self, issuer_url, credential_type):
        print(f"[{self.name}] Requesting VC...")
        payload = {
            "type": "CredentialApplication", "credentialType": credential_type,
            "applicant": self.wallet.did, "timestamp": time.time(), "nonce": str(uuid.uuid4())
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        payload["signature"] = self.wallet.sign_message(serialized)
        
        try:
            resp = requests.post(f"{issuer_url}/issue_vc", json=payload, timeout=30)
            if resp.status_code == 200:
                vc_data = resp.json()
                self._save_vc_to_wallet(vc_data)
                print(f"[{self.name}] ✅ VC Acquired.")
                return True, "VC Received"
            return False, f"Issuer Error {resp.status_code}"
        except Exception as e:
            print(f"[{self.name}] VC Request Failed: {e}")
            return False, str(e)

    def execute_full_audit(self, target_did):
        """
        Execute a full audit flow (Auth -> Probe -> Context)
        This is the core logic for the Server response to /start_audit
        """
        print(f"[{self.name}] Starting Audit for {target_did}...")
        
        # 1. Auth
        auth_req = {
            "nonce": str(uuid.uuid4()), "verifier_did": self.wallet.did, "type": "AuthRequest", "timestamp": time.time()
        }
        auth_req["verifier_signature"] = self.wallet.sign_message(json.dumps(auth_req, sort_keys=True, separators=(',', ':')))
        
        try:
            resp = requests.post(f"{HOLDER_API_URL}/auth", json=auth_req, timeout=30)
            if resp.status_code != 200:
                print(f"[{self.name}] ❌ Auth Failed: {resp.text}")
                return {"status": "Auth Failed"}
            
            vp = resp.json()
            self._append_interaction(target_did, auth_req, vp)
            print(f"[{self.name}] ✅ Auth Passed")
            
            # 2. Probe
            payload, exp_hash, _, raw_text, _ = self._construct_probe_payload()
            ser_pay = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            payload["verifier_signature"] = self.wallet.sign_message(ser_pay)
            
            resp = requests.post(f"{HOLDER_API_URL}/probe", json=payload, timeout=30)
            probe_resp_data = resp.json()
            res_text = probe_resp_data.get("execution_result", "")
            self._append_interaction(target_did, payload, probe_resp_data)
            
            passed, msg = self._verify_tool_outputs(res_text, exp_hash)
            if not passed:
                print(f"[{self.name}] ❌ Probe Failed: {msg}")
                return {"status": "Probe Failed", "details": msg}
            print(f"[{self.name}] ✅ Probe Passed")

            # 3. Context
            ctx_req = {"nonce": str(uuid.uuid4()), "verifier_did": self.wallet.did, "type": "ContextHashCheck"}
            ctx_req["verifier_signature"] = self.wallet.sign_message(json.dumps(ctx_req, sort_keys=True, separators=(',', ':')))
            
            resp = requests.post(f"{HOLDER_API_URL}/context_hash", json=ctx_req, timeout=30)
            context_resp_data = resp.json()
            remote_hash = context_resp_data.get("context_hash")
            local_hash = self._get_local_snapshot_hash(target_did)
            self._append_interaction(target_did, ctx_req, context_resp_data)

            if remote_hash == local_hash:
                print(f"[{self.name}] ✅ Context Hash Match")
                return {"status": "Success"}
            else:
                print(f"[{self.name}] ❌ Context Mismatch")
                return {"status": "Context Failed"}

        except Exception as e:
            print(f"[{self.name}] Exception: {e}")
            return {"status": "Exception", "details": str(e)}

# === Server Instantiation ===
verifier_logic = VerifierServerLogic(DEFAULT_ROLE)

# === API Definitions ===

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "did": verifier_logic.wallet.did,
        "vcs": len(verifier_logic.wallet.my_vcs),
        "status": "ready"
    })

@app.route('/control/start_audit', methods=['POST'])
def start_audit():
    """Receive command, execute audit in background"""
    target = request.json.get("target_holder_did")
    
    # Submit to thread pool
    executor.submit(verifier_logic.execute_full_audit, target)
    
    return jsonify({"status": "Audit Triggered", "target": target})

if __name__ == "__main__":
    # Param 1: Port
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5002
    
    # Param 2: Role name
    role_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ROLE
    
    # Param 3: Target Holder URL
    # start_network.py will pass this in, e.g., http://localhost:5000
    target_url = sys.argv[3] if len(sys.argv) > 3 else HOLDER_API_URL
    
    # Override global config so the address used in execute_full_audit changes
    HOLDER_API_URL = target_url
    
    print("="*60)
    print(f"Verifier Server Launching...")
    print(f"Port: {port}")
    print(f"Role: {role_arg}")
    print(f"Target Holder: {target_url}")
    
    # Critical step: Re-initialize Server logic object with the new role
    verifier_logic = VerifierServerLogic(role_arg)
    
    # perform_startup_check in VerifierServerLogic checks for local VC; if missing, requests one from Issuer
    verifier_logic.perform_startup_check()
    
    app.run(host='0.0.0.0', port=port)