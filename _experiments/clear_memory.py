import os
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET_DIRS = [
    os.path.join(PROJECT_ROOT, "agents", "holder", "data"),
    os.path.join(PROJECT_ROOT, "agents", "verifier", "data"),
]

total = 0
for data_dir in TARGET_DIRS:
    files = glob.glob(os.path.join(data_dir, "*memory*.json"))
    print(f"\n[{data_dir}] Found {len(files)} memory files")
    for f in files:
        os.remove(f)
        print(f"  Deleted: {os.path.basename(f)}")
    total += len(files)

print(f"\nDone. {total} files deleted.")
