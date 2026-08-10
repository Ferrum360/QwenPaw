import sys

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    lines = f.readlines()

result = []
skip_block = False
for i, line in enumerate(lines):
    stripped = line.strip()
    
    if stripped == '=======':
        skip_block = True
        continue
    
    if skip_block:
        if not stripped or line.startswith('    ') or line.startswith('\t'):
            continue
        else:
            skip_block = False
            result.append(line)
    else:
        result.append(line)

with open(sys.argv[1], 'w', encoding='utf-8') as f:
    f.writelines(result)

print(f"Lines before: {len(lines)}, after: {len(result)}")
remaining = [l for l in result if '<<<<<<' in l or '======' in l or '>>>>>>' in l]
print(f"Remaining markers: {len(remaining)}")
