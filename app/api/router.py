from fastapi import APIRouter, FastAPI

api_router = APIRouter(prefix="/router", tags=["router"])

@api_router.get("/health")
def health():
    return {
        "status": "ok"
    } 
