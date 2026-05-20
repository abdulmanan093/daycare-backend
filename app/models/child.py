"""
Child Models
Pydantic models for child management
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.user import Gender, UserStatus


class ChildCreateRequest(BaseModel):
    """Create child request"""
    fullName: str = Field(..., min_length=2, max_length=100)
    dateOfBirth: Optional[datetime] = None
    gender: Optional[Gender] = None
    parentId: Optional[str] = None  # Reference to parent userId
    assignedRoom: str
    medicalNotes: Optional[str] = Field(None, max_length=1000)
    allergyInfo: Optional[str] = Field(None, max_length=500)
    profileImage: Optional[str] = None  # Base64 or URL


class ChildUpdateRequest(BaseModel):
    """Update child request"""
    fullName: Optional[str] = Field(None, min_length=2, max_length=100)
    dateOfBirth: Optional[datetime] = None
    gender: Optional[Gender] = None
    parentId: Optional[str] = None
    assignedRoom: Optional[str] = None
    medicalNotes: Optional[str] = None
    allergyInfo: Optional[str] = None
    status: Optional[UserStatus] = None


class ChildResponse(BaseModel):
    """Child response model"""
    childId: str
    fullName: str
    dateOfBirth: Optional[datetime] = None
    age: Optional[int] = None  # Calculated field
    gender: Optional[Gender] = None
    parentId: Optional[str] = None
    parentName: Optional[str]  # Populated from parent lookup
    assignedRoom: str
    roomName: Optional[str]  # Populated from room lookup
    medicalNotes: Optional[str]
    allergyInfo: Optional[str]
    profileImageUrl: Optional[str]
    status: UserStatus
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class ChildListResponse(BaseModel):
    """List of children response"""
    children: list[ChildResponse]
    total: int
    page: int = 1
    pageSize: int = 50
