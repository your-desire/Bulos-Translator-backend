"""Backend application package"""
from app.main import app
from app.routers.stt import router as stt_router
__all__ = ["app"]
