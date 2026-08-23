import sys, json
data = json.load(sys.stdin)
for j in data.get('jobs', []):
    if 'Integrated' in j['name'] and 'macos' in j['name']:
        for i, s in enumerate(j.get('steps', [])):
            print(f'{i}: {s["name"]} -> {s.get("conclusion")}')
