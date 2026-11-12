"""Static pages + health."""
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import STATIC_DIR

router = APIRouter()

@router.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/health")
@router.get("/healthz")
def health():
    return {"status": "ok"}


@router.get("/studio")
def studio_page():
    return FileResponse(os.path.join(STATIC_DIR, "studio.html"))


@router.get("/timeline")
def timeline_page():
    return FileResponse(os.path.join(STATIC_DIR, "timeline.html"))


@router.get("/bulk")
def bulk_page():
    return FileResponse(os.path.join(STATIC_DIR, "bulk.html"))
