"""
MongoDB Database Setup
Automatically creates collections, indexes, and sample data
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from app.config import settings
from datetime import datetime
import bcrypt


class MongoDBSetup:
    """Handles MongoDB database initialization"""
    
    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client[settings.MONGODB_DATABASE]
    
    async def setup_all(self, seed_sample_data: bool = False):
        """Run all setup tasks"""
        print("🔵 Setting up MongoDB...")
        
        try:
            # 1. Create collections
            await self.create_collections()
            
            # 2. Create indexes
            await self.create_indexes()
            
            # 3. Optionally seed sample data
            if seed_sample_data:
                await self.seed_sample_data()
            
            print("✅ MongoDB setup completed successfully!")
            
        except Exception as e:
            print(f"⚠️  MongoDB setup warning: {e}")
    
    async def create_collections(self):
        """Create all required collections
        
        Note: User collections (staff, parents, children) are now in Supabase.
        Only operational data remains in MongoDB.
        """
        print("  📚 Creating collections...")
        
        # Only operational data - users are now in Supabase
        collections = [
            "rooms",
            "cameras",
            "face_embeddings",
            "alerts",
            "attendance_logs",
            "activity_logs"
        ]
        
        existing_collections = await self.db.list_collection_names()
        
        for collection_name in collections:
            if collection_name not in existing_collections:
                await self.db.create_collection(collection_name)
                print(f"    ✓ Created collection: {collection_name}")
            else:
                print(f"    ℹ Collection already exists: {collection_name}")
    
    async def create_indexes(self):
        """Create indexes for all collections
        
        Note: User collections (staff, parents, children) are now in Supabase.
        Only operational data indexes are created here.
        """
        print("  📇 Creating indexes...")
        
        # === ROOMS Indexes ===
        rooms_indexes = [
            IndexModel([("name", ASCENDING)], unique=True),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("cameraIp", ASCENDING)])
        ]
        try:
            await self.db.rooms.create_indexes(rooms_indexes)
            print("    ✓ Rooms indexes created")
        except Exception as e:
            print(f"    ℹ Rooms indexes: {str(e)[:50]}")
        
        # === CAMERAS Indexes ===
        cameras_indexes = [
            IndexModel([("camera_code", ASCENDING)], unique=True),
            IndexModel([("room_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)])
        ]
        try:
            await self.db.cameras.create_indexes(cameras_indexes)
            print("    ✓ Cameras indexes created")
        except Exception as e:
            print(f"    ℹ Cameras indexes: {str(e)[:50]}")
        
        # === FACE_EMBEDDINGS Indexes ===
        face_embeddings_indexes = [
            IndexModel([("entity_type", ASCENDING), ("entity_id", ASCENDING)]),
            IndexModel([("is_active", ASCENDING)])
        ]
        try:
            await self.db.face_embeddings.create_indexes(face_embeddings_indexes)
            print("    ✓ Face embeddings indexes created")
        except Exception as e:
            print(f"    ℹ Face embeddings indexes: {str(e)[:50]}")
        
        # === ALERTS Indexes ===
        alerts_indexes = [
            IndexModel([("status", ASCENDING)]),
            IndexModel([("alert_type", ASCENDING)]),
            IndexModel([("severity", ASCENDING)]),
            IndexModel([("camera_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)])
        ]
        try:
            await self.db.alerts.create_indexes(alerts_indexes)
            print("    ✓ Alerts indexes created")
        except Exception as e:
            print(f"    ℹ Alerts indexes: {str(e)[:50]}")
        
        # === ATTENDANCE_LOGS Indexes ===
        attendance_indexes = [
            IndexModel([("child_id", ASCENDING), ("date", DESCENDING)]),
            IndexModel([("date", DESCENDING)]),
            IndexModel([("check_in.time", DESCENDING)])
        ]
        try:
            await self.db.attendance_logs.create_indexes(attendance_indexes)
            print("    ✓ Attendance logs indexes created")
        except Exception as e:
            print(f"    ℹ Attendance logs indexes: {str(e)[:50]}")
        
        # === ACTIVITY_LOGS Indexes ===
        activity_indexes = [
            IndexModel([("actor_id", ASCENDING)]),
            IndexModel([("resource_type", ASCENDING), ("resource_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)])
        ]
        try:
            await self.db.activity_logs.create_indexes(activity_indexes)
            print("    ✓ Activity logs indexes created")
        except Exception as e:
            print(f"    ℹ Activity logs indexes: {str(e)[:50]}")
    
    async def seed_sample_data(self):
        """Insert sample data for testing (optional)"""
        print("  🌱 Seeding sample data...")
        
        # Check if data already exists
        room_count = await self.db.rooms.count_documents({})
        
        if room_count > 0:
            print(f"    ℹ Sample data already exists ({room_count} rooms)")
            return
        
        # Sample Room
        sample_room = {
            "room_code": "RM001",
            "room_name": "Sunflower Room",
            "room_type": "classroom",
            "capacity": 15,
            "current_occupancy": 0,
            "age_group": {
                "min_age_months": 24,
                "max_age_months": 48
            },
            "assigned_staff_ids": [],
            "camera_ids": [],
            "floor_number": 1,
            "building": "Main Building",
            "room_color_code": "#FFD700",
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            result = await self.db.rooms.insert_one(sample_room)
            print(f"    ✓ Sample room created: {sample_room['room_name']}")
            room_id = result.inserted_id
            
            # Sample Camera linked to room
            sample_camera = {
                "camera_code": "CAM001",
                "camera_name": "Sunflower Room - Entry",
                "room_id": room_id,
                "camera_type": "ip_camera",
                "connection_details": {
                    "ip_address": "192.168.1.100",
                    "port": 554,
                    "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                    "username": "admin",
                    "password": "[ENCRYPTED]"
                },
                "resolution": {
                    "width": 1920,
                    "height": 1080
                },
                "fps": 30,
                "location": {
                    "position": "entry_door",
                    "floor_number": 1,
                    "building": "Main Building"
                },
                "ai_features_enabled": {
                    "face_recognition": True,
                    "attendance_tracking": True,
                    "stranger_detection": True,
                    "activity_monitoring": False
                },
                "status": "online",
                "last_heartbeat": datetime.utcnow(),
                "last_face_detected": datetime.utcnow(),
                "installation_date": datetime(2024, 1, 1),
                "maintenance_schedule": "monthly",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await self.db.cameras.insert_one(sample_camera)
            print(f"    ✓ Sample camera created: {sample_camera['camera_name']}")
            
            print("  ✅ Sample data seeded successfully!")
            
        except Exception as e:
            print(f"    ⚠️  Error seeding sample data: {e}")


async def initialize_mongodb(client: AsyncIOMotorClient, seed_data: bool = False):
    """Main function to initialize MongoDB"""
    setup = MongoDBSetup(client)
    await setup.setup_all(seed_sample_data=seed_data)
