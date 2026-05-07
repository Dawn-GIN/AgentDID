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

import time
import json
import hashlib
import secrets
import csv

def generate_turn_data(round_idx):
    """
    Simulate data for one turn of conversation.
    To ensure the accuracy of the linear growth test, the amount of data added per round should remain stable.
    Assume each conversation turn (Prompt + Response) is about 500 characters (approximately 120-150 Tokens).
    """
    return {
        "round_index": round_idx,
        "role": "user",
        "content": f"Please calculate the hash for task {round_idx}..." + secrets.token_hex(64), # Simulate user input
        "agent_response": {
            "result": f"The result is {secrets.token_hex(16)}", # Simulate Agent response
                "thought": secrets.token_hex(500), # Simulate intermediate thought process
                "timestamp": time.time()
        }
    }

def main():
    print("="*60)
    print("=== Context Consistency Hash Calculation: Extreme Stress Test ===")
    print("="*60)

    # === Configuration Parameters ===
    MAX_ROUNDS = 35000  
    # Record data every 1000 rounds to prevent CSV file from becoming too large
    SAMPLE_INTERVAL = 1000 
    
    # Simulate memory
    memory_storage = []
    
    # CSV file path (saved in the same directory as the current script)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(current_dir, "benchmark_hash_results.csv")

    print(f"Testing in progress (Total {MAX_ROUNDS} rounds)...")
    print(f"{'Round':<8} | {'Tokens(Est)':<12} | {'Size(KB)':<10} | {'Time(ms)':<10}")
    print("-" * 50)

    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(["Round_Index", "Estimated_Tokens", "JSON_Size_KB", "Calc_Time_ms"])

        for i in range(1, MAX_ROUNDS + 1):
            new_data = generate_turn_data(i)
            memory_storage.append(new_data)

            if i % SAMPLE_INTERVAL == 0:
                
                # --- [Core Measurement] ---
                t_start = time.perf_counter()
                json_str = json.dumps(memory_storage, sort_keys=True)
                _ = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
                t_end = time.perf_counter()
                duration_ms = (t_end - t_start) * 1000
                
                # --- [Auxiliary Metrics] ---
                size_bytes = len(json_str)
                size_kb = size_bytes / 1024
                tokens_est = int(size_bytes / 4)

                # --- [Write to CSV] ---
                writer.writerow([i, tokens_est, f"{size_kb:.2f}", f"{duration_ms:.4f}"])
                
                # --- [Single-line refresh] ---
                progress = (i / MAX_ROUNDS) * 100
                sys.stdout.write(f"\rProgress: {progress:.1f}% | Current Round: {i} | Token Estimate: {tokens_est/1000000:.2f}M | Time: {duration_ms:.2f}ms")
                sys.stdout.flush()

    print("="*60)
    print(f"Test completed!")
    print(f"Data saved to: {csv_file_path}")
    print("="*60)

if __name__ == "__main__":
    main()