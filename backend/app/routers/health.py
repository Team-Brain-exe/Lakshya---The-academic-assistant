from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Public health check used by the hosting platform and smoke tests."""
    return {"status": "ok"}
