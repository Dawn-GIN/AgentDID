import os
import sys
import hashlib   
import datetime  

os.environ["NO_PROXY"] = "aliyuncs.com,dashscope.aliyuncs.com,localhost,127.0.0.1"

# === LangChain & QwQ Import ===
from langchain_qwq import ChatQwQ
from langchain.agents import create_agent 
from langgraph.checkpoint.memory import InMemorySaver
from langchain.tools import tool

# === Path Adaptation ===
# Assume running from project root, ensure infrastructure and sibling modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir)) # Locate project root
if root_dir not in sys.path:
    sys.path.append(root_dir)

from infrastructure.load_config import load_key_config

# === Tools Definition ===

@tool
def get_hash(text: str) -> str:
    """
    Useful for calculating the SHA-256 hash of a given string.
    Input: The text string to hash.
    Output: The hexadecimal representation of the hash.
    """
    # Simulate tool execution log to visualize Agent reasoning in console
    # print(f"\n[Tool] Calculating hash: '{text[:15]}...'")
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

@tool
def get_current_utc_date() -> str:
    """
    Useful for getting the current UTC date and time.
    No input required.
    Output: Current UTC timestamp string (e.g., 2024-01-01 12:00:00 UTC).
    """
    # print(f"\n[Tool] Getting current UTC time...")
    # Get standard UTC time
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def get_holder_tools():
    """
    Returns list of tools available to Holder Agent.
    """
    return [get_hash, get_current_utc_date]

# === System Prompt ===
# Core Instruction: Clearly distinguish three modes; responsible only for decision and calculation, not signing
SYSTEM_PROMPT = """You are an autonomous AI Agent (Holder) with DID: {did}.
Your role is to act as the "Brain" - making decisions and processing information.
The system Runtime (your "Body") handles all cryptographic signing, private keys, and VC presentations.

CRITICAL INSTRUCTIONS - DISTINGUISH THREE MODES:

[MODE 0: PREPARATION]
- Trigger: Input warns "No VC found".
- Goal: Request a Verifiable Credential from the Issuer.
- Action: Output exactly: "COMMAND: REQUEST_VC | <Issuer_URL> | <Credential_Type>"

[MODE 1: AUTHENTICATION]
- Trigger: Input mentions "Authentication Request" or asks for identity verification.
- Goal: Decide whether to present your identity (and VCs) to the Verifier.
- Action:
  1. Analyze the request details (Verifier DID, Nonce).
  2. If you trust the verifier and agree to authenticate, output exactly: "APPROVE".
  3. If you decline, output exactly: "REJECT".

[MODE 2: PROBE TASK]
- Trigger: Input mentions "New Task" or "Task ID".
- Goal: Execute the requested task accurately using available tools.
- Action:
  1. ANALYZE the prompt.
  2. USE calculation tools (e.g., 'get_hash', 'get_current_utc_date') to obtain facts.
  3. WAIT for tool observations.
  4. GENERATE a final plain text summary as the result.
  DO NOT attempt to sign the result. Just output the final answer text.

[MODE 3: CONTEXT CHECK]
- Trigger: Input mentions "Context Hash Request".
- Goal: Decide whether to provide your memory state hash for auditing.
- Action:
  1. If you agree to provide the context hash, output exactly: "APPROVE".
  2. If you decline, output exactly: "REJECT".

Your goal is ACCURACY, CONSISTENCY, and SECURITY. 
"""

def create_holder_agent(did_string):
    """
    Create Holder Agent
    :param did_string: Agent DID，used to populate System Prompt
    """
    # 1. Load config to get API Key
    config = load_key_config()
    api_key = config.get("qwq_api_key") or os.environ.get("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("[Agent] Error: qwq_api_key missing, please configure in key.json.")
        return None
    
    # Set environment variable for LangChain
    os.environ["DASHSCOPE_API_KEY"] = api_key

    try:
        # 2. Initialize LLM
        # Use low temperature (0.01) to ensure consistency and rigor in decisions
        llm = ChatQwQ(
            model="qwen-plus",
            temperature=0.01,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # 3. Set short-term memory (Conversation Buffer)
        # Note: This is the buffer for Agent thought process; actual persistent history is written to disk by Runtime
        checkpointer = InMemorySaver()

        # 4. Get tools
        # Call functions defined in this file
        tools = get_holder_tools()

        # 5. Format Prompt
        formatted_system_prompt = SYSTEM_PROMPT.format(did=did_string)

        # 6. Create Agent
        # Encapsulate ReAct or Tool Calling logic using LangChain's create_agent
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=formatted_system_prompt,
            checkpointer=checkpointer
        )
        
        return agent
        
    except Exception as e:
        print(f"[Error] Agent initialization failed: {e}")
        return None
