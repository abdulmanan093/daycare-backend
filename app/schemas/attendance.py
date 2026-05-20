"""
Attendance Document Schema
MongoDB collection structure for attendance records
"""
from datetime import datetime
from typing import Optional


class AttendanceDocument:
    """MongoDB Attendance Document Schema"""
    
    collection_name = "attendance"
    
    # Indexes
    indexes = [
        {"key": "recordId", "unique": True},
        {"key": "entityId"},
        {"key": "entityType"},
        {"key": "timestamp"},
        {"key": "type"}
    ]
    
    # Schema structure
    schema = {
        "recordId": str,            # Unique ID
        "entityId": str,            # childId or userId
        "entityType": str,          # child | staff | parent
        "type": str,                # check_in | check_out
        "method": str,              # face_recognition | manual | qr_code
        "roomId": Optional[str],    # Room ID
        "recordedBy": Optional[str],  # userId who recorded (for manual)
        "timestamp": datetime,      # When attendance was recorded
        "notes": Optional[str],     # Additional notes
        "createdAt": datetime
    }
