import sys, json
data = json.load(sys.stdin)
for r in data.get('check_runs', []):
    if 'Unit Tests' in r['name'] and 'windows' in r['name'].lower():
        print(f"Name: {r['name']}")
        print(f"Status: {r['status']}")
        print(f"Conclusion: {r.get('conclusion')}")
        ann = r.get('annotations', [])
        if ann:
            for a in ann[:3]:
                s = a.get('output',{}).get('summary','') or ''
                t = a.get('output',{}).get('text','') or ''
                print((s + '\n' + t)[:800])
                print()
