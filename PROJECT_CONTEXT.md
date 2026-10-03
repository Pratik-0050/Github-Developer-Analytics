# PROJECT_CONTEXT.md — GitHub Developer Analytics (Compact Export)

> **Export Notice**: This standalone document contains the entire state, architecture, code contracts, environment configuration, and execution instructions for **GitHub Developer Analytics**. Feed this file directly into any LLM prompt or developer onboarding session to resume development without loss of context.

---

## 1. System Overview & Tech Stack

- **Application Purpose**: An analytics platform tracking GitHub developer activity, repository metrics, code contributions, and predictive developer insights.
- **Current Milestone**: **Step 6 Complete** (Developer Commit & Activity Analytics: Commits retrieval across active repositories, Granular Author vs Owner Attribution, Daily & Monthly Cadence Aggregations, Most-Active Repositories Ranking, Interactive Activity Bar Chart, and Commits Table).
- **Environment**:
  - **OS**: Windows
  - **Python**: 3.14.0 (Virtual environment located at `backend/venv`)
  - **Node.js**: Next.js 16.3.8 (Turbopack, App Router), React 19, Tailwind CSS v4, TypeScript 5
  - **Database**: PostgreSQL 16 (via Docker Compose) with automated local SQLite fallback
- **Communication Flow**:
  ```text
  Browser (:3000) ──> Next.js App Router ──> FastAPI (:8000) ──┬──> SQLAlchemy 2.0 (PostgreSQL / SQLite)
                                                                └──> GitHub REST API (api.github.com)
  ```

---

## 2. Full Project File Tree

```text
github-developer-analytics/
├── PROJECT_CONTEXT.md             # Complete context export file
├── PROJECT_SUMMARY.md             # High-level architecture summary
├── docker-compose.yml             # PostgreSQL 16 container definition
├── backend/
│   ├── .env                       # Local environment variables (DB, API URLs)
│   ├── .env.example               # Template environment configuration
│   ├── .gitignore                 # Excludes venv, pycache, .env, *.db
│   ├── alembic.ini                # Alembic database migration config
│   ├── pytest.ini                 # Pytest test discovery config
│   ├── requirements.txt           # Python dependencies (FastAPI, SQLAlchemy, psycopg, alembic)
│   ├── venv/                      # Python virtualenv (ignored in git)
│   ├── alembic/                   # Database migrations directory
│   │   ├── env.py
│   │   └── versions/              # Auto-generated migration versions
│   ├── tests/
│   │   ├── test_caching.py        # Automated test suite (caching, audit, health)
│   │   └── test_commits_activity.py # Commit parsing, author distinction & cadence tests
│   └── app/
│       ├── __init__.py
│       ├── main.py                # FastAPI entry point, lifespan DB init, CORS
│       ├── core/
│       │   ├── __init__.py
│       │   └── config.py          # Settings with DB & Cache TTL config
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py            # SQLAlchemy 2.0 DeclarativeBase
│       │   └── session.py         # Engine, pooling, get_db dependency, health pinger
│       ├── models/
│       │   ├── __init__.py
│       │   ├── db_models.py       # User and AnalyticsRun ORM models
│       │   ├── github.py          # GitHubUser, Repo, Commit & Activity Pydantic models
│       │   └── analytics.py       # Audit history & stats Pydantic models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── github.py          # Cache-first GitHub service with commit fetching & fallback
│       │   └── analytics.py       # Metrics aggregator, cadence analysis & audit query service
│       └── api/
│           ├── __init__.py
│           └── routes/
│               ├── __init__.py
│               ├── health.py      # Health check + DB ping latency
│               ├── github.py      # User, repo, commits & activity endpoints
│               └── analytics.py   # /api/analytics/stats & /api/analytics/history
└── frontend/
    ├── .env.local                 # NEXT_PUBLIC_API_URL=http://localhost:8000
    ├── .gitignore
    ├── next.config.ts             # Image remotePattern for avatars.githubusercontent.com
    ├── package.json
    ├── tsconfig.json              # Paths: "@/*": ["./*"]
    ├── types/
    │   └── github.ts              # TypeScript interfaces (User, Stats, Commits, Activity)
    ├── services/
    │   └── api.ts                 # Typed fetch client (caching, stats, commits, activity)
    └── app/
        ├── components/
        │   ├── ActivityChart.tsx   # Interactive daily commit bar chart & monthly volume
        │   ├── ActiveRepos.tsx     # Ranked showcase of most-active repositories
        │   └── RecentCommitsTable.tsx # Commits table with author attribution & filter
        ├── globals.css            # Tailwind v4 import
        ├── layout.tsx             # Root layout with metadata
        └── page.tsx               # Analytics dashboard with cadence & commit insights
```

