"""
Attendance Models
Pydantic models for attendance tracking
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class AttendanceType(str, Enum):
    """Attendance type enumeration"""
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"


class AttendanceMethod(str, Enum):
    """Attendance method enumeration"""
    FACE_RECOGNITION = "face_recognition"
    MANUAL = "manual"
    QR_CODE = "qr_code"


class AttendanceRecordRequest(BaseModel):
    """Create attendance record request"""
    entityId: str  # childId or userId
    entityType: str  # "child", "staff", etc.
    type: AttendanceType
    method: AttendanceMethod
    roomId: Optional[str] = None
    recordedBy: Optional[str] = None  # userId who recorded (for manual)
    notes: Optional[str] = None


class AttendanceRecordResponse(BaseModel):
    """Attendance record response"""
    recordId: str
    entityId: str
    entityName: str
    entityType: str
    type: AttendanceType
    method: AttendanceMethod
    roomId: Optional[str]
    roomName: Optional[str]
    recordedBy: Optional[str]
    recordedByName: Optional[str]
    timestamp: datetime
    notes: Optional[str]
    
    class Config:
        from_attributes = True


class AttendanceListResponse(BaseModel):
    """List of attendance records response"""
    records: list[AttendanceRecordResponse]
    total: int
    page: int = 1
    pageSize: int = 100
