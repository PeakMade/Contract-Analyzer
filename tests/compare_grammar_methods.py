"""
Compare Word COM vs GPT grammar checking methods side-by-side.
Useful for testing and comparing results on your contracts.
"""
import sys
import os
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def compare_methods(file_path: str):
    """
    Run both grammar checking methods on the same document and compare results.
    
    Args:
        file_path: Path to .docx file to analyze
    """
    print("="*80)
    print("GRAMMAR CHECK METHOD COMPARISON")
    print("="*80)
    print(f"Document: {file_path}")
    print()
    
    # Verify file exists
    if not os.path.exists(file_path):
        print(f"❌ ERROR: File not found: {file_path}")
        return
    
    # Extract text for GPT method
    print("Step 1: Extracting text from document...")
    try:
        from app.services.text_extractor import extract_text
        text = extract_text(file_path)
        print(f"✓ Extracted {len(text):,} characters")
        if len(text) > 20000:
            print(f"  ⚠️ Note: GPT will only analyze first 20,000 characters")
    except Exception as e:
        print(f"❌ Failed to extract text: {e}")
        return
    
    # Method 1: Word COM API
    print("\n" + "-"*80)
    print("METHOD 1: Microsoft Word COM API")
    print("-"*80)
    
    word_result = None
    word_time = None
    
    try:
        from app.services.word_grammar_checker import check_spelling_grammar_with_word, is_word_com_available
        
        if not is_word_com_available():
            print("⚠️ Word COM API not available (Microsoft Word not installed)")
            print("   Skipping Word COM test...")
        else:
            print("Running Word COM grammar check...")
            start_time = time.time()
            word_result = check_spelling_grammar_with_word(file_path)
            word_time = time.time() - start_time
            
            print(f"\n✓ Word COM Results:")
            print(f"   Method: {word_result.get('method', 'unknown')}")
            print(f"   Duration: {word_time:.2f} seconds")
            print(f"   Issues found: {word_result.get('issues_found', False)}")
            print(f"   Error count: {word_result.get('error_count', 0)}")
            
            if word_result.get('raw_counts'):
                raw = word_result['raw_counts']
                print(f"   - Spelling errors: {raw.get('spelling', 0)}")
                print(f"   - Grammar errors: {raw.get('grammar', 0)}")
                print(f"   - Processed: {raw.get('processed', 0)} (max 50)")
            
            if word_result.get('error_message'):
                print(f"   ⚠️ Error: {word_result['error_message']}")
    
    except ImportError:
        print("⚠️ pywin32 not installed - cannot test Word COM")
        print("   Install with: pip install pywin32")
    except Exception as e:
        print(f"❌ Word COM test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 2: GPT
    print("\n" + "-"*80)
    print("METHOD 2: OpenAI GPT-4o-mini")
    print("-"*80)
    
    gpt_result = None
    gpt_time = None
    
    try:
        from app.services.llm_client import check_spelling_grammar
        
        print("Running GPT grammar check...")
        start_time = time.time()
        gpt_result = check_spelling_grammar(text)
        gpt_time = time.time() - start_time
        
        print(f"\n✓ GPT Results:")
        print(f"   Method: {gpt_result.get('method', 'unknown')}")
        print(f"   Duration: {gpt_time:.2f} seconds")
        print(f"   Issues found: {gpt_result.get('issues_found', False)}")
        print(f"   Error count: {gpt_result.get('error_count', 0)}")
        print(f"   Characters analyzed: {len(text[:20000]):,}")
        
        if gpt_result.get('error_message'):
            print(f"   ⚠️ Error: {gpt_result['error_message']}")
    
    except Exception as e:
        print(f"❌ GPT test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Comparison Summary
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    
    if word_result and gpt_result:
        print(f"\n{'Metric':<30} {'Word COM':<20} {'GPT':<20}")
        print("-"*80)
        print(f"{'Duration':<30} {f'{word_time:.2f}s':<20} {f'{gpt_time:.2f}s':<20}")
        print(f"{'Errors Found':<30} {word_result.get('error_count', 0):<20} {gpt_result.get('error_count', 0):<20}")
        print(f"{'Method Status':<30} {word_result.get('method', 'unknown'):<20} {gpt_result.get('method', 'unknown'):<20}")
        
        # Speed comparison
        if word_time and gpt_time:
            faster = "Word COM" if word_time < gpt_time else "GPT"
            speedup = max(word_time, gpt_time) / min(word_time, gpt_time)
            print(f"\n⚡ Speed: {faster} is {speedup:.1f}x faster")
        
        # Cost estimate
        print(f"\n💰 Cost Estimate:")
        print(f"   Word COM: $0.00 (free)")
        print(f"   GPT: ~$0.10-0.20 (API call)")
        
    elif word_result:
        print("\n✓ Word COM available - this is the recommended method")
        print("  - Zero cost")
        print("  - No character limits")
        print("  - Fast processing")
        
    elif gpt_result:
        print("\n⚠️ Only GPT available")
        print("  - API costs apply (~$0.10-0.20 per check)")
        print("  - Limited to 20,000 characters")
        print("  - Consider installing Microsoft Word for free checking")
    
    # Sample errors comparison
    if word_result and gpt_result:
        if word_result.get('errors') or gpt_result.get('errors'):
            print("\n" + "="*80)
            print("SAMPLE ERRORS (First 3 from each method)")
            print("="*80)
            
            print("\n📝 Word COM Errors:")
            if word_result.get('errors'):
                for i, err in enumerate(word_result['errors'][:3], 1):
                    print(f"\n  {i}. {err.get('type', 'unknown').upper()}")
                    print(f"     Error: {err.get('error_text', 'N/A')[:60]}")
                    print(f"     Suggestion: {err.get('suggestion', 'N/A')[:60]}")
            else:
                print("  No errors found")
            
            print("\n🤖 GPT Errors:")
            if gpt_result.get('errors'):
                for i, err in enumerate(gpt_result['errors'][:3], 1):
                    print(f"\n  {i}. {err.get('type', 'unknown').upper()}")
                    print(f"     Error: {err.get('error_text', 'N/A')[:60]}")
                    print(f"     Suggestion: {err.get('suggestion', 'N/A')[:60]}")
                    print(f"     Explanation: {err.get('explanation', 'N/A')[:60]}")
            else:
                print("  No errors found")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python compare_grammar_methods.py <path_to_docx_file>")
        print("\nExample:")
        print("  python compare_grammar_methods.py \"C:/contracts/sample.docx\"")
        sys.exit(1)
    
    file_path = sys.argv[1]
    compare_methods(file_path)
