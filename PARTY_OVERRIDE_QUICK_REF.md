# Party Override Feature - Quick Reference

## 🎯 What It Does
Allows you to manually correct party names detected by AI on the results page.

## 📍 Where to Find It
**Results Page** → Next to party information → **[Edit Parties]** button

## 🔄 How to Use

### Step 1: Review AI-Detected Parties
On the results page, you'll see:
```
Parties: Phonesuite (Contractor) and Partner Hotel (Customer) [Edit Parties]
```

### Step 2: Click "Edit Parties" Button
Modal opens with editable fields:
- Party 1: Legal Name, Defined As, Role
- Party 2: Legal Name, Defined As, Role

### Step 3: Edit Party Information
**Example:**
- Change "Phonesuite" → "HIS Corporation"
- Change "Partner Hotel" → "ABC Hotels Inc"
- Adjust roles if needed (Contractor ↔ Customer)

### Step 4: Apply Changes
Click **"Apply Changes"** → Page reloads → Suggestions updated!

### Step 5: Download Document
When you click "Apply Selected", the downloaded document will use your corrected party names.

## 🔁 Reset to AI Detection
Changed your mind? Click **"Reset to AI Detection"** to restore the original AI-detected values.

## ⏱️ How Long Do Changes Last?
**30 minutes** (cache lifetime) - Perfect for completing your review and downloading the document!

## ✨ What Gets Updated
- ✅ All suggestion text (replaces "Contractor" and "Customer")
- ✅ Party display at top of page
- ✅ Downloaded Word document
- ✅ Both results page AND document generation

## 💡 Common Use Cases

### AI Got Party Names Wrong
**Before:** "ABC Corp (Contractor) and XYZ Inc (Customer)"
**After:** Click Edit → Fix names → Apply → All suggestions update

### AI Detected Short Names
**Before:** "HIS (Contractor)"
**After:** Edit to "HIS Corporation" for clarity

### Role Reversal
**Before:** AI thinks Party A is Customer but they're actually Contractor
**After:** Swap roles in modal → Apply

## ⚠️ Important Notes

1. **Temporary**: Changes expire after 30 minutes (enough time to complete your work)
2. **Page-Specific**: Each contract analysis has its own override
3. **Auto-Reload**: Page refreshes after applying changes to show updated suggestions
4. **Required Fields**: All fields must be filled out

## 🚨 Troubleshooting

### "Edit Parties" button doesn't appear
→ AI didn't detect parties in this contract

### Changes don't show after Apply
→ Check browser console (F12) for errors
→ Ensure Flask is running

### Changes disappeared
→ Cache expired (30 min) or session ended
→ Simply edit parties again!

## 🎓 Pro Tips

1. **Preview First**: Review AI suggestions before editing parties
2. **Quick Fix**: If only one party name is wrong, just change that one
3. **Full Names**: Use complete legal names for clarity in documents
4. **Role Check**: Verify roles match who provides vs receives services
5. **Reset Safety**: Use Reset button if you make a mistake

---

**Need Help?** Check `PARTY_OVERRIDE_FEATURE.md` for full technical documentation.
