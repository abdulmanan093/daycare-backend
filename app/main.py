"""
Main FastAPI Application
Entry point for ChildSense AI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.utils.database import MongoDB


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    print("🚀 Starting ChildSense AI Backend...")
    
    # Initialize databases (auto-setup)
    try:
        # Import setup modules
        from app.utils.supabase_setup import initialize_supabase
        
        # Run Supabase setup
        await initialize_supabase()
        
    except Exception as e:
        print(f"⚠️  Database setup encountered an issue: {e}")
        print("   Continuing startup anyway...")
    
    print(f"✅ Application started in {settings.ENVIRONMENT} mode")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    print("✅ Application shut down gracefully")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="FastAPI backend for ChildSense AI ecosystem",
    lifespan=lifespan
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


# Configuration endpoint for clients (dashboard, parent app)
@app.get("/config")
async def get_client_config():
    """
    Returns configuration for client applications (dashboard, parent app).
    This ensures all clients use the same ML service URL.
    """
    return {
        "ml_api_url": settings.ML_SERVICE_URL,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to ChildSense AI Backend API",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
        "config": "/config"
    }


# Import and include routers
from app.api.v1 import router as api_v1_router

app.include_router(api_v1_router, prefix="/api/v1")
