"""
Face Recognition Service
Generate face embeddings using InsightFace or similar ML model
"""
from typing import List, Optional, Tuple
import numpy as np
from fastapi import UploadFile, HTTPException
from PIL import Image
import io


class FaceRecognitionService:
    """
    Face recognition service for generating and matching embeddings
    
    This is a placeholder implementation. In production, use InsightFace or dlib.
    """
    
    def __init__(self):
        # TODO: Initialize face detection and recognition models
        # Example: self.model = insightface.app.FaceAnalysis()
        self.model = None
        self.embedding_size = 512  # Standard for ArcFace
    
    async def validate_face_image(self, image_file: UploadFile) -> bool:
        """
        Validate that the image contains a clear, frontal face
        
        Args:
            image_file: Uploaded image file
            
        Returns:
            True if image is valid
            
        Raises:
            HTTPException: If image is invalid
        """
        try:
            # Read image
            content = await image_file.read()
            image = Image.open(io.BytesIO(content))
            
            # Basic validation
            if image.size[0] < 100 or image.size[1] < 100:
                raise HTTPException(status_code=400, detail="Image too small. Minimum 100x100 pixels")
            
            # TODO: Add face detection validation
            # - Check for single face
            # - Check face size (not too small)
            # - Check pose (frontal face)
            # - Check blur/quality
            
            # Reset file pointer
            await image_file.seek(0)
            
            return True
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")
    
    async def generate_embedding(self, image_file: UploadFile) -> List[float]:
        """
        Generate face embedding from image
        
        Args:
            image_file: Uploaded face image
            
        Returns:
            Face embedding as list of floats
            
        Raises:
            HTTPException: If face cannot be detected or processed
        """
        try:
            # Validate image
            await self.validate_face_image(image_file)
            
            # Read image
            content = await image_file.read()
            image = Image.open(io.BytesIO(content))
            
            # TODO: Replace with actual face recognition model
            # Example with InsightFace:
            # faces = self.model.get(np.array(image))
            # if len(faces) != 1:
            #     raise HTTPException(400, "Expected exactly one face")
            # embedding = faces[0].embedding.tolist()
            
            # Placeholder: Random embedding for testing
            embedding = np.random.randn(self.embedding_size).tolist()
            
            return embedding
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {str(e)}")
    
    async def generate_multiple_embeddings(
        self,
        image_files: List[UploadFile]
    ) -> List[List[float]]:
        """
        Generate embeddings from multiple face images by calling ml_api
        
        Args:
            image_files: List of face images (3-4 recommended)
            
        Returns:
            List of embeddings
        """
        import httpx
        from app.config import settings

        if len(image_files) < 1:
            raise HTTPException(
                status_code=400,
                detail="At least 1 face image required for enrollment"
            )
        
        # Prepare files for multipart/form-data request
        files = []
        for img in image_files:
            await img.seek(0)
            content = await img.read()
            files.append(("images", (img.filename, content, img.content_type)))
        
        ml_url = f"{settings.ML_SERVICE_URL}/models/face-insight/generate-embedding"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(ml_url, files=files, timeout=30.0)
                if response.status_code != 200:
                    detail = response.text
                    try:
                        payload = response.json()
                        detail = payload.get("detail") or payload.get("message") or detail
                    except Exception:
                        pass
                    raise HTTPException(status_code=400, detail=f"ML API Error: {detail}")
                
                data = response.json()
                if "embeddings" not in data:
                    raise HTTPException(status_code=500, detail="Invalid response from ML API")
                
                # Reset pointers back to 0 just in case
                for img in image_files:
                    await img.seek(0)
                    
                return data["embeddings"]
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to communicate with ML API: {str(e)}")
    
    def calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score (0-1, higher is more similar)
        """
        e1 = np.array(embedding1)
        e2 = np.array(embedding2)
        
        # Cosine similarity
        similarity = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))
        
        # Convert to 0-1 range
        return float((similarity + 1) / 2)
    
    def match_face(
        self,
        query_embedding: List[float],
        stored_embeddings: List[List[float]],
        threshold: float = 0.6
    ) -> Tuple[bool, float]:
        """
        Match a face embedding against stored embeddings
        
        Args:
            query_embedding: Embedding to match
            stored_embeddings: List of stored embeddings
            threshold: Similarity threshold (default 0.6)
            
        Returns:
            Tuple of (is_match, best_score)
        """
        if not stored_embeddings:
            return False, 0.0
        
        # Calculate similarity with all stored embeddings
        similarities = [
            self.calculate_similarity(query_embedding, stored_emb)
            for stored_emb in stored_embeddings
        ]
        
        best_score = max(similarities)
        is_match = best_score >= threshold
        
        return is_match, best_score
