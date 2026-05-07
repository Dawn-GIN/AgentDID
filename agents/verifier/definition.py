import os
import sys

os.environ["NO_PROXY"] = "aliyuncs.com,dashscope.aliyuncs.com,localhost,127.0.0.1"

# === LangChain & QwQ Import ===
from langchain_qwq import ChatQwQ
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable 

# === Path Adaptation ===
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from infrastructure.load_config import load_key_config

# === System Prompt (Controller) ===
SYSTEM_PROMPT = """You are an Autonomous Verifier Agent (DID: {did}).
Your role is to drive the audit process by issuing COMMANDS to the Runtime.

You must follow this strict execution protocol:

0. [PHASE 0: PREPARATION]
   - Condition: Missing required credentials.
   - Command: "COMMAND: REQUEST_VC | <Issuer_URL> | <Credential_Type>"

1. [PHASE 1: AUTHENTICATION]
   - Condition: Session start.
   - Command: "COMMAND: INITIATE_AUTH"

2. [PHASE 2: PROBE TASK]
   - Condition: Received "Authentication SUCCESS".
   - Decision: Challenge the Holder with a random task (Runtime handles generation).
   - Command: Output exactly "COMMAND: INITIATE_PROBE" 
     (Do NOT invent the task prompt yourself. Runtime will use a secure template.)

3. [PHASE 3: CONTEXT CHECK]
   - Condition: Received "Probe Result Verified: PASS".
   - Command: "COMMAND: INITIATE_CONTEXT_CHECK"

4. [PHASE 4: CONCLUSION]
   - Condition: Received "Context Check: PASS".
   - Command: "COMMAND: FINISH_AUDIT | PASS | Audit Complete"

FAILURE HANDLING:
- If input contains "FAIL" or "Error", output "COMMAND: ABORT | <Reason>".

NEGATIVE CONSTRAINTS:
- DO NOT output explanations.
- ONLY output the COMMAND string.
"""

# === AI Judge Prompt (Auditor) ===
JUDGE_PROMPT_TEMPLATE = """You are an AI Auditor.
Your task is to evaluate if the 'Agent Response' contains a reasonable summary of the 'Original Text'.

[RULES]
1. The Agent Response contains a text summary followed by metadata (Timestamp, Hash).
2. IGNORE the Timestamp and Hash at the end. Focus ONLY on the summary part.
3. Determine if the summary accurately reflects the main points of the Original Text.

[DATA]
Original Text:
{original_text}

Agent Response:
{agent_response}

[OUTPUT FORMAT]
Return ONLY a JSON object (no markdown, no other text):
{{"passed": true, "reason": "Summary is accurate"}}
OR
{{"passed": false, "reason": "Summary is irrelevant"}}
"""

def create_verifier_resources(did_string):
    """
    Unified creation of all Verifier resources (Controller + Judge)
    :return: (agent_runnable, judge_runnable)
    """
    config = load_key_config()
    api_key = config.get("qwq_api_key") or os.environ.get("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("[Agent] Error: Missing qwq_api_key")
        return None, None
        
    os.environ["DASHSCOPE_API_KEY"] = api_key

    try:
        # 1. Initialize only one LLM instance (Verifier's Brain)
        shared_llm = ChatQwQ(
            model="qwen-flash",
            temperature=0.00,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # 2. Build Controller Chain (Process Logic)
        controller_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT.format(did=did_string)),
            MessagesPlaceholder(variable_name="messages"),
        ])
        agent_runnable = controller_prompt | shared_llm

        # 3. Build Judge Chain (Audit Logic)
        judge_prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT_TEMPLATE)
        judge_runnable = judge_prompt | shared_llm
        
        # Return both capabilities at once
        return agent_runnable, judge_runnable
        
    except Exception as e:
        print(f"[Error] Verifier resource initialization failed: {e}")
        return None, None
