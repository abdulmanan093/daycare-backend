# ChildSense AI Backend

FastAPI backend for the ChildSense AI ecosystem, serving Admin Dashboard, Staff App, and Parent App.

## Tech Stack

- **Framework**: FastAPI
- **Databases**: MongoDB (AI/ML data) + Supabase (Auth & Storage)
- **Authentication**: JWT tokens
- **ML**: InsightFace for face recognition

## Setup

### Prerequisites

- Python 3.9+
- MongoDB Atlas account
- Supabase account

### Installation

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run the server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Access API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Architecture

### Database Strategy

**MongoDB** stores:
- User profiles (admin, staff, helpers, parents)
- Child profiles
- Face embeddings
- Alerts and activity logs
- Access permissions

**Supabase** handles:
- Authentication
- Media storage (profile images, alert videos, screenshots)
- Real-time features

### Access Control

| Role   | Admin Dashboard | Staff App | Parent App |
|--------|----------------|-----------|------------|
| Admin  | ✅             | ❌        | ❌         |
| Staff  | ❌             | ✅        | ❌         |
| Parent | ❌             | ❌        | ✅         |
| Helper | ❌             | ❌        | ❌         |
| Child  | ❌             | ❌        | ❌         |

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/token/refresh` - Refresh token
- `GET /api/v1/auth/me` - Get current user

### User Management
- `POST /api/v1/users/{role}` - Create user (admin, staff, helper, parent)
- `GET /api/v1/users/{role}` - List users by role
- `GET /api/v1/users/{role}/{id}` - Get user details
- `PUT /api/v1/users/{role}/{id}` - Update user
- `DELETE /api/v1/users/{role}/{id}` - Delete user

### Children Management
- `POST /api/v1/children` - Create child
- `GET /api/v1/children` - List children
- `GET /api/v1/children/{id}` - Get child details
- `PUT /api/v1/children/{id}` - Update child

### Alerts
- `GET /api/v1/alerts` - List alerts (role-filtered)
- `GET /api/v1/alerts/{id}` - Get alert with signed media URLs
- `POST /api/v1/alerts/{id}/acknowledge` - Acknowledge alert

## Privacy & Security

- ✅ Face images are **immediately deleted** after embedding generation
- ✅ Media access uses **time-limited signed URLs** (5-minute expiry)
- ✅ Role-based access control on all endpoints
- ✅ JWT tokens with refresh mechanism
- ✅ Passwords hashed with bcrypt

## Development

### Project Structure
```
backend/
├── app/
│   ├── api/v1/          # API routes
│   ├── models/          # Pydantic models
│   ├── schemas/         # MongoDB schemas
│   ├── services/        # Business logic
│   ├── utils/           # Utilities
│   └── ml/              # ML services
├── tests/               # Test suite
└── requirements.txt
```

## License

Private - ChildSense AI Project
