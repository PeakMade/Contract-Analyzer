"""
Python Template for Safe File Editing
Use this for complex multi-line edits or when PowerShell regex gets tricky
"""

import sys
import shutil
from datetime import datetime
from pathlib import Path


class SafeFileEditor:
    """Safe file editor with automatic backup and verification"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.backup_path = None
        self.original_content = None
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
    
    def create_backup(self):
        """Create timestamped backup"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_path = self.file_path.with_suffix(f'.backup_{timestamp}')
        shutil.copy2(self.file_path, self.backup_path)
        print(f"✓ Backup created: {self.backup_path}")
    
    def read_file(self):
        """Read file content"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.original_content = f.read()
        return self.original_content
    
    def write_file(self, content: str):
        """Write content to file"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def verify_change(self, expected_text: str):
        """Verify that expected text exists in file on disk"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            disk_content = f.read()
        
        if expected_text in disk_content:
            print(f"✓ Change verified on disk")
            self._show_context(disk_content, expected_text)
            return True
        else:
            print(f"✗ ERROR: Verification failed - change not found on disk!")
            return False
    
    def _show_context(self, content: str, search_text: str):
        """Show context around the change"""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if search_text[:50] in line:  # Match first 50 chars
                print(f"\n--- Change Preview ---")
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                for j in range(start, end):
                    prefix = ">>> " if j == i else "    "
                    print(f"{prefix}{lines[j]}")
                break
    
    def rollback(self):
        """Restore from backup"""
        if self.backup_path and self.backup_path.exists():
            shutil.copy2(self.backup_path, self.file_path)
            print(f"✓ File restored from backup")
        else:
            print(f"⚠ No backup available")
    
    def replace(self, search: str, replace: str, verify_text: str = None):
        """
        Safe find-and-replace operation
        
        Args:
            search: Text to search for
            replace: Text to replace with
            verify_text: Specific text to verify (defaults to replace text)
        """
        print(f"\n=== SAFE FILE EDITOR ===")
        
        # Create backup
        self.create_backup()
        
        # Read current content
        content = self.read_file()
        
        # Verify search pattern exists
        if search not in content:
            print(f"✗ ERROR: Search pattern not found in file!")
            print(f"Pattern: {search[:100]}...")
            return False
        
        # Perform replacement
        new_content = content.replace(search, replace)
        
        # Write to file
        self.write_file(new_content)
        print(f"✓ File written to disk")
        
        # Verify
        verify_text = verify_text or replace
        if self.verify_change(verify_text):
            print(f"\n=== EDIT COMPLETE ===")
            return True
        else:
            print(f"\nRestoring from backup...")
            self.rollback()
            print(f"\n=== EDIT FAILED ===")
            return False


# Example usage
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python safe_edit_template.py <file> <search> <replace>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    search_text = sys.argv[2]
    replace_text = sys.argv[3]
    
    editor = SafeFileEditor(file_path)
    success = editor.replace(search_text, replace_text)
    
    sys.exit(0 if success else 1)
