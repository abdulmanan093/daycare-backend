"""
Alert Models
Pydantic models for alert management
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AlertType(str, Enum):
    """Alert type enumeration"""
    DANGEROUS_OBJECT = "dangerous_object"
    FALL_DETECTION = "fall_detection"
    CRY_DETECTION = "cry_detection"
    FIRE_SMOKE = "fire_smoke"
    UNAUTHORIZED_PERSON = "unauthorized_person"
    EMOTION_DISTRESS = "emotion_distress"
    SAFE_ZONE_BREACH = "safe_zone_breach"


class AlertSeverity(str, Enum):
    """Alert severity enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertMedia(BaseModel):
    """Alert media URLs"""
    videoUrl: Optional[str] = None
    screenshotUrl: Optional[str] = None


class AlertCreateRequest(BaseModel):
    """Create alert request"""
    type: AlertType
    severity: AlertSeverity
    roomId: str
    detectedEntityId: Optional[str] = None  # childId if detected
    media: AlertMedia
    allowedRoles: List[str] = Field(default_factory=lambda: ["admin"])
    allowedUsers: List[str] = Field(default_factory=list)


class AlertStatus(str, Enum):
    """Alert status enumeration"""
    ACTIVE = "Active"
    ACKNOWLEDGED = "Acknowledged"
    RESOLVED = "Resolved"


class AlertUpdateRequest(BaseModel):
    """Update alert request"""
    status: Optional[AlertStatus] = None
    notes: Optional[str] = None  # legacy: admin-only, maps to admin_notes
    staffNotes: Optional[str] = None
    adminNotes: Optional[str] = None
    roomId: Optional[str] = None
    childId: Optional[str] = None



class AlertResponse(BaseModel):
    """Alert response model"""
    alertId: str
    type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    roomId: Optional[str] = None
    roomName: Optional[str] = None
    detectedEntityId: Optional[str] = None
    detectedEntityName: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None
    media: AlertMedia
    signedMediaUrls: Optional[dict] = None  # Time-limited signed URLs
    allowedRoles: List[str] = Field(default_factory=list)
    allowedUsers: List[str] = Field(default_factory=list)
    timestamp: datetime
    acknowledged: bool = False
    acknowledgedBy: Optional[str] = None
    acknowledgedAt: Optional[datetime] = None
    createdAt: datetime
    
    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """List of alerts response"""
    alerts: List[AlertResponse]
    total: int
    page: int = 1
    pageSize: int = 50


class AcknowledgeAlertRequest(BaseModel):
    """Acknowledge alert request"""
    userId: str
    notes: Optional[str] = None
