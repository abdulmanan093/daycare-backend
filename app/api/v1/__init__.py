"""
API v1 Router
Main router aggregating all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1 import auth, admin, staff, helpers, parents, children, rooms, alerts

# Create main v1 router
router = APIRouter()

# Include sub-routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(admin.router, prefix="/admin", tags=["Admin Management"])
router.include_router(staff.router, prefix="/staff", tags=["Staff Management"])
router.include_router(helpers.router, prefix="/helpers", tags=["Helper Management"])
router.include_router(parents.router, prefix="/parents", tags=["Parent Management"])
router.include_router(children.router, prefix="/children", tags=["Children Management"])
router.include_router(rooms.router, prefix="/rooms", tags=["Room Management"])
router.include_router(alerts.router, prefix="/alerts", tags=["Alert Management"])
