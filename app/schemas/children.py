"""
Child Document Schema
MongoDB collection structure for children
"""
from datetime import datetime
from typing import Optional


class ChildDocument:
    """MongoDB Child Document Schema"""
    
    collection_name = "children"
    
    # Indexes
    indexes = [
        {"key": "childId", "unique": True},
        {"key": "parentId"},
        {"key": "assignedRoom"},
        {"key": "status"}
    ]
    
    # Schema structure
    schema = {
        "childId": str,             # Unique ID (CHD_...)
        "fullName": str,
        "dateOfBirth": datetime,
        "gender": str,              # male | female | other
        "parentId": str,            # Reference to parent userId
        "assignedRoom": str,        # Room ID
        "medicalNotes": Optional[str],
        "allergyInfo": Optional[str],
        "profileImageUrl": Optional[str],  # Supabase URL
        "status": str,              # active | inactive
        "createdAt": datetime,
        "updatedAt": datetime
    }
