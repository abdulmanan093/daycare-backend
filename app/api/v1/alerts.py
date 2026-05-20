
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, File, UploadFile
from starlette.responses import Response
import httpx
from typing import List, Optional, Any, Tuple, Dict, Set
from urllib.parse import unquote
import base64
import binascii
import re
import uuid
from app.models.alert import AlertCreateRequest, AlertUpdateRequest, AlertStatus, AlertType
from app.dependencies import get_current_user, require_staff_or_admin
from app.models.auth import TokenData
from app.utils.supabase_client import SupabaseClient
from app.config import settings
from app.services.media_service import MediaService
from datetime import datetime
from pydantic import BaseModel, Field

class SystemAlertCreateRequest(BaseModel):
    """Payload from ml_api / internal services. `type` is normalized to DB alert_type."""
    type: str
    severity: str = "medium"
    roomId: Optional[str] = None
    cameraId: Optional[str] = None
    description: str
    media: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    detectedEntityId: Optional[str] = None
    detectedEntityName: Optional[str] = None
    screenshot_base64: Optional[str] = None


def _normalize_ml_alert_type(raw: str) -> str:
    r = (raw or "").strip().lower()
    if r in ("fire", "smoke", "fire_smoke"):
        return "fire_smoke"
    if r in ("unsafe_zone", "safe_zone", "safe_zone_breach"):
        return "safe_zone_breach"
    if r in ("unknown_person", "unknown", "unauthorized", "unauthorized_person"):
        return "unauthorized_person"
    if r in ("distress", "emotion_distress", "cry", "cry_detection"):
        return "emotion_distress"
    allowed = {
        "dangerous_object",
        "fall_detection",
        "cry_detection",
        "fire_smoke",
        "unauthorized_person",
        "emotion_distress",
        "safe_zone_breach",
    }
    if r in allowed:
        return r
    return "unauthorized_person"


def _normalize_ml_severity(raw: str) -> str:
    s = (raw or "medium").strip().lower()
    return {
        "info": "low",
 "low": "low",
        "warning": "medium",
        "medium": "medium",
        "error": "high",
        "high": "high",
        "critical": "critical",
    }.get(s, "medium")


def _human_alert_title(alert_type: str, detected_entity_name: Optional[str] = None, description: Optional[str] = None) -> str:
    t = alert_type or "alert"
    if t == "fire_smoke":
        title = "Smoke detected" if description and "smoke" in description.lower() else "Fire detected"
    elif t == "safe_zone_breach":
        title = "Safe zone breach"
    elif t == "unauthorized_person":
        title = "Unauthorized person"
    elif t == "emotion_distress":
        title = "Distress detected"
    else:
        title = t.replace("_", " ").capitalize()
    if detected_entity_name:
        title = f"{title} — {detected_entity_name}"
    return title


def _normalize_ml_description(description: str, raw_type: str) -> str:
    desc = (description or "").strip()
    if not desc:
        if raw_type in ("fire", "smoke"):
            return f"{raw_type.capitalize()} detected — take action immediately!"
        return "An alert has been detected."
    if raw_type in ("fire", "smoke"):
        if "detected" in desc.lower():
            label = "Fire" if raw_type == "fire" else "Smoke"
            return f"{label} detected — take action immediately!"
    desc = re.sub(r"\s*for \d+s?", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\s*\(conf=[^)]+\)", "", desc, flags=re.IGNORECASE)
    desc = desc.strip()
    return desc


