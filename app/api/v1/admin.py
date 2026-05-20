"""
Admin Management Endpoints
Create and manage admin users in separate admins table
Now uses Supabase for all admin data
"""
from typing import Annotated, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from datetime import datetime, date
import json
import re
from app.models.auth import TokenData
from app.services.supabase_service import get_supabase_service, SupabaseService
from app.services.media_service import MediaService
from app.dependencies import get_current_user, require_admin
from app.utils.security import generate_user_id


router = APIRouter()


def _alert_type_title(alert_type: Optional[str], description: Optional[str] = None) -> str:
    if not alert_type:
        return "Alert"
    t = str(alert_type).lower()
    if t == "fire_smoke":
        if description and "smoke" in description.lower():
            return "Smoke detected"
        return "Fire detected"
    if t == "safe_zone_breach":
        return "Safe Zone Breach"
    if t == "unauthorized_person":
        return "Unauthorized Person"
    if t == "emotion_distress":
        return "Distress Detected"
    return str(alert_type).replace("_", " ").strip().title()


def replace_uuid_with_short_id(match, act_str):
    uuid_str = match.group(0)
    prefix = "u"
    lower_act = act_str.lower()
    if "child" in lower_act:
        prefix = "c"
    elif "staff" in lower_act:
        prefix = "s"
    elif "parent" in lower_act:
        prefix = "p"
    
    clean = re.sub(r'[^a-zA-Z0-9]', '', uuid_str)
    hash_val = 0
    for char in clean:
        hash_val = (hash_val + ord(char)) % 1000
    code = str((hash_val % 90) + 10).zfill(2)
    return f"{prefix}{code}"


def _format_activity_details(details: Any) -> str:
    if not details or not isinstance(details, dict):
        return "System operation"
    act = details.get("action")
    if isinstance(act, str) and act.strip():
        act_str = act.strip()
        return re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', lambda m: replace_uuid_with_short_id(m, act_str), act_str, flags=re.IGNORECASE)
    uf = details.get("updated_fields")
    if isinstance(uf, list) and uf:
        return "Updated: " + ", ".join(str(x) for x in uf)
    try:
        res = json.dumps(details, default=str)[:280]
        return re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', lambda m: replace_uuid_with_short_id(m, res), res, flags=re.IGNORECASE)
    except Exception:
        return "System operation"


def _format_admin_response(admin: dict) -> dict:
    """Format Supabase admin record to API response"""
    return {
        "userId": admin.get("id"),  # Supabase UUID
        "adminCode": admin.get("admin_code"),
        "fullName": admin.get("full_name"),
        "email": admin.get("email"),
        "phone": admin.get("phone"),
        "role": "admin",
        "profileImageUrl": admin.get("profile_image_url"),
        "status": admin.get("status", "active"),
        "hasAuthAccount": admin.get("auth_id") is not None,
        "hasPassword": admin.get("auth_id") is not None,
        "createdAt": admin.get("created_at"),
        "updatedAt": admin.get("updated_at"),
        "lastLoginAt": admin.get("last_login_at")
    }


@router.post("")
async def create_admin(
    fullName: Annotated[str, Form()],
    email: Annotated[str, Form()],
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    phone: Annotated[Optional[str], Form()] = None,
    password: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None
):
    """Create a new admin (Admin only)"""
    # Only admin can create admins
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if email already exists
    existing_admin = supabase.get_admin_by_email(email)
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this email already exists"
        )
    
    # Create auth account if password provided
    auth_id = None
    if password:
        try:
            auth_result = supabase.create_auth_user(
                email=email,
                password=password,
                role="admin"
            )
            auth_id = auth_result.get("id")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create auth account: {str(e)}"
            )
    
    # Upload profile image if provided
    profile_image_url = None
    if profileImage:
        media_service = MediaService()
        temp_id = generate_user_id("admin")
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            temp_id,
            "admin"
        )
    
    # Create admin in Supabase
    try:
        admin = supabase.create_admin(
            full_name=fullName,
            email=email,
            phone=phone,
            profile_image_url=profile_image_url,
            auth_id=auth_id
        )
        
        return _format_admin_response(admin)
    except Exception as e:
        # Rollback auth user if admin creation fails
        if auth_id:
            try:
                supabase.delete_auth_user(auth_id)
            except:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("")
