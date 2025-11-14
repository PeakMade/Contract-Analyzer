"""
In-memory progress tracking for contract AI analysis.
Stores progress state keyed by contract_id.
"""

from typing import Optional

# In-memory store: {contract_id: {percent, stage, done, error}}
_progress_store = {}


def set_progress(
    contract_id: str,
    percent: int,
    stage: str,
    done: bool = False,
    error: Optional[str] = None
) -> None:
    """
    Set or update progress for a contract analysis.
    
    Args:
        contract_id: Unique identifier for the contract
        percent: Progress percentage (0-100)
        stage: Current stage description
        done: Whether analysis is complete
        error: Error message if analysis failed
    """
    _progress_store[contract_id] = {
        "percent": percent,
        "stage": stage,
        "done": done,
        "error": error
    }


def get_progress(contract_id: str) -> Optional[dict]:
    """
    Retrieve current progress for a contract analysis.
    
    Args:
        contract_id: Unique identifier for the contract
        
    Returns:
        Progress dict or None if not found
    """
    return _progress_store.get(contract_id)


def clear_progress(contract_id: str) -> None:
    """
    Remove progress entry for a contract.
    
    Args:
        contract_id: Unique identifier for the contract
    """
    if contract_id in _progress_store:
        del _progress_store[contract_id]
