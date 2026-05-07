# AgentDID

A decentralized identity authentication and state verification framework for AI agents based on DIDs and Verifiable Credentials. This is the evaluation code for the paper *"AgentDID: Trustless Identity Authentication for AI Agents"*.

Copyright 2025-2026, Liu Xiaoyu, MIT License

## Hardware Requirements

Experiments are conducted on a virtual machine equipped with a 24-core Intel(R) Xeon(R) Silver 4214R CPU (48 logical cores) and 64 GB of memory, running Ubuntu 22.04.1 LTS.

For basic demo usage (2v2 mode), a standard desktop with 4+ cores and 8 GB RAM is sufficient.

## Build and Installation

### Environment

- OS: Ubuntu 22.04 LTS (also tested on Windows 10/11)
- Python: 3.11+
- Node.js: 18.20+
- npm: 10.8+

### Install System Dependencies (Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 python3-pip nodejs npm
```

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Install Node.js Dependencies

```bash
npm install
```

## Configuration and Usage

### Configure Keys

1. Copy the example config:

```bash
cp config/key_example.json config/key.json
```

2. Edit `config/key.json` and fill in:
   - Sepolia Testnet API URL (e.g., Infura or Alchemy endpoint)
   - LLM API Key (for the Agent's language model)
   - Private key of an Ethereum account holding Sepolia ETH

### Mode 1: 2v2 Full Demo

Demonstrates the complete interaction cycle between 2 Holders and 2 Verifiers.

[Watch Demo Video](media/AgentDID_Demo.mp4)

Before running, edit `infrastructure/load_config.py` line 18, set the config path to `"agents_4_key.json"`:

```bash
# Step 1: Initialize accounts (generate key pairs, register DIDs, authorize Delegates)
python _demo_2v2/setup_4_agents.py

# Step 2: Start Issuer service
python _ops_services/issuer_server.py

# Step 3: Start Agent network (in a new terminal)
python _demo_2v2/start_network.py

# Step 4: Trigger audit process (in a new terminal)
python _demo_2v2/trigger_audit.py
```

Expected output: The Verifier initiates a Probe Task to the Holder, performing status detection and Context Consistency Checks. Results are printed to the terminal.

### Mode 2: Massive Experiments (Stress Test)

Performance stress testing, latency measurement, and VC storage cost analysis.

Modify `infrastructure/load_config.py` (Line 18) to target `"key.json"`.

```bash
# Step 1: Batch identity generation (modify N in the script)
python _experiments/setup_agents_N.py

# Step 2: Ensure generated holders_key.json and verifiers_key.json are in data/

# Step 3: Start Issuer
python _ops_services/issuer_server.py

# Step 4: Start Holders (in a new terminal)
python _experiments/start_p2p_holders.py

# Step 5: Start Verifiers and run stress test (in a new terminal)
python _experiments/stress_test_p2p.py
```

Results are output as CSV files in `_experiments/result/`.

### Benchmarks

```bash
# VC size measurement
python _experiments/measure_vc_size.py

# Context hash performance test
python _experiments/context_test.py
```

## Troubleshooting

- **FileNotFoundError**: Ensure you are running scripts from the project root directory.
- **DID Resolution Failed**: Check if Node.js is installed and `node` is in your system PATH.
- **Insufficient Gas**: Ensure the master account in `key.json` has enough Sepolia ETH.

## License

[MIT License](LICENSE)
