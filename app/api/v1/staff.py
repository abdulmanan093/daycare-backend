"""
Staff Management Endpoints
Create and manage staff users (staff & helper types)
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


def _format_staff_response(staff: dict) -> dict:
    """Format Supabase staff record to API response"""
    # assignedRoom: frontend expects a single string, not an array
    room_ids = staff.get("assigned_room_ids", [])
    assigned_room = room_ids[0] if room_ids else None
    
    return {
        "userId": staff.get("id"),  # Supabase UUID
        "staffCode": staff.get("staff_code"),
        "role": staff.get("staff_type", "staff"),  # Match staffType for role display
        "staffType": staff.get("staff_type", "staff"),
        "email": staff.get("email"),
        "loginEnabled": staff.get("login_enabled", False),
        "hasPassword": staff.get("auth_id") is not None,
        "fullName": staff.get("full_name"),
        "phoneNumber": staff.get("phone"),
        "gender": staff.get("gender"),
        "address": staff.get("address"),
        "assignedRoom": assigned_room,
        "profileImageUrl": staff.get("profile_image_url"),
        "status": staff.get("status", "active"),
        "createdAt": staff.get("created_at"),
        "updatedAt": staff.get("updated_at")
    }


def _created_at_sort_key(row: dict) -> str:
    """ISO timestamps sort lexicographically when zero-padded."""
    return str(row.get("createdAt") or row.get("created_at") or "")


def _merge_users_by_created_desc(admins: list, staff: list) -> list:
    """Merge two lists sorted by createdAt descending (newest first)."""
    i, j = 0, 0
    out = []
    while i < len(admins) and j < len(staff):
        if _created_at_sort_key(admins[i]) >= _created_at_sort_key(staff[j]):
            out.append(admins[i])
            i += 1
        else:
            out.append(staff[j])
            j += 1
    out.extend(admins[i:])
    out.extend(staff[j:])
    return out


def _exact_table_count(db, table: str) -> int:
    """
    Reliable row count for pagination guards.
    head=True + count=exact often yields count=0 with postgrest-py on empty JSON bodies;
    limit(1) keeps the payload tiny but preserves Content-Range total.
    """
    res = db.table(table).select("id", count="exact").limit(1).execute()
    if res.count is not None:
        return int(res.count)
    return 0


def _format_admin_as_staff(admin: dict) -> dict:
    """Format Supabase admin record to same structure as staff response"""
    return {
        "userId": admin.get("id"),
        "staffCode": None,
        "role": "admin",
        "staffType": "admin",
        "email": admin.get("email"),
        "loginEnabled": True,
        "hasPassword": admin.get("auth_id") is not None,
        "fullName": admin.get("full_name"),
        "phoneNumber": admin.get("phone"),
        "gender": None,
        "address": None,
        "assignedRoom": None,
        "profileImageUrl": admin.get("profile_image_url"),
        "status": admin.get("status", "active"),
        "createdAt": admin.get("created_at"),
        "updatedAt": admin.get("updated_at")
    }


@router.post("")
async def create_staff(
    fullName: Annotated[str, Form()],
    email: Annotated[str, Form()],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    gender: Annotated[Optional[str], Form()] = None,
    phoneNumber: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    password: Annotated[Optional[str], Form()] = None,
    assignedRoom: Annotated[Optional[str], Form()] = None,
    cnic: Annotated[Optional[str], Form()] = None,
    staffType: Annotated[Optional[str], Form()] = "staff",  # staff | helper | admin
    loginEnabled: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None,
    _: TokenData = Depends(require_admin)
):
    """Create a new staff/admin user (Admin only)
    
    - staffType="admin" creates entry in Supabase admins table
    - staffType="staff" or "helper" creates entry in Supabase staff table
    """
    
    # Parse login enabled
    login_enabled = False
    if loginEnabled is not None:
        login_enabled = loginEnabled.lower() in ('true', '1', 'yes')
    elif password and password.strip():
        login_enabled = True
    
    # Upload profile image if provided
    profile_image_url = None
    print(f"[staff create] profileImage={profileImage is not None} filename={getattr(profileImage, 'filename', None)}")
    if profileImage:
        media_service = MediaService()
        temp_id = generate_user_id("staff")
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            temp_id,
            "staff"
        )
    
    try:
        # If staffType is "admin", create in admins table
        if staffType and staffType.lower() == "admin":
            # Check if admin email already exists
            existing = supabase.get_admin_by_email(email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin with this email already exists"
                )
            
            admin = supabase.create_admin(
                full_name=fullName,
                email=email,
                phone=phoneNumber,
                profile_image_url=profile_image_url,
                password=password  # Creates auth user if provided
            )
            
            return {
                "message": "Admin created successfully",
                "staff": {
                    "userId": admin.get("id"),
                    "adminCode": admin.get("admin_code"),
                    "role": "admin",
                    "staffType": "admin",
                    "email": admin.get("email"),
                    "loginEnabled": admin.get("has_auth_account", False),
                    "fullName": admin.get("full_name"),
                    "phoneNumber": admin.get("phone"),
                    "profileImageUrl": admin.get("profile_image_url"),
                    "status": admin.get("status", "active"),
                    "createdAt": admin.get("created_at"),
                    "updatedAt": admin.get("updated_at")
                }
            }
        
        # Otherwise create in staff table (staff or helper)
        staff = supabase.create_staff(
            full_name=fullName,
            email=email,
            password=password,
            phone=phoneNumber,
            staff_type=staffType if staffType in ["staff", "helper"] else "staff",
            login_enabled=login_enabled,
            profile_image_url=profile_image_url,
            assigned_room_ids=[assignedRoom] if assignedRoom else [],
            gender=gender,
            address=address
        )
        
        return {
            "message": "Staff created successfully",
            "staff": _format_staff_response(staff)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{staff_id}/faces")
async def upload_staff_faces(
    staff_id: str,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    faceImages: Annotated[Optional[List[UploadFile]], File(description="3-4 face images for enrollment")] = None,
    _: TokenData = Depends(require_admin)
):
    """Upload face images for staff member"""
    
    # Verify staff exists in Supabase
    staff = supabase.get_staff_by_id(staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # If no images provided, clear existing embeddings
    if not faceImages or len(faceImages) == 0:
        supabase.delete_face_embeddings_for_person(staff_id)
        media_service = MediaService()
        await media_service.delete_face_photos(staff_id, "staff")
        
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
            "staffId": staff_id,
            "embeddingsCount": 0
        }

    # Generate face embeddings
    face_service = FaceRecognitionService()
    embeddings = await face_service.generate_multiple_embeddings(faceImages)
    
    # Replace stored face photos with current uploaded set
    media_service = MediaService()
    uploaded_face_urls = await media_service.upload_face_photos(faceImages, staff_id, "staff")
    photo_url = uploaded_face_urls[0] if uploaded_face_urls else None
    
    # Store embeddings in Supabase
    supabase.insert_face_embedding(
        person_id=staff_id,
        person_type="staff",
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
        "staffId": staff_id,
        "embeddingsCount": len(embeddings)
    }


@router.get("")
def list_staff(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    page: int = 1,
    page_size: int = Query(50, alias="pageSize"),
    staff_type: Optional[str] = None,
    status: Optional[str] = None
):
    """List staff members with DB-level pagination (admins + staff merged by created_at when unfiltered)."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size - 1
    db = supabase.client
    
    # Enforce active only for non-admins
    filter_status = "active" if current_user.role != "admin" else (status.lower() if status and status.lower() != "all" else None)

    # Admins only (same as legacy filter)
    if staff_type and staff_type.lower() == "admin":
        q = db.table("admins").select("*", count="exact")
        if filter_status:
            q = q.eq("status", filter_status)
        res = q.order("created_at", desc=True).range(start_idx, end_idx).execute()
        users = [_format_admin_as_staff(a) for a in (res.data or [])]
        return {"users": users, "total": res.count or 0, "page": page, "pageSize": page_size}

    # Single staff_type row set (staff | helper | any other value), no admins
    if staff_type and staff_type.lower() != "admin":
        st = staff_type.lower()
        q = db.table("staff").select("*", count="exact").eq("staff_type", st)
        if filter_status:
            q = q.eq("status", filter_status)
        res = q.order("created_at", desc=True).range(start_idx, end_idx).execute()
        users = [_format_staff_response(s) for s in (res.data or [])]
        return {"users": users, "total": res.count or 0, "page": page, "pageSize": page_size}

    # Default: merge admins + all staff by created_at
    # Fetch exact counts for pagination
    q_admins = db.table("admins").select("id", count="exact").limit(1)
    if filter_status:
        q_admins = q_admins.eq("status", filter_status)
    q_staff = db.table("staff").select("id", count="exact").limit(1)
    if filter_status:
        q_staff = q_staff.eq("status", filter_status)
        
    c_admins = q_admins.execute().count or 0
    c_staff = q_staff.execute().count or 0
    total = c_admins + c_staff

    if total > 0 and start_idx >= total:
        return {"users": [], "total": total, "page": page, "pageSize": page_size}

    merge_prefix_len = start_idx + page_size
    
    q_a = db.table("admins").select("*").order("created_at", desc=True)
    if filter_status:
        q_a = q_a.eq("status", filter_status)
    admins_raw = q_a.execute().data or []
    
    q_s = db.table("staff").select("*").order("created_at", desc=True).range(0, max(merge_prefix_len - 1, 0))
    if filter_status:
        q_s = q_s.eq("status", filter_status)
    staff_raw = q_s.execute().data or []

    admins_f = [_format_admin_as_staff(a) for a in admins_raw]
    staff_f = [_format_staff_response(s) for s in staff_raw]
    merged = _merge_users_by_created_desc(admins_f, staff_f)
    users = merged[start_idx : start_idx + page_size]

    return {"users": users, "total": total, "page": page, "pageSize": page_size}


