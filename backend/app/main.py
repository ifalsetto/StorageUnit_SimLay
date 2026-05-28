from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from app.core.database import init_db
from app.routers import runs, media, items, evidence, exports, process, profiles, connectors, decisions, ocr

BASE_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(title="StorageUnit SimLay", version="1.1.0-ocr-testground")

cors_origins = os.getenv(
    "SIMLAY_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    (BASE_DIR / "data" / "uploads").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "exports").mkdir(parents=True, exist_ok=True)

@app.get("/")
def root():
    return {"app": "StorageUnit SimLay", "status": "ok", "docs": "/docs", "ocr": "/api/ocr/health"}

app.include_router(runs.router)
app.include_router(media.router)
app.include_router(items.router)
app.include_router(evidence.router)
app.include_router(exports.router)
app.include_router(process.router)
app.include_router(profiles.router)
app.include_router(connectors.router)
app.include_router(decisions.router)
app.include_router(ocr.router)

uploads = BASE_DIR / "data" / "uploads"
exports_dir = BASE_DIR / "data" / "exports"
uploads.mkdir(parents=True, exist_ok=True)
exports_dir.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(uploads)), name="uploads")
app.mount("/exports", StaticFiles(directory=str(exports_dir)), name="exports")
