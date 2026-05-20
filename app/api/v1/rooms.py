
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Annotated
from app.models.room import RoomResponse, RoomCreateRequest, RoomUpdateRequest, RoomStatus, CameraType
from app.dependencies import get_current_user, require_admin
from app.models.auth import TokenData
from app.utils.supabase_client import SupabaseClient
from datetime import datetime
import random
import string

router = APIRouter()

def _map_room_to_frontend(room: dict, camera: dict = None) -> dict:
    res = {
        "roomId": room.get("id"),
        "name": room.get("room_name"),
        "capacity": room.get("capacity"),
        "currentOccupancy": room.get("current_occupancy", 0),
        "status": room.get("status"),
        "createdAt": room.get("created_at"),
        "updatedAt": room.get("updated_at"),
    }
    if camera:
        res["cameraId"] = camera.get("id")
        res["cameraType"] = camera.get("camera_type")
        res["cameraName"] = camera.get("camera_name")
        res["cameraIp"] = camera.get("camera_ip")
        res["channels"] = camera.get("channels")
        res["rtspPort"] = camera.get("rtsp_port")
        res["username"] = camera.get("rtsp_username")
        res["useLocalProxy"] = camera.get("use_local_proxy")
        res["streamUrl"] = camera.get("stream_url")
    return res

@router.get("", response_model=List[RoomResponse])
def get_rooms(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100
):
    """
    Get all rooms with their primary camera attached
    """
    try:
        supabase = SupabaseClient.get_service_client()
        
        # Fetch rooms
        rooms_res = supabase.table("rooms").select("*").order("room_name").range(skip, skip + limit - 1).execute()
        rooms = rooms_res.data
        
        # Fetch all cameras mapped to these rooms
        room_ids = [r["id"] for r in rooms]
        cameras = []
        if room_ids:
            cams_res = supabase.table("cameras").select("*").in_("room_id", room_ids).execute()
            cameras = cams_res.data
            
        # Map them together
        cam_map = {}
        for c in cameras:
            # just take the first camera for the room
            if c["room_id"] not in cam_map:
                cam_map[c["room_id"]] = c
                
        return [_map_room_to_frontend(r, cam_map.get(r["id"])) for r in rooms]
    except Exception as e:
        print(f"Error in get_rooms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)]
):
    """
    Get room by ID
    """
    supabase = SupabaseClient.get_service_client()
    result = supabase.table("rooms").select("*").eq("id", room_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Room not found")
        
    cam_result = supabase.table("cameras").select("*").eq("room_id", room_id).execute()
    camera = cam_result.data[0] if cam_result.data else None
        
    return _map_room_to_frontend(result.data[0], camera)

@router.get("/{room_id}/stream-url")
def get_room_stream_url(
    room_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)]
):
    """
    Get the resolved stream URL for a room's first camera
    """
    supabase = SupabaseClient.get_service_client()
    result = supabase.table("cameras").select("*").eq("room_id", room_id).eq("status", "active").limit(1).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="No stream URL configured for this room")
        
    cam = result.data[0]
    return {"streamUrl": cam.get("stream_url")}

@router.get("/{room_id}/stream-urls")
def get_room_stream_urls(
    room_id: str,
    current_user: Annotated[TokenData, Depends(get_current_user)]
):
    """
    Get all resolved stream URLs for a room.
    """
    supabase = SupabaseClient.get_service_client()
    result = supabase.table("cameras").select("*").eq("room_id", room_id).eq("status", "active").execute()
    
    urls = [cam.get("stream_url") for cam in result.data if cam.get("stream_url")]
    return {"streams": urls}

