"""
Authentication Middleware
JWT token validation middleware
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.security import decode_token
from typing import Optional


security = HTTPBearer()


async def verify_token(request: Request) -> Optional[dict]:
    """
    Verify JWT token from request headers
    
    Args:
        request: FastAPI request object
        
    Returns:
        Decoded token payload or None
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    
    return payload


async def require_authentication(request: Request):
    """
    Middleware to require authentication
    
    Raises:
        HTTPException: If token is invalid or missing
    """
    payload = await verify_token(request)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Attach user info to request state
    request.state.user = payload
