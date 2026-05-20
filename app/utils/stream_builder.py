"""
Stream URL builder for different camera types
"""
from typing import Optional


def build_stream_url(room: dict, channel: Optional[int] = None) -> str:
    """
    Build the stream URL based on camera type.
    
    For DAHUA_DVR: constructs an RTSP URL using DVR IP (or SmartPSS local proxy),
    credentials, and channel number.
    For IP_CAMERA: returns the stored stream_url directly.
    
    Args:
        room: Room document from MongoDB
        channel: Specific channel number to use. If None, uses the first
                 channel in the room's channels list (default 1).
    """
    camera_type = room.get("cameraType")

    if camera_type == "DAHUA_DVR":
        username = room.get("username", "admin")
        password = room.get("password", "admin123")
        rtsp_port = room.get("rtspPort", 554)
        use_local_proxy = room.get("useLocalProxy", True)

        # Determine host: SmartPSS local proxy or direct DVR IP
        if use_local_proxy:
            host = "127.0.0.1"
            rtsp_port = 35639
        else:
            host = room.get("cameraIp", "")

        # Determine channel
        if channel is not None:
            ch = channel
        else:
            channels = room.get("channels") or [1]
            ch = channels[0] if channels else 1

        return (
            f"rtsp://{username}:{password}"
            f"@{host}:{rtsp_port}"
            f"/cam/realmonitor?channel={ch}&subtype=0"
        )

    elif camera_type in ("IP_CAMERA", "UPLOAD_VIDEO"):
        return room.get("streamUrl", "")

    elif camera_type == "LAPTOP_WEBCAM":
        return "0"

    else:
        return ""


def build_all_stream_urls(room: dict) -> list[dict]:
    """
    Build stream URLs for ALL channels of a DVR room.
    Returns a list of {channel, url} dicts.
    For IP_CAMERA, returns a single entry.
    """
    camera_type = room.get("cameraType")

    if camera_type == "DAHUA_DVR":
        channels = room.get("channels") or [1]
        return [
            {"channel": ch, "url": build_stream_url(room, channel=ch)}
            for ch in channels
        ]
    elif camera_type in ("IP_CAMERA", "UPLOAD_VIDEO"):
        url = room.get("streamUrl", "")
        return [{"channel": None, "url": url}] if url else []
    elif camera_type == "LAPTOP_WEBCAM":
        return [{"channel": None, "url": "0"}]
    else:
        return []
