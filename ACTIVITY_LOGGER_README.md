# Activity Logger - Quick Reference

## Overview
The Activity Logger automatically logs user activities to SharePoint for auditing and tracking purposes.

## SharePoint Configuration

**List Name:** Contract Analyzer Log  
**List ID:** `f3ccd59d-1497-42a0-985f-6faa7fa6e226`

### Fields (Column Names in SharePoint)
- **UserEmail** (Single line of text) - User's email address
- **UserDisplayName** (Single line of text) - User's full name
- **Contract Name** (Single line of text) - Name of the contract being analyzed
- **TimeofAnalysis** (Date and Time) - Timestamp of when the analysis occurred
- **AnalysisSuccessorFail** (Single line of text) - Status: "Success" or "Fail"

## Environment Variable

Add to `.env` file:
```
SP_LOG_LIST_ID=f3ccd59d-1497-42a0-985f-6faa7fa6e226
```

## Usage in Code

### Import
```python
from app.services.activity_logger import logger as activity_logger
```

### Log Successful Analysis
```python
activity_logger.log_analysis_success(
    contract_name="Sample Contract.pdf",
    user_email="user@example.com",  # Optional - defaults to session user
    user_display_name="John Doe"     # Optional - defaults to session user
)
```

### Log Failed Analysis
```python
activity_logger.log_analysis_failure(
    contract_name="Sample Contract.pdf"
)
```

### Log In-Progress Analysis (Optional)
```python
activity_logger.log_analysis_start(
    contract_name="Sample Contract.pdf"
)
```

## Current Implementation

Activity logging is automatically triggered in `main.py` at:

1. **Successful Analysis** - After AI analysis completes successfully
2. **Failed Analysis** - When any exception occurs during analysis

No manual intervention needed - logging happens automatically!

## Testing

Run the test script to verify logging is working:

```bash
python tests/test_activity_logger.py
```

This will:
- Check environment configuration
- Create a test log entry in SharePoint
- Verify the entry was created successfully

## Troubleshooting

If logging fails, check:
1. **Environment Variable** - Ensure `SP_LOG_LIST_ID` is set in `.env`
2. **SharePoint Permissions** - App must have write access to the list
3. **Field Names** - Ensure SharePoint column names match exactly:
   - `UserEmail`
   - `UserDisplayName`
   - `Contract_x0020_Name` (SharePoint encodes spaces as `_x0020_`)
   - `TimeofAnalysis`
   - `AnalysisSuccessorFail`
4. **Access Token** - Verify the app can authenticate to SharePoint

## Field Name Encoding

SharePoint automatically encodes certain characters in internal field names:
- Space → `_x0020_`
- Example: "Contract Name" becomes "Contract_x0020_Name"

The logger handles this encoding automatically.

## Future Enhancements

Consider adding logging for:
- User logins/logouts
- Contract uploads
- Standards selection
- Document downloads
- Settings changes
