"""
Child Management Endpoints
Create and manage children linked to parents
Now uses Supabase for child data and face embeddings
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
from app.utils.helpers import calculate_age


router = APIRouter()


def _format_child_response(child: dict) -> dict:
    """Format Supabase child record to API response"""
    parent_info = child.get("parents") or {}
    
    # Handle date_of_birth
    dob = child.get("date_of_birth")
    if dob and isinstance(dob, str):
        try:
            dob = datetime.fromisoformat(dob.replace('Z', '+00:00'))
        except:
            dob = None
    
    return {
        "childId": child.get("id"),  # Supabase UUID
        "childCode": child.get("child_code"),
        "fullName": child.get("full_name"),
        "dateOfBirth": dob,
        "age": calculate_age(dob) if dob else None,
        "gender": child.get("gender"),
        "parentId": child.get("parent_id"),
        "parentName": parent_info.get("full_name") if parent_info else None,
        "assignedRoom": child.get("room_id"),
        "roomName": None,  # TODO: Fetch from Supabase rooms
        "medicalNotes": child.get("medical_notes"),
        "allergyInfo": ", ".join(child.get("allergies", [])) if child.get("allergies") else None,
        "profileImageUrl": child.get("profile_image_url"),
        "status": child.get("status", "active"),
        "enrollmentStatus": child.get("enrollment_status", "active"),
        "hasFaceEmbedding": child.get("has_face_embedding", False),
        "createdAt": child.get("created_at"),
        "updatedAt": child.get("updated_at")
    }


@router.post("")
async def create_child(
    fullName: Annotated[str, Form()],
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    assignedRoom: Annotated[Optional[str], Form()] = None,
    parentId: Annotated[Optional[str], Form()] = None,
    dateOfBirth: Annotated[Optional[str], Form()] = None,
    gender: Annotated[Optional[str], Form()] = None,
    medicalNotes: Annotated[Optional[str], Form()] = None,
    allergyInfo: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None
):
    """Create a new child (Admin only)"""
    # Only admin can create children
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Parse date
    dob = None
    if dateOfBirth and dateOfBirth.strip():
        try:
            dob = dateOfBirth.split('T')[0]  # Keep just date part
        except:
            dob = dateOfBirth
    
    # Capitalize gender to match DB constraint (Male/Female/Other)
    normalized_gender = None
    if gender and gender.strip():
        normalized_gender = gender.strip().capitalize()
    
    # Handle parent ID
    parent_uuid = None
    if parentId and parentId.strip() and parentId != "__UNASSIGNED__":
        # Verify parent exists in Supabase
        parent = supabase.get_parent_by_id(parentId)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent not found")
        parent_uuid = parentId
    
    # Upload profile image if provided
    profile_image_url = None
    print(f"[child create] profileImage={profileImage is not None} filename={getattr(profileImage, 'filename', None)}")
    if profileImage:
        media_service = MediaService()
        temp_id = generate_user_id("child")
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            temp_id,
            "child"
        )
    
    # Create child in Supabase
    try:
        child = supabase.create_child(
            full_name=fullName,
            date_of_birth=dob,
            gender=normalized_gender,
            parent_id=parent_uuid,
            room_id=assignedRoom,
            medical_notes=medicalNotes,
            allergy_info=allergyInfo,
            profile_image_url=profile_image_url
        )
        
        return _format_child_response(child)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{child_id}/faces")
async def upload_child_faces(
    child_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    faceImages: Annotated[Optional[List[UploadFile]], File(description="3-4 face images for enrollment")] = None
):
    """Upload face images for child"""
    # Only admin can upload child faces
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Verify child exists in Supabase
    child = supabase.get_child_by_id(child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
        
    # If no images provided, clear existing embeddings
    if not faceImages or len(faceImages) == 0:
        supabase.delete_face_embeddings_for_person(child_id)
        media_service = MediaService()
        await media_service.delete_face_photos(child_id, "child")
        # Update child record to mark face as not registered
        supabase.update_child(child_id, {
            "has_face_embedding": False
        })
        
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
            "childId": child_id,
            "embeddingsCount": 0
        }

    # Generate face embeddings
    face_service = FaceRecognitionService()
    embeddings = await face_service.generate_multiple_embeddings(faceImages)
    
    # Replace stored face photos with current uploaded set
    media_service = MediaService()
    uploaded_face_urls = await media_service.upload_face_photos(faceImages, child_id, "child")
    photo_url = uploaded_face_urls[0] if uploaded_face_urls else None
    
    # Store embeddings in Supabase
    supabase.insert_face_embedding(
        person_id=child_id,
        person_type="child",
        embeddings=embeddings,
        photo_url=photo_url
    )
    
    # Update child record to mark face as registered.
    # Some deployments may not yet have `face_registered_at` column.
    try:
        supabase.update_child(child_id, {
            "has_face_embedding": True,
            "face_registered_at": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"Warning: Failed to set face_registered_at on child record: {e}")
        try:
            # Fallback to the most important flag so UI can reflect success.
            supabase.update_child(child_id, {
                "has_face_embedding": True
            })
        except Exception as inner:
            print(f"Warning: Failed to update child face flag: {inner}")
    
    # Trigger ML API to reload embeddings
    from app.config import settings
    import httpx
    loaded_identity_count = None
    try:
        async with httpx.AsyncClient() as client:
            reload_resp = await client.post(
                f"{settings.ML_SERVICE_URL}/models/face-insight/reload-embeddings",
                timeout=10.0
            )
            if reload_resp.status_code == 200:
                try:
                    loaded_identity_count = reload_resp.json().get("loaded_identity_count")
                except Exception:
                    loaded_identity_count = None
    except Exception as e:
        print(f"Warning: Failed to reload ML API embeddings: {e}")
    
    return {
        "message": "Face images processed successfully",
        "childId": child_id,
        "embeddingsCount": len(embeddings),
        "photoUrl": photo_url,
        "photoUrls": uploaded_face_urls,
        "loadedIdentityCount": loaded_identity_count,
    }


@router.get("")
def list_children(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    page: int = 1,
    page_size: int = Query(50, alias="pageSize"),
    status: Optional[str] = None
):
    """List children (filtered by permissions)"""
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    start = (page - 1) * page_size
    end = start + page_size - 1

    # Filter based on role (parents can only see their own children)
    parent_id_filter = None
    if current_user.role == "parent":
        parent = supabase.get_parent_by_auth_id(current_user.supabaseUserId)
        if parent:
            parent_id_filter = parent.get("id")
        else:
            return {
                "children": [],
                "total": 0,
                "page": page,
                "pageSize": page_size,
            }

    # Fetch only requested page directly from DB (avoid full table scan in Python).
    query = supabase.client.table("children").select(
        "*, parents(id, full_name, phone, email, relationship)",
        count="exact",
    )
    if parent_id_filter:
        query = query.eq("parent_id", parent_id_filter)
        
    if current_user.role != "admin":
        query = query.eq("status", "active")
    elif status and status.lower() != "all":
        query = query.eq("status", status.lower())

    result = query.order("created_at", desc=True).range(start, end).execute()
    rows = result.data or []

    return {
        "children": [_format_child_response(c) for c in rows],
        "total": result.count or 0,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/{child_id}")
def get_child(
    child_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Get child details"""
    child = supabase.get_child_by_id(child_id)
    
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    # Check permissions for parents
    if current_user.role == "parent":
        parent = supabase.get_parent_by_auth_id(current_user.supabaseUserId)
        if not parent or child.get("parent_id") != parent.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")

    response = _format_child_response(child)
    media_service = MediaService()
    embedding_face_urls = supabase.list_face_embedding_photo_urls(child_id, "child")
    face_photo_urls = media_service.list_face_photo_access_urls(
        child_id, "child", embedding_face_urls
    )
    response["facePhotoUrls"] = face_photo_urls
    # Keep a generic alias for frontend convenience.
    response["photos"] = face_photo_urls
    return response


