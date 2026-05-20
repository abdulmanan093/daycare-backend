"""
Authentication Models
Pydantic models for authentication requests and responses
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    """Login request model"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response model"""
    accessToken: str
    refreshToken: str
    expiresIn: Optional[int] = None
    tokenType: str = "bearer"
    user: Optional["UserInfo"] = None


class TokenData(BaseModel):
    """Token payload data"""
    userId: str
    email: Optional[str] = None
    role: str
    supabaseUserId: Optional[str] = None


class RegisterRequest(BaseModel):
    """Registration request model"""
    fullName: str
    email: EmailStr
    password: str
    phoneNumber: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class UserInfo(BaseModel):
    """Current user information response"""
    userId: str
    email: Optional[str]
    role: str
    fullName: str
    phone: Optional[str] = None
    profileImageUrl: Optional[str] = None
    loginEnabled: bool


# Resolve forward reference for TokenResponse.user
TokenResponse.model_rebuild()
