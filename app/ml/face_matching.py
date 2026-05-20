"""
Face Matching Service
Match faces for attendance and identification
"""
from typing import List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.utils.database import Collections
from app.ml.face_recognition import FaceRecognitionService
from fastapi import HTTPException


class FaceMatchingService:
    """Service for matching faces against database"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.face_embeddings_collection = db[Collections.FACE_EMBEDDINGS]
        self.face_recognition = FaceRecognitionService()
    
    async def find_match(
        self,
        query_embedding: List[float],
        entity_type: Optional[str] = None,
        threshold: float = 0.6
    ) -> Tuple[Optional[str], float]:
        """
        Find matching entity by face embedding
        
        Args:
            query_embedding: Face embedding to match
            entity_type: Optional filter by entity type (child, staff, etc.)
            threshold: Similarity threshold
            
        Returns:
            Tuple of (entityId, confidence_score) or (None, 0.0)
        """
        # Build query filter
        query_filter = {}
        if entity_type:
            query_filter["entityType"] = entity_type
        
        # Fetch all face embeddings
        cursor = self.face_embeddings_collection.find(query_filter)
        face_records = await cursor.to_list(length=None)
        
        best_match_id = None
        best_score = 0.0
        
        # Compare against all stored embeddings
        for record in face_records:
            stored_embeddings = record.get("embeddings", [])
            is_match, score = self.face_recognition.match_face(
                query_embedding,
                stored_embeddings,
                threshold
            )
            
            if is_match and score > best_score:
                best_score = score
                best_match_id = record["entityId"]
        
        return best_match_id, best_score
    
    async def verify_identity(
        self,
        query_embedding: List[float],
        entity_id: str,
        threshold: float = 0.6
    ) -> Tuple[bool, float]:
        """
        Verify if embedding matches a specific entity
        
        Args:
            query_embedding: Face embedding to verify
            entity_id: Entity ID to verify against
            threshold: Similarity threshold
            
        Returns:
            Tuple of (is_verified, confidence_score)
        """
        # Fetch embeddings for specific entity
        record = await self.face_embeddings_collection.find_one({"entityId": entity_id})
        
        if not record:
            return False, 0.0
        
        stored_embeddings = record.get("embeddings", [])
        is_match, score = self.face_recognition.match_face(
            query_embedding,
            stored_embeddings,
            threshold
        )
        
        return is_match, score
