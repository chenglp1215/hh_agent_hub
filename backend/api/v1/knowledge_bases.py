import os
import re
from fastapi import APIRouter, Depends
from models.knowledge_base import KnowledgeBase, ContentBlock
from schemas.knowledge_base import KBCreate, KBUpdate
from api.deps import get_current_user, require_admin
from utils.response import success, error

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])


@router.get("")
async def list_kbs(user=Depends(get_current_user)):
    kbs = await KnowledgeBase.all()
    return success(data=[{
        "id": k.id, "name": k.name, "display_name": k.display_name,
        "description": k.description, "kb_type": k.kb_type,
        "document_count": k.document_count, "status": k.status,
        "embedding_model": k.embedding_model,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    } for k in kbs])


@router.get("/{kb_id}")
async def get_kb(kb_id: int, user=Depends(get_current_user)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    return success(data={
        "id": k.id, "name": k.name, "display_name": k.display_name,
        "description": k.description, "kb_type": k.kb_type,
        "config": k.config, "document_count": k.document_count,
        "status": k.status, "embedding_model": k.embedding_model,
    })


@router.post("")
async def create_kb(body: KBCreate, user=Depends(require_admin)):
    existing = await KnowledgeBase.get_or_none(name=body.name)
    if existing:
        return error(code=400, message="名称已存在")
    k = await KnowledgeBase.create(
        name=body.name, display_name=body.display_name,
        description=body.description, kb_type=body.kb_type,
        config=body.config, embedding_model=body.embedding_model,
        created_by=user,
    )
    return success(data={"id": k.id, "name": k.name}, message="创建成功")


@router.put("/{kb_id}")
async def update_kb(kb_id: int, body: KBUpdate, user=Depends(require_admin)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    if body.display_name is not None:
        k.display_name = body.display_name
    if body.description is not None:
        k.description = body.description
    if body.config is not None:
        k.config = body.config
    if body.embedding_model is not None:
        k.embedding_model = body.embedding_model
    await k.save()
    return success(message="更新成功")


@router.delete("/{kb_id}")
async def delete_kb(kb_id: int, user=Depends(require_admin)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    await ContentBlock.filter(kb_id=kb_id).delete()
    await k.delete()
    return success(message="已删除")


@router.post("/{kb_id}/sync")
async def sync_kb(kb_id: int, user=Depends(require_admin)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    await ContentBlock.filter(kb_id=kb_id).delete()
    count = await _index_kb(k)
    k.document_count = count
    k.status = "active"
    await k.save()
    return success(data={"document_count": count}, message=f"同步完成，共 {count} 个文档块")


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: int, user=Depends(get_current_user)):
    k = await KnowledgeBase.get_or_none(id=kb_id)
    if not k:
        return error(code=404, message="知识库不存在")
    blocks = await ContentBlock.filter(kb_id=kb_id)
    source_files = list(set(b.source_file for b in blocks))
    return success(data=[{
        "source_file": f,
        "block_count": sum(1 for b in blocks if b.source_file == f),
    } for f in source_files])


async def _index_kb(kb) -> int:
    count = 0
    config = kb.config or {}
    if kb.kb_type == "file":
        source_path = config.get("source_path", "")
        file_patterns = config.get("file_patterns", ["*.md"])
        if os.path.isdir(source_path):
            for root, _, files in os.walk(source_path):
                for fn in files:
                    if any(fn.endswith(pat.replace("*", "")) for pat in file_patterns):
                        filepath = os.path.join(root, fn)
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        sections = re.split(r"\n(?=## )", content)
                        for section in sections:
                            heading_match = re.match(r"^## (.+)", section)
                            heading = heading_match.group(1) if heading_match else fn
                            body = section.strip()
                            if body:
                                await ContentBlock.create(
                                    kb_id=kb.id,
                                    source_file=filepath,
                                    heading_path=f"{fn} > {heading}",
                                    body=body,
                                    token_count=len(body) // 2,
                                )
                                count += 1
    elif kb.kb_type == "url":
        urls = config.get("urls", [])
        for url in urls:
            await ContentBlock.create(
                kb_id=kb.id,
                source_file=url,
                heading_path=url,
                body=f"External URL: {url}",
                token_count=len(url) // 2,
            )
            count += 1
    return count
