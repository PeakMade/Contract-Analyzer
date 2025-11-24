# Enhanced Debugging Implementation - COMPLETE

## ✅ What Was Implemented

Added comprehensive debugging to both `text_extractor.py` and `llm_client.py` to diagnose the numbering extraction issue.

## Changes Made

### 1. Enhanced Text Extraction Debugging (`text_extractor.py`)

**New Debug Output:**
- Shows numbering definitions found in document
- Lists first 10 numbered paragraphs during extraction
- Displays extraction summary with statistics
- Checks for common numbering patterns in extracted text
- **Saves full extracted text to `DEBUG_EXTRACTED_TEXT.txt`**

**What You'll See When Running:**
```
======================================================================
TEXT EXTRACTION DEBUG: contract_name.docx
======================================================================
[1/5] Extracting numbering definitions...
      Found X numbering definitions
      
[2/5] Processing paragraphs...
      ✓ Para 2: 1. Section Name
      ✓ Para 4: 2. Another Section
      
[3/5] Processing tables...
      Found X table cells with content
      
[4/5] Extraction Summary:
      Total paragraphs: X
      Numbered paragraphs: X
      Numbering success rate: X%
      
[5/5] Checking for common numbering patterns:
      ✓ '1.' appears X times
      ✓ 'I.' appears X times
      
      💾 Saved full extraction to: DEBUG_EXTRACTED_TEXT.txt
======================================================================
```

### 2. Enhanced AI Analysis Debugging (`llm_client.py`)

**New Debug Output:**
- Shows what text is being sent to the AI
- Checks if numbering exists in the text
- Displays AI's response for each standard
- Shows the location the AI reported

**What You'll See:**
```
[AI DEBUG] Analyzing standard: Confidentiality
[AI DEBUG] Contract text length: 23861 chars
[AI DEBUG] First 500 chars sent to AI: ...
[AI DEBUG] Numbering in text: decimal=True, roman=False, section=True
[AI DEBUG] AI response received: 287 chars
[AI DEBUG] Analysis result for 'Confidentiality':
[AI DEBUG]   - found: True
[AI DEBUG]   - location: '3. Confidentiality and Non-Compete'
[AI DEBUG]   - duration: 2.34s
```

## How to Use

### Step 1: Restart the App
The Flask app should auto-reload with the new code. If not:
```powershell
# Stop the app (Ctrl+C)
# Restart it
python main.py
```

### Step 2: Upload and Analyze a Contract
1. Go to http://localhost:5000
2. Upload a contract
3. Run analysis
4. **Watch the terminal output** for detailed debugging

### Step 3: Check the Debug File
After extraction, you'll find: `DEBUG_EXTRACTED_TEXT.txt`

This file contains:
- Full extraction statistics
- Complete extracted text (exactly what the AI receives)
- You can search this file for section numbers

## What This Reveals

The debugging will show us:

### ✅ If Numbering Definitions Exist
```
Found 5 numbering definitions
```
→ Document uses automatic Word numbering

```
Found 0 numbering definitions
⚠ No numbering definitions found
```
→ Document uses manual numbering OR no numbering

### ✅ If Numbers Are in Extracted Text
```
✓ '1.' appears 12 times
✓ 'I.' appears 3 times
```
→ Numbers ARE in the text (either from automatic extraction or manual typing)

```
✗ '1.' appears 0 times
```
→ Numbers are NOT in the text - extraction problem

### ✅ What the AI Receives
Open `DEBUG_EXTRACTED_TEXT.txt` and you'll see the EXACT text the AI analyzes.

Search for section headings to verify numbering is present.

### ✅ What the AI Reports
```
[AI DEBUG]   - location: '3. Confidentiality and Non-Compete'
```
→ AI found and reported the number correctly

```
[AI DEBUG]   - location: 'Location unclear in document'
```
→ AI couldn't find a numbered heading

## Diagnostic Scenarios

### Scenario 1: "Found 0 numbering definitions" + Numbers ARE in text
**Meaning:** Document uses manually typed numbers (not automatic Word numbering)
**Status:** ✅ Should work fine - numbers are in the text

### Scenario 2: "Found X numbering definitions" + Numbers ARE in text  
**Meaning:** Automatic numbering extraction working correctly
**Status:** ✅ Perfect - our code is working

### Scenario 3: "Found X numbering definitions" + Numbers NOT in text
**Meaning:** Automatic numbering exists but not being extracted
**Status:** ❌ Problem with our extraction code - needs fixing

### Scenario 4: "Found 0 definitions" + Numbers NOT in text
**Meaning:** Document has no numbering at all
**Status:** ⚠️ AI will report "Location unclear" (expected behavior)

## Next Steps Based on Findings

### If Numbers ARE in `DEBUG_EXTRACTED_TEXT.txt`:
→ Problem is with the AI not recognizing them
→ May need to adjust AI prompt
→ Check if format is unusual (e.g., "Section I." vs "1.")

### If Numbers are NOT in `DEBUG_EXTRACTED_TEXT.txt`:
→ Problem is with extraction
→ Need to check if document uses special numbering format
→ May need multi-level numbering support (1.1, 1.2, etc.)

### If AI sees numbers but reports "Location unclear":
→ AI can't match heading to clause
→ Document structure might be non-standard
→ May need to relax AI's heading detection rules

## Testing Your Actual Contract

1. **Upload the contract that showed no numbers**
2. **Watch the terminal carefully** - you'll see detailed extraction logs
3. **Open DEBUG_EXTRACTED_TEXT.txt** after analysis
4. **Search for section names** in the debug file
5. **Report back what you find:**
   - How many numbering definitions were found?
   - Are numbers present in the extracted text?
   - What does the AI report for locations?

## Files Created

- `DEBUG_EXTRACTED_TEXT.txt` - Created every time a contract is extracted
- Contains full extracted text for inspection

## Cleanup

To disable debugging later (once issue is fixed):
- Remove the print statements from `text_extractor.py`
- Remove the print statements from `llm_client.py`
- Or keep them for future troubleshooting

---

**Status:** ✅ Enhanced Debugging Active  
**Next Action:** Analyze a contract and review the debug output
