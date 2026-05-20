"""
Helper Management Endpoints
Create and manage helper users (no login access)
Helpers are stored in Supabase staff table with staff_type="helper"
"""
from typing import Annotated, Optional
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from datetime import datetime
from app.models.auth import TokenData
from app.services.supabase_service import get_supabase_service, SupabaseService
from app.services.media_service import MediaService
from app.dependencies import get_current_user, require_admin
from app.utils.security import generate_user_id


router = APIRouter()


def _format_helper_response(helper: dict) -> dict:
    """Format Supabase staff record (helper) to API response"""
    return {
        "userId": helper.get("id"),  # Supabase UUID
        "staffCode": helper.get("staff_code"),
        "fullName": helper.get("full_name"),
        "email": helper.get("email"),
        "phone": helper.get("phone"),
        "role": "helper",
        "staffType": "helper",
        "assignedRooms": helper.get("assigned_room_ids", []),
        "gender": helper.get("gender"),
        "dateOfBirth": helper.get("date_of_birth"),
        "address": helper.get("address"),
        "cnic": helper.get("cnic"),
        "profileImageUrl": helper.get("profile_image_url"),
        "status": helper.get("status", "active"),
        "employmentStatus": helper.get("employment_status", "active"),
        "loginEnabled": False,  # Helpers never have login
        "createdAt": helper.get("created_at"),
        "updatedAt": helper.get("updated_at")
    }


@router.post("")
async def create_helper(
    fullName: Annotated[str, Form()],
    phoneNumber: Annotated[str, Form()],
    gender: Annotated[str, Form()],
    dateOfBirth: Annotated[str, Form()],
    address: Annotated[str, Form()],
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    assignedRoom: Annotated[Optional[str], Form()] = None,
    cnic: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None
):
    """
    Create a new helper user (Admin only)
    
    Helpers do NOT have login access - they exist as profiles only
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Parse date
    dob = None
    if dateOfBirth and dateOfBirth.strip():
        try:
            dob = dateOfBirth.split('T')[0]
        except:
            dob = dateOfBirth
    
    # Upload profile image if provided
    profile_image_url = None
    if profileImage:
        media_service = MediaService()
        temp_id = generate_user_id("helper")
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            temp_id,
            "staff"
        )
    
    # Create helper in Supabase (staff table with staff_type="helper")
    try:
        # Helpers need a placeholder email since email is required in schema
        # Generate unique email based on phone number or name
        unique_suffix = hashlib.md5(f"{fullName}{phoneNumber}{datetime.utcnow().timestamp()}".encode()).hexdigest()[:8]
        placeholder_email = f"helper_{unique_suffix}@childsense.internal"
        
        helper = supabase.create_staff(
            full_name=fullName,
            email=placeholder_email,  # Placeholder email for helpers
            password=None,
            phone=phoneNumber,
            staff_type="helper",
            login_enabled=False,  # Helpers CANNOT login
            profile_image_url=profile_image_url,
            assigned_room_ids=[assignedRoom] if assignedRoom else []
        )
        
        # Update additional fields
        if dob or gender or address or cnic:
            update_data = {}
            if dob:
                update_data["date_of_birth"] = dob
            if gender:
                update_data["gender"] = gender
            if address:
                update_data["address"] = address
            if cnic:
                update_data["cnic"] = cnic
            helper = supabase.update_staff(helper["id"], update_data)
        
        return _format_helper_response(helper)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("")
async def list_helpers(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    page: int = 1,
    page_size: int = 50
):
    """List all helpers (Admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get helpers from Supabase (staff with staff_type="helper")
    helpers_list = supabase.get_all_staff(staff_type="helper")
    
    # Pagination
    total = len(helpers_list)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = helpers_list[start:end]
    
    return {
        "users": [_format_helper_response(h) for h in paginated],
        "total": total,
        "page": page,
        "pageSize": page_size
    }


@router.get("/{helper_id}")
async def get_helper(
    helper_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Get helper details"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    helper = supabase.get_staff_by_id(helper_id)
    
    if not helper or helper.get("staff_type") != "helper":
        raise HTTPException(status_code=404, detail="Helper not found")
    
    return _format_helper_response(helper)


@router.put("/{helper_id}")
async def update_helper(
    helper_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    fullName: Annotated[Optional[str], Form()] = None,
    phoneNumber: Annotated[Optional[str], Form()] = None,
    gender: Annotated[Optional[str], Form()] = None,
    dateOfBirth: Annotated[Optional[str], Form()] = None,
    address: Annotated[Optional[str], Form()] = None,
    cnic: Annotated[Optional[str], Form()] = None,
    assignedRoom: Annotated[Optional[str], Form()] = None,
    helperStatus: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None
):
    """Update helper user"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Verify it's a helper
    existing = supabase.get_staff_by_id(helper_id)
    if not existing or existing.get("staff_type") != "helper":
        raise HTTPException(status_code=404, detail="Helper not found")
    
    # Build update data
    update_data = {}
    if fullName:
        update_data["full_name"] = fullName
    if phoneNumber is not None:
        update_data["phone"] = phoneNumber
    if gender:
        update_data["gender"] = gender
    if dateOfBirth:
        try:
            update_data["date_of_birth"] = dateOfBirth.split('T')[0]
        except:
            update_data["date_of_birth"] = dateOfBirth
    if address is not None:
        update_data["address"] = address
    if cnic is not None:
        update_data["cnic"] = cnic
    if assignedRoom is not None:
        update_data["assigned_room_ids"] = [assignedRoom] if assignedRoom else []
    if helperStatus:
        update_data["status"] = helperStatus
    
    # Upload new profile image if provided
    if profileImage:
        media_service = MediaService()
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            helper_id,
            "staff"
        )
        update_data["profile_image_url"] = profile_image_url
    
    if not update_data:
        return _format_helper_response(existing)
    
    helper = supabase.update_staff(helper_id, update_data)
    
    if not helper:
        raise HTTPException(status_code=404, detail="Helper not found")
    
    return _format_helper_response(helper)


@router.delete("/{helper_id}", status_code=204)
async def delete_helper(
    helper_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Delete helper"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Verify it's a helper
    existing = supabase.get_staff_by_id(helper_id)
    if not existing or existing.get("staff_type") != "helper":
        raise HTTPException(status_code=404, detail="Helper not found")
    
    success = supabase.delete_staff(helper_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Helper not found")
    
    return None
