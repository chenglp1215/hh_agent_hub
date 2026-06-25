from fastapi import APIRouter, Depends, Query
from models.agent import Agent
from models.mcp_server import AgentMcpLink, McpServerRegistry
from models.knowledge_base import AgentKbLink, KnowledgeBase
from models.skill import AgentSkillLink, SkillRegistry
from schemas.agent import AgentCreate, AgentUpdate, AgentTestRequest
from api.deps import get_current_user, require_admin
from utils.response import success, error
from loguru import logger

router = APIRouter(prefix="/agents", tags=["Agent"])


@router.get("")
async def list_agents(
    agent_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    user=Depends(get_current_user),
):
    qs = Agent.all()
    if agent_type:
        qs = qs.filter(agent_type=agent_type)
    if status:
        qs = qs.filter(status=status)
    agents = await qs

    if search:
        agents = [a for a in agents if search.lower() in (a.name + (a.display_name or "")).lower()]

    result = []
    for a in agents:
        mcp_count = await AgentMcpLink.filter(agent_id=a.id).count()
        kb_count = await AgentKbLink.filter(agent_id=a.id).count()
        skill_count = await AgentSkillLink.filter(agent_id=a.id).count()
        result.append({
            "id": a.id, "name": a.name, "display_name": a.display_name,
            "description": a.description, "role": a.role,
            "agent_type": a.agent_type, "status": a.status,
            "resource_count": {"mcp": mcp_count, "kb": kb_count, "skills": skill_count},
            "supervisor_prompt_template": a.supervisor_prompt_template,
            "custom_prompt_override": a.custom_prompt_override,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        })
    return success(data=result)


@router.get("/{agent_id}")
async def get_agent(agent_id: int, user=Depends(get_current_user)):
    a = await Agent.get_or_none(id=agent_id)
    if not a:
        return error(code=404, message="Agent 不存在")

    mcp_links = await AgentMcpLink.filter(agent_id=agent_id).prefetch_related("mcp_server")
    kb_links = await AgentKbLink.filter(agent_id=agent_id).prefetch_related("kb")
    skill_links = await AgentSkillLink.filter(agent_id=agent_id).prefetch_related("skill")

    return success(data={
        "id": a.id, "name": a.name, "display_name": a.display_name,
        "description": a.description, "role": a.role, "agent_type": a.agent_type,
        "llm_config": a.llm_config, "llm_config_id": a.llm_config_id,
        "http_config": a.http_config,
        "claudecode_config": a.claudecode_config,
        "a2a_config": a.a2a_config,
        "reasonix_config": a.reasonix_config, "system_prompt": a.system_prompt,
        "status": a.status, "knowledge_base_ids": a.knowledge_base_ids,
        "supervisor_prompt_template": a.supervisor_prompt_template,
        "custom_prompt_override": a.custom_prompt_override,
        "mcp_links": [{"id": ml.id, "mcp_server": {"id": ml.mcp_server.id, "name": ml.mcp_server.name}, "enabled_tools": ml.enabled_tools, "enabled": ml.enabled} for ml in mcp_links],
        "kb_links": [{"id": kl.id, "kb": {"id": kl.kb.id, "name": kl.kb.name}} for kl in kb_links],
        "skill_links": [{"id": sl.id, "skill": {"id": sl.skill.id, "name": sl.skill.name}} for sl in skill_links],
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    })


@router.post("")
async def create_agent(body: AgentCreate, user=Depends(get_current_user)):
    # Validate settings_json size for claudecode agents
    if body.agent_type == "claudecode" and body.claudecode_config:
        sj = body.claudecode_config.get("settings_json", "")
        if len(sj) > 100000:
            return error(code=400, message="settings_json 内容过长，最大支持 100KB")

    existing = await Agent.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="Agent 名称已存在")

    # custom_prompt_override 仅管理员可设置
    if body.custom_prompt_override and user.role != "admin":
        return error(code=403, message="自定义 Prompt 覆盖仅管理员可设置")

    a = await Agent.create(
        name=body.name, display_name=body.display_name,
        description=body.description, role=body.role,
        agent_type=body.agent_type,
        llm_config_id=body.llm_config_id,
        llm_config=body.llm_config, http_config=body.http_config,
        claudecode_config=body.claudecode_config,
        a2a_config=body.a2a_config,
        reasonix_config=body.reasonix_config,
        system_prompt=body.system_prompt,
        knowledge_base_ids=body.kb_ids,
        supervisor_prompt_template=body.supervisor_prompt_template,
        custom_prompt_override=body.custom_prompt_override,
        created_by=user,
    )

    for link in body.mcp_links:
        mcp_id = link.get("mcp_server_id")
        if mcp_id:
            await AgentMcpLink.get_or_create(
                agent_id=a.id, mcp_server_id=mcp_id,
                defaults={"enabled_tools": link.get("enabled_tools", []), "enabled": True},
            )

    for kb_id in body.kb_ids:
        await AgentKbLink.get_or_create(agent_id=a.id, kb_id=kb_id)

    for skill_id in body.skill_ids:
        await AgentSkillLink.get_or_create(agent_id=a.id, skill_id=skill_id)

    logger.info(f"Agent created: {a.name} (id={a.id})")
    return success(data={"id": a.id, "name": a.name}, message="创建成功")


@router.put("/{agent_id}")
async def update_agent(agent_id: int, body: AgentUpdate, user=Depends(get_current_user)):
    a = await Agent.get_or_none(id=agent_id)
    if not a:
        return error(code=404, message="Agent 不存在")

    updatable = ["display_name", "description", "role", "agent_type",
                 "llm_config_id", "llm_config", "http_config", "claudecode_config",
                 "a2a_config", "reasonix_config", "system_prompt", "status",
                 "supervisor_prompt_template"]
    for field in updatable:
        val = getattr(body, field, None)
        if val is not None:
            # Validate settings_json size for claudecode config
            if field == "claudecode_config" and isinstance(val, dict) and val.get("settings_json", ""):
                sj = val["settings_json"]
                if len(sj) > 100000:
                    return error(code=400, message="settings_json 内容过长，最大支持 100KB")
            setattr(a, field, val)

    # custom_prompt_override 仅管理员可设置
    if body.custom_prompt_override is not None:
        if user.role != "admin":
            return error(code=403, message="自定义 Prompt 覆盖仅管理员可设置")
        a.custom_prompt_override = body.custom_prompt_override

    if body.kb_ids is not None:
        a.knowledge_base_ids = body.kb_ids
        await AgentKbLink.filter(agent_id=agent_id).delete()
        for kb_id in body.kb_ids:
            await AgentKbLink.get_or_create(agent_id=agent_id, kb_id=kb_id)

    if body.mcp_links is not None:
        await AgentMcpLink.filter(agent_id=agent_id).delete()
        for link in body.mcp_links:
            mcp_id = link.get("mcp_server_id")
            if mcp_id:
                await AgentMcpLink.get_or_create(
                    agent_id=agent_id, mcp_server_id=mcp_id,
                    defaults={"enabled_tools": link.get("enabled_tools", []), "enabled": True},
                )

    if body.skill_ids is not None:
        await AgentSkillLink.filter(agent_id=agent_id).delete()
        for skill_id in body.skill_ids:
            await AgentSkillLink.get_or_create(agent_id=agent_id, skill_id=skill_id)

    await a.save()
    return success(message="更新成功")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, user=Depends(get_current_user)):
    a = await Agent.get_or_none(id=agent_id)
    if not a:
        return error(code=404, message="Agent 不存在")
    await AgentMcpLink.filter(agent_id=agent_id).delete()
    await AgentKbLink.filter(agent_id=agent_id).delete()
    await AgentSkillLink.filter(agent_id=agent_id).delete()
    await a.delete()
    return success(message="已删除")