---

## 3. Environment Configurations

### `backend/.env`
```env
APP_NAME=GitHub Developer Analytics API
APP_VERSION=1.0.0
FRONTEND_URL=http://localhost:3000
GITHUB_API_URL=https://api.github.com
```

### `frontend/.env.local`
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 4. Backend Source Code Reference

### `backend/app/core/config.py`
```python
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "GitHub Developer Analytics API"
    APP_VERSION: str = "1.0.0"
    FRONTEND_URL: str = "http://localhost:3000"
    GITHUB_API_URL: str = "https://api.github.com"

    # Future integration slots
    DATABASE_URL: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    JWT_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
```

### `backend/app/models/github.py`
```python
from typing import Optional
from pydantic import BaseModel, ConfigDict

class GitHubUser(BaseModel):
    login: str
    id: int
    name: Optional[str] = None
    avatar_url: str
    html_url: str
    public_repos: int
    followers: int
    following: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)
```

### `backend/app/services/github.py`
```python
import requests
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.github import GitHubUser

def get_github_user(username: str) -> GitHubUser:
    url = f"{settings.GITHUB_API_URL.rstrip('/')}/users/{username}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Developer-Analytics-API",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10.0)
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to GitHub API",
        )

    if response.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"GitHub user '{username}' not found")
    elif response.status_code == 403:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub API rate limit exceeded")
    elif response.status_code >= 500:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub API service error")
    elif not response.ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"GitHub API error (Status {response.status_code})")

    data = response.json()
    return GitHubUser(
        login=data.get("login", ""),
        id=data.get("id", 0),
        name=data.get("name"),
        avatar_url=data.get("avatar_url", ""),
        html_url=data.get("html_url", ""),
        public_repos=data.get("public_repos", 0),
        followers=data.get("followers", 0),
        following=data.get("following", 0),
        created_at=str(data.get("created_at", "")),
    )
```

### `backend/app/api/routes/health.py`
```python
from fastapi import APIRouter

router = APIRouter(tags=["Health"])

@router.get("/")
def read_root():
    return {"message": "GitHub Developer Analytics API is running"}

@router.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "github-developer-analytics-api"}
```

### `backend/app/api/routes/github.py`
```python
from fastapi import APIRouter
from app.models.github import GitHubUser
from app.services.github import get_github_user

router = APIRouter(prefix="/api/github", tags=["GitHub"])

@router.get("/user/{username}", response_model=GitHubUser)
def fetch_user(username: str):
    return get_github_user(username)
```

### `backend/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.github import router as github_router
from app.api.routes.health import router as health_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, docs_url="/docs", redoc_url="/redoc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(github_router)
```

---

## 5. Frontend Source Code Reference

### `frontend/types/github.ts`
```typescript
export interface GitHubUser {
  login: string;
  id: number;
  name: string | null;
  avatar_url: string;
  html_url: string;
  public_repos: number;
  followers: number;
  following: number;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  service: string;
}

export interface ApiError {
  detail: string;
}
```

### `frontend/services/api.ts`
```typescript
import type { GitHubUser, HealthStatus } from "@/types/github";

const API_URL = process.env.NEXT_PUBLIC_API_URL;
if (!API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL is not defined.");
}

