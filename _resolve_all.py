import sys, re

def resolve_conflicts(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by <<<<<<< markers, each section is: HEADER + ======= + OUR_HEADER
    # We want to keep only the HEAD side (before ======)
    parts = re.split(r'<<<<<<.+?\n(.+?)\n=======\s*\n(.*?)(?=\n<<<<<<|>>>|$)', content, flags=re.DOTALL)
    
    if len(parts) == 1:
        # No conflict markers found, or different format
        pass
    
    # Simpler approach: for each conflict block, extract HEAD side
    pattern = r'<<<<<<.+?\n((?:.*?\n)*?)(?=\n=======)'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    result_parts = []
    prev_end = 0
    for m in matches:
        head_part = m.group(1).rstrip('\n')
        # Find the end of this block (after >>>>>>> marker)
        end_match = re.search(r'\n>>>>>>> .+?', content[m.end():])
        if end_match:
            block_end = m.start() + end_match.end()
        else:
            block_end = len(content)
        
        # Get everything between previous block end and HEAD part start
        before = content[prev_end:m.start()]
        result_parts.append(before)
        result_parts.append(head_part + '\n')
        prev_end = block_end
    
    result_parts.append(content[prev_end:])
    result = ''.join(result_parts)
    
    # Clean up any remaining ======= lines
    result = re.sub(r'^={7,}$\n?', '', result, flags=re.MULTILINE)
    # Clean up any remaining >>>>>>> lines  
    result = re.sub(r'^>.{7,}\n?', '', result, flags=re.MULTILINE)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"Resolved {len(matches)} conflicts in {filepath}")

for path in sys.argv[1:]:
    resolve_conflicts(path)
