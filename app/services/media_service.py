"""
Media Service
Handles Supabase storage operations for images and videos
"""
from typing import Optional, BinaryIO, List
from datetime import timedelta
from urllib.parse import unquote
from app.utils.supabase_client import SupabaseClient
from app.config import settings
from app.utils.helpers import sanitize_filename
import uuid
from fastapi import UploadFile, HTTPException


class MediaService:
    """Media storage service using Supabase Storage"""
    
    def __init__(self):
        self.client = SupabaseClient.get_client()
        self.service_client = SupabaseClient.get_service_client()
    
    async def upload_profile_image(
        self,
        file: UploadFile,
        entity_id: str,
        entity_type: str
    ) -> str:
        """
        Upload profile image to Supabase Storage.

        ALL entity types (child, staff, admin, parent) are stored in the
        single `profile-images` bucket.  Files are prefixed with the entity
        type so they are clearly identifiable:
            child_<id>_profile.jpg
            staff_<id>_profile.jpg
            parent_<id>_profile.jpg
            admin_<id>_profile.jpg

        Args:
            file: Uploaded file
            entity_id: ID of entity (userId or childId)
            entity_type: Type of entity (admin, staff, child, parent, etc.)

        Returns:
            Public URL of uploaded image
        """
        try:
            # Generate unique filename — always use the single profiles bucket
            file_ext = 'jpg'
            if file.filename and '.' in file.filename:
                file_ext = file.filename.split('.')[-1].lower()

            # Read file content
            content = await file.read()

            # Single bucket for all profile images
            bucket = settings.SUPABASE_BUCKET_PROFILES

            # Prefix with entity_type so files don't collide across types
            # Pattern: child_<id>_profile.jpg  /  staff_<id>_profile.jpg
            filename = f"{entity_type}_{entity_id}_profile.{file_ext}"

            # Remove older profile files for this entity (all common extensions)
            old_candidates = [
                f"{entity_type}_{entity_id}_profile.jpg",
                f"{entity_type}_{entity_id}_profile.jpeg",
                f"{entity_type}_{entity_id}_profile.png",
                f"{entity_type}_{entity_id}_profile.webp",
                f"{entity_type}_{entity_id}_profile.gif",
                # Legacy filenames without entity_type prefix (backward compat)
                f"{entity_id}_profile.jpg",
                f"{entity_id}_profile.jpeg",
                f"{entity_id}_profile.png",
                f"{entity_id}_profile.webp",
            ]
            try:
                self.service_client.storage.from_(bucket).remove(old_candidates)
            except Exception:
                pass

            try:
                # Upload new file
                response = self.service_client.storage.from_(bucket).upload(
                    filename,
                    content,
                    file_options={
                        "content-type": file.content_type or "image/jpeg",
                        "upsert": "true"
                    }
                )
            except Exception:
                # If upload fails, try removing old file first then re-uploading
                try:
                    self.service_client.storage.from_(bucket).remove([filename])
                except Exception:
                    pass
                response = self.service_client.storage.from_(bucket).upload(
                    filename,
                    content,
                    file_options={"content-type": file.content_type or "image/jpeg"}
                )

            # Get public URL
            public_url = self.service_client.storage.from_(bucket).get_public_url(filename)
            # Add version query to bypass browser/CDN cache after profile updates
            public_url = f"{public_url.split('?')[0]}?v={uuid.uuid4().hex[:10]}"
            print(f"[MediaService] Uploaded to bucket='{bucket}' file='{filename}' url='{public_url}'")
            return public_url

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")


    async def upload_face_photo(
        self,
        file: UploadFile,
        entity_id: str,
        entity_type: str
    ) -> str:
        """
        Upload face AI photo to Supabase Storage
        
        Args:
            file: Uploaded file
            entity_id: ID of entity (userId or childId)
            entity_type: Type of entity
            
        Returns:
            Public URL of uploaded image
        """
        try:
            file_ext = 'jpg'
            if file.filename and '.' in file.filename:
                file_ext = file.filename.split('.')[-1].lower()
            filename = f"{entity_type}_{entity_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
            content = await file.read()
            
            bucket = settings.SUPABASE_BUCKET_FACE_PHOTOS
            try:
                response = self.service_client.storage.from_(bucket).upload(
                    filename,
                    content,
                    file_options={
                        "content-type": file.content_type or "image/jpeg",
                        "upsert": "true"
                    }
                )
            except Exception:
                try:
                    self.service_client.storage.from_(bucket).remove([filename])
                except Exception:
                    pass
                response = self.service_client.storage.from_(bucket).upload(
                    filename,
                    content,
                    file_options={"content-type": file.content_type or "image/jpeg"}
                )
            
            public_url = self.service_client.storage.from_(bucket).get_public_url(filename)
            return public_url
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload face photo: {str(e)}")

    async def upload_face_photos(
        self,
        files: list[UploadFile],
        entity_id: str,
        entity_type: str
    ) -> list[str]:
        """
        Replace all stored face photos for a person with newly uploaded photos.
        """
        try:
            bucket = settings.SUPABASE_BUCKET_FACE_PHOTOS
            prefix = f"{entity_type}_{entity_id}_face_"

            # Remove any previous face photos for this person
            try:
                existing = self.service_client.storage.from_(bucket).list(
                    "",
                    {"limit": 1000, "search": prefix}
                )
                old_paths = [obj.get("name") for obj in existing or [] if obj.get("name", "").startswith(prefix)]
                if old_paths:
                    self.service_client.storage.from_(bucket).remove(old_paths)
            except Exception:
                pass

            uploaded_urls: list[str] = []
            for idx, file in enumerate(files):
                await file.seek(0)
                file_ext = "jpg"
                if file.filename and "." in file.filename:
                    file_ext = file.filename.split(".")[-1].lower()
                filename = f"{prefix}{idx}.{file_ext}"
                content = await file.read()

                self.service_client.storage.from_(bucket).upload(
                    filename,
                    content,
                    file_options={
                        "content-type": file.content_type or "image/jpeg",
                        "upsert": "true"
                    }
                )

                public_url = self.service_client.storage.from_(bucket).get_public_url(filename)
                uploaded_urls.append(public_url)

            return uploaded_urls
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload face photos: {str(e)}")

    async def delete_face_photos(self, entity_id: str, entity_type: str) -> bool:
        """Delete all stored face photos for a person."""
        try:
            bucket = settings.SUPABASE_BUCKET_FACE_PHOTOS
            prefix = f"{entity_type}_{entity_id}_face_"
            existing = self.service_client.storage.from_(bucket).list(
                "",
                {"limit": 1000, "search": prefix}
            )
            old_paths = [obj.get("name") for obj in existing or [] if obj.get("name", "").startswith(prefix)]
            if old_paths:
                self.service_client.storage.from_(bucket).remove(old_paths)
            return True
        except Exception:
            return False

    def _list_face_photo_object_names(self, entity_id: str, entity_type: str) -> List[str]:
        """Object keys in the face-photos bucket for this person (sorted, unique)."""
        bucket = settings.SUPABASE_BUCKET_FACE_PHOTOS
        current_prefix = f"{entity_type}_{entity_id}_face_"
        legacy_prefix = f"{entity_type}_{entity_id}_"

        current_objects = self.service_client.storage.from_(bucket).list(
            "",
            {"limit": 1000, "search": current_prefix}
        )
        legacy_objects = self.service_client.storage.from_(bucket).list(
            "",
            {"limit": 1000, "search": legacy_prefix}
        )

        names: List[str] = []
        for obj in (current_objects or []):
            name = obj.get("name", "")
            if name.startswith(current_prefix):
                names.append(name)
        for obj in (legacy_objects or []):
            name = obj.get("name", "")
            if name.startswith(legacy_prefix) and "_profile." not in name:
                names.append(name)

        return sorted(set(names))

    def _create_signed_url_safe(self, bucket: str, path: str, expires_in: int) -> str:
        try:
            signed = self.service_client.storage.from_(bucket).create_signed_url(path, expires_in)
            if not isinstance(signed, dict):
                return ""
            return signed.get("signedURL") or signed.get("signedUrl") or ""
        except Exception:
            return ""

    def _object_path_from_face_photo_reference(self, ref: str) -> Optional[str]:
        """Map a stored public URL, signed URL, or bare key to an object path in the face-photos bucket."""
        if not ref or not str(ref).strip():
            return None
        ref = str(ref).strip()
        bucket = settings.SUPABASE_BUCKET_FACE_PHOTOS
        sign_marker = f"/object/sign/{bucket}/"
        if sign_marker in ref:
            return unquote(ref.split(sign_marker, 1)[1].split("?")[0])
        public_marker = f"/object/public/{bucket}/"
        if public_marker in ref:
            return unquote(ref.split(public_marker, 1)[1].split("?")[0])
        if not ref.startswith("http"):
            return ref.lstrip("/")
        return None

    def list_face_photo_access_urls(
        self,
        entity_id: str,
        entity_type: str,
        embedding_photo_urls: Optional[List[str]] = None,
        expires_in: int = 7200,
    ) -> List[str]:
        """
        Time-limited URLs suitable for <img src> when the face-photos bucket is private.
        Merges storage objects with optional embedding table URLs, deduped by object path.
        """
        try:
            bucket = settings.SUPABASE_BUCKET_FACE_PHOTOS
            ordered_paths: List[str] = []
            seen: set[str] = set()

            for name in self._list_face_photo_object_names(entity_id, entity_type):
                if name not in seen:
                    seen.add(name)
                    ordered_paths.append(name)

            for url in embedding_photo_urls or []:
                path = self._object_path_from_face_photo_reference(url)
                if path and path not in seen:
                    seen.add(path)
                    ordered_paths.append(path)

            out: List[str] = []
            for path in ordered_paths:
                signed = self._create_signed_url_safe(bucket, path, expires_in)
                if signed:
                    out.append(signed)
            return out
        except Exception:
            return []

    def list_face_photo_urls(self, entity_id: str, entity_type: str) -> List[str]:
        """Backward-compatible alias: signed URLs for dashboard / img tags."""
        return self.list_face_photo_access_urls(entity_id, entity_type, None, 7200)

    
    async def upload_alert_video(
        self,
        file: UploadFile,
        alert_id: str
    ) -> str:
        """
        Upload alert video clip to Supabase Storage
        
        Args:
            file: Video file
            alert_id: Alert ID
            
        Returns:
            Storage path (not public URL for security)
        """
        try:
            file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'mp4'
            filename = f"alerts/{alert_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
            
            content = await file.read()
            
            bucket = settings.SUPABASE_BUCKET_ALERTS
            response = self.service_client.storage.from_(bucket).upload(
                filename,
                content,
                file_options={"content-type": file.content_type or "video/mp4"}
            )
            
            # Return storage path, not public URL
            return filename
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")
    
    async def upload_alert_screenshot(
        self,
        file: UploadFile,
        alert_id: str
    ) -> str:
        """
        Upload alert screenshot to Supabase Storage
        
        Args:
            file: Screenshot file
            alert_id: Alert ID
            
        Returns:
            Storage path
        """
        try:
            file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
            filename = f"screenshots/{alert_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
            
            content = await file.read()
            
            bucket = settings.SUPABASE_BUCKET_ALERTS
            response = self.service_client.storage.from_(bucket).upload(
                filename,
                content,
                file_options={"content-type": file.content_type or "image/jpeg"}
            )
            
            return filename
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload screenshot: {str(e)}")

    def upload_alert_screenshot_bytes(self, content: bytes, alert_id: str, ext: str = "jpg") -> str:
        """Upload raw JPEG/PNG bytes for an alert; returns storage path under the alerts bucket."""
        try:
            file_ext = (ext or "jpg").lower().lstrip(".")
            if file_ext not in ("jpg", "jpeg", "png", "webp"):
                file_ext = "jpg"
            filename = f"screenshots/{alert_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
            bucket = settings.SUPABASE_BUCKET_ALERTS
            ctype = "image/jpeg" if file_ext in ("jpg", "jpeg") else f"image/{file_ext}"
            self.service_client.storage.from_(bucket).upload(
                filename,
                content,
                file_options={"content-type": ctype},
            )
            return filename
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload screenshot bytes: {str(e)}")
    
    def generate_signed_url(
        self,
        bucket: str,
        path: str,
        expires_in: int = 300  # 5 minutes default
    ) -> str:
        """
        Generate time-limited signed URL for private media access
        
        Args:
            bucket: Storage bucket name
            path: File path in bucket
            expires_in: Expiration time in seconds
            
        Returns:
            Signed URL
        """
        try:
            signed_url = self.service_client.storage.from_(bucket).create_signed_url(
                path,
                expires_in
            )
            return signed_url.get('signedURL', '')
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate signed URL: {str(e)}")
    
    async def delete_file(self, bucket: str, path: str) -> bool:
        """
        Delete file from Supabase Storage
        
        Args:
            bucket: Storage bucket name
            path: File path in bucket
            
        Returns:
            True if successful
        """
        try:
            self.service_client.storage.from_(bucket).remove([path])
            return True
        except Exception:
            return False
