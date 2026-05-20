"""
Authentication Endpoints
Login, token refresh, and user info
Now uses Supabase for all user data
"""
from typing import Annotated
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.auth import LoginRequest, TokenResponse, RefreshTokenRequest, UserInfo, RegisterRequest
from app.services.auth_service import AuthService
from app.services.supabase_service import get_supabase_service, SupabaseService
from app.dependencies import get_current_user
from app.models.auth import TokenData


router = APIRouter()


def _normalize_actor_type_for_activity_log(role: Optional[str]) -> str:
    """activity_logs.actor_type CHECK allows admin|staff|parent|system only."""
    if not role:
        return "system"
    r = str(role).lower().strip()
    if r in ("admin", "staff", "parent", "system"):
        return r
    return "system"


@router.post("/login", response_model=TokenResponse)
async def login(
    login_request: LoginRequest
):
    """
    Login endpoint
    
    - **email**: User email address
    - **password**: User password
    
    Returns JWT access and refresh tokens
    """
    auth_service = AuthService()
    return await auth_service.authenticate_user(login_request)


@router.post("/register", response_model=TokenResponse)
async def register(
    register_request: RegisterRequest,
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """
    Register new admin user via signup page
    
    - **fullName**: Full name
    - **email**: Email address
    - **password**: Password
    - **phoneNumber**: Phone number
    
    Creates admin in Supabase admins table.
    Returns JWT tokens after successful registration.
    """
    auth_service = AuthService()
    
    # Check if admin already exists in Supabase
    existing_admin = supabase.get_admin_by_email(register_request.email)
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please login instead."
        )
    
    # Also check staff and parents tables
    existing_staff = supabase.get_staff_by_email(register_request.email)
    if existing_staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered as staff. Please login instead."
        )
    
    existing_parent = supabase.get_parent_by_email(register_request.email)
    if existing_parent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered as parent. Please login instead."
        )
    
    try:
        # Create admin in Supabase (creates auth user + admins table entry)
        admin = supabase.create_admin(
            full_name=register_request.fullName,
            email=register_request.email,
            phone=register_request.phoneNumber,
            password=register_request.password  # This creates auth user
        )
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create admin account"
            )
        
    except Exception as e:
        error_msg = str(e).lower()
        if "already" in error_msg or "exists" in error_msg or "duplicate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered. Please login instead."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )
    
    # Auto-login after registration
    login_req = LoginRequest(email=register_request.email, password=register_request.password)
    return await auth_service.authenticate_user(login_req)



@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest
):
    """
    Refresh access token
    
    - **refresh_token**: Valid refresh token
    
    Returns new JWT access and refresh tokens
    """
    auth_service = AuthService()
    return await auth_service.refresh_access_token(refresh_request.refresh_token)


@router.get("/me", response_model=UserInfo)
async def get_me(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """
    Get current user information
    
    Requires valid JWT token in Authorization header
    """
    # Get user profile from Supabase using auth ID
    user_data = supabase.get_user_profile(current_user.supabaseUserId)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    profile = user_data.get("profile", {})
    role = user_data.get("role", "unknown")
    login_enabled = profile.get("login_enabled", True) if role != "admin" else True
    
    return UserInfo(
        userId=profile.get("id"),
        email=profile.get("email"),
        role=role,
        fullName=profile.get("full_name"),
        phone=profile.get("phone"),
        profileImageUrl=profile.get("profile_image_url"),
        loginEnabled=login_enabled
    )


class UpdateProfileRequest(BaseModel):
    """Update profile request"""
    fullName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@router.put("/update-profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """
    Update current user's profile (name, email, phone)
    """
    user_data = supabase.get_user_profile(current_user.supabaseUserId)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = user_data.get("profile", {})
    role = user_data.get("role", "unknown")
    profile_id = profile.get("id")

    update_data = {}
    if request.fullName is not None:
        update_data["full_name"] = request.fullName
    if request.phone is not None:
        update_data["phone"] = request.phone
    if request.email is not None:
        update_data["email"] = request.email
        # Also update email in Supabase Auth
        try:
            supabase._client.auth.admin.update_user_by_id(
                current_user.supabaseUserId,
                {"email": request.email}
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update email: {str(e)}"
            )

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    try:
        from datetime import datetime
        update_data["updated_at"] = datetime.utcnow().isoformat()
        table = "admins" if role == "admin" else ("parents" if role == "parent" else "staff")
        result = supabase._client.table(table).update(update_data).eq("id", profile_id).execute()
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile row not found for update")
        
        # Log activity
        try:
            supabase._client.table("activity_logs").insert({
                "action": "Profile Update",
                "actor_id": profile_id,
                "actor_type": _normalize_actor_type_for_activity_log(role),
                "details": {"updated_fields": list(update_data.keys())}
            }).execute()
        except Exception as e:
            print("Failed to log activity:", e)

        return {"message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    newPassword: str


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """
    Change current user's password (no old password required)
    Updates password in Supabase Auth
    """
    if len(request.newPassword) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters"
        )
    
    try:
        supabase._client.auth.admin.update_user_by_id(
            current_user.supabaseUserId,
            {"password": request.newPassword}
        )

        # Log activity
        try:
            user_data = supabase.get_user_profile(current_user.supabaseUserId)
            if user_data:
                profile = user_data.get("profile", {})
                role = user_data.get("role", "unknown")
                supabase._client.table("activity_logs").insert({
                    "action": "Password Change",
                    "actor_id": profile.get("id"),
                    "actor_type": _normalize_actor_type_for_activity_log(role),
                    "details": {"action": "User changed their password"}
                }).execute()
        except Exception as e:
            print("Failed to log activity:", e)

        return {"message": "Password updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update password: {str(e)}"
        )


@router.post("/logout")
async def logout():
    """
    Logout endpoint
    
    In a stateless JWT system, logout is handled client-side by deleting tokens.
    This endpoint exists for consistency and can be extended for token blacklisting.
    """
    return {"message": "Logged out successfully"}

class ActivityLogRequest(BaseModel):
    action: str
    details: Optional[dict] = None

@router.post("/activity-log")
async def create_activity_log(
    request: ActivityLogRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    supabase: Annotated[SupabaseService, Depends(get_supabase_service)]
):
    """
    Generic endpoint for the dashboard to log any administrative action.
    """
    try:
        user_data = supabase.get_user_profile(current_user.supabaseUserId)
        actor_id = None
        actor_type = "system"
        if user_data:
            profile = user_data.get("profile", {})
            actor_id = profile.get("id")
            actor_type = _normalize_actor_type_for_activity_log(user_data.get("role"))

        supabase._client.table("activity_logs").insert({
            "action": request.action,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "details": request.details or {}
        }).execute()
        return {"message": "Activity logged"}
    except Exception as e:
        print("Failed to log activity:", e)
        # We don't raise an error because logging is non-critical
        return {"message": "Failed to log activity, but ignored"}
