from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from api.v1.auth import router as auth_router
router.include_router(auth_router)


from api.v1.configs import router as configs_router
router.include_router(configs_router)


from api.v1.mcp_servers import router as mcp_servers_router
router.include_router(mcp_servers_router)


from api.v1.skills import router as skills_router
router.include_router(skills_router)


from api.v1.knowledge_bases import router as kb_router
router.include_router(kb_router)


@router.get("/ping")
async def ping():
    return {"ping": "pong"}
