# Fix render_template party_info parameter
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the malformed render_template call
content = content.replace(
    "        ,`n            party_info=party_info`n        )",
    ",\n            party_info=party_info\n        )"
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Fixed render_template party_info parameter")
