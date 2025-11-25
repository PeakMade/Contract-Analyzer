"""
Party name replacement utility for personalizing contract suggestions.

Replaces generic terms (Contractor, Customer) with actual party names
detected in the contract.
"""

import re
from typing import Dict, Optional


def replace_party_terms(text: str, party_info: Dict) -> str:
    """
    Replace generic party terms with actual party names from contract.
    
    Args:
        text: Suggestion text containing "Contractor" and/or "Customer"
        party_info: Dictionary with party1/party2 info including 'role' and 'defined_as'
        
    Returns:
        Text with party terms replaced
        
    Example:
        party_info = {
            'party1': {'defined_as': 'HIS', 'role': 'contractor'},
            'party2': {'defined_as': 'Partner', 'role': 'customer'},
            'found': True
        }
        
        Input: "Contractor shall notify Customer within 30 days."
        Output: "HIS shall notify Partner within 30 days."
    """
    print(f"\n[replace_party_terms] Called with:")
    print(f"  text length: {len(text) if text else 0}")
    print(f"  party_info: {party_info}")
    
    # Fallback: if party detection failed, return original text
    if not party_info or not party_info.get('found'):
        print(f"[replace_party_terms] Party detection failed or not found, returning original")
        return text
    
    party1 = party_info.get('party1', {})
    party2 = party_info.get('party2', {})
    
    # Determine which party is contractor and which is customer
    contractor_name = None
    customer_name = None
    
    print(f"[replace_party_terms] Determining roles...")
    print(f"  party1: {party1}")
    print(f"  party2: {party2}")
    
    if party1.get('role') == 'contractor':
        contractor_name = party1.get('defined_as')
        print(f"  ✓ party1 is contractor: {contractor_name}")
    elif party1.get('role') == 'customer':
        customer_name = party1.get('defined_as')
        print(f"  ✓ party1 is customer: {customer_name}")
    
    if party2.get('role') == 'contractor':
        contractor_name = party2.get('defined_as')
        print(f"  ✓ party2 is contractor: {contractor_name}")
    elif party2.get('role') == 'customer':
        customer_name = party2.get('defined_as')
        print(f"  ✓ party2 is customer: {customer_name}")
    
    print(f"[replace_party_terms] Final determination:")
    print(f"  contractor_name: {contractor_name}")
    print(f"  customer_name: {customer_name}")
    
    # Fallback: if roles not determined, return original
    if not contractor_name and not customer_name:
        print(f"[replace_party_terms] No roles determined, returning original")
        return text
    
    # Replace Contractor terms (case-insensitive, all occurrences)
    if contractor_name:
        # Handle possessive forms: Contractor's → HIS's or HIS'
        # Use HIS' if name already ends with 's', otherwise add 's
        contractor_possessive = f"{contractor_name}'" if contractor_name.endswith('s') else f"{contractor_name}'s"
        
        # Replace "Contractor's" (case-insensitive)
        text = re.sub(
            r'\bContractor\'s\b',
            contractor_possessive,
            text,
            flags=re.IGNORECASE
        )
        
        # Replace "Contractor" (case-insensitive)
        text = re.sub(
            r'\bContractor\b',
            contractor_name,
            text,
            flags=re.IGNORECASE
        )
    
    # Replace Customer terms (case-insensitive, all occurrences)
    if customer_name:
        # Handle possessive forms: Customer's → Partner's or Partner'
        customer_possessive = f"{customer_name}'" if customer_name.endswith('s') else f"{customer_name}'s"
        
        print(f"[replace_party_terms] Replacing Customer with {customer_name}")
        
        # Replace "Customer's" (case-insensitive)
        text = re.sub(
            r'\bCustomer\'s\b',
            customer_possessive,
            text,
            flags=re.IGNORECASE
        )
        
        # Replace "Customer" (case-insensitive)
        text = re.sub(
            r'\bCustomer\b',
            customer_name,
            text,
            flags=re.IGNORECASE
        )
    
    print(f"[replace_party_terms] Replacement complete, returning text (length: {len(text)})")
    return text


def transform_suggestions(items: list, party_info: Dict) -> list:
    """
    Transform a list of suggestion items by replacing party terms.
    
    Args:
        items: List of dicts with 'suggestion' key
        party_info: Party information dictionary
        
    Returns:
        New list with transformed suggestions
    """
    print(f"\n[transform_suggestions] Called with {len(items)} items")
    print(f"[transform_suggestions] party_info: {party_info}")
    
    if not party_info or not party_info.get('found'):
        print(f"[transform_suggestions] Party info not found, returning items unchanged")
        return items
    
    print(f"[transform_suggestions] Processing items...")
    transformed = []
    for i, item in enumerate(items):
        new_item = item.copy()
        if 'suggestion' in new_item and new_item['suggestion']:
            print(f"\n[transform_suggestions] Item {i+1}/{len(items)}: {new_item.get('standard', 'Unknown')}")
            original_suggestion = new_item['suggestion']
            new_item['suggestion'] = replace_party_terms(new_item['suggestion'], party_info)
            if original_suggestion != new_item['suggestion']:
                print(f"  ✓ Suggestion was modified")
            else:
                print(f"  - Suggestion unchanged (no Contractor/Customer terms found)")
        transformed.append(new_item)
    
    print(f"[transform_suggestions] Returning {len(transformed)} transformed items\n")
    return transformed
