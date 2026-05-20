"""
Room Models
Pydantic models for room management
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RoomStatus(str, Enum):
    """Room status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class CameraType(str, Enum):
    """Camera type enumeration"""
    DAHUA_DVR = "DAHUA_DVR"
    IP_CAMERA = "IP_CAMERA"
    LAPTOP_WEBCAM = "LAPTOP_WEBCAM"
    UPLOAD_VIDEO = "UPLOAD_VIDEO"


class RoomCreateRequest(BaseModel):
    """Create room request"""
    name: str = Field(..., min_length=2, max_length=100)
    capacity: int = Field(..., gt=0)
    cameraType: CameraType
    cameraName: Optional[str] = None
    # DVR fields
    cameraIp: Optional[str] = None
    channels: Optional[List[int]] = None
    rtspPort: Optional[int] = Field(554, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    useLocalProxy: Optional[bool] = True
    # IP Camera fields
    streamUrl: Optional[str] = None


class RoomUpdateRequest(BaseModel):
    """Update room request"""
    name: Optional[str] = None
    capacity: Optional[int] = None
    cameraType: Optional[CameraType] = None
    cameraName: Optional[str] = None
    cameraIp: Optional[str] = None
    channels: Optional[List[int]] = None
    rtspPort: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    useLocalProxy: Optional[bool] = None
    streamUrl: Optional[str] = None
    status: Optional[RoomStatus] = None


class RoomResponse(BaseModel):
    """Room response model"""
    roomId: str
    name: str
    capacity: int
    currentOccupancy: int = 0
    cameraId: Optional[str] = None
    cameraType: Optional[CameraType] = None
    cameraName: Optional[str] = None
    cameraIp: Optional[str] = None
    channels: Optional[List[int]] = None
    rtspPort: Optional[int] = None
    username: Optional[str] = None
    useLocalProxy: Optional[bool] = None
    streamUrl: Optional[str] = None
    status: RoomStatus = RoomStatus.ACTIVE
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    
    class Config:
        from_attributes = True

