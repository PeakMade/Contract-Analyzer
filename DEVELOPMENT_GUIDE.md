# Development Guide - File Editing Best Practices

## ⚠️ Critical Issue: VS Code AI Tool Cache

### The Problem
The AI file editing tools (`read_file` and `replace_string_in_file`) can cache file content from VS Code's extension, causing them to show different content than what's actually on disk. This can lead to:
- Edits appearing successful but never written to disk
- Hours of debugging "caching" issues in Flask/Python
- Confusion about what code is actually running

**Real Example:** Spent multiple hours debugging "Flask reloader caching" when files simply weren't being edited on disk.

---

## 🛡️ Safe File Editing Protocol

### **Standard Workflow for Critical Edits**

#### **ALWAYS** Use This Verification Sequence:

```powershell
# 1. Read the ACTUAL file from disk BEFORE editing
Get-Content -Path "main.py" -Encoding UTF8 | Select-String -Pattern "function_name" -Context 3,3

# 2. Make your edit using AI tool (replace_string_in_file)
# [AI makes the edit]

# 3. IMMEDIATELY verify edit on disk
Get-Content -Path "main.py" -Encoding UTF8 | Select-String -Pattern "NEW_CODE_PATTERN" -Context 3,3

# 4. If verification fails -> Use safe editing templates instead
```

### **When to Use Safe Editing Templates**

Use `safe_edit.ps1` or `safe_edit_template.py` for:
- ✅ Multi-line function replacements
- ✅ Edits that failed verification
- ✅ Critical production code changes
- ✅ Complex string replacements with special characters

### **When AI Tools Are Safe**

AI tools are generally safe for:
- ✅ Creating new files
- ✅ Reading files (but verify with PowerShell if suspicious)
- ✅ Simple single-line changes (but still verify)
- ✅ Non-critical files (docs, tests, etc.)

---

## 🔧 Safe Editing Tools

### **Option 1: PowerShell Template** (Recommended for simple edits)

```powershell
.\safe_edit.ps1 -FilePath "main.py" -SearchPattern "old_code" -ReplaceWith "new_code"
```

**Features:**
- Automatic timestamped backup
- Pattern verification before edit
- Disk write verification after edit
- Change context preview (5 lines around change)
- Automatic rollback on failure

**Best for:** Simple string replacements, single-line changes

### **Option 2: Python Template** (Recommended for complex edits)

```powershell
python safe_edit_template.py "main.py" "old_code" "new_code"
```

**Features:**
- Object-oriented design for complex operations
- Multi-line editing support
- Custom verification logic
- Programmatic control

**Best for:** Multi-line functions, complex logic changes, batch operations

---

## 📋 Verification Checklist

Before considering any edit complete:

- [ ] **Pre-Edit Check:** Read actual file from disk using PowerShell
- [ ] **Edit Execution:** Make the edit using appropriate tool
- [ ] **Post-Edit Verification:** Confirm change exists on disk using PowerShell
- [ ] **Pattern Match:** Verify new code pattern appears in file
- [ ] **Context Check:** Review surrounding lines for accuracy
- [ ] **Backup Exists:** Confirm backup file created (for safe edit tools)
- [ ] **Git Status:** Check `git diff` to see actual changes
- [ ] **App Test:** Restart Flask/app to test with new code

---

## 🚨 Red Flags - When to Suspect Cache Issues

Watch for these warning signs:
- ⚠️ AI says "I can see the code is..." but PowerShell shows different
- ⚠️ Multiple edit attempts all report "success" with no changes
- ⚠️ Git diff shows no changes after "successful" edit
- ⚠️ Flask/app behavior doesn't match expected code changes
- ⚠️ Read-then-edit cycle shows same content after edit

**Action:** Immediately switch to PowerShell verification + safe edit templates

---

## 💡 Best Practices

### **DO:**
- ✅ Always verify edits with `Get-Content` immediately after
- ✅ Use safe edit templates for production code
- ✅ Create backups before critical edits
- ✅ Check `git diff` to confirm changes
- ✅ Reload VS Code workspace after major edits (Ctrl+Shift+P → "Developer: Reload Window")
- ✅ Use PowerShell for ground truth about file contents

### **DON'T:**
- ❌ Trust AI read_file output without PowerShell verification
- ❌ Make multiple edits without verifying each one
- ❌ Assume Flask "caching" when code doesn't work
- ❌ Skip verification steps to save time
- ❌ Edit production files without backups

---

## 🔍 Debugging File Edit Issues

If edits aren't working:

```powershell
# 1. Check what's ACTUALLY on disk
Get-Content -Path "main.py" -Encoding UTF8

# 2. Check VS Code isn't caching
# Reload Window: Ctrl+Shift+P → "Developer: Reload Window"

# 3. Check git to see what's changed
git diff main.py

# 4. Use safe edit template to force disk write
.\safe_edit.ps1 -FilePath "main.py" -SearchPattern "old" -ReplaceWith "new"

# 5. Verify the change
Get-Content -Path "main.py" -Encoding UTF8 | Select-String -Pattern "new" -Context 2,2
```

---

## 📚 Quick Reference

### **PowerShell Commands**

```powershell
# Read entire file
Get-Content -Path "file.py" -Encoding UTF8

# Search with context
Get-Content -Path "file.py" -Encoding UTF8 | Select-String -Pattern "search_term" -Context 5,5

# Count lines
Get-Content -Path "file.py" | Measure-Object -Line

# Get specific line range
Get-Content -Path "file.py" -Encoding UTF8 | Select-Object -Skip 99 -First 50
```

### **Safe Edit Commands**

```powershell
# PowerShell template
.\safe_edit.ps1 -FilePath "main.py" -SearchPattern "old" -ReplaceWith "new"

# Python template
python safe_edit_template.py "main.py" "old_code" "new_code"
```

### **Git Verification**

```powershell
# See what changed
git diff main.py

# See staged changes
git diff --staged

# See change statistics
git diff --stat
```

---

## 📖 Related Documentation

- `safe_edit.ps1` - PowerShell safe editing template
- `safe_edit_template.py` - Python safe editing template
- `AZURE_DOWNLOAD_FIX.md` - Previous debugging documentation
- `ENHANCED_DEBUGGING_GUIDE.md` - General debugging strategies

---

## 🎯 Success Story

**Problem:** Spent hours debugging "Flask reloader caching" when implementing party name replacement feature. AI reported successful edits but code never changed.

**Root Cause:** VS Code AI tools were cached and not writing to disk.

**Solution:** Created safe edit templates and verification protocol. Now all critical edits are verified immediately.

**Outcome:** Feature implemented successfully, future edits protected by verification protocol.

---

**Remember:** When in doubt, verify with PowerShell. It reads directly from disk and never lies! 🔒
