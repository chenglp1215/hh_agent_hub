from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from api.v1.auth import router as auth_router
router.include_router(auth_router)


from api.v1.configs import router as configs_router
router.include_router(configs_router)

from api.v1.llm_configs import router as llm_configs_router
router.include_router(llm_configs_router)


from api.v1.mcp_servers import router as mcp_servers_router
router.include_router(mcp_servers_router)


from api.v1.skills import router as skills_router
router.include_router(skills_router)


from api.v1.knowledge_bases import router as kb_router
router.include_router(kb_router)


from api.v1.agents import router as agents_router
router.include_router(agents_router)


from api.v1.workflows import router as workflows_router
router.include_router(workflows_router)


from api.v1.apps import router as apps_router
router.include_router(apps_router)


from api.v1.chat import router as chat_router
router.include_router(chat_router)


from api.v1.traces import router as traces_router
router.include_router(traces_router)


from api.v1.metrics import router as metrics_router
router.include_router(metrics_router)


from api.v1.ws import router as ws_router
router.include_router(ws_router)


@router.get("/ping")
async def ping():
    return {"ping": "pong"}
