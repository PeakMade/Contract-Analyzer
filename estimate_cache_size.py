"""
Quick script to estimate the size of analysis cache JSON.
"""
import json

# Simulate a typical analysis result for ONE standard
single_standard_result = {
    'found': False,
    'excerpt': None,
    'location': None,
    'suggestion': """Contractor agrees that it shall perform all phases of the services described of this Agreement with the same degree of care, skill and judgment that is customarily exercised by similar contractors in the same industry or profession performing services for projects of similar complexity and scope in similar locations as the Property. Contractor warrants to Owner that the work performed will conform to the Agreement, will be free from defects, and that any materials or equipment used or installed at the Property will be of good quality, in good working condition for the purpose intended under the Agreement and new (unless otherwise required by the Agreement).""",
    'source': 'sharepoint'
}

# A found standard (typically has shorter excerpt/location, no suggestion)
found_standard_result = {
    'found': True,
    'excerpt': 'The Contractor shall maintain comprehensive general liability insurance...',
    'location': 'Section 7.2 - Insurance Requirements',
    'suggestion': None,
    'source': 'sharepoint'
}

# Grammar error (typical)
grammar_error = {
    'type': 'spelling',
    'error_text': 'recieve',
    'location': '...party shall recieve payment within...',
    'suggestion': 'receive',
    'explanation': 'Spelling error detected by Microsoft Word'
}

# Party info
party_info = {
    'found': True,
    'party1': {
        'legal_name': 'ABC Corporation Inc.',
        'defined_as': 'Contractor',
        'location': 'Page 1, Recitals'
    },
    'party2': {
        'legal_name': 'XYZ Management Company LLC',
        'defined_as': 'Customer', 
        'location': 'Page 1, Recitals'
    }
}

# Typical cache data structure
# Assume: 20 standards, 15 missing (with suggestions), 5 found
# Assume: 25 grammar errors
cache_data = {
    'results': {},
    'selected': [
        'Standard of Care', 'Insurance', 'Indemnity', 'Termination', 
        'Confidentiality', 'Independent Contractor', 'Payment Terms',
        'Dispute Resolution', 'Governing Law', 'Force Majeure',
        'Assignment', 'Severability', 'Representations and Warranties',
        'Limitation of Liability', 'Intellectual Property', 'Data Protection',
        'Audit Rights', 'Non-Disclosure', 'Permits and Licenses', 'Emergency Incident Notification'
    ],
    'party_info': party_info,
    'original_party_info': party_info.copy(),
    'grammar': {
        'issues_found': True,
        'error_count': 25,
        'errors': [grammar_error] * 25,  # 25 errors
        'method': 'hybrid',
        'methods_used': ['Word COM', 'GPT'],
        'breakdown': {
            'spelling': 15,
            'grammar': 10
        }
    },
    'ts': '2026-03-09T15:30:00.000000'
}

# Add 15 missing standards (with suggestions) and 5 found standards
for i in range(15):
    cache_data['results'][f'Standard_{i+1}'] = single_standard_result.copy()

for i in range(5):
    cache_data['results'][f'Found_Standard_{i+1}'] = found_standard_result.copy()

# Convert to JSON and measure
json_string = json.dumps(cache_data, indent=2)
json_bytes = json_string.encode('utf-8')

print("="*70)
print("ANALYSIS CACHE SIZE ESTIMATE")
print("="*70)
print(f"\nAssumptions:")
print(f"  - 20 standards analyzed")
print(f"  - 15 missing standards (with full suggestion text ~400 chars each)")
print(f"  - 5 found standards (with excerpt, no suggestion)")
print(f"  - 25 grammar/spelling errors")
print(f"  - Party information included")
print(f"\nResults:")
print(f"  JSON size with formatting: {len(json_string):,} characters")
print(f"  JSON size in bytes: {len(json_bytes):,} bytes")
print(f"  JSON size in KB: {len(json_bytes)/1024:.2f} KB")

# Compact JSON (no indentation)
json_compact = json.dumps(cache_data)
print(f"\nCompact JSON (no formatting):")
print(f"  Size: {len(json_compact):,} characters")
print(f"  Bytes: {len(json_compact.encode('utf-8')):,} bytes")
print(f"  KB: {len(json_compact.encode('utf-8'))/1024:.2f} KB")

print(f"\n" + "="*70)
print("SHAREPOINT FIELD LIMITS")
print("="*70)
print(f"  Multi-line text (plain): 63,999 characters")
print(f"  Multi-line text (rich/enhanced): 63,999 characters")
print(f"  Note field: Can store ~1 MB with proper configuration")
print(f"\nConclusion:")
if len(json_compact) < 63999:
    print(f"  ✅ FITS EASILY in SharePoint multi-line text field")
    print(f"  ({len(json_compact):,} / 63,999 characters = {len(json_compact)/63999*100:.1f}% used)")
else:
    print(f"  ⚠️  May exceed standard SharePoint limit")
    print(f"  Consider using Note field or external storage")

# Show first 500 characters as preview
print(f"\n" + "="*70)
print("JSON PREVIEW (first 500 chars)")
print("="*70)
print(json_string[:500] + "...")
