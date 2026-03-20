# Grammar Checker Testing Guide

## Quick Test Commands

### Test 1: Compare Both Methods on a Contract
```powershell
python tests/compare_grammar_methods.py "path\to\your\contract.docx"
```

Example:
```powershell
python tests/compare_grammar_methods.py "Z:\Shared\Technology\AI Projects\Contract Analyzer\tests\sample_contract.docx"
```

This will run **both** Word COM and GPT on the same file and show you:
- Speed comparison
- Error count comparison  
- Sample errors from each
- Cost estimate

---

### Test 2: Force Specific Method in Web App

#### Use Word COM (if available):
```powershell
# Set in PowerShell before running app
$env:GRAMMAR_CHECK_METHOD = "word_com"
python main.py
```

#### Use GPT only:
```powershell
# Set in PowerShell before running app
$env:GRAMMAR_CHECK_METHOD = "gpt"
python main.py
```

#### Use Auto (default - tries Word COM first, falls back to GPT):
```powershell
# Set in PowerShell before running app
$env:GRAMMAR_CHECK_METHOD = "auto"
python main.py
```

Or edit `.env` file:
```env
GRAMMAR_CHECK_METHOD=word_com   # Force Word COM
# OR
GRAMMAR_CHECK_METHOD=gpt        # Force GPT
# OR
GRAMMAR_CHECK_METHOD=auto       # Auto select (default)
```

---

### Test 3: Check Word COM Availability
```powershell
python tests/test_word_com.py
```

This verifies:
- Is Microsoft Word installed?
- Can pywin32 access Word?
- Does grammar checking work?

---

## Where to See Method Used

After running analysis, on the **Apply Suggestions** page:

1. Scroll to **"Spelling & Grammar Check"** section (pink header)
2. Click to expand the section
3. Look at the header - you'll see:
   - **(Microsoft Word)** - if Word COM was used
   - **(AI-Powered)** - if GPT was used

---

## Testing Workflow

### Step 1: Baseline Test (GPT)
```powershell
# Force GPT to establish baseline
$env:GRAMMAR_CHECK_METHOD = "gpt"
python main.py
```
1. Upload a contract
2. Select standards and analyze
3. Note: error count, types, and suggestions
4. Check terminal output for timing

### Step 2: Test Word COM
```powershell
# Force Word COM
$env:GRAMMAR_CHECK_METHOD = "word_com"
python main.py
```
1. Analyze same contract
2. Compare: error count, types, and suggestions
3. Check terminal output for timing
4. Note any differences

### Step 3: Compare Side-by-Side
```powershell
# Use comparison script
python tests/compare_grammar_methods.py "path\to\contract.docx"
```
Review the detailed comparison report

---

## Expected Results

### Word COM:
- ✅ Faster (1-2 seconds)
- ✅ Free (no API costs)
- ✅ Good at spelling errors
- ⚠️ Basic grammar detection
- ⚠️ No grammar suggestions (only flags issues)

### GPT:
- ✅ Context-aware grammar checking
- ✅ Provides detailed explanations
- ✅ Suggests corrections for everything
- ✅ Understands legal terminology
- ⚠️ Slower (3-5 seconds)
- ⚠️ Costs ~$0.10-0.20 per check
- ⚠️ Limited to 20,000 characters

---

## Troubleshooting

### Word COM shows as unavailable
- Verify Microsoft Word is installed
- Run: `python tests/test_word_com.py`
- Check pywin32 installation: `pip show pywin32`

### GPT not working
- Check `OPENAI_API_KEY` in `.env`
- Verify internet connection
- Check OpenAI API quota/billing

### UI not showing method badge
- Refresh the page after setting environment variable
- Check browser console for errors
- Verify `grammar_results.method` in template

---

## Recommendation

For **production deployment**:
- Use `GRAMMAR_CHECK_METHOD=auto` (default)
- Ensures Word COM is used when available
- Automatic GPT fallback if Word unavailable
- Best of both worlds

For **testing/comparison**:
- Force each method individually
- Compare results on your actual contracts
- Document any significant differences
