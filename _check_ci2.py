import sys, json
data = json.load(sys.stdin)
runs = data.get('check_runs', [])
statuses = {}
for r in runs:
    name = r['name']
    status = r['status']
    conclusion = r.get('conclusion') or 'RUNNING'
    if name not in statuses:
        statuses[name] = []
    statuses[name].append((status, conclusion))

passed = []
failed = []
running = []
skipped = []

for name, entries in sorted(statuses.items()):
    # Take the latest entry
    status, conclusion = max(entries, key=lambda x: x[0])
    
    if conclusion == 'success':
        passed.append(name)
    elif conclusion == 'failure':
        failed.append(name)
    elif status == 'completed':
        skipped.append(name)
    else:
        running.append(name)

print("=== PASSED ===")
for n in passed: print(f"  [PASS] {n}")

if failed:
    print("\n=== FAILED ===")
    for n in failed: print(f"  [FAIL] {n}")

if running:
    print(f"\n=== RUNNING ({len(running)}) ===")
    for n in running[:15]: print(f"  [....] {n}")
    if len(running) > 15: print(f"  ... and {len(running)-15} more")

if skipped:
    print(f"\n=== SKIPPED ===")
    for n in skipped: print(f"  [SKIP] {n}")