@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    room_data: RoomCreateRequest,
    current_user: Annotated[TokenData, Depends(require_admin)]
):
    """
    Create a new room and camera (Admin only)
    """
    supabase = SupabaseClient.get_service_client()
    
    existing = supabase.table("rooms").select("id").eq("room_name", room_data.name).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Room with this name already exists")
    
    room_code = f"RM-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"

    # Insert room
    insert_data = {
        "room_name": room_data.name,
        "room_code": room_code,
        "capacity": room_data.capacity,
        "current_occupancy": 0,
        "status": "active"
    }
    result = supabase.table("rooms").insert(insert_data).execute()
    new_room = result.data[0]
    
    # Insert camera
    camera_data = {
        "camera_name": room_data.cameraName or f"{room_data.name} Camera",
        "camera_code": f"CAM-{room_code}",
        "room_id": new_room["id"],
        "camera_type": room_data.cameraType.value if hasattr(room_data.cameraType, 'value') else room_data.cameraType,
        "camera_ip": room_data.cameraIp,
        "channels": room_data.channels,
        "rtsp_port": room_data.rtspPort,
        "rtsp_username": room_data.username,
        "rtsp_password_enc": room_data.password,
        "use_local_proxy": room_data.useLocalProxy,
        "stream_url": room_data.streamUrl,
        "status": "active"
    }
    camera_data = {k: v for k, v in camera_data.items() if v is not None}
    cam_result = supabase.table("cameras").insert(camera_data).execute()
    camera = cam_result.data[0] if cam_result.data else None
    
    return _map_room_to_frontend(new_room, camera)

@router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: str,
    room_data: RoomUpdateRequest,
    current_user: Annotated[TokenData, Depends(require_admin)]
):
    """
    Update a room and camera (Admin only)
    """
    supabase = SupabaseClient.get_service_client()
    
    # 1. Update Room
    update_data = {k: v for k, v in room_data.model_dump(exclude_unset=True).items()}
    db_update = {}
    if "name" in update_data: db_update["room_name"] = update_data["name"]
    if "capacity" in update_data: db_update["capacity"] = update_data["capacity"]
    if "status" in update_data: db_update["status"] = update_data["status"].value if hasattr(update_data["status"], 'value') else update_data["status"]
    
    if db_update:
        db_update["updated_at"] = datetime.utcnow().isoformat()
        room_res = supabase.table("rooms").update(db_update).eq("id", room_id).execute()
        if not room_res.data:
            raise HTTPException(status_code=404, detail="Room not found")
            
    # 2. Update or Insert Camera
    cam_update = {}
    if "cameraName" in update_data: cam_update["camera_name"] = update_data["cameraName"]
    if "cameraType" in update_data: 
        cam_update["camera_type"] = update_data["cameraType"].value if hasattr(update_data["cameraType"], 'value') else update_data["cameraType"]
    if "cameraIp" in update_data: cam_update["camera_ip"] = update_data["cameraIp"]
    if "channels" in update_data: cam_update["channels"] = update_data["channels"]
    if "rtspPort" in update_data: cam_update["rtsp_port"] = update_data["rtspPort"]
    if "username" in update_data: cam_update["rtsp_username"] = update_data["username"]
    if "password" in update_data: cam_update["rtsp_password_enc"] = update_data["password"]
    if "useLocalProxy" in update_data: cam_update["use_local_proxy"] = update_data["useLocalProxy"]
    if "streamUrl" in update_data: cam_update["stream_url"] = update_data["streamUrl"]
    
    camera = None
    if cam_update:
        # Check if camera exists
        existing_cam = supabase.table("cameras").select("id").eq("room_id", room_id).execute()
        if existing_cam.data:
            cam_update["updated_at"] = datetime.utcnow().isoformat()
            cam_res = supabase.table("cameras").update(cam_update).eq("id", existing_cam.data[0]["id"]).execute()
            camera = cam_res.data[0] if cam_res.data else None
        else:
            # Need to create it
            room_res = supabase.table("rooms").select("*").eq("id", room_id).execute()
            room = room_res.data[0]
            cam_update["room_id"] = room_id
            cam_update["camera_code"] = f"CAM-{room['room_code']}"
            if "camera_name" not in cam_update:
                cam_update["camera_name"] = f"{room['room_name']} Camera"
            cam_update["status"] = "active"
            
            cam_res = supabase.table("cameras").insert(cam_update).execute()
            camera = cam_res.data[0] if cam_res.data else None
    else:
        cam_res = supabase.table("cameras").select("*").eq("room_id", room_id).execute()
        camera = cam_res.data[0] if cam_res.data else None

    final_room = supabase.table("rooms").select("*").eq("id", room_id).execute()
    return _map_room_to_frontend(final_room.data[0], camera)

@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    current_user: Annotated[TokenData, Depends(require_admin)]
):
    """
    Delete a room (Admin only)
    """
    supabase = SupabaseClient.get_service_client()
    result = supabase.table("rooms").delete().eq("id", room_id).execute()
    
    # Cameras are deleted by ON DELETE CASCADE in Supabase schema
    return None

