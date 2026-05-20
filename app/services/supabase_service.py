"""
Supabase Service
Handles all user operations with Supabase (PostgreSQL + Auth)
Users: admins, staff, parents, children
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import random
import string
from supabase import create_client, Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def _generate_code(prefix: str, length: int = 6) -> str:
    """Generate a unique code with prefix
    
    Examples: STF-ABC123, PAR-XYZ789, CHD-DEF456
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=length))
    return f"{prefix}-{random_part}"


class SupabaseService:
    """Supabase service for user management"""
    
    def __init__(self):
        # Create a fresh client every time — prevents HTTP/2 "Server disconnected"
        # errors that occur when a long-lived singleton connection is reused after idle.
        self._client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
    
    @property
    def client(self) -> Client:
        return self._client
    
    def _reconnect(self):
        """Recreate the client to recover from a dropped connection."""
        self._client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
    
    # ==================== AUTH HELPER METHODS ====================
    
    def create_auth_user(
        self,
        email: str,
        password: str,
        role: str
    ) -> Dict[str, Any]:
        """Create Supabase auth user"""
        try:
            auth_response = self._client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "role": role
                }
            })
            return {"id": str(auth_response.user.id)}
        except Exception as e:
            logger.error(f"Error creating auth user: {e}")
            raise
    
    def delete_auth_user(self, auth_id: str) -> bool:
        """Delete Supabase auth user"""
        try:
            self._client.auth.admin.delete_user(auth_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting auth user: {e}")
            return False
    
    # ==================== ADMIN METHODS ====================
    
    def create_admin(
        self,
        full_name: str,
        email: str,
        phone: str = None,
        profile_image_url: str = None,
        auth_id: str = None,
        password: str = None
    ) -> Dict[str, Any]:
        """Create admin profile in admins table
        
        If auth_id is provided, uses it directly.
        If password is provided without auth_id, creates auth user first.
        """
        try:
            # Create auth user if password provided but no auth_id
            if password and not auth_id:
                auth_response = self._client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "role": "admin",
                        "full_name": full_name
                    }
                })
                auth_id = str(auth_response.user.id)
            
            # Create admin profile - only include columns that exist in schema
            admin_data = {
                "auth_id": auth_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "profile_image_url": profile_image_url,
                "status": "active"
            }
            
            # Remove None values to avoid inserting nulls
            admin_data = {k: v for k, v in admin_data.items() if v is not None}
            
            result = self._client.table("admins").insert(admin_data).execute()
            
            # Add has_auth_account to response for API compatibility
            data = result.data[0] if result.data else None
            if data:
                data["has_auth_account"] = auth_id is not None
            return data
        except Exception as e:
            logger.error(f"Error creating admin: {e}")
            raise
    
    def get_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get admin by email"""
        result = self._client.table("admins").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    
    def get_all_admins(self) -> List[Dict[str, Any]]:
        """Get all admins"""
        result = self._client.table("admins").select("*").order("created_at", desc=True).execute()
        return result.data
    
    def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """Get admin by ID"""
        result = self._client.table("admins").select("*").eq("id", admin_id).execute()
        return result.data[0] if result.data else None
    
    def get_admin_by_auth_id(self, auth_id: str) -> Optional[Dict[str, Any]]:
        """Get admin by Supabase auth ID"""
        result = self._client.table("admins").select("*").eq("auth_id", auth_id).execute()
        return result.data[0] if result.data else None
    
    def update_admin(self, admin_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update admin profile"""
        update_data["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("admins").update(update_data).eq("id", admin_id).execute()
        return result.data[0] if result.data else None
    
    def delete_admin(self, admin_id: str) -> bool:
        """Delete admin"""
        try:
            admin = self.get_admin_by_id(admin_id)
            if admin and admin.get("auth_id"):
                self._client.auth.admin.delete_user(admin["auth_id"])
            self._client.table("admins").delete().eq("id", admin_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting admin: {e}")
            return False
    
    def get_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get admin by email"""
        result = self._client.table("admins").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    
    def create_auth_user(self, email: str, password: str, role: str = "admin") -> Dict[str, Any]:
        """Create Supabase auth user"""
        try:
            auth_response = self._client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "role": role
                }
            })
            return {"id": str(auth_response.user.id)}
        except Exception as e:
            logger.error(f"Error creating auth user: {e}")
            raise
    
    def delete_auth_user(self, auth_id: str) -> bool:
        """Delete Supabase auth user"""
        try:
            self._client.auth.admin.delete_user(auth_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting auth user: {e}")
            return False
    
    # ==================== STAFF METHODS ====================
    
    def create_staff(
        self,
        full_name: str,
        email: str,
        password: str = None,
        phone: str = None,
        staff_type: str = "staff",  # staff | helper
        login_enabled: bool = True,
        profile_image_url: str = None,
        assigned_room_ids: List[str] = None,
        gender: str = None,
        address: str = None
    ) -> Dict[str, Any]:
        """Create staff user"""
        try:
            auth_id = None
            
            # Create auth user only if login is enabled
            if login_enabled and password and email:
                auth_response = self._client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "role": "staff",
                        "user_type": staff_type,
                        "full_name": full_name
                    }
                })
                auth_id = str(auth_response.user.id)
            
            # Create staff profile with generated code
            staff_code = _generate_code("STF")
            staff_data = {
                "staff_code": staff_code,
                "auth_id": auth_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "staff_type": staff_type,
                "login_enabled": login_enabled,
                "profile_image_url": profile_image_url,
                "assigned_room_ids": assigned_room_ids or [],
                "gender": gender,
                "address": address,
                "status": "active"
            }
            
            # Remove None values
            staff_data = {k: v for k, v in staff_data.items() if v is not None}
            
            result = self._client.table("staff").insert(staff_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating staff: {e}")
            raise
    
    def get_all_staff(self, staff_type: str = None) -> List[Dict[str, Any]]:
        """Get all staff, optionally filtered by type"""
        query = self._client.table("staff").select("*")
        if staff_type:
            query = query.eq("staff_type", staff_type)
        result = query.order("created_at", desc=True).execute()
        return result.data
    
    def get_staff_by_id(self, staff_id: str) -> Optional[Dict[str, Any]]:
        """Get staff by ID"""
        result = self._client.table("staff").select("*").eq("id", staff_id).execute()
        return result.data[0] if result.data else None
    
    def get_staff_by_auth_id(self, auth_id: str) -> Optional[Dict[str, Any]]:
        """Get staff by Supabase auth ID"""
        result = self._client.table("staff").select("*").eq("auth_id", auth_id).execute()
        return result.data[0] if result.data else None
    
    def get_staff_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get staff by email"""
        result = self._client.table("staff").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    
    def update_staff(self, staff_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update staff profile"""
        update_data["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("staff").update(update_data).eq("id", staff_id).execute()
        return result.data[0] if result.data else None
    
    def set_staff_password(self, staff_id: str, email: str, password: str, full_name: str = None) -> Optional[str]:
        """Create or update auth user for staff. Returns auth_id."""
        try:
            staff = self.get_staff_by_id(staff_id)
            if not staff:
                return None
            
            auth_id = staff.get("auth_id")
            
            if auth_id:
                # Update existing auth user's password
                self._client.auth.admin.update_user_by_id(
                    auth_id,
                    {"password": password}
                )
                return auth_id
            else:
                # Create new auth user
                staff_type = staff.get("staff_type", "staff")
                auth_response = self._client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "role": staff_type,
                        "user_type": staff_type,
                        "full_name": full_name or staff.get("full_name")
                    }
                })
                new_auth_id = str(auth_response.user.id)
                # Link auth_id to staff profile
                self._client.table("staff").update({
                    "auth_id": new_auth_id,
                    "login_enabled": True
                }).eq("id", staff_id).execute()
                return new_auth_id
        except Exception as e:
            logger.error(f"Error setting staff password: {e}")
            raise
    
    def delete_staff(self, staff_id: str) -> bool:
        """Soft delete staff"""
        try:
            self._client.table("staff").update({"status": "inactive"}).eq("id", staff_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting staff: {e}")
            return False
    
    # ==================== PARENT METHODS ====================
    
    def create_parent(
        self,
        full_name: str,
        email: str = None,
        password: str = None,
        phone: str = None,
        relationship: str = "Mother",
        address: str = None,
        login_enabled: bool = False,
        profile_image_url: str = None
    ) -> Dict[str, Any]:
        """Create parent user"""
        try:
            auth_id = None
            
            # Create auth user only if login is enabled
            if login_enabled and email and password:
                auth_response = self._client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "role": "parent",
                        "full_name": full_name
                    }
                })
                auth_id = str(auth_response.user.id)
            
            # Create parent profile with generated code
            parent_code = _generate_code("PAR")
            parent_data = {
                "parent_code": parent_code,
                "auth_id": auth_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "relationship": relationship,
                "address": address,
                "login_enabled": login_enabled,
                "profile_image_url": profile_image_url,
                "status": "active"
            }
            
            # Remove None values
            parent_data = {k: v for k, v in parent_data.items() if v is not None}
            
            result = self._client.table("parents").insert(parent_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating parent: {e}")
            raise
    
    def get_all_parents(self) -> List[Dict[str, Any]]:
        """Get all parents"""
        result = self._client.table("parents").select("*").order("created_at", desc=True).execute()
        return result.data
    
    def get_parent_by_id(self, parent_id: str) -> Optional[Dict[str, Any]]:
        """Get parent by ID"""
        result = self._client.table("parents").select("*").eq("id", parent_id).execute()
        return result.data[0] if result.data else None
    
    def get_parent_by_auth_id(self, auth_id: str) -> Optional[Dict[str, Any]]:
        """Get parent by Supabase auth ID"""
        result = self._client.table("parents").select("*").eq("auth_id", auth_id).execute()
        return result.data[0] if result.data else None
    
    def get_parent_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get parent by email"""
        result = self._client.table("parents").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    
    def update_parent(self, parent_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update parent profile"""
        update_data["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("parents").update(update_data).eq("id", parent_id).execute()
        return result.data[0] if result.data else None
    
    def set_parent_password(self, parent_id: str, email: str, password: str, full_name: str = None) -> Optional[str]:
        """Create or update auth user for parent. Returns auth_id."""
        try:
            parent = self.get_parent_by_id(parent_id)
            if not parent:
                return None
            
            auth_id = parent.get("auth_id")
            
            if auth_id:
                # Update existing auth user's password
                self._client.auth.admin.update_user_by_id(
                    auth_id,
                    {"password": password}
                )
                return auth_id
            else:
                # Create new auth user
                if not email:
                    email = parent.get("email")
                if not email:
                    raise ValueError("Email is required to create login credentials")
                auth_response = self._client.auth.admin.create_user({
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "role": "parent",
                        "full_name": full_name or parent.get("full_name")
                    }
                })
                new_auth_id = str(auth_response.user.id)
                # Link auth_id to parent profile
                self._client.table("parents").update({
                    "auth_id": new_auth_id,
                    "login_enabled": True
                }).eq("id", parent_id).execute()
                return new_auth_id
        except Exception as e:
            logger.error(f"Error setting parent password: {e}")
            raise
    
    def delete_parent(self, parent_id: str) -> bool:
        """Soft delete parent"""
        try:
            self._client.table("parents").update({"status": "inactive"}).eq("id", parent_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting parent: {e}")
            return False
    
    # ==================== CHILDREN METHODS ====================
    
    def create_child(
        self,
        full_name: str,
        date_of_birth: str = None,
        gender: str = None,
        parent_id: str = None,
        room_id: str = None,
        medical_notes: str = None,
        allergy_info: str = None,
        profile_image_url: str = None
    ) -> Dict[str, Any]:
        """Create child record"""
        try:
            # Generate child code
            child_code = _generate_code("CHD")
            child_data = {
                "child_code": child_code,
                "full_name": full_name,
                "date_of_birth": date_of_birth,
                "gender": gender,
                "parent_id": parent_id,
                "room_id": room_id,
                "medical_notes": medical_notes,
                "allergies": [allergy_info] if allergy_info else [],
                "profile_image_url": profile_image_url,
                "status": "active",
                "enrollment_status": "active"
            }
            
            # Remove None values
            child_data = {k: v for k, v in child_data.items() if v is not None}
            
            result = self._client.table("children").insert(child_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating child: {e}")
            raise
    
    def get_all_children(self) -> List[Dict[str, Any]]:
        """Get all children with parent info"""
        result = self._client.table("children").select(
            "*, parents(id, full_name, phone, email, relationship)"
        ).order("created_at", desc=True).execute()
        return result.data
    
    def get_child_by_id(self, child_id: str) -> Optional[Dict[str, Any]]:
        """Get child by ID with parent info"""
        result = self._client.table("children").select(
            "*, parents(id, full_name, phone, email, relationship)"
        ).eq("id", child_id).execute()
        return result.data[0] if result.data else None
    
    def update_child(self, child_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update child record"""
        update_data["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("children").update(update_data).eq("id", child_id).execute()
        return result.data[0] if result.data else None
    
    def delete_child(self, child_id: str) -> bool:
        """Soft delete child"""
        try:
            self._client.table("children").update({"status": "inactive"}).eq("id", child_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting child: {e}")
            return False
    
    def get_children_by_parent(self, parent_id: str) -> List[Dict[str, Any]]:
        """Get all children for a parent"""
        result = self._client.table("children").select("*").eq("parent_id", parent_id).execute()
        return result.data
    
    def get_children_by_room(self, room_id: str) -> List[Dict[str, Any]]:
        """Get all children in a room"""
        result = self._client.table("children").select("*").eq("room_id", room_id).execute()
        return result.data
    
    # ==================== FACE EMBEDDINGS METHODS ====================
    
    def insert_face_embedding(self, person_id: str, person_type: str, embeddings: List[List[float]], photo_url: str = None) -> bool:
        """Insert face embeddings for a person"""
        try:
            # Delete any existing embeddings first to avoid duplicates
            self.delete_face_embeddings_for_person(person_id)
            
            # Insert new embeddings
            records = []
            for emb in embeddings:
                records.append({
                    "person_id": person_id,
                    "person_type": person_type,
                    "embedding_vector": emb,
                    "photo_url": photo_url,
                    "is_active": True
                })
            
            if records:
                self._client.table("face_embeddings").insert(records).execute()
            return True
        except Exception as e:
            logger.error(f"Error inserting face embeddings: {e}")
            raise
            
    def delete_face_embeddings_for_person(self, person_id: str) -> bool:
        """Delete all face embeddings for a specific person"""
        try:
            self._client.table("face_embeddings").delete().eq("person_id", person_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting face embeddings: {e}")
            return False

    def list_face_embedding_photo_urls(self, person_id: str, person_type: str) -> List[str]:
        """Return distinct non-empty face photo URLs from embeddings table."""
        try:
            result = (
                self._client.table("face_embeddings")
                .select("photo_url")
                .eq("person_id", person_id)
                .eq("person_type", person_type)
                .eq("is_active", True)
                .execute()
            )
            urls = [
                row.get("photo_url")
                for row in (result.data or [])
                if isinstance(row.get("photo_url"), str) and row.get("photo_url").strip()
            ]
            # Preserve order while de-duplicating.
            return list(dict.fromkeys(urls))
        except Exception as e:
            logger.error(f"Error listing face embedding photo urls: {e}")
            return []
    
    # ==================== AUTH METHODS ====================
    
    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return session"""
        try:
            response = self._client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return {
                "user": response.user,
                "session": response.session
            }
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise
    
    def get_user_role(self, auth_id: str) -> Optional[str]:
        """Determine user role by checking all user tables"""
        # Check admins
        admin = self._client.table("admins").select("id").eq("auth_id", auth_id).execute()
        if admin.data:
            return "admin"
        
        # Check staff
        staff = self._client.table("staff").select("id, staff_type").eq("auth_id", auth_id).execute()
        if staff.data:
            return staff.data[0].get("staff_type", "staff")
        
        # Check parents
        parent = self._client.table("parents").select("id").eq("auth_id", auth_id).execute()
        if parent.data:
            return "parent"
        
        return None
    
    def get_user_profile(self, auth_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by auth ID (checks all user tables)"""
        # Check admins
        admin = self._client.table("admins").select("*").eq("auth_id", auth_id).execute()
        if admin.data:
            return {"role": "admin", "profile": admin.data[0]}
        
        # Check staff
        staff = self._client.table("staff").select("*").eq("auth_id", auth_id).execute()
        if staff.data:
            return {"role": staff.data[0].get("staff_type", "staff"), "profile": staff.data[0]}
        
        # Check parents
        parent = self._client.table("parents").select("*").eq("auth_id", auth_id).execute()
        if parent.data:
            return {"role": "parent", "profile": parent.data[0]}
        
        return None


# Singleton instance
def get_supabase_service() -> SupabaseService:
    """FastAPI dependency — creates a fresh SupabaseService per request.
    This prevents HTTP/2 'Server disconnected' errors caused by reusing
    a long-lived stale connection from a module-level singleton.
    """
    return SupabaseService()
