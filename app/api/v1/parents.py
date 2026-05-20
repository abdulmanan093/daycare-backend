"""
Parent Management Endpoints
Create and manage parent users
Now uses Supabase for user data
"""
from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from datetime import datetime
from app.models.auth import TokenData
from app.services.supabase_service import get_supabase_service, SupabaseService
from app.services.media_service import MediaService
from app.dependencies import get_current_user, require_admin
from app.ml.face_recognition import FaceRecognitionService
from app.utils.security import generate_user_id


router = APIRouter()


def _format_parent_response(parent: dict) -> dict:
    """Format Supabase parent record to API response"""
    return {
        "userId": parent.get("id"),  # Supabase UUID
        "parentCode": parent.get("parent_code"),
        "role": "parent",
        "email": parent.get("email"),
        "loginEnabled": parent.get("login_enabled", False),
        "hasPassword": parent.get("auth_id") is not None,
        "fullName": parent.get("full_name"),
        "phoneNumber": parent.get("phone"),
        "gender": None,  # Not stored in new schema
        "dateOfBirth": None,  # Not stored in new schema
        "address": parent.get("address"),
        "relationship": parent.get("relationship"),
        "profileImageUrl": parent.get("profile_image_url"),
        "status": parent.get("status", "active"),
        "createdAt": parent.get("created_at"),
        "updatedAt": parent.get("updated_at")
    }


