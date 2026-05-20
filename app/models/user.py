"""
User Models
Pydantic models for user management (Admin, Staff, Helper, Parent)
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    STAFF = "staff"
    HELPER = "helper"
    PARENT = "parent"


class Gender(str, Enum):
    """Gender enumeration"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class UserStatus(str, Enum):
    """User status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class UserBase(BaseModel):
    """Base user model with common fields"""
    fullName: str = Field(..., min_length=2, max_length=100)
    phoneNumber: Optional[str] = Field(None, max_length=15)
    gender: Optional[Gender] = None
    dateOfBirth: Optional[datetime] = None
    address: Optional[str] = Field(None, max_length=500)
    cnic: Optional[str] = Field(None, max_length=20)
    assignedRoom: Optional[str] = None
    relationship: Optional[str] = Field(None, max_length=20)  # Mother/Father/Guardian for parents


class UserCreateRequest(UserBase):
    """Create user request (for Admin, Staff, Helper, Parent)"""
    role: UserRole
    email: Optional[EmailStr] = None  # Required for admin, staff, parent
    password: Optional[str] = Field(None)  # Required if login enabled
    loginEnabled: bool = False
    profileImage: Optional[str] = None  # Base64 or URL


class UserUpdateRequest(BaseModel):
    """Update user request"""
    fullName: Optional[str] = Field(None, min_length=2, max_length=100)
    phoneNumber: Optional[str] = None
    gender: Optional[Gender] = None
    dateOfBirth: Optional[datetime] = None
    address: Optional[str] = None
    cnic: Optional[str] = None
    assignedRoom: Optional[str] = None
    status: Optional[UserStatus] = None
    loginEnabled: Optional[bool] = None
    relationship: Optional[str] = None  # Mother/Father/Guardian for parents


class UserResponse(UserBase):
    """User response model"""
    userId: str
    role: UserRole
    email: Optional[str]
    loginEnabled: bool
    profileImageUrl: Optional[str]
    status: UserStatus
    relationship: Optional[str] = None  # Mother/Father/Guardian for parents
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """List of users response"""
    users: list[UserResponse]
    total: int
    page: int = 1
    pageSize: int = 50