@router.get("/{staff_id}")
def get_staff(
    staff_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Get staff or admin details"""
    # Check staff table first
    staff = supabase.get_staff_by_id(staff_id)
    if staff:
        response = _format_staff_response(staff)
        media_service = MediaService()
        embedding_face_urls = supabase.list_face_embedding_photo_urls(staff_id, "staff")
        face_photo_urls = media_service.list_face_photo_access_urls(
            staff_id, "staff", embedding_face_urls
        )
        response["facePhotoUrls"] = face_photo_urls
        # Keep a generic alias for frontend convenience.
        response["photos"] = face_photo_urls
        return response
    
    # Check admins table
    admin = supabase.get_admin_by_id(staff_id)
    if admin:
        response = _format_admin_as_staff(admin)
        media_service = MediaService()
        # Admin face photos are stored under the "staff" entity namespace.
        embedding_face_urls = supabase.list_face_embedding_photo_urls(staff_id, "staff")
        face_photo_urls = media_service.list_face_photo_access_urls(
            staff_id, "staff", embedding_face_urls
        )
        response["facePhotoUrls"] = face_photo_urls
        response["photos"] = face_photo_urls
        return response
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")


@router.put("/{staff_id}")
async def update_staff(
    staff_id: str,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    fullName: Annotated[Optional[str], Form()] = None,
    email: Annotated[Optional[str], Form()] = None,
    phoneNumber: Annotated[Optional[str], Form()] = None,
    staffStatus: Annotated[Optional[str], Form()] = None,
    userStatus: Annotated[Optional[str], Form(alias="status")] = None,
    gender: Annotated[Optional[str], Form()] = None,
    staffType: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    assignedRoom: Annotated[Optional[str], Form()] = None,
    loginEnabled: Annotated[Optional[str], Form()] = None,
    password: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None,
    _: TokenData = Depends(require_admin)
):
    """Update staff or admin user"""
    
    # Accept status from either field name
    effective_status = staffStatus or userStatus
    
    # Check if this is an admin
    admin = supabase.get_admin_by_id(staff_id)
    if admin:
        # Handle admin update
        admin_update = {}
        if fullName:
            admin_update["full_name"] = fullName
        if email:
            admin_update["email"] = email
        if phoneNumber:
            admin_update["phone"] = phoneNumber
        if effective_status:
            admin_update["status"] = effective_status
        
        if profileImage:
            media_service = MediaService()
            profile_image_url = await media_service.upload_profile_image(
                profileImage, staff_id, "admin"
            )
            admin_update["profile_image_url"] = profile_image_url
        
        if admin_update:
            # Update auth email if needed
            if email and admin.get("auth_id") and email != admin.get("email"):
                try:
                    supabase._client.auth.admin.update_user_by_id(
                        admin.get("auth_id"), {"email": email, "email_confirm": True}
                    )
                except Exception as e:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update email: {str(e)}")

            admin = supabase.update_admin(staff_id, admin_update)
            if not admin:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
        
        # Handle password update for admin
        if password and password.strip():
            auth_id = admin.get("auth_id")
            if auth_id:
                try:
                    supabase._client.auth.admin.update_user_by_id(
                        auth_id, {"password": password.strip()}
                    )
                except Exception as e:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to set password: {str(e)}")
        
        return {
            "message": "Admin updated successfully",
            "staff": _format_admin_as_staff(admin)
        }
    
    # Handle staff update
    # Build update data
    update_data = {}
    if fullName:
        update_data["full_name"] = fullName
    if email:
        update_data["email"] = email
    if phoneNumber:
        update_data["phone"] = phoneNumber
    if effective_status:
        update_data["status"] = effective_status
    if gender:
        update_data["gender"] = gender
    if staffType:
        update_data["staff_type"] = staffType
    if address:
        update_data["address"] = address
    if assignedRoom:
        update_data["assigned_room_ids"] = [assignedRoom]
    if loginEnabled is not None:
        update_data["login_enabled"] = loginEnabled.lower() in ('true', '1', 'yes')
    
    # Upload new profile image if provided
    if profileImage:
        media_service = MediaService()
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            staff_id,
            "staff"
        )
        update_data["profile_image_url"] = profile_image_url
    
    if not update_data and not password:
        staff = supabase.get_staff_by_id(staff_id)
        if not staff:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
        return _format_staff_response(staff)
    
    # Update profile data if any
    if update_data:
        # Update auth email if needed
        staff = supabase.get_staff_by_id(staff_id)
        if staff and email and staff.get("auth_id") and email != staff.get("email"):
            try:
                supabase._client.auth.admin.update_user_by_id(
                    staff.get("auth_id"), {"email": email, "email_confirm": True}
                )
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update email: {str(e)}")

        staff = supabase.update_staff(staff_id, update_data)
        if not staff:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    else:
        staff = supabase.get_staff_by_id(staff_id)
        if not staff:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    
    # Handle password: create or update auth user
    if password and password.strip():
        try:
            email = staff.get("email")
            supabase.set_staff_password(staff_id, email, password.strip(), staff.get("full_name"))
            # Re-fetch staff to get updated auth_id
            staff = supabase.get_staff_by_id(staff_id)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to set password: {str(e)}")
    
    return {
        "message": "Staff updated successfully",
        "staff": _format_staff_response(staff)
    }


@router.delete("/{staff_id}")
async def delete_staff(
    staff_id: str,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    _: TokenData = Depends(require_admin)
):
    """Delete staff or admin user"""
    # Try staff first
    staff = supabase.get_staff_by_id(staff_id)
    if staff:
        success = supabase.delete_staff(staff_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
        # Also delete face embeddings from Supabase
        supabase.delete_face_embeddings_for_person(staff_id)
        media_service = MediaService()
        await media_service.delete_face_photos(staff_id, "staff")
        return {"message": "Staff member deleted successfully", "userId": staff_id}
    
    # Try admin
    admin = supabase.get_admin_by_id(staff_id)
    if admin:
        success = supabase.delete_admin(staff_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
        return {"message": "Admin deleted successfully", "userId": staff_id}
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