@router.post("")
async def create_parent(
    fullName: Annotated[str, Form()],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    email: Annotated[Optional[str], Form()] = None,
    gender: Annotated[Optional[str], Form()] = None,
    dateOfBirth: Annotated[Optional[str], Form()] = None,
    phoneNumber: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    password: Annotated[Optional[str], Form()] = None,
    cnic: Annotated[Optional[str], Form()] = None,
    relationship: Annotated[Optional[str], Form()] = "Mother",
    loginEnabled: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None,
    _: TokenData = Depends(require_admin)
):
    """Create a new parent user (Admin only)"""
    
    # Parse login enabled
    login_enabled = False
    if loginEnabled is not None:
        login_enabled = loginEnabled.lower() in ('true', '1', 'yes')
    elif password and password.strip():
        login_enabled = True
    
    # Upload profile image if provided
    profile_image_url = None
    print(f"[parent create] profileImage={profileImage is not None} filename={getattr(profileImage, 'filename', None)}")
    if profileImage:
        media_service = MediaService()
        temp_id = generate_user_id("parent")
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            temp_id,
            "parent"
        )
    
    # Create parent in Supabase
    try:
        parent = supabase.create_parent(
            full_name=fullName,
            email=email,
            password=password,
            phone=phoneNumber,
            relationship=relationship or "Mother",
            address=address,
            login_enabled=login_enabled,
            profile_image_url=profile_image_url
        )
        
        return {
            "message": "Parent created successfully",
            "parent": _format_parent_response(parent)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{parent_id}/faces")
async def upload_parent_faces(
    parent_id: str,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    faceImages: Annotated[Optional[List[UploadFile]], File(description="3-4 face images for enrollment")] = None,
    _: TokenData = Depends(require_admin)
):
    """Upload face images for parent (for pickup verification)"""
    
    # Verify parent exists in Supabase
    parent = supabase.get_parent_by_id(parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
        
    # If no images provided, clear existing embeddings
    if not faceImages or len(faceImages) == 0:
        supabase.delete_face_embeddings_for_person(parent_id)
        media_service = MediaService()
        await media_service.delete_face_photos(parent_id, "parent")
        
        # Trigger ML API to reload embeddings
        from app.config import settings
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{settings.ML_SERVICE_URL}/models/face-insight/reload-embeddings", timeout=5.0)
        except Exception as e:
            print(f"Warning: Failed to reload ML API embeddings: {e}")
            
        return {
            "message": "Face embeddings cleared successfully",
            "parentId": parent_id,
            "embeddingsCount": 0
        }

    # Generate face embeddings
    face_service = FaceRecognitionService()
    embeddings = await face_service.generate_multiple_embeddings(faceImages)
    
    # Replace stored face photos with current uploaded set
    media_service = MediaService()
    uploaded_face_urls = await media_service.upload_face_photos(faceImages, parent_id, "parent")
    photo_url = uploaded_face_urls[0] if uploaded_face_urls else None
    
    # Store embeddings in Supabase
    supabase.insert_face_embedding(
        person_id=parent_id,
        person_type="parent",
        embeddings=embeddings,
        photo_url=photo_url
    )
    
    # Trigger ML API to reload embeddings
    from app.config import settings
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{settings.ML_SERVICE_URL}/models/face-insight/reload-embeddings", timeout=5.0)
    except Exception as e:
        print(f"Warning: Failed to reload ML API embeddings: {e}")
    
    return {
        "message": "Face images processed successfully",
        "parentId": parent_id,
        "embeddingsCount": len(embeddings)
    }


@router.get("")
def list_parents(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    page: int = 1,
    page_size: int = Query(50, alias="pageSize"),
    status: Optional[str] = None
):
    """List parents with DB-level pagination."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    start = (page - 1) * page_size
    end = start + page_size - 1

    query = supabase.client.table("parents").select("*", count="exact")
    
    if current_user.role != "admin":
        query = query.eq("status", "active")
    elif status and status.lower() != "all":
        query = query.eq("status", status.lower())

    result = (
        query
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )
    rows = result.data or []

    return {
        "users": [_format_parent_response(p) for p in rows],
        "total": result.count or 0,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/{parent_id}")
def get_parent(
    parent_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Get parent details"""
    # Parents can only view their own profile unless admin/staff
    if current_user.role == "parent" and current_user.userId != parent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    parent = supabase.get_parent_by_id(parent_id)
    
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    
    response = _format_parent_response(parent)
    media_service = MediaService()
    embedding_face_urls = supabase.list_face_embedding_photo_urls(parent_id, "parent")
    face_photo_urls = media_service.list_face_photo_access_urls(
        parent_id, "parent", embedding_face_urls
    )
    response["facePhotoUrls"] = face_photo_urls
    # Keep a generic alias for frontend convenience.
    response["photos"] = face_photo_urls
    return response


@router.put("/{parent_id}")
async def update_parent(
    parent_id: str,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    fullName: Annotated[Optional[str], Form()] = None,
    email: Annotated[Optional[str], Form()] = None,
    phoneNumber: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    relationship: Annotated[Optional[str], Form()] = None,
    parentStatus: Annotated[Optional[str], Form()] = None,
    userStatus: Annotated[Optional[str], Form(alias="status")] = None,
    loginEnabled: Annotated[Optional[str], Form()] = None,
    password: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None,
    _: TokenData = Depends(require_admin)
):
    """Update parent user"""
    
    # Accept status from either field name
    effective_status = parentStatus or userStatus
    
    # Build update data
    update_data = {}
    if fullName:
        update_data["full_name"] = fullName
    if email:
        update_data["email"] = email
    if phoneNumber:
        update_data["phone"] = phoneNumber
    if address:
        update_data["address"] = address
    if relationship:
        update_data["relationship"] = relationship
    if effective_status:
        update_data["status"] = effective_status
    if loginEnabled is not None:
        update_data["login_enabled"] = loginEnabled.lower() in ('true', '1', 'yes')
    
    # Upload new profile image if provided
    print(f"[parent update] profileImage={profileImage is not None} filename={getattr(profileImage, 'filename', None)}")
    if profileImage:
        media_service = MediaService()
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            parent_id,
            "parent"
        )
        update_data["profile_image_url"] = profile_image_url
    
    if not update_data and not password:
        parent = supabase.get_parent_by_id(parent_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
        return _format_parent_response(parent)
    
    # Update profile data if any
    if update_data:
        # Update auth email if needed
        parent = supabase.get_parent_by_id(parent_id)
        if parent and email and parent.get("auth_id") and email != parent.get("email"):
            try:
                supabase._client.auth.admin.update_user_by_id(
                    parent.get("auth_id"), {"email": email, "email_confirm": True}
                )
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update email: {str(e)}")

        parent = supabase.update_parent(parent_id, update_data)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    else:
        parent = supabase.get_parent_by_id(parent_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    
    # Handle password: create or update auth user
    if password and password.strip():
        try:
            email = parent.get("email")
            supabase.set_parent_password(parent_id, email, password.strip(), parent.get("full_name"))
            # Re-fetch parent to get updated auth_id
            parent = supabase.get_parent_by_id(parent_id)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to set password: {str(e)}")
    
    return {
        "message": "Parent updated successfully",
        "parent": _format_parent_response(parent)
    }


@router.delete("/{parent_id}")
async def delete_parent(
    parent_id: str,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    _: TokenData = Depends(require_admin)
):
    """Delete parent user"""
    success = supabase.delete_parent(parent_id)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
    
    # Also delete face embeddings from Supabase
    supabase.delete_face_embeddings_for_person(parent_id)
    media_service = MediaService()
    await media_service.delete_face_photos(parent_id, "parent")
    
    return {"message": "Parent deleted successfully", "userId": parent_id}
