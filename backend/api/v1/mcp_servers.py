from datetime import datetime
from fastapi import APIRouter, Depends
from models.mcp_server import McpServerRegistry
from schemas.mcp_server import McpServerCreate, McpServerUpdate
from api.deps import get_current_user, require_admin
from core.mcp_client import mcp_client
from utils.response import success, error

router = APIRouter(prefix="/mcp-servers", tags=["MCP Server"])


@router.get("")
async def list_mcp_servers(user=Depends(get_current_user)):
    servers = await McpServerRegistry.all()
    return success(data=[{
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "base_url": s.base_url,
        "headers": s.headers, "single_endpoint": s.single_endpoint,
        "discovered_tools": s.discovered_tools, "status": s.status,
        "timeout": s.timeout,
        "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in servers])


@router.get("/{server_id}")
async def get_mcp_server(server_id: int, user=Depends(get_current_user)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    return success(data={
        "id": s.id, "name": s.name, "display_name": s.display_name,
        "description": s.description, "base_url": s.base_url,
        "headers": s.headers, "single_endpoint": s.single_endpoint,
        "timeout": s.timeout,
        "discovered_tools": s.discovered_tools, "status": s.status,
    })


@router.post("")
async def create_mcp_server(body: McpServerCreate, user=Depends(require_admin)):
    existing = await McpServerRegistry.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    s = await McpServerRegistry.create(
        name=body.name, display_name=body.display_name,
        description=body.description, base_url=body.base_url.rstrip("/"),
        headers=body.headers or {}, single_endpoint=body.single_endpoint,
        timeout=body.timeout,
        created_by=user,
    )
    return success(data={"id": s.id, "name": s.name}, message="注册成功")


@router.put("/{server_id}")
async def update_mcp_server(server_id: int, body: McpServerUpdate, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    if body.display_name is not None:
        s.display_name = body.display_name
    if body.description is not None:
        s.description = body.description
    if body.base_url is not None:
        s.base_url = body.base_url.rstrip("/")
    if body.headers is not None:
        s.headers = body.headers
    if body.single_endpoint is not None:
        s.single_endpoint = body.single_endpoint
    if body.timeout is not None:
        s.timeout = body.timeout
    await s.save()
    return success(message="更新成功")


@router.delete("/{server_id}")
async def delete_mcp_server(server_id: int, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    await s.delete()
    return success(message="已删除")


@router.post("/{server_id}/discover")
async def discover_tools(server_id: int, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    try:
        await mcp_client.connect(server_id, s.base_url, s.headers, single_endpoint=s.single_endpoint)
        tools = await mcp_client.discover_tools(server_id)
        s.discovered_tools = tools
        s.status = "active"
        s.last_checked_at = datetime.now()
        await s.save()
        return success(data=tools, message=f"发现 {len(tools)} 个工具")
    except Exception as e:
        s.status = "error"
        await s.save()
        return error(code=-1, message=f"连接失败: {str(e)}")


@router.post("/{server_id}/test")
async def test_connection(server_id: int, user=Depends(require_admin)):
    s = await McpServerRegistry.get_or_none(id=server_id)
    if not s:
        return error(code=404, message="MCP Server 不存在")
    try:
        conn = await mcp_client.connect(server_id, s.base_url, s.headers, single_endpoint=s.single_endpoint)
        ok = await mcp_client.ping(conn)
        s.status = "active" if ok else "error"
        s.last_checked_at = datetime.now()
        await s.save()
        return success(data={"connected": ok})
    except Exception as e:
        s.status = "error"
        s.last_checked_at = datetime.now()
        await s.save()
        return success(data={"connected": False, "error": str(e)})


@router.post("/batch-test")
async def batch_test_connections(user=Depends(require_admin)):
    """测试所有 MCP Server 的连接状态并更新 status"""
    servers = await McpServerRegistry.all()
    results = []
    for s in servers:
        try:
            conn = await mcp_client.connect(s.id, s.base_url, s.headers, single_endpoint=s.single_endpoint)
            ok = await mcp_client.ping(conn)
            s.status = "active" if ok else "error"
        except Exception:
            s.status = "error"
            ok = False
        s.last_checked_at = datetime.now()
        await s.save()
        results.append({
            "id": s.id,
            "name": s.name,
            "connected": ok,
            "status": s.status,
        })
    return success(data={"results": results, "total": len(servers)})