def _extract_person_label(description: str, metadata: Any) -> Optional[str]:
    meta = metadata if isinstance(metadata, dict) else {}
    candidates = [
        meta.get("detected_entity_name"),
        meta.get("detectedEntityName"),
        meta.get("person_label"),
        meta.get("label"),
        meta.get("identity_label"),
        meta.get("name"),
        meta.get("child_name"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    if description:
        match = re.search(r"Track #\d+ \(([^)]+)\)", description)
        if match:
            return match.group(1).strip()
        match = re.search(r"\b(Person \d+)\b", description)
        if match:
            return match.group(1).strip()
        if "unknown person" in description.lower():
            return "Unknown"
    return None


def _should_notify_parents(detected_entity_name: Optional[str], metadata: Any) -> bool:
    if detected_entity_name:
        return True
    if isinstance(metadata, dict):
        if metadata.get("detected_entity_id") or metadata.get("detectedEntityId") or metadata.get("child_id") or metadata.get("childId"):
            return True
    return False


def _media_paths_for_public_url(val: str) -> str:
    """Turn stored relative paths into `bucket/path` for Supabase public URL."""
    if not val or val.startswith("http"):
        return val
    b_alerts = settings.SUPABASE_BUCKET_ALERTS
    if val.startswith("clips/"):
        return f"alert-clips/{val}"
    if val.startswith(f"{b_alerts}/"):
        return val
    return f"{b_alerts}/{val}"


def _parse_storage_object_ref(url_or_path: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (bucket, object_key) for a Supabase public object URL or 'bucket/key' path."""
    if not url_or_path or not isinstance(url_or_path, str):
        return None
    s = url_or_path.strip()
    if not s:
        return None
    # Skip internal placeholders (processing://, None-as-string, etc.)
    if s.startswith("processing://") or s == "None":
        return None
    s = s.split("?")[0]
    marker = "/storage/v1/object/public/"
    if marker in s:
        tail = s.split(marker, 1)[1]
        if "/" not in tail:
            return None
        bucket, path = tail.split("/", 1)
        return bucket, unquote(path)
    if s.startswith("http"):
        return None
    if "/" in s:
        bucket, path = s.split("/", 1)
        return bucket, unquote(path)
    return None


def _collect_alert_storage_paths(alert: dict, clip_rows: List[dict]) -> Dict[str, Set[str]]:
    """Group storage object keys by bucket name for removal."""
    by_bucket: Dict[str, Set[str]] = {}

    def add_ref(ref: Optional[str]) -> None:
        parsed = _parse_storage_object_ref(ref)
        if not parsed:
            return
        b, key = parsed
        if b and key:
            by_bucket.setdefault(b, set()).add(key)

    media = alert.get("media") or {}
    if isinstance(media, dict):
        add_ref(media.get("videoUrl"))
        add_ref(media.get("screenshotUrl"))

    add_ref(alert.get("clip_url"))
    add_ref(alert.get("screenshot_url"))

    for row in clip_rows or []:
        if not isinstance(row, dict):
            continue
        add_ref(row.get("storage_url"))
        bn = row.get("bucket_name") or "alert-clips"
        fn = row.get("file_name")
        if fn and isinstance(fn, str):
            by_bucket.setdefault(bn, set()).add(fn)

    return by_bucket


def _delete_alert_files(supabase, alert: dict) -> None:
    """Best-effort removal of clip/screenshot objects from Supabase Storage."""
    clip_rows: List[dict] = []
    try:
        clips = (
            supabase.table("alert_clips")
            .select("storage_url, bucket_name, file_name")
            .eq("alert_id", alert.get("id"))
            .execute()
        )
        clip_rows = clips.data or []
    except Exception as e:
        print(f"⚠️ alert_clips lookup (optional): {e}")

    grouped = _collect_alert_storage_paths(alert, clip_rows)
    for bucket, keys in grouped.items():
        if not keys:
            continue
        try:
            supabase.storage.from_(bucket).remove(list(keys))
            print(f"🗑️ Removed {len(keys)} object(s) from bucket '{bucket}' for alert {alert.get('id')}")
        except Exception as e:
            print(f"⚠️ Storage remove failed bucket={bucket} keys={list(keys)[:3]}…: {e}")


router = APIRouter()

def _send_push_notifications(supabase, title: str, body: str, role_filter: Optional[str] = None) -> None:
    """Send Expo push notifications to registered tokens, optionally filtered by user role."""
    try:
        if role_filter == "staff":
            res = supabase.table("user_push_tokens").select("token").eq("app_role", "staff").execute()
        elif role_filter == "parent":
            res = supabase.table("user_push_tokens").select("token").eq("app_role", "parent").execute()
        else:
            res = supabase.table("user_push_tokens").select("token").execute()

        tokens = [row.get("token") for row in (res.data or []) if row.get("token")]
        print(f"Found {len(tokens)} push tokens for role_filter='{role_filter}'")  # Debug
    except Exception as e:
        print(f"⚠️ push token lookup failed: {e}")
        return

    if not tokens:
        print(f"No tokens found for role_filter='{role_filter}', skipping push")
        return

    payload = [
        {
            "to": token,
            "title": title,
            "body": body,
            "sound": "default",
            "priority": "high",
        }
        for token in tokens
    ]

    print(f"Sending push notification to {len(tokens)} tokens with title: {title}")  # Debug
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.post("https://exp.host/--/api/v2/push/send", json=payload)
            if r.status_code >= 400:
                print(f"⚠️ push send failed: {r.status_code} {r.text[:200]}")
            else:
                print(f"✅ Push sent successfully to {len(tokens)} tokens")
    except Exception as e:
        print(f"⚠️ push send error: {e}")


def _send_parent_notifications(supabase, title: str, body: str) -> None:
    """Send notifications to ALL parents (used when a specific child is detected)."""
    _send_push_notifications(
        supabase,
        title=title,
        body=body,
        role_filter="parent"
    )


def _send_room_parent_notifications(supabase, room_id: str, title: str, body: str) -> None:
    """Send push notifications only to parents whose children are in the given room."""
    if not room_id:
        # No room info — fall back to all parents
        _send_parent_notifications(supabase, title=title, body=body)
        return
    try:
        # 1. Find all children assigned to this room
        children_res = (
            supabase.table("children")
            .select("parent_id")
            .eq("room_id", room_id)
            .execute()
        )
        parent_ids = [
            row["parent_id"]
            for row in (children_res.data or [])
            if row.get("parent_id")
        ]
        if not parent_ids:
            print(f"No children found in room {room_id}, skipping room parent notify.")
            return

        # 2. Find auth_ids for those parents
        parents_res = (
            supabase.table("parents")
            .select("auth_id")
            .in_("id", parent_ids)
            .execute()
        )
        auth_ids = [
            row["auth_id"]
            for row in (parents_res.data or [])
            if row.get("auth_id")
        ]
        if not auth_ids:
            print(f"No auth_ids found for parents in room {room_id}, skipping.")
            return

        # 3. Get push tokens for those auth_ids (user_push_tokens.user_id = auth.users.id)
        tokens_res = (
            supabase.table("user_push_tokens")
            .select("token")
            .eq("app_role", "parent")
            .in_("user_id", auth_ids)
            .execute()
        )
        tokens = [
            row["token"]
            for row in (tokens_res.data or [])
            if row.get("token")
        ]
        if not tokens:
            print(f"No push tokens found for parents in room {room_id}.")
            return

        print(f"Sending room-targeted notification to {len(tokens)} parent token(s) for room {room_id}.")
        payload = [
            {
                "to": token,
                "title": title,
                "body": body,
                "sound": "default",
                "priority": "high",
            }
            for token in tokens
        ]
        with httpx.Client(timeout=8.0) as client:
            r = client.post("https://exp.host/--/api/v2/push/send", json=payload)
            if r.status_code >= 400:
                print(f"⚠️ room parent push send failed: {r.status_code} {r.text[:200]}")
            else:
                print(f"✅ Room parent push sent to {len(tokens)} token(s) in room {room_id}")
    except Exception as e:
        print(f"⚠️ _send_room_parent_notifications error: {e}")

def _map_alert_to_frontend(alert: dict) -> dict:
    """Map Supabase column names to frontend expected names."""
    raw_status = (alert.get("status") or "active").lower()
    # Normalise to title-case so the frontend always gets 'Active' | 'Acknowledged' | 'Resolved'
    status_display = {
        "active": "Active",
        "acknowledged": "Acknowledged",
        "resolved": "Resolved",
    }.get(raw_status, "Active")

    room_name = alert.get("room_name")
    if not room_name and alert.get("rooms"):
        room_name = alert.get("rooms", {}).get("room_name")

    camera_name = None
    if alert.get("cameras"):
        camera_name = alert.get("cameras", {}).get("camera_name")

    child_name = alert.get("detected_entity_name")
    if not child_name and alert.get("children"):
        child_name = alert.get("children", {}).get("full_name")

    media = alert.get("media") or {"videoUrl": None, "screenshotUrl": None}
    
    # Convert relative storage paths to public object URLs (bucket must allow public read or use signed URLs later)
    for key in ["videoUrl", "screenshotUrl"]:
        val = media.get(key)
        if val and not val.startswith("http"):
            path = _media_paths_for_public_url(val)
            media[key] = f"{settings.SUPABASE_URL}/storage/v1/object/public/{path}"

    return {
        "alertId": alert.get("id"),
        "type": alert.get("alert_type"),
        "severity": alert.get("severity"),
        "status": status_display,
        "description": alert.get("description"),
        "roomId": alert.get("room_id"),
        "roomName": room_name,
        "cameraId": alert.get("camera_id"),
        "cameraName": camera_name,
        "detectedEntityId": alert.get("detected_entity_id"),
        "detectedEntityName": child_name,
        "media": media,
        "metadata": alert.get("metadata") or {},
        "acknowledged": raw_status in ("resolved", "acknowledged"),
        "acknowledgedBy": alert.get("acknowledged_by"),
        "acknowledgedAt": alert.get("acknowledged_at"),
        "timestamp": alert.get("created_at"),
        "createdAt": alert.get("created_at"),
        "notes": alert.get("acknowledge_notes"),
        "staffNotes": alert.get("staff_notes") or "",
        "adminNotes": alert.get("admin_notes") or "",
    }

@router.get("", response_model=List[Any])
def get_alerts(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    type: Optional[str] = None,
    room_id: Optional[str] = None,
    lite: bool = False,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get all alerts with optional filtering.
    Returns plain dicts to avoid Pydantic enum validation failures on DB data.
    Use lite=true for faster list rows (no room/camera join).
    """
    supabase = SupabaseClient.get_service_client()
    if lite:
        select_cols = (
            # List view: keep payload small (no *) — detail endpoint can fetch full row.
            "id, alert_type, severity, status, description, room_id, camera_id, media, "
            "created_at, detected_entity_id, detected_entity_name, staff_notes, admin_notes, acknowledge_notes, "
            "rooms(room_name), cameras(camera_name)"
        )
    else:
        # Even non-lite list should not pull *, because media/metadata JSON can be large.
        select_cols = (
            "id, alert_type, severity, status, description, room_id, camera_id, media, metadata, "
            "created_at, detected_entity_id, detected_entity_name, staff_notes, admin_notes, acknowledge_notes, "
            "rooms(room_name), cameras(camera_name)"
        )

    query = supabase.table("alerts").select(select_cols)

    if status and status.lower() != "all":
        # Status is stored lowercase ("active" | "acknowledged" | "resolved") so indexes work.
        query = query.eq("status", status.strip().lower())
    if type and type.lower() != "all":
        query = query.eq("alert_type", type)
    if room_id:
        query = query.eq("room_id", room_id)

    cap = min(max(limit, 1), 500)
    sk = max(skip, 0)
    # Sort and pagination
    result = query.order("created_at", desc=True).range(sk, sk + cap - 1).execute()

    return [_map_alert_to_frontend(a) for a in (result.data or [])]


@router.get("/counts")
def get_alert_status_counts(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Head-only counts per status for dashboard cards (no alert row payload).
    Declared before /{alert_id} so 'counts' is not parsed as an id.
    """
    supabase = SupabaseClient.get_service_client()

    def _count_by_status(svc, status_value: str) -> int:
        # Use limit(1) + count=exact so Content-Range returns totals
        res = (
            svc.table("alerts")
            .select("id", count="exact")
            .eq("status", status_value)
            .limit(1)
            .execute()
        )
        return res.count or 0

    try:
        return {
            "active": _count_by_status(supabase, "active"),
            "acknowledged": _count_by_status(supabase, "acknowledged"),
            "resolved": _count_by_status(supabase, "resolved"),
        }
    except Exception as e:
        # Supabase HTTP/2 connections can occasionally reset on Windows dev.
        # Retry once with a fresh service client to avoid bubbling 500s.
        print(f"⚠️ alerts/counts transient failure: {e}; retrying once")
        try:
            supabase2 = SupabaseClient.get_service_client()
            return {
                "active": _count_by_status(supabase2, "active"),
                "acknowledged": _count_by_status(supabase2, "acknowledged"),
                "resolved": _count_by_status(supabase2, "resolved"),
            }
        except Exception as e2:
            print(f"⚠️ alerts/counts retry failed: {e2}")
            return {"active": 0, "acknowledged": 0, "resolved": 0}


@router.get("/{alert_id}", response_model=Any)
def get_alert(
    alert_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get alert by ID
    """
    supabase = SupabaseClient.get_service_client()
    result = supabase.table("alerts").select("*, rooms(room_name), cameras(camera_name)").eq("id", alert_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert_data = result.data[0]
    

            
    return _map_alert_to_frontend(alert_data)

@router.post("", response_model=Any, status_code=status.HTTP_201_CREATED)
def create_alert(
    alert_data: AlertCreateRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Create a new alert
    """
    supabase = SupabaseClient.get_service_client()

    child_id = alert_data.childId or alert_data.detectedEntityId
    insert_data = {
        "alert_type": alert_data.type.value if hasattr(alert_data.type, 'value') else alert_data.type,
        "severity": alert_data.severity.value if hasattr(alert_data.severity, 'value') else str(alert_data.severity),
        "description": alert_data.description,
        "room_id": alert_data.roomId,
        "camera_id": alert_data.cameraId,
        "detected_entity_id": child_id,
        "media": (alert_data.media.model_dump() if hasattr(alert_data.media, 'model_dump') else dict(alert_data.media)) if alert_data.media else {},
        "metadata": alert_data.metadata or {},
        # Store lowercase to unlock (status, created_at) indexes.
        "status": "active"
    }

    # Remove Nones
    insert_data = {k: v for k, v in insert_data.items() if v is not None}

    result = supabase.table("alerts").insert(insert_data).execute()
    row = result.data[0]
    _send_push_notifications(
        supabase,
        title=f"STAFF Notification: 🚨Alert: {row.get('alert_type', 'alert')}",
        body=row.get("description") or "A new alert has been triggered.",
        role_filter="staff"
    )
    return _map_alert_to_frontend(row)

@router.post("/system", response_model=Any, status_code=status.HTTP_201_CREATED)
def create_system_alert(
    alert_data: SystemAlertCreateRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
):
    """
    Create alert from trusted internal ML service.
    """
    if x_api_key != settings.ML_ALERT_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    supabase = SupabaseClient.get_service_client()
    normalized_type = _normalize_ml_alert_type(alert_data.type)
    normalized_severity = _normalize_ml_severity(alert_data.severity)
    normalized_description = _normalize_ml_description(alert_data.description, alert_data.type)
    
    detected_entity_name = alert_data.detectedEntityName or _extract_person_label(alert_data.description, alert_data.metadata)
    detected_entity_id = alert_data.detectedEntityId

    media = dict(alert_data.media or {})
    if not media.get("videoUrl"):
        media["videoUrl"] = None
    if not media.get("screenshotUrl"):
        media["screenshotUrl"] = None

    if normalized_type == "fire_smoke" and alert_data.roomId:
        # Throttle per raw sub-type (fire vs smoke) so a smoke alert does not
        # block a fire alert and vice versa.
        raw_subtype = (alert_data.type or "").strip().lower()  # "fire" or "smoke"
        # Check if there's already an active alert of the same raw sub-type
        existing = (
            supabase.table("alerts")
            .select("id")
            .eq("alert_type", "fire_smoke")
            .eq("status", "active")
            .eq("room_id", alert_data.roomId)
            .contains("metadata", {"ml_subtype": raw_subtype})
            .limit(1)
            .execute()
        )
        if existing.data:
            # Return early without creating a new alert
            return {"detail": f"Throttled: Active {raw_subtype} alert already exists for this room.", "status": "throttled", "id": existing.data[0]["id"]}

    # Build metadata — inject raw subtype so per-type throttle check works
    base_meta = dict(alert_data.metadata or {})
    raw_subtype_for_meta = (alert_data.type or "").strip().lower()
    if normalized_type == "fire_smoke" and raw_subtype_for_meta in ("fire", "smoke"):
        base_meta["ml_subtype"] = raw_subtype_for_meta

    insert_data = {
        "alert_type": normalized_type,
        "severity": normalized_severity,
        "description": normalized_description,
        "room_id": alert_data.roomId,
        "camera_id": alert_data.cameraId,
        "detected_entity_id": detected_entity_id,
        "detected_entity_name": detected_entity_name,
        # Do NOT store a placeholder videoUrl — clip upload patches media.videoUrl later.
        # Storing "processing://..." causes phantom storage refs during delete.
        "media": {"videoUrl": None, "screenshotUrl": media.get("screenshotUrl")},
        "metadata": base_meta,
        "status": "active",
    }
    insert_data = {k: v for k, v in insert_data.items() if v is not None}

    result = supabase.table("alerts").insert(insert_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create alert")

    row = result.data[0]
    alert_id = row.get("id")

    # Optional screenshot from ML (base64 JPEG/PNG)
    raw_b64 = alert_data.screenshot_base64
    if raw_b64 and alert_id:
        try:
            payload = raw_b64.strip()
            if payload.startswith("data:") and "," in payload:
                payload = payload.split(",", 1)[1]
            raw = base64.b64decode(payload, validate=False)
            if len(raw) > 50:
                media_svc = MediaService()
                path = media_svc.upload_alert_screenshot_bytes(raw, str(alert_id))
                merged = dict(row.get("media") or {})
                merged["screenshotUrl"] = path
                supabase.table("alerts").update({"media": merged}).eq("id", alert_id).execute()
                row = supabase.table("alerts").select("*").eq("id", alert_id).execute().data[0]
        except (binascii.Error, ValueError, Exception):
            pass

    _send_push_notifications(
        supabase,
        title=f"🚨 {_human_alert_title(normalized_type, row.get('detected_entity_name'), normalized_description)}",
        body=normalized_description,
        role_filter="staff"
    )

    # Fire/smoke: notify ONLY parents whose children are in the affected room
    if normalized_type == "fire_smoke":
        _send_room_parent_notifications(
            supabase,
            room_id=alert_data.roomId,
            title=f"🔥 {_human_alert_title(normalized_type, None, normalized_description)}",
            body=normalized_description,
        )
    elif _should_notify_parents(detected_entity_name, alert_data.metadata):
        # For child-specific alerts (e.g. distress), notify the specific child's parent
        if detected_entity_id:
            # Look up the child's parent_id and notify only them
            try:
                child_res = supabase.table("children").select("parent_id").eq("id", detected_entity_id).single().execute()
                parent_id = child_res.data.get("parent_id") if child_res.data else None
                if parent_id:
                    parent_res = supabase.table("parents").select("auth_id").eq("id", parent_id).single().execute()
                    auth_id = parent_res.data.get("auth_id") if parent_res.data else None
                    if auth_id:
                        tokens_res = supabase.table("user_push_tokens").select("token").eq("app_role", "parent").eq("user_id", auth_id).execute()
                        tokens = [r["token"] for r in (tokens_res.data or []) if r.get("token")]
                        if tokens:
                            payload = [{"to": t, "title": f"🚨 {_human_alert_title(normalized_type, detected_entity_name, normalized_description)}", "body": normalized_description, "sound": "default", "priority": "high"} for t in tokens]
                            with httpx.Client(timeout=8.0) as client:
                                client.post("https://exp.host/--/api/v2/push/send", json=payload)
            except Exception as e:
                print(f"⚠️ specific parent notify error: {e}")
        else:
            _send_parent_notifications(
                supabase,
                title=f"🚨 {_human_alert_title(normalized_type, detected_entity_name, normalized_description)}",
                body=normalized_description,
            )
    return _map_alert_to_frontend(row)

@router.put("/{alert_id}", response_model=Any)
def update_alert(
    alert_id: str,
    alert_data: AlertUpdateRequest,
    current_user: TokenData = Depends(require_staff_or_admin),
):
    """
    Update an alert (staff + admin). Uses service role so RLS does not block staff.
    staff_notes / admin_notes: each role may only update its own field.
    acknowledged_by is set only for admins (DB FK targets admins.id).
    """
    supabase = SupabaseClient.get_service_client()
    role = (current_user.role or "").lower()
    profile_id = current_user.userId

    update_dict = {}
    if alert_data.status is not None:
        raw_status = alert_data.status.value if hasattr(alert_data.status, "value") else str(alert_data.status)
        s = (raw_status or "").strip().lower()
        if s in ("active", "acknowledged", "resolved"):
            update_dict["status"] = s
        if update_dict.get("status") in ("resolved", "acknowledged"):
            update_dict["acknowledged_at"] = datetime.utcnow().isoformat()
            if role == "admin" and profile_id:
                update_dict["acknowledged_by"] = profile_id
    if getattr(alert_data, 'description', None) is not None:
        if role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can edit alert description")
        update_dict["description"] = alert_data.description

    # Dual notes: staff vs admin (do not overwrite each other)
    if alert_data.staffNotes is not None:
        if role != "staff":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only staff can update staff notes",
            )
        update_dict["staff_notes"] = alert_data.staffNotes

    admin_text = alert_data.adminNotes
    if admin_text is None and alert_data.notes is not None and role == "admin":
        admin_text = alert_data.notes
    if admin_text is not None:
        if role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can update admin notes",
            )
        update_dict["admin_notes"] = admin_text
        # Keep legacy column in sync for SQL reports / old clients
        update_dict["acknowledge_notes"] = admin_text

    if update_dict:
        result = supabase.table("alerts").update(update_dict).eq("id", alert_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Alert not found")
        return _map_alert_to_frontend(result.data[0])

    # If no updates, just fetch and return
    result = supabase.table("alerts").select("*").eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _map_alert_to_frontend(result.data[0])


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: str,
    current_user: TokenData = Depends(require_staff_or_admin),
):
    """
    Permanently remove an alert, related DB rows (FK cascade), and stored media (clip/screenshot).
    Used by Dismiss in admin dashboard and staff app.
    """
    supabase = SupabaseClient.get_service_client()
    existing = supabase.table("alerts").select("*").eq("id", alert_id).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert_row = existing.data[0]
    _delete_alert_files(supabase, alert_row)

    supabase.table("alerts").delete().eq("id", alert_id).execute()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{alert_id}/clip", response_model=Any)
async def upload_alert_clip(
    alert_id: str,
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Accept an ML-annotated video clip for an alert, upload to Supabase Storage,
    and patch the alert row's media.videoUrl so the dashboard video player works.

    Called by ml_api after a 10s pre + 15s post alert clip is encoded.
    Auth: same ML_ALERT_API_KEY as the /system endpoint.
    """
    if x_api_key != settings.ML_ALERT_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    supabase = SupabaseClient.get_service_client()

    # Verify alert exists
    check = supabase.table("alerts").select("id, media").eq("id", alert_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Upload clip to Supabase Storage under alert-clips bucket
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Extract extension dynamically (e.g. webm, mp4)
    file_ext = file.filename.split('.')[-1].lower() if file.filename and '.' in file.filename else 'webm'
    content_type = file.content_type or f"video/{file_ext}"

    bucket = settings.SUPABASE_BUCKET_ALERTS
    # Store directly in the bucket root as requested
    clip_filename = f"{alert_id}_{uuid.uuid4().hex[:8]}.{file_ext}"

    try:
        supabase.storage.from_(bucket).upload(
            clip_filename,
            content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")

    # Build a public URL for the clip (bucket must be public, or use signed URLs)
    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{clip_filename}"

    existing_media = dict(check.data[0].get("media") or {})
    old_url = existing_media.get("videoUrl")

    # If this alert somehow already had a clip, delete it from storage to avoid orphaned files
    if old_url:
        parsed = _parse_storage_object_ref(old_url)
        if parsed:
            b, key = parsed
            try:
                supabase.storage.from_(b).remove([key])
                print(f"🗑️ Cleaned up previous clip '{key}' from bucket '{b}'")
            except Exception:
                pass

    # Patch the alert's media.videoUrl
    existing_media["videoUrl"] = public_url

    update_res = (
        supabase.table("alerts")
        .update({"media": existing_media})
        .eq("id", alert_id)
        .execute()
    )
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to patch alert media")

    print(f"🎬 Alert {alert_id}: clip uploaded and media.videoUrl patched → {public_url}")
    return _map_alert_to_frontend(update_res.data[0])
