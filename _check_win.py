import sys, json
data = json.load(sys.stdin)
for r in data.get('check_runs', []):
    if 'windows' in r['name'].lower() and 'integrated' in r['name'].lower():
        print(f"Name: {r['name']}")
        print(f"Status: {r['status']}")
        print(f"Conclusion: {r.get('conclusion')}")
        print(f"Started: {r.get('started_at')}")
        print(f"URL: {r['html_url']}")
