"""
Alert Document Schema
MongoDB collection structure for alerts
"""
from datetime import datetime
from typing import Optional, List, Dict


class AlertDocument:
    """MongoDB Alert Document Schema"""
    
    collection_name = "alerts"
    
    # Indexes
    indexes = [
        {"key": "alertId", "unique": True},
        {"key": "roomId"},
        {"key": "type"},
        {"key": "severity"},
        {"key": "timestamp"},
        {"key": "acknowledged"}
    ]
    
    # Schema structure
    schema = {
        "alertId": str,             # Unique ID
        "type": str,                # dangerous_object | fall_detection | cry_detection | fire_smoke | unauthorized_person
        "severity": str,            # low | medium | high | critical
        "roomId": str,              # Room where alert occurred
        "detectedEntityId": Optional[str],  # childId if detected
        "media": Dict[str, Optional[str]],  # {"videoUrl": "...", "screenshotUrl": "..."}
        "allowedRoles": List[str],  # ["admin", "staff", "parent"]
        "allowedUsers": List[str],  # Specific userIds who can access
        "timestamp": datetime,      # When alert occurred
        "acknowledged": bool,       # Has alert been acknowledged?
        "acknowledgedBy": Optional[str],  # userId who acknowledged
        "acknowledgedAt": Optional[datetime],  # When acknowledged
        "createdAt": datetime
    }
