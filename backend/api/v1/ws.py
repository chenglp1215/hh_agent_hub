from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.ws_manager import ws_manager
from loguru import logger

router = APIRouter()


@router.websocket("/ws/execution/{execution_id}/live")
async def watch_execution(websocket: WebSocket, execution_id: str):
    await ws_manager.subscribe(execution_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from {execution_id}")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        ws_manager.unsubscribe(execution_id, websocket)
