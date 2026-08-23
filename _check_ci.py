import sys, json
data = json.load(sys.stdin)
for r in data.get('check_runs', []):
    if r['name'] == 'run':
        print('=== run job ===')
        print('Status:', r['status'])
        print('Conclusion:', r.get('conclusion'))
        print('URL:', r['html_url'])

print()
print('=== All FAILURES ===')
for r in data.get('check_runs', []):
    if r.get('conclusion') == 'failure':
        print('  [' + r['name'] + '] ' + r['html_url'])
