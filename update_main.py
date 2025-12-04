"""
Script to properly update main.py with party replacement functionality
"""

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with timestamp extraction
for i, line in enumerate(lines):
    # Add party_info extraction after selected_standards line
    if "selected_standards = cached_data.get('selected', [])" in line:
        lines.insert(i + 1, "        party_info = cached_data.get('party_info', {'found': False})\n")
        break

# Find the line before "Rendering apply_suggestions"
for i, line in enumerate(lines):
    if 'print(f"Rendering apply_suggestions with {len(summary_items)} items")' in line:
        # Insert party replacement logic before this line
        insert_lines = [
            "\n",
            "        # Transform suggestions with actual party names\n",
            "        from app.utils.party_replacer import transform_suggestions\n",
            "        summary_items = transform_suggestions(summary_items, party_info)\n",
            "        print(f\"[DEBUG] Party replacement applied\")\n",
            "\n"
        ]
        for j, insert_line in enumerate(insert_lines):
            lines.insert(i + j, insert_line)
        break

# Find render_template call and add party_info parameter
for i, line in enumerate(lines):
    if 'timestamp=timestamp' in line and 'render_template' in lines[i-4]:
        # This is the last parameter line, add party_info
        lines[i] = line.rstrip().rstrip(')') + ',\n'
        lines.insert(i + 1, '            party_info=party_info\n')
        lines.insert(i + 2, '        )\n')
        break

# Find apply_suggestions_action and add party replacement
for i, line in enumerate(lines):
    if 'print(f"  [{i+1}] {item.get(\'standard\', \'N/A\')[:40]}...")' in line:
        # Insert party replacement logic after this block
        insert_lines = [
            "\n",
            "        # Get party info from cache for party replacement\n",
            "        cached_data = analysis_cache.get(contract_id)\n",
            "        party_info = cached_data.get('party_info', {'found': False}) if cached_data else {'found': False}\n",
            "        from app.utils.party_replacer import transform_suggestions\n",
            "        items = transform_suggestions(items, party_info)\n",
            "        print(f\"[DEBUG] Party replacement applied to document suggestions\")\n",
            "\n"
        ]
        for j, insert_line in enumerate(insert_lines):
            lines.insert(i + 1 + j, insert_line)
        break

# Write back
with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✓ main.py updated successfully")
