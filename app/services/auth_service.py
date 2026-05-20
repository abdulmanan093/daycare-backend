"""
Authentication Service
Handles Supabase authentication (login, signup, token management)
Now uses Supabase for both auth and user data
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from app.utils.supabase_client import SupabaseClient
from app.services.supabase_service import get_supabase_service
from app.models.auth import LoginRequest, TokenResponse, UserInfo
from gotrue.errors import AuthApiError


class AuthService:
    """Authentication service using Supabase Auth"""
    
    def __init__(self):
        self.supabase = SupabaseClient.get_client()
        self.service_client = SupabaseClient.get_service_client()
        self.supabase_service = get_supabase_service()
    
    async def create_supabase_user(self, email: str, password: str) -> str:
        """
        Create user in Supabase Auth using regular signup
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Supabase user ID
            
        Raises:
            HTTPException: If user creation fails
        """
        try:
            # Use regular signup (works with anon key)
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response and response.user:
                return response.user.id
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create Supabase user"
            )
            
        except AuthApiError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supabase error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user: {str(e)}"
            )
    
    async def authenticate_user(self, login_request: LoginRequest) -> TokenResponse:
        """
        Authenticate user with Supabase
        """
        import asyncio
        loop = asyncio.get_event_loop()

        try:
            # Run the blocking Supabase call in a thread pool so it doesn't freeze the event loop
            auth_response = await loop.run_in_executor(
                None,
                lambda: self.supabase.auth.sign_in_with_password({
                    "email": login_request.email,
                    "password": login_request.password
                })
            )
            
            if not auth_response or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Get user profile from Supabase tables (also blocking — run in executor)
            user_data = await loop.run_in_executor(
                None,
                lambda: self.supabase_service.get_user_profile(auth_response.user.id)
            )
            
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No user profile found for this account. If you're a new user, please sign up first. Staff/Admins should be created by an administrator from the dashboard."
                )
            
            profile = user_data.get("profile", {})
            role = user_data.get("role", "unknown")
            
            # Check if user is active
            if profile.get("status") != "active":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive"
                )
            
            # Check if login is enabled (for staff/parents)
            login_enabled = profile.get("login_enabled", True) if role != "admin" else True
            if not login_enabled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Login not enabled for this account"
                )
            
            return TokenResponse(
                accessToken=auth_response.session.access_token,
                refreshToken=auth_response.session.refresh_token,
                expiresIn=auth_response.session.expires_in,
                tokenType="bearer",
                user=UserInfo(
                    userId=profile.get("id"),
                    email=profile.get("email"),
                    role=role,
                    fullName=profile.get("full_name"),
                    profileImageUrl=profile.get("profile_image_url"),
                    loginEnabled=login_enabled
                )
            )
            
        except HTTPException:
            raise
        except AuthApiError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication error: {str(e)}"
            )

    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New token response
            
        Raises:
            HTTPException: If refresh fails
        """
        try:
            # Refresh session with Supabase
            auth_response = self.supabase.auth.refresh_session(refresh_token)
            
            if not auth_response or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Get user profile from Supabase
            user_data = self.supabase_service.get_user_profile(auth_response.user.id)
            
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            profile = user_data.get("profile", {})
            role = user_data.get("role", "unknown")
            login_enabled = profile.get("login_enabled", True) if role != "admin" else True
            
            return TokenResponse(
                accessToken=auth_response.session.access_token,
                refreshToken=auth_response.session.refresh_token,
                expiresIn=auth_response.session.expires_in,
                tokenType="bearer",
                user=UserInfo(
                    userId=profile.get("id"),
                    email=profile.get("email"),
                    role=role,
                    fullName=profile.get("full_name"),
                    profileImageUrl=profile.get("profile_image_url"),
                    loginEnabled=login_enabled
                )
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {str(e)}"
            )
    
    async def get_current_user_info(self, supabase_user_id: str) -> UserInfo:
        """
        Get current user info from Supabase
        
        Args:
            supabase_user_id: Supabase user ID from token
            
        Returns:
            User information
            
        Raises:
            HTTPException: If user not found
        """
        user_data = self.supabase_service.get_user_profile(supabase_user_id)
        
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
            profileImageUrl=profile.get("profile_image_url"),
            loginEnabled=login_enabled
        )
    
    async def delete_supabase_user(self, supabase_user_id: str) -> bool:
        """
        Delete user from Supabase Auth (Admin API)
        
        Args:
            supabase_user_id: Supabase user ID
            
        Returns:
            True if successful
        """
        try:
            self.service_client.auth.admin.delete_user(supabase_user_id)
            return True
        except Exception as e:
            print(f"Error deleting Supabase user: {str(e)}")
            return False