@router.put("/{child_id}")
async def update_child(
    child_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    fullName: Annotated[Optional[str], Form()] = None,
    dateOfBirth: Annotated[Optional[str], Form()] = None,
    gender: Annotated[Optional[str], Form()] = None,
    parentId: Annotated[Optional[str], Form()] = None,
    assignedRoom: Annotated[Optional[str], Form()] = None,
    medicalNotes: Annotated[Optional[str], Form()] = None,
    allergyInfo: Annotated[Optional[str], Form()] = None,
    childStatus: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None
):
    """Update child details"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Build update data
    update_data = {}
    if fullName:
        update_data["full_name"] = fullName
    if dateOfBirth:
        try:
            update_data["date_of_birth"] = dateOfBirth.split('T')[0]
        except:
            update_data["date_of_birth"] = dateOfBirth
    if gender:
        update_data["gender"] = gender.strip().capitalize()
    if parentId is not None:
        if parentId and parentId.strip() and parentId != "__UNASSIGNED__":
            # Verify parent exists
            parent = supabase.get_parent_by_id(parentId)
            if not parent:
                raise HTTPException(status_code=404, detail="Parent not found")
            update_data["parent_id"] = parentId
        else:
            update_data["parent_id"] = None
    if assignedRoom:
        update_data["room_id"] = assignedRoom
    if medicalNotes is not None:
        update_data["medical_notes"] = medicalNotes
    if allergyInfo is not None:
        update_data["allergies"] = [allergyInfo] if allergyInfo else []
    if childStatus:
        update_data["status"] = childStatus
    
    # Upload new profile image if provided
    print(f"[child update] profileImage={profileImage is not None} filename={getattr(profileImage, 'filename', None)}")
    if profileImage:
        media_service = MediaService()
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            child_id,
            "child"
        )
        update_data["profile_image_url"] = profile_image_url
    
    if not update_data:
        child = supabase.get_child_by_id(child_id)
        if not child:
            raise HTTPException(status_code=404, detail="Child not found")
        return _format_child_response(child)
    
    child = supabase.update_child(child_id, update_data)
    
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    
    return _format_child_response(child)


@router.delete("/{child_id}", status_code=204)
async def delete_child(
    child_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Delete child"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    success = supabase.delete_child(child_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Child not found")
    
    # Also delete face embeddings from Supabase
    supabase.delete_face_embeddings_for_person(child_id)
    media_service = MediaService()
    await media_service.delete_face_photos(child_id, "child")
    
    return None