def list_admins(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    page: int = 1,
    page_size: int = 50
):
    """List all admins (Admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get all admins from Supabase
    admins_list = supabase.get_all_admins()
    
    # Pagination
    total = len(admins_list)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = admins_list[start:end]
    
    return {
        "admins": [_format_admin_response(a) for a in paginated],
        "total": total,
        "page": page,
        "pageSize": page_size
    }


# Static paths must be registered before /{admin_id} or "notifications" is parsed as a UUID.
@router.get("/notifications")
def admin_notifications(
    current_user: Annotated[TokenData, Depends(require_admin)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    limit: int = Query(25, ge=1, le=50),
):
    """
    Combined recent ML alerts + dashboard activity logs for the notification bell.
    Uses service role on the server (dashboard JWT is not a Supabase session).
    """
    fetch_n = min(limit * 2, 60)
    try:
        alerts_res = (
            supabase._client.table("alerts")
            .select("id, alert_type, description, status, timestamp, created_at, room_name")
            .order("created_at", desc=True)
            .limit(fetch_n)
            .execute()
        )
    except Exception as e:
        print(f"admin_notifications alerts: {e}")
        alerts_res = type("R", (), {"data": []})()

    try:
        logs_res = (
            supabase._client.table("activity_logs")
            .select("id, action, details, actor_type, created_at")
            .order("created_at", desc=True)
            .limit(fetch_n)
            .execute()
        )
    except Exception as e:
        print(f"admin_notifications activity_logs: {e}")
        logs_res = type("R", (), {"data": []})()

    items: list[dict] = []
    for a in alerts_res.data or []:
        ts = a.get("timestamp") or a.get("created_at")
        if ts is not None and hasattr(ts, "isoformat"):
            ts_out = ts.isoformat()
        else:
            ts_out = ts
        desc = (a.get("description") or "").strip()
        room = (a.get("room_name") or "").strip()
        if room and desc:
            desc = f"{desc} · {room}"
        elif room:
            desc = room
        items.append(
            {
                "id": f"alert-{a.get('id')}",
                "kind": "alert",
                "title": _alert_type_title(a.get("alert_type"), desc),
                "description": desc or _alert_type_title(a.get("alert_type")),
                "createdAt": ts_out,
                "isNew": (a.get("status") or "") == "Active",
            }
        )

    for log in logs_res.data or []:
        ts = log.get("created_at")
        if ts is not None and hasattr(ts, "isoformat"):
            ts_out = ts.isoformat()
        else:
            ts_out = ts
        items.append(
            {
                "id": f"log-{log.get('id')}",
                "kind": "activity",
                "title": log.get("action") or "Activity",
                "description": _format_activity_details(log.get("details")),
                "createdAt": ts_out,
                "isNew": True,
            }
        )

    def sort_key(row: dict):
        t = row.get("createdAt")
        if t is None:
            return ""
        return str(t)

    items.sort(key=sort_key, reverse=True)
    return {"items": items[:limit]}


@router.get("/attendance-summary")
def admin_attendance_summary(
    current_user: Annotated[TokenData, Depends(require_admin)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    attendance_date: Optional[str] = Query(
        None,
        alias="date",
        description="Local calendar day YYYY-MM-DD (browser should send its 'today').",
    ),
):
    """Present / absent counts for one day across all rooms/children."""
    if attendance_date:
        try:
            d = date.fromisoformat(attendance_date[:10])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date; use YYYY-MM-DD",
            )
    else:
        d = date.today()
    date_str = d.isoformat()

    present_statuses = ["present", "late", "early_pickup"]
    try:
        # Primary table used by staff app
        r_present = (
            supabase._client.table("attendance")
            .select("id", count="exact")
            .eq("date", date_str)
            .in_("status", present_statuses)
            .execute()
        )
        present = r_present.count if getattr(r_present, "count", None) is not None else len(
            r_present.data or []
        )
    except Exception as e:
        print(f"attendance_summary present(attendance): {e}")
        # Fallback for legacy schema
        try:
            r_present_old = (
                supabase._client.table("attendance_logs")
                .select("id", count="exact")
                .eq("date", date_str)
                .in_("status", present_statuses)
                .execute()
            )
            present = r_present_old.count if getattr(r_present_old, "count", None) is not None else len(
                r_present_old.data or []
            )
        except Exception as e2:
            print(f"attendance_summary present(attendance_logs): {e2}")
            present = 0

    # Absent = all children not marked present for that day
    try:
        r_children = supabase._client.table("children").select("id", count="exact").limit(1).execute()
        total_children = r_children.count if getattr(r_children, "count", None) is not None else len(
            r_children.data or []
        )
        absent = max((total_children or 0) - (present or 0), 0)
    except Exception as e:
        print(f"attendance_summary total children: {e}")
        absent = 0

    return {"date": date_str, "present": present, "absent": absent}


@router.get("/{admin_id}")
def get_admin(
    admin_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Get admin details"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    admin = supabase.get_admin_by_id(admin_id)
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    return _format_admin_response(admin)


@router.put("/{admin_id}")
async def update_admin(
    admin_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)],
    fullName: Annotated[Optional[str], Form()] = None,
    email: Annotated[Optional[str], Form()] = None,
    phone: Annotated[Optional[str], Form()] = None,
    adminStatus: Annotated[Optional[str], Form()] = None,
    password: Annotated[Optional[str], Form()] = None,
    profileImage: Annotated[Optional[UploadFile], File()] = None
):
    """Update admin details"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Build update data
    update_data = {}
    if fullName:
        update_data["full_name"] = fullName
    if email:
        # Check for email conflicts
        existing = supabase.get_admin_by_email(email)
        if existing and existing.get("id") != admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        update_data["email"] = email
    if phone is not None:
        update_data["phone"] = phone
    if adminStatus:
        update_data["status"] = adminStatus
    
    # Upload new profile image if provided
    if profileImage:
        media_service = MediaService()
        profile_image_url = await media_service.upload_profile_image(
            profileImage,
            admin_id,
            "admin"
        )
        update_data["profile_image_url"] = profile_image_url
    
    if not update_data and not password:
        admin = supabase.get_admin_by_id(admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        return _format_admin_response(admin)
    
    # Update profile data if any
    if update_data:
        admin = supabase.update_admin(admin_id, update_data)
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
    else:
        admin = supabase.get_admin_by_id(admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
    
    # Handle password: create or update auth user
    if password and password.strip():
        try:
            admin_email = email or admin.get("email")
            auth_id = admin.get("auth_id")
            
            if auth_id:
                # Update existing auth user's password
                supabase._client.auth.admin.update_user_by_id(
                    auth_id,
                    {"password": password.strip()}
                )
            else:
                # Create new auth user
                auth_response = supabase._client.auth.admin.create_user({
                    "email": admin_email,
                    "password": password.strip(),
                    "email_confirm": True,
                    "user_metadata": {
                        "role": "admin",
                        "full_name": admin.get("full_name")
                    }
                })
                new_auth_id = str(auth_response.user.id)
                supabase.update_admin(admin_id, {"auth_id": new_auth_id})
            
            # Re-fetch admin to get updated auth_id
            admin = supabase.get_admin_by_id(admin_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to set password: {str(e)}"
            )
    
    return _format_admin_response(admin)


@router.delete("/{admin_id}", status_code=204)
async def delete_admin(
    admin_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """Delete admin"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get admin to find auth_id
    admin = supabase.get_admin_by_id(admin_id)
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Prevent self-deletion
    if admin.get("auth_id") == current_user.supabaseUserId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account"
        )
    
    # Delete auth account if exists
    if admin.get("auth_id"):
        try:
            supabase.delete_auth_user(admin["auth_id"])
        except Exception as e:
            print(f"Warning: Failed to delete auth user: {e}")
    
    # Delete admin record
    success = supabase.delete_admin(admin_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    return None
