import re

with open('_head_mw.py', encoding='utf-8') as f:
    head = f.read()
with open('_our_mw.py', encoding='utf-8') as f:
    our = f.read()

def extract_method(text, class_name, method_name):
    cls = re.search(rf'class {class_name}.*?(?=\nclass |\Z)', text, re.DOTALL)
    if not cls:
        return None
    method = re.search(rf'(async )?def {method_name}.*?(?=\n    (async )?def |\Z)', cls.group(0), re.DOTALL)
    return method.group(0) if method else None

h_sys = extract_method(head, 'MemoryMiddleware', 'on_system_prompt')
o_sys = extract_method(our, 'MemoryMiddleware', 'on_system_prompt')

print("=== HEAD on_system_prompt ===")
if h_sys:
    for i, line in enumerate(h_sys.split('\n')[:20]):
        print(f'{i+1}: {line}')
else:
    print("NOT FOUND")

print()
print("=== OUR on_system_prompt ===")
if o_sys:
    for i, line in enumerate(o_sys.split('\n')[:20]):
        print(f'{i+1}: {line}')
else:
    print("NOT FOUND")

# Check for run_sync_io or similar thread execution
for name, text in [('HEAD', h_sys), ('OUR', o_sys)]:
    has_sync = bool(re.search(r'run_sync_io|to_thread|loop\.run_in_executor', text or ''))
    has_memory = bool(re.search(r'get_memory_prompt', text or ''))
    print(f'\n{name}: run_sync_io={has_sync}, get_memory_prompt={has_memory}')
