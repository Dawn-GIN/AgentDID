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
import csv
import multiprocessing
import time
from multiprocessing import Process

# === Import Runtime Class ===
from agents.verifier.runtime import VerifierRuntime

# === Global Configuration ===
VERIFIERS_KEY_PATH = os.path.join(project_root, "data", "verifiers_key.json")
result_dir = os.path.join(current_dir, "result")
if not os.path.exists(result_dir):
    os.makedirs(result_dir)
CSV_REPORT_PATH = os.path.join(result_dir, "N=1.csv")

# Stress Test Scale
MAX_PAIRS = 1

# Holder server host — change to remote IP when Holders run on a separate machine
# e.g. HOLDER_HOST = "192.168.1.100"
HOLDER_HOST = "localhost"

def run_p2p_worker(name, config, role_name, stats_queue, barrier, target_url):
    """
    Verifier Worker Process
    Verifier(N) -> Holder(N)
    """
    try:
        # Initialize Verifier Runtime
        verifier = VerifierRuntime(
            role_name=role_name, 
            config=config, 
            instance_name=name,
            target_holder_url=target_url
        )
        
        # Start execution
        verifier.run(max_turns=12, barrier=barrier, stats_queue=stats_queue)
        
    except Exception as e:
        print(f"[{name}] Crash: {e}")

def main():
    print("="*60)
    print(f"P2P STRESS TEST | Mode: 1 Verifier vs 1 Holder")
    print("="*60)
    
    # 1. Load Verifier keys
    if not os.path.exists(VERIFIERS_KEY_PATH):
        print(f"[Error] Key file not found: {VERIFIERS_KEY_PATH}")
        sys.exit(1)
        
    with open(VERIFIERS_KEY_PATH, 'r', encoding='utf-8') as f:
        full_config = json.load(f)
        
    # 2. Filter and sort roles
    accounts = full_config.get("accounts", {})
    verifier_roles = [k for k in accounts.keys() if "_op" in k and "verifier" in k]
    try:
        verifier_roles.sort(key=lambda x: int(x.split('_')[1]))
    except:
        verifier_roles.sort()
    
    # Slice
    num_pairs = min(MAX_PAIRS, len(verifier_roles))
    active_roles = verifier_roles[:num_pairs]
    
    print(f"Launching {num_pairs} pairs...")
    
    # 3. Prepare multiprocessing
    stats_queue = multiprocessing.Queue()
    start_barrier = multiprocessing.Barrier(num_pairs)
    processes = []
    
    # 4. Start Verifier processes with 1-to-1 port binding
    for i, role in enumerate(active_roles):
        # Logical mapping: Verifier i targets Holder i
        # Holder ports start from 5000: 5000, 5001, ..., 5000+n-1
        target_port = 5000 + i
        target_url = f"http://{HOLDER_HOST}:{target_port}"
        
        p_name = f"Verifier-{i+1}"
        
        p = Process(
            target=run_p2p_worker, 
            args=(p_name, full_config, role, stats_queue, start_barrier, target_url)
        )
        processes.append(p)
        p.start()
        
        if (i + 1) % 20 == 0:
            time.sleep(0.5) # Slight flow control to prevent freezing during startup burst

    print(f"\n[Main] All {num_pairs} Verifiers spawned. Waiting for results...")
    
    # 5. Collect data
    results = []
    collected_count = 0
    start_wait = time.time()
    
    # Wait until all data is collected or timeout
    while collected_count < num_pairs:
        try:
            if time.time() - start_wait > 300:
                print("\n[Main] ⚠️ Global Timeout reached!")
                break
                
            data = stats_queue.get(timeout=10)
            results.append(data)
            collected_count += 1
            sys.stdout.write(f"\r[Main] Completed: {collected_count}/{num_pairs}")
            sys.stdout.flush()
        except:
            pass # Continue waiting
            
    print("\n[Main] Collection done. Cleaning up...")

    # 6. Cleanup processes
    for p in processes:
        if p.is_alive():
            p.terminate()
        p.join()

    # 7. Generate report
    if results:
        # 1. Preprocess data: Calculate Total_Duration
        processed_results = []
        for row in results:
            # Use .get() to prevent missing keys due to failure, default to 0
            t4 = row.get("T4") or 0
            t8 = row.get("T8") or 0
            t12 = row.get("T12") or 0
            
            # Calculate total duration (Sum of three phases)
            row["Total_Duration"] = t4 + t8 + t12
            processed_results.append(row)

        # 2. Define CSV headers
        fieldnames = [
            "Verifier", 
            "T1", "T2", "T3", "T4",    # Auth Phase
            "T5", "T6", "T7", "T8",    # Probe Phase
            "T9", "T10", "T11", "T12", # Context Phase
            "SLA_Load_Ratio",
            "Total_Duration"           # Total duration
        ]

        # 3. Write CSV
        try:
            with open(CSV_REPORT_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in processed_results:
                    # Format floats, keep 4 decimal places
                    formatted = {
                        k: (f"{v:.4f}" if isinstance(v, float) else v) 
                        for k, v in row.items()
                    }
                    writer.writerow(formatted)
            print(f"✅ Report saved to: {CSV_REPORT_PATH}")
            
        except Exception as e:
            print(f"Error saving report: {e}")

        # 4. Print performance metrics to terminal (TPS & Max Latency)
        print("\n" + "="*80)
        print(f"{'Phase / Metric':<25} | {'TPS (txn/s)':<15} | {'Avg Latency (s)':<15} | {'Max Latency (s)':<15} | {'Count':<8}")
        print("-" * 80)

        # Define the four dimensions for statistics
        metrics_config = [
            ("Auth Phase (T4)", "T4"),
            ("Probe Phase (T8)", "T8"),
            ("Context Phase (T12)", "T12"),
            ("Full Process (Total)", "Total_Duration")
        ]

        for label, key in metrics_config:
            # Filter successful data for this phase (value > 0)
            valid_values = [r[key] for r in processed_results if r.get(key) is not None and r[key] > 0]
            
            if valid_values:
                count = len(valid_values)
                # In concurrent scenarios, this depends on the slowest request
                max_val = max(valid_values)
                avg_val = sum(valid_values) / count
                
                # TPS = Total transactions completed / Total time for this batch (i.e., Max Latency)
                tps = count / max_val if max_val > 0 else 0.0
                
                print(f"{label:<25} | {tps:<12.2f} | {avg_val:<15.4f} | {max_val:<15.4f} | {count:<8}")
            else:
                print(f"{label:<25} | {'N/A':<15} | {'N/A':<15} | {'N/A':<15} | {'0':<8}")
        
        print("="*80)

    else:
        print("No results collected.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
