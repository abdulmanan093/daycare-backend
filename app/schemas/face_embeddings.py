"""
Face Embedding Document Schema
MongoDB collection structure for face embeddings
"""
from datetime import datetime
from typing import List


class FaceEmbeddingDocument:
    """MongoDB Face Embedding Schema"""
    
    collection_name = "face_embeddings"
    
    # Indexes
    indexes = [
        {"key": "embeddingId", "unique": True},
        {"key": "entityId"},
        {"key": "entityType"}
    ]
    
    # Schema structure
    schema = {
        "embeddingId": str,         # Unique ID
        "entityId": str,            # userId or childId
        "entityType": str,          # admin | staff | helper | parent | child
        "embeddings": List[List[float]],  # Multiple face embeddings (for variation)
        "model": str,               # e.g., "arcface", "dlib", "insightface"
        "createdAt": datetime,
        "updatedAt": datetime
    }
