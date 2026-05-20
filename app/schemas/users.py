"""
User Document Schema
MongoDB collection structure for users
"""
from datetime import datetime
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    STAFF = "staff"
    HELPER = "helper"
    PARENT = "parent"


class UserDocument:
    """MongoDB User Document Schema"""
    
    collection_name = "users"
    
    # Indexes
    indexes = [
        {"key": "userId", "unique": True},
        {"key": "email", "unique": True, "sparse": True},
        {"key": "role"},
        {"key": "status"}
    ]
    
    # Schema structure
    schema = {
        "userId": str,              # Unique ID (e.g., ADM_12AB34CD)
        "supabaseUserId": Optional[str],  # Supabase Auth user ID (null for helpers/children)
        "role": str,                # admin | staff | helper | parent
        "email": Optional[str],     # Only for admin, staff, parent
        # passwordHash removed - Supabase handles authentication
        "loginEnabled": bool,       # Can this user log in?
        "fullName": str,
        "phoneNumber": str,
        "cnic": Optional[str],
        "gender": str,              # male | female | other
        "dateOfBirth": datetime,
        "address": str,
        "assignedRoom": Optional[str],  # Room ID
        "status": str,              # active | inactive
        "profileImageUrl": Optional[str],  # Supabase URL
        "createdAt": datetime,
        "updatedAt": datetime
    }