@router.post("/{agent_id}/test")
async def test_agent(agent_id: int, body: AgentTestRequest, user=Depends(get_current_user)):
    a = await Agent.get_or_none(id=agent_id)
    if not a:
        return error(code=404, message="Agent 不存在")

    try:
        from core.agent_factory import agent_factory
        from models.knowledge_base import ContentBlock

        mcp_links = await AgentMcpLink.filter(agent_id=agent_id).prefetch_related("mcp_server")
        kb_links = await AgentKbLink.filter(agent_id=agent_id).prefetch_related("kb")
        skill_links = await AgentSkillLink.filter(agent_id=agent_id).prefetch_related("skill")

        # Pre-resolve KB ContentBlock content
        kb_content = []
        if a.knowledge_base_ids:
            blocks = await ContentBlock.filter(kb_id__in=a.knowledge_base_ids).order_by("source_file", "id")
            for b in blocks:
                kb_content.append({
                    "heading_path": b.heading_path or b.source_file,
                    "body": b.body,
                    "source_file": b.source_file,
                })

        # Pre-resolve Skill content
        skill_content = []
        for sl in skill_links:
            skill = sl.skill
            skill_content.append({
                "name": skill.name,
                "description": skill.description,
                "skill_type": skill.skill_type,
                "content": skill.content,
            })

        mcp_servers = [{
            "id": ml.mcp_server.id, "name": ml.mcp_server.name,
            "base_url": ml.mcp_server.base_url,
            "headers": ml.mcp_server.headers,
            "single_endpoint": ml.mcp_server.single_endpoint,
            "enabled_tools": ml.enabled_tools,
            "enabled": ml.enabled,
        } for ml in mcp_links]

        config = {
            "name": a.name, "agent_type": a.agent_type, "role": a.role,
            "llm_config": a.llm_config, "llm_config_id": a.llm_config_id,
            "http_config": a.http_config,
            "claudecode_config": a.claudecode_config,
            "a2a_config": a.a2a_config,
            "reasonix_config": a.reasonix_config,
            "system_prompt": a.system_prompt,
            "mcp_servers": mcp_servers,
            "knowledge_base_ids": a.knowledge_base_ids or [],
            "skills": skill_content,
        }

        if a.agent_type == "claudecode":
            agent_node = await agent_factory.create_claudecode_agent(
                config,
                mcp_servers=mcp_servers,
                kb_content=kb_content,
                skill_content=skill_content,
            )
        elif a.agent_type == "reasonix":
            agent_node = await agent_factory.create_reasonix_agent(
                config,
                mcp_servers=mcp_servers,
                kb_content=kb_content,
                skill_content=skill_content,
            )
        else:
            agent_node = await agent_factory.create(config)

        result = await agent_node({"user_input": body.message, "messages": [], "intermediate_results": {}})
        output = result.get("intermediate_results", {}).get(a.name, "")
        return success(data={"response": output})
    except Exception as e:
        logger.error(f"Agent test failed: {e}")
        return error(code=-1, message=f"测试失败: {str(e)}")


@router.post("/{agent_id}/copy")
async def copy_agent(agent_id: int, user=Depends(get_current_user)):
    a = await Agent.get_or_none(id=agent_id)
    if not a:
        return error(code=404, message="Agent 不存在")

    new_name = f"{a.name}_copy"
    counter = 1
    while await Agent.get_or_none(name=new_name):
        new_name = f"{a.name}_copy{counter}"
        counter += 1

    new_agent = await Agent.create(
        name=new_name, display_name=f"{a.display_name} (副本)" if a.display_name else None,
        description=a.description, role=a.role, agent_type=a.agent_type,
        llm_config=a.llm_config, http_config=a.http_config,
        claudecode_config=a.claudecode_config,
        a2a_config=a.a2a_config,
        reasonix_config=a.reasonix_config,
        system_prompt=a.system_prompt,
        knowledge_base_ids=a.knowledge_base_ids,
        supervisor_prompt_template=a.supervisor_prompt_template,
        custom_prompt_override=a.custom_prompt_override,
        created_by=user,
    )

    mcp_links = await AgentMcpLink.filter(agent_id=agent_id)
    for ml in mcp_links:
        await AgentMcpLink.create(agent_id=new_agent.id, mcp_server_id=ml.mcp_server_id, enabled_tools=ml.enabled_tools, enabled=ml.enabled)

    kb_links = await AgentKbLink.filter(agent_id=agent_id)
    for kl in kb_links:
        await AgentKbLink.create(agent_id=new_agent.id, kb_id=kl.kb_id)

    skill_links = await AgentSkillLink.filter(agent_id=agent_id)
    for sl in skill_links:
        await AgentSkillLink.create(agent_id=new_agent.id, skill_id=sl.skill_id)

    return success(data={"id": new_agent.id, "name": new_agent.name}, message=f"已复制为 {new_name}")
