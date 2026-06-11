from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from api.v1.auth import router as auth_router
router.include_router(auth_router)


from api.v1.configs import router as configs_router
router.include_router(configs_router)


@router.get("/ping")
async def ping():
    return {"ping": "pong"}
