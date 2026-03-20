# Grammar Check Configuration

## Overview
The Contract Analyzer uses a **HYBRID APPROACH** combining the best of both methods:

### Default: Hybrid Mode (Recommended)
- **Microsoft Word COM API** for spelling errors
  - Fast, free, accurate spelling detection
  - Zero API costs
  - Local processing
  
- **OpenAI GPT-4o-mini** for grammar errors  
  - Context-aware grammar checking
  - Legal document expertise
  - Excludes valid legal conventions (all-caps, defined terms)
  - ~$0.05-0.10 per analysis (grammar only)

### Why Hybrid?
Word COM is excellent at spelling but flags legal conventions as grammar errors (e.g., ALL-CAPS defined terms, legal paragraph numbering). GPT with legal context provides better grammar checking for contracts while Word handles spelling more accurately and for free.

## Installation

### Install pywin32 (for Word COM API)
```powershell
pip install -r requirements.txt
```

This will install `pywin32==306` which enables Word COM API support.

### Post-Install Script (Windows)
After installing pywin32, run the post-install script:
```powershell
python C:\Python3X\Scripts\pywin32_postinstall.py -install
```

### Verify Word COM API Availability
Run this test:
```python
from app.services.word_grammar_checker import is_word_com_available
print(f"Word COM available: {is_word_com_available()}")
```

## Configuration

### Environment Variable: `GRAMMAR_CHECK_METHOD`

Control which grammar checking method to use:

```env
# Hybrid mode (default): Word COM spelling + GPT grammar
GRAMMAR_CHECK_METHOD=auto

# Force Word COM only for spelling (legacy - no grammar check)
GRAMMAR_CHECK_METHOD=word_com

# Force GPT only for both spelling and grammar (legacy)
GRAMMAR_CHECK_METHOD=gpt
```

Add this to your `.env` file or set as system environment variable.

## Behavior

### Hybrid Mode (Default - Recommended)
1. Word COM checks for spelling errors (up to 50 errors)
2. GPT checks for grammar errors with legal context (up to 40 errors)
3. Results are merged and displayed together
4. Spelling: Free, fast, accurate
5. Grammar: Legal-aware, excludes defined terms and legal conventions

### Word COM Only Mode (Legacy)
- Only spelling errors detected
- Grammar checking disabled
- Use when you want manual grammar review

### GPT Only Mode (Legacy)
- Both spelling and grammar checked by GPT
- Higher cost (~$0.10-0.20 per analysis)
- Use when Word is not available

## UI Indicators

The results page shows which method was used:
- **(Hybrid: Word + AI)** - Default hybrid mode
- **(Microsoft Word)** - Word COM only (legacy)
- **(AI-Powered)** - GPT only (legacy)

## Legal Context Features (GPT Grammar)

The GPT grammar checker is specifically tuned for legal contracts:
- **Excludes**: ALL-CAPS text, defined terms in quotes, legal jargon
- **Focuses on**: True grammar errors (subject-verb agreement, tense, structure)
- **Understands**: Legal paragraph numbering (e.g., "Section 5.1 states...")
- **Persona**: Professional legal contract reviewer

## Troubleshooting

### Word COM fails with "Dispatch failed"
- Ensure Microsoft Word is installed
- Run pywin32 post-install script
- Check that Word is not running with admin privileges if your app isn't
- Verify pywin32 is properly installed: `pip show pywin32`

### Seeing all-caps terms flagged as errors
- This should not happen in hybrid mode (GPT excludes all-caps)
- If using Word COM only mode, switch to hybrid mode

### Want to force GPT only
- Set `GRAMMAR_CHECK_METHOD=gpt` in environment
- Useful for testing or if Word has compatibility issues

## Cost Comparison

| Method | Spelling Cost | Grammar Cost | Total Cost | Speed | Best For |
|--------|---------------|--------------|------------|-------|----------|
| **Hybrid (Default)** | $0.00 (Word) | ~$0.05-0.10 (GPT) | ~$0.05-0.10 | ~3-4 sec | Production - Best accuracy + cost balance |
| Word COM Only | $0.00 (Word) | $0.00 (none) | $0.00 | ~1-2 sec | Cost-critical, manual grammar review |
| GPT Only | ~$0.05-0.10 (GPT) | ~$0.05-0.10 (GPT) | ~$0.10-0.20 | ~3-5 sec | No Word available, full AI analysis |

**Recommendation:** Use Hybrid mode (default) for production - combines free, accurate spelling with legal-aware grammar checking.
