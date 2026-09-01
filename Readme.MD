# 🚀 SocialPilot — Social Media Management Platform
backend:- .venv\Scripts\activate uvicorn app.main:app --reload

fronten:- npm run dev


SocialPilot is a social media workspace platform built with FastAPI, React, PostgreSQL (Supabase), and MongoDB.

---

## 🏗️ Architecture Overview

- **Backend**: FastAPI (Python 3.11+), SQLAlchemy ORM, Alembic Migrations, Motor (Async MongoDB), PyJWT, Fernet Token Encryption.
- **Relational Store**: PostgreSQL (Supabase) for structured domain entities (Users, Teams, Social Accounts, Permissions, Sync Logs).
- **Document Store**: MongoDB for flexible platform metadata and rich profile documents (with automatic graceful degradation when MongoDB URI is absent).
- **Frontend**: React + Vite with responsive glassmorphism UI, React Router v6, Axios with JWT interceptors.

---

## ⚡ Quick Start

### 1. Backend Setup

```bash
cd backend

# 1. Activate virtual environment
.\venv\Scripts\activate

# 2. Configure environment (.env)
# Copy from .env.example and provide your DATABASE_URL / SECRET_KEY / FERNET_KEY

# 3. Run database migrations
alembic upgrade head

# 4. Start backend development server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start Vite development server
npm run dev
```
Frontend application will be available at [http://localhost:5173](http://localhost:5173).

---

## 🧪 Running Automated Tests

```bash
cd backend
.\venv\Scripts\pytest -v
```

All 26 automated tests verify:
- Authentication & JWT issuance/validation
- RBAC permissions & user settings
- Social provider registry (Facebook, Instagram, LinkedIn, X, YouTube, Pinterest)
- AES-256 Fernet token encryption at rest
- OAuth authorization & callback redirection flows
- Multi-account management, token expiration detection, sync logs, and disconnect
- Team collaboration & member role assignments

---

## 🛡️ Milestone 1 Features

- [x] **JWT Auth & RBAC**: User registration, login, profile management, and role enforcement (`content_creator`, `social_media_manager`, `marketing_team`, `administrator`).
- [x] **Hybrid Persistence**: PostgreSQL relational schema + MongoDB flexible metadata cache.
- [x] **At-Rest Token Encryption**: All OAuth credentials encrypted with Fernet symmetric keys.
- [x] **Social Provider Engine**: Unified architecture for 6 platforms with configuration detection.
- [x] **Account Management Dashboard**: Real-time status badges, manual sync, permission inspection, and disconnection.
- [x] **Team Workspaces**: Team creation and role-governed member management.
