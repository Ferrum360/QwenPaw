import difflib, sys

with open(sys.argv[1], encoding='utf-8') as f:
    head_lines = f.readlines()
with open(sys.argv[2], encoding='utf-8') as f:
    our_lines = f.readlines()

# Find differences
diff = list(difflib.unified_diff(head_lines, our_lines, lineterm=''))
print("=== DIFF (HEAD -> OUR) ===")
for line in diff[:50]:
    if line.startswith('+') and not line.startswith('+++'):
        print(f"  +{line[1:]}")
    elif line.startswith('-') and not line.startswith('---'):
        print(f"  -{line[1:]}")
