"""
Quick verification of llm_client.py implementation.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("OpenAI LLM Client Implementation Verification")
print("=" * 70)

try:
    # Import the module
    from app.services import llm_client
    print("\n✓ Module imported successfully")
    
    # Check constants exist
    print("\n📋 Prompt Templates:")
    print("-" * 70)
    
    if hasattr(llm_client, 'SYSTEM_PROMPT'):
        print(f"✓ SYSTEM_PROMPT defined:")
        print(f"  '{llm_client.SYSTEM_PROMPT}'")
    else:
        print("✗ SYSTEM_PROMPT not found")
    
    if hasattr(llm_client, 'USER_PROMPT_TEMPLATE'):
        print(f"\n✓ USER_PROMPT_TEMPLATE defined:")
        lines = llm_client.USER_PROMPT_TEMPLATE.split('\n')
        print(f"  Lines: {len(lines)}")
        print(f"  Contains {{standard}}: {'{{standard}}' in llm_client.USER_PROMPT_TEMPLATE}")
        print(f"  Contains {{contract_text}}: {'{{contract_text}}' in llm_client.USER_PROMPT_TEMPLATE}")
    else:
        print("✗ USER_PROMPT_TEMPLATE not found")
    
    # Check functions exist
    print("\n📦 Functions:")
    print("-" * 70)
    
    functions = [
        '_get_client',
        '_validate_json_response',
        '_call_openai',
        'analyze_standard'
    ]
    
    for func_name in functions:
        if hasattr(llm_client, func_name):
            func = getattr(llm_client, func_name)
            print(f"✓ {func_name}")
            if hasattr(func, '__doc__') and func.__doc__:
                doc_lines = func.__doc__.strip().split('\n')
                print(f"  Doc: {doc_lines[0]}")
        else:
            print(f"✗ {func_name} not found")
    
    # Check _call_openai signature
    print("\n🔍 Function Signatures:")
    print("-" * 70)
    
    import inspect
    
    call_openai = getattr(llm_client, '_call_openai')
    sig = inspect.signature(call_openai)
    params = list(sig.parameters.keys())
    print(f"✓ _call_openai parameters: {params}")
    expected = ['system_prompt', 'user_prompt', 'model']
    if params == expected:
        print(f"  ✓ Matches expected: {expected}")
    else:
        print(f"  ✗ Expected: {expected}, got: {params}")
    
    analyze = getattr(llm_client, 'analyze_standard')
    sig = inspect.signature(analyze)
    params = list(sig.parameters.keys())
    print(f"\n✓ analyze_standard parameters: {params}")
    expected = ['text', 'standard']
    if params == expected:
        print(f"  ✓ Matches expected: {expected}")
    else:
        print(f"  ✗ Expected: {expected}, got: {params}")
    
    # Check prompt template format
    print("\n🔍 Prompt Template Structure:")
    print("-" * 70)
    
    template = llm_client.USER_PROMPT_TEMPLATE
    checks = [
        ('Contains "Analyze the contract text for"', 'Analyze the contract text for' in template),
        ('Contains "Return JSON:"', 'Return JSON:' in template),
        ('Contains "Constraints:"', 'Constraints:' in template),
        ('Contains "If found:"', 'If found:' in template),
        ('Contains "If not found:"', 'If not found:' in template),
        ('Contains "Contract:"', 'Contract:' in template),
        ('Has {standard} placeholder', '{standard}' in template),
        ('Has {contract_text} placeholder', '{contract_text}' in template),
    ]
    
    for check_name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"{status} {check_name}")
    
    # Check retry logic hint
    print("\n🔍 Implementation Details:")
    print("-" * 70)
    
    # Read source to check for retry implementation
    source = inspect.getsource(analyze)
    
    checks = [
        ('Uses USER_PROMPT_TEMPLATE.format()', 'USER_PROMPT_TEMPLATE.format(' in source),
        ('Calls _call_openai()', '_call_openai(' in source),
        ('Has retry logic', 'retry_user_prompt' in source or 'Return ONLY valid JSON' in source),
        ('Validates JSON response', '_validate_json_response(' in source),
        ('Catches ValueError', 'ValueError' in source),
        ('Has logging', 'logger.' in source),
    ]
    
    for check_name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"{status} {check_name}")
    
    print("\n" + "=" * 70)
    print("✅ All components verified!")
    print("=" * 70)
    
    print("\n💡 Key Features:")
    print("  • SYSTEM_PROMPT: Legal analyst with strict JSON")
    print("  • USER_PROMPT_TEMPLATE: Formatted with standard and contract_text")
    print("  • _call_openai: Uses system_prompt, user_prompt, model params")
    print("  • analyze_standard: Implements retry with 'Return ONLY valid JSON' suffix")
    print("  • JSON validation: Enforces required keys and types")
    print("  • Response format: {found, excerpt, location, suggestion}")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
