from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping():
    return {"module": "hr_assistant", "status": "ok"}