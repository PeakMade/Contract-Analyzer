# PowerShell Template for Safe File Editing
# Use this template when editing critical files to bypass VS Code caching

param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,
    
    [Parameter(Mandatory=$true)]
    [string]$SearchPattern,
    
    [Parameter(Mandatory=$true)]
    [string]$ReplaceWith,
    
    [switch]$Backup = $true
)

Write-Host "`n=== SAFE FILE EDITOR ===" -ForegroundColor Cyan

# Create backup if requested
if ($Backup) {
    $backupPath = "$FilePath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $FilePath $backupPath
    Write-Host "✓ Backup created: $backupPath" -ForegroundColor Green
}

# Read file content
$content = Get-Content $FilePath -Raw

# Verify pattern exists
if ($content -notmatch [regex]::Escape($SearchPattern)) {
    Write-Host "✗ ERROR: Search pattern not found in file!" -ForegroundColor Red
    Write-Host "Pattern: $SearchPattern" -ForegroundColor Yellow
    exit 1
}

# Perform replacement
$newContent = $content -replace [regex]::Escape($SearchPattern), $ReplaceWith

# Write to file
$newContent | Set-Content $FilePath -NoNewline

# Verify the change was applied
$verifyContent = Get-Content $FilePath -Raw
if ($verifyContent -match [regex]::Escape($ReplaceWith)) {
    Write-Host "✓ File edited successfully" -ForegroundColor Green
    Write-Host "✓ Change verified on disk" -ForegroundColor Green
    
    # Show context around the change
    Write-Host "`n--- Change Preview ---" -ForegroundColor Cyan
    $lines = $verifyContent -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match [regex]::Escape($ReplaceWith)) {
            $start = [Math]::Max(0, $i - 2)
            $end = [Math]::Min($lines.Count - 1, $i + 2)
            for ($j = $start; $j -le $end; $j++) {
                if ($j -eq $i) {
                    Write-Host ">>> $($lines[$j])" -ForegroundColor Green
                } else {
                    Write-Host "    $($lines[$j])"
                }
            }
            break
        }
    }
} else {
    Write-Host "✗ ERROR: Verification failed - change not found on disk!" -ForegroundColor Red
    Write-Host "Restoring from backup..." -ForegroundColor Yellow
    Copy-Item $backupPath $FilePath -Force
    Write-Host "✓ File restored" -ForegroundColor Green
    exit 1
}

Write-Host "`n=== EDIT COMPLETE ===" -ForegroundColor Cyan
