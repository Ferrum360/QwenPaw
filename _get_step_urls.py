import sys, json
data = json.load(sys.stdin)
for j in data.get('jobs', []):
    if 'Integrated' in j['name'] and 'macos' in j['name']:
        print("Job ID:", j['id'])
        for i, s in enumerate(j.get('steps', [])):
            print(f'Step {i}: keys={list(s.keys())}')
            if 'url' in s:
                print(f'  URL: {s["url"]}')
