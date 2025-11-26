# Party Override Feature - Implementation Summary

## Feature Overview
Added an "Edit Parties" button on the contract analysis results page that allows users to override/edit party information detected by AI. Changes apply immediately to all suggestions and persist through document generation.

## Implementation Date
November 26, 2025

## User Experience

### Location
Results page (`/apply_suggestions_new/<contract_id>`), next to the party information display

### Workflow
1. User views contract analysis results with AI-detected parties
2. Clicks "Edit Parties" button next to party information
3. Modal dialog opens with editable fields:
   - Party 1: Legal Name, Defined As, Role (Contractor/Customer)
   - Party 2: Legal Name, Defined As, Role (Contractor/Customer)
4. User edits values and clicks "Apply Changes"
5. AJAX call updates cache with new party information
6. Page automatically reloads with updated suggestions
7. All instances of "Contractor" and "Customer" now reflect the new party names

### Additional Features
- **Reset Button**: "Reset to AI Detection" button restores original AI-detected values
- **Validation**: All fields are required before submission
- **Loading State**: Button shows spinner during update
- **Persistence**: Changes persist for cache lifetime (30 minutes)

## Technical Implementation

### Files Modified

#### 1. `app/templates/apply_suggestions.html`
**Changes:**
- Added "Edit Parties" button next to party information display (line ~28)
- Added Bootstrap modal with form fields for editing party information (lines ~248-318)
- Added JavaScript for party override functionality (lines ~320-391)
  - AJAX submission to update API endpoint
  - Form validation
  - Loading states
  - Reset functionality
  - Page reload after successful update

**Button Code:**
```html
<button type="button" class="btn btn-sm btn-outline-primary ms-2" 
        data-bs-toggle="modal" data-bs-target="#editPartiesModal">
    <i class="bi bi-pencil"></i> Edit Parties
</button>
```

#### 2. `main.py`
**Changes:**
- Added new API route: `/api/contract/<contract_id>/update-parties` (POST)
- Route validates party information structure
- Updates `party_info` in analysis cache
- Maintains cache TTL (30 minutes)
- Returns success/error JSON response

**Route Location:** Line ~656 (before `apply_suggestions_new` route)

### Data Flow

```
User Input (Modal Form)
    ↓
JavaScript (AJAX POST)
    ↓
Flask Route: /api/contract/<contract_id>/update-parties
    ↓
Validate Party Info Structure
    ↓
Retrieve Cached Analysis Data
    ↓
Update party_info in Cache
    ↓
Save to Cache (TTL: 1800s)
    ↓
Return Success JSON
    ↓
Page Reload
    ↓
apply_suggestions_new() Route
    ↓
Retrieve Updated Party Info from Cache
    ↓
transform_suggestions() with New Party Names
    ↓
Render Template with Updated Suggestions
```

### Cache Structure

```python
cached_data = {
    'results': {...},           # AI analysis results
    'selected': [...],          # Selected standards
    'party_info': {             # ← Updated by override feature
        'found': True,
        'party1': {
            'legal_name': 'New Name 1',
            'defined_as': 'Contractor',
            'role': 'contractor'
        },
        'party2': {
            'legal_name': 'New Name 2',
            'defined_as': 'Customer',
            'role': 'customer'
        }
    },
    'ts': '2025-11-26T...'     # Timestamp
}
```

## API Endpoint Details

### Route
`POST /api/contract/<contract_id>/update-parties`

### Authentication
Requires `@login_required` decorator

### Request Body
```json
{
    "found": true,
    "party1": {
        "legal_name": "ABC Company",
        "defined_as": "Contractor",
        "role": "contractor"
    },
    "party2": {
        "legal_name": "XYZ Corporation",
        "defined_as": "Customer",
        "role": "customer"
    }
}
```

### Response (Success)
```json
{
    "success": true,
    "message": "Party information updated successfully"
}
```

### Response (Error)
```json
{
    "success": false,
    "error": "Error message"
}
```

### Status Codes
- `200`: Success
- `400`: Invalid party information or missing data
- `404`: No analysis found in cache
- `500`: Server error

## Integration Points

### Existing Features
- **Party Detection** (`app/services/llm_client.py`): AI detection still runs, override only changes cache
- **Party Replacement** (`app/utils/party_replacer.py`): Uses updated party info automatically
- **Document Generation** (`apply_suggestions_action` route): Applies party replacement before editing document

### Automatic Behaviors
1. Page reload fetches updated party info from cache
2. `transform_suggestions()` automatically called with new party info
3. Document download uses updated party names
4. Cache expiration (30 min) resets to AI-detected values

## Design Decisions

### Temporary Storage (Not Persistent)
- **Rationale**: Override is workflow-specific, not a contract attribute
- **Duration**: 30 minutes (cache TTL)
- **Benefit**: No database schema changes, cleaner data model

### No Activity Logging
- **Rationale**: Temporary change, not business-critical event
- **Alternative**: Could add logging if audit trail needed

### Role Options: Contractor/Customer
- **Options**: "Contractor" and "Customer"
- **Mapping**: Maps to existing party replacement logic
- **Display**: Capitalized in UI (Title case)

### Reset Functionality
- **Purpose**: Revert to AI-detected values
- **Implementation**: Stores original `party_info` in JavaScript variable
- **Behavior**: Restores form fields and triggers save

## Testing Checklist

- [ ] Edit Parties button appears when parties detected
- [ ] Modal opens with correct party information
- [ ] All form fields are editable
- [ ] Role dropdown shows Contractor/Customer options
- [ ] Form validation works (required fields)
- [ ] Apply Changes updates cache via API
- [ ] Page reloads with updated suggestions
- [ ] Suggestions reflect new party names
- [ ] Downloaded document uses new party names
- [ ] Reset button restores AI-detected values
- [ ] Error handling for network failures
- [ ] Loading states display correctly
- [ ] No console errors

## Future Enhancements (Optional)

1. **Persistent Override**: Store in SharePoint list if needed
2. **Activity Logging**: Log party overrides for audit trail
3. **Bulk Edit**: Edit multiple contracts' parties at once
4. **Party History**: Track changes over time
5. **Smart Suggestions**: Suggest party names from previous contracts
6. **Role Customization**: Allow custom role labels beyond Contractor/Customer

## Known Limitations

1. **Cache Expiration**: Changes lost after 30 minutes (by design)
2. **Session-Specific**: Changes not shared across users/sessions
3. **No Validation**: Doesn't verify party names against contract text
4. **Single Contract**: Must edit each contract individually

## Dependencies

- **Frontend**: Bootstrap 5 (modals), Bootstrap Icons
- **Backend**: Flask, existing cache infrastructure
- **JavaScript**: Fetch API, ES6 syntax

## Compatibility

- **Browsers**: Modern browsers with ES6 support
- **Python**: 3.8+ (f-string, type hints)
- **Flask**: Existing version (no changes required)

## Rollback Plan

If issues arise, revert these changes:
1. Remove "Edit Parties" button from template
2. Remove modal HTML from template
3. Remove JavaScript party override code
4. Remove `/api/contract/<contract_id>/update-parties` route from `main.py`

Files to revert:
- `app/templates/apply_suggestions.html`
- `main.py`

## Success Metrics

- Users successfully override incorrect AI party detection
- Suggestions update with correct party names
- Downloaded documents reflect accurate party information
- No increase in support requests about party names

---

**Implementation Status**: ✅ Complete
**Tested**: Pending user acceptance testing
**Deployed**: Pending Flask restart