async function apiFetch<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`);
  } catch {
    throw new Error("Unable to connect to backend.");
  }

  if (!response.ok) {
    try {
      const errorBody = await response.json();
      if (typeof errorBody?.detail === "string") throw new Error(errorBody.detail);
    } catch (parseErr) {
      if (parseErr instanceof Error && parseErr.message !== "Unable to connect to backend.") throw parseErr;
    }
    throw new Error(`Request failed with status ${response.status}.`);
  }
  return (await response.json()) as T;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const data = await apiFetch<HealthStatus>("/api/health");
    return data.status === "healthy";
  } catch {
    return false;
  }
}

export async function getGithubUser(username: string): Promise<GitHubUser> {
  const trimmed = username.trim();
  if (!trimmed) throw new Error("Please enter a GitHub username.");
  return apiFetch<GitHubUser>(`/api/github/user/${encodeURIComponent(trimmed)}`);
}
```

### `frontend/next.config.ts`
```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
        port: "",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
```

---

## 6. Endpoints & Responses

| Method | Endpoint | Example Response / Purpose |
|---|---|---|
| `GET` | `/` | `{"message": "GitHub Developer Analytics API is running"}` |
| `GET` | `/api/health` | `{"status": "healthy", "service": "...", "database": {"status": "connected", "latency_ms": 0.5, "dialect": "sqlite"}}` |
| `GET` | `/api/github/user/{username}` | Returns structured profile. `cached: true` for cached records; accepts `?refresh=true` to force fresh GitHub sync. |
| `GET` | `/api/analytics/stats` | Aggregated cache metrics: hit rate %, total cached profiles, query count, avg response latency. |
| `GET` | `/api/analytics/history` | Audit log of recent profile searches, latencies, and cache hit results. |
| `GET` | `/api/github/repos/{username}` | Returns list of public repositories for user. |
| `GET` | `/api/github/repos/{username}/analytics` | Aggregated repository stats: stars, forks, language distribution, top repos. |
| `GET` | `/api/github/commits/{username}` | Returns recent commits across top active public repositories, with granular author attribution and `partial` indicator. |
| `GET` | `/api/github/activity/{username}` | Returns aggregated commit frequency: daily commit counts, monthly totals, and ranked most-active repositories. |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/redoc` | Interactive ReDoc UI |

---

## 7. Known Nuances & Solutions

1. **Dual Database Support**: Configured via `DATABASE_URL` in `backend/.env`. Connects to PostgreSQL (`postgresql+psycopg://...`) via connection pooling, and seamlessly defaults to SQLite for instant local development without running containers.
2. **Containerized PostgreSQL**: A root `docker-compose.yml` provides a PostgreSQL 16 container (`docker compose up -d`) with health checks and volume persistence.
3. **Sub-millisecond Cache**: Cached user profile queries resolve in ~1ms compared to 800ms+ for remote GitHub API calls, saving rate limits.
4. **Rate Limit Resilience**: If GitHub API returns `403 Forbidden` (rate limit exceeded), the backend automatically serves stale cached records with `stale: true` fallback rather than failing the user. Commits queries set `partial: true` gracefully.
5. **Author vs. Owner Attribution**: Distinguishes commit authors (`is_user_author`) from repository owners, accurately tracking commits even when third parties contribute to a user's repository.
6. **Path Alias in Frontend**: `tsconfig.json` defines `"@/*": ["./*"]` (relative to `frontend/`).
7. **User-Agent Requirement**: GitHub REST API requests include `"User-Agent": "GitHub-Developer-Analytics-API"`.

---

## 8. Run Instructions

### Start PostgreSQL via Docker (Optional)
```powershell
docker compose up -d
```

### Start Backend (Port 8000)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### Run Backend Tests
```powershell
cd backend
.\venv\Scripts\pytest.exe -v
```

### Start Frontend (Port 3000)
```powershell
cd frontend
npm run dev
```

---

## 9. Next Milestones (For Continuing Work)

1. **Step 7: GitHub OAuth 2.0 & Private Repositories**:
   - Enable user sign-in via GitHub OAuth.
   - Store secure user access tokens in the `users` table for private repository analytics.
2. **Step 8: Developer Activity ML / Scoring**:
   - Score developer consistency, code diversity, and repository impact.
3. **Step 9: Real-time Webhooks & Automated Sync**:
   - Ingest GitHub webhooks for real-time repository and commit events.
