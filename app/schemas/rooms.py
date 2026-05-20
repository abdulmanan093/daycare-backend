"""
Room Document Schema
MongoDB collection structure for rooms
"""
from datetime import datetime
from typing import Optional


class RoomDocument:
    """MongoDB Room Document Schema"""
    
    collection_name = "rooms"
    
    # Indexes
    indexes = [
        {"key": "roomId", "unique": True},
        {"key": "name"},
        {"key": "status"}
    ]
    
    # Schema structure
    schema = {
        "roomId": str,              # Unique ID (ROOM_...)
        "name": str,                # Room name
        "capacity": int,            # Maximum capacity
        "currentOccupancy": int,    # Current number of children
        "description": Optional[str],
        "floorNumber": Optional[int],
        "status": str,              # active | inactive | maintenance
        "createdAt": datetime,
        "updatedAt": datetime
    }
