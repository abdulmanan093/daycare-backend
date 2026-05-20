"""
Helper Utilities
Miscellaneous utility functions
"""
from datetime import datetime
from typing import Optional, Dict, Any
import re


def calculate_age(date_of_birth: Optional[datetime]) -> Optional[int]:
    """
    Calculate age from date of birth
    
    Args:
        date_of_birth: Date of birth (optional)
        
    Returns:
        Age in years or None if date_of_birth is None
    """
    if not date_of_birth:
        return None
        
    today = datetime.utcnow()
    age = today.year - date_of_birth.year
    
    # Adjust if birthday hasn't occurred this year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    
    return age


def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid email format
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove any non-alphanumeric characters except dots and dashes
    filename = re.sub(r'[^\w\-.]', '_', filename)
    return filename.lower()


def format_response(
    success: bool,
    message: str,
    data: Optional[Any] = None,
    errors: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Format standardized API response
    
    Args:
        success: Whether operation was successful
        message: Response message
        data: Optional response data
        errors: Optional error details
        
    Returns:
        Formatted response dictionary
    """
    response = {
        "success": success,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    if errors is not None:
        response["errors"] = errors
    
    return response
