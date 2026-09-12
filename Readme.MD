# 🚀 SocialPilot — Social Media Management Platform

backend:- `.venv\Scripts\activate` → `uvicorn app.main:app --reload`

frontend:- `npm run dev`

## Google OAuth: https://console.cloud.google.com/auth/clients?project=socialpilot-507310
## Callback: http://localhost:8000/api/v1/social/oauth/google/callback

SocialPilot is a full-stack social media scheduling and publishing platform built with FastAPI, React, PostgreSQL (Supabase), and MongoDB.

---

## 🏗️ Architecture Overview

- **Backend**: FastAPI (Python 3.11+), SQLAlchemy ORM, Alembic Migrations, Motor (Async MongoDB), PyJWT, Fernet Token Encryption, Celery + Redis.
- **Relational Store**: PostgreSQL (Supabase) for Users, Teams, Social Accounts, Posts, Publishing Jobs, and Publishing Logs.
- **Document Store**: MongoDB for flexible platform metadata (graceful degradation when URI absent).
- **Task Queue**: Celery workers + Redis broker for async multi-platform publishing with retry/backoff.
- **Frontend**: React + Vite, glassmorphism UI, React Router v6, Axios with JWT interceptors.

---

## ⚡ Quick Start

### 1. Backend

```bash
cd backend
.\venv\Scripts\activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: [http://localhost:5173](http://localhost:5173)

### 3. Celery Worker (async publishing)

```bash
cd backend
.\venv\Scripts\activate
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat   --loglevel=info
```

---

## 🧪 Running Automated Tests

```bash
cd backend
.\venv\Scripts\pytest -v
```

**105 automated tests** covering:
- Authentication & JWT issuance/validation
- RBAC permissions & user settings
- Social provider registry (Facebook, Instagram, LinkedIn, X, YouTube, Pinterest)
- AES-256 Fernet token encryption at rest
- OAuth authorization & callback redirection flows
- Multi-account management, token expiration detection, sync logs, and disconnect
- Team collaboration & member role assignments
- Content scheduling, draft lifecycle, recurring post generation
- Publishing calendar with date/status filtering and ownership isolation
- Multi-platform publishing with per-platform success/failure result tracking
- Publishing queue with atomic job claiming, retry & exponential backoff
- Async Celery-based publishing workers with duplicate-prevention
- Publishing logs & audit trail with platform/status filtering and pagination
- End-to-end lifecycle: login → OAuth → draft → schedule → calendar → queue → async publish → logs

---

## 🛡️ Milestone 1 Features

- [x] **JWT Auth & RBAC**: User registration, login, profile management, and role enforcement (`content_creator`, `marketing_team`, `business_user`, `administrator`).
- [x] **Hybrid Persistence**: PostgreSQL relational schema + MongoDB flexible metadata cache.
- [x] **At-Rest Token Encryption**: All OAuth credentials encrypted with Fernet symmetric keys.
- [x] **Social Provider Engine**: Unified architecture for 6 platforms with configuration detection.
- [x] **Account Management Dashboard**: Real-time status badges, manual sync, permission inspection, and disconnection.
- [x] **Team Workspaces**: Team creation and role-governed member management.

---

## 🚀 Milestone 2 Features

- [x] **Content Scheduling** *(Phase 1)*: Schedule posts for multiple social accounts with future-date validation, content-type selection, and full ownership isolation.
- [x] **Publishing Calendar** *(Phase 2)*: Date-range & status-filtered calendar; week/month/day views; multi-account badge rendering.
- [x] **Draft Post Lifecycle** *(Phase 3)*: Create, edit, convert to scheduled, and delete drafts with ownership enforcement.
- [x] **Recurring Posts** *(Phase 4)*: Daily / weekly / monthly rules with safe month-end handling; occurrences auto-generated as scheduled posts visible in Calendar; rules viewable and deactivatable.
- [x] **Multi-Platform Publishing** *(Phase 5)*: LinkedIn, Facebook, Instagram, X/Twitter, YouTube, Pinterest adapters; per-platform `PostPublishResult`; "Publish Now" in frontend; token-expiry detection.
- [x] **Automated Scheduled Publishing** *(Phase 6)*: Celery Beat scans for due posts and enqueues them automatically.
- [x] **Async Publishing Workers** *(Phase 7)*: Celery workers execute platform adapters asynchronously; post status aggregated across all platform jobs.
- [x] **Publishing Queue & Retry** *(Phase 8)*: Per-platform `PublishingJob` queue with atomic claiming, exponential-backoff retry, transient vs permanent error classification.
- [x] **Publishing Logs & Tracking** *(Phase 9)*: Full audit trail (`QUEUED → PROCESSING → PUBLISHING_STARTED → PUBLISHED / RETRYING / FAILED`); filterable, paginated; secret sanitization in error messages.
- [x] **End-to-End Integration** *(Phase 10)*: 105/105 backend tests passing; frontend production build passing; full lifecycle verified.

---

## 📡 API Overview

| Resource | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Users | `GET/PUT /users/me`, settings |
| Teams | `CRUD /teams`, `POST /teams/{id}/members` |
| Social | `GET /social/accounts`, OAuth flows |
| Posts | `CRUD /posts`, `/posts/calendar`, `/posts/scheduled`, `/posts/drafts` |
| Publish | `POST /posts/{id}/publish`, `GET /posts/{id}/publishing-logs` |
| Recurring | `CRUD /recurring-posts` |
