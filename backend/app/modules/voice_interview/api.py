from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping():
    return {"module": "voice_interview", "status": "ok"}