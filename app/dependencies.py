"""
Application Dependencies
FastAPI dependency injection for database, authentication, etc.
Now uses Supabase for user lookups instead of MongoDB.
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.supabase_service import get_supabase_service, SupabaseService
from app.models.auth import TokenData


# Security scheme
security = HTTPBearer()

import time
# Simple TTL Cache for auth tokens to prevent 4x Supabase HTTP requests per API call
_auth_cache = {}
CACHE_TTL = 300  # 5 minutes


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> TokenData:
    """
    Dependency to get current authenticated user from Supabase JWT token
    
    Validates the token via Supabase Auth, then looks up the user profile
    in Supabase tables (admins, staff, parents).
    
    Args:
        credentials: Bearer token from request header
        
    Returns:
        TokenData with user information
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Check cache first
    now = time.time()
    if token in _auth_cache:
        cached_data, timestamp = _auth_cache[token]
        if now - timestamp < CACHE_TTL:
            return cached_data
            
    user_role_hint = None

    try:
        import asyncio
        from app.utils.supabase_client import SupabaseClient
        
        loop = asyncio.get_event_loop()
        # Verify Supabase token by fetching user from Supabase Auth (blocking → thread pool)
        user_response = await loop.run_in_executor(
            None,
            lambda: SupabaseClient.get_client().auth.get_user(token)
        )
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )
            
        supabase_user_id = str(user_response.user.id)
        supabase_email = user_response.user.email
        app_metadata = getattr(user_response.user, "app_metadata", None) or {}
        user_metadata = getattr(user_response.user, "user_metadata", None) or {}
        user_role_hint = app_metadata.get("role") or user_metadata.get("role")
        if isinstance(user_role_hint, str):
            user_role_hint = user_role_hint.strip().lower() or None
        else:
            user_role_hint = None
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error validating credentials: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Look up user profile in Supabase tables (admins, staff, parents)
    supabase = get_supabase_service()
    try:
        user_profile = await loop.run_in_executor(
            None,
            lambda: supabase.get_user_profile(supabase_user_id)
        )
    except Exception as e:
        print(f"Error fetching user profile from Supabase: {str(e)}")
        if user_role_hint:
            # Fallback for transient Supabase table connectivity issues.
            return TokenData(
                userId=supabase_user_id,
                email=supabase_email,
                role=user_role_hint,
                supabaseUserId=supabase_user_id,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )
    
    if not user_profile:
        if user_role_hint:
            return TokenData(
                userId=supabase_user_id,
                email=supabase_email,
                role=user_role_hint,
                supabaseUserId=supabase_user_id,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found in database"
        )
    
    profile = user_profile["profile"]
    role = user_profile["role"]
    
    token_data = TokenData(
        userId=str(profile.get("id")),
        email=profile.get("email", supabase_email),
        role=role,
        supabaseUserId=supabase_user_id
    )
    
    # Save to cache
    _auth_cache[token] = (token_data, time.time())
    
    return token_data


async def require_admin(
    current_user: Annotated[TokenData, Depends(get_current_user)]
) -> TokenData:
    """
    Dependency to require admin role
    
    Raises:
        HTTPException: If user is not admin
    """
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_staff_or_admin(
    current_user: Annotated[TokenData, Depends(get_current_user)]
) -> TokenData:
    """
    Dependency to require staff or admin role
    
    Raises:
        HTTPException: If user is not staff or admin
    """
    if current_user.role.lower() not in ["admin", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff or Admin access required"
        )
    return current_user
