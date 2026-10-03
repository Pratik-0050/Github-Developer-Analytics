# GitHub Developer Analytics - Run script (Windows PowerShell 5.1)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\run-app.ps1
#   powershell -ExecutionPolicy Bypass -File .\run-app.ps1 -NoDocker
#
# This starts:
#   Backend  (FastAPI) : http://localhost:8000 (docs: /docs, health: /api/health)
#   Frontend (Next.js) : http://localhost:3000

param(
  [switch]$NoDocker = $false
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host "Project root: $Root"

# 1. Start PostgreSQL (optional - backend falls back to SQLite if skipped)
if (-not $NoDocker) {
  Write-Host "`n[1/3] Starting PostgreSQL via Docker..."
  docker compose up -d
} else {
  Write-Host "`n[1/3] Skipping Docker (-NoDocker). Using SQLite fallback."
}

# 2. Start Backend (FastAPI :8000) in a new window
Write-Host "[2/3] Starting Backend (uvicorn app.main:app --reload)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"

# 3. Start Frontend (Next.js :3000) in a new window
Write-Host "[3/3] Starting Frontend (npm run dev)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run dev"

Write-Host "`nWaiting 8s for servers to boot..."
Start-Sleep -Seconds 8

# 4. Verify
Write-Host "`n--- Verify ---"
Write-Host "Backend : "; curl.exe -s -m 10 http://localhost:8000/api/health
Write-Host ""
Write-Host -NoNewline "Frontend: "; curl.exe -s -m 10 -o NUL -w "%{http_code}`n" http://localhost:3000/

Write-Host "`nDone. Open:"
Write-Host "  Frontend: http://localhost:3000"
Write-Host "  Backend : http://localhost:8000/docs"
Write-Host "  Health  : http://localhost:8000/api/health"
