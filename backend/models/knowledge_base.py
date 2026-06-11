from tortoise import fields, Model


class KnowledgeBase(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    kb_type = fields.CharField(max_length=20, default="file")
    config = fields.JSONField(null=True)
    document_count = fields.IntField(default=0)
    embedding_model = fields.CharField(max_length=100, null=True)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "knowledge_bases"


class AgentKbLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    kb = fields.ForeignKeyField("models.KnowledgeBase", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_kb_links"
        unique_together = [("agent_id", "kb_id")]


class ContentBlock(Model):
    id = fields.IntField(pk=True)
    kb = fields.ForeignKeyField("models.KnowledgeBase", on_delete=fields.CASCADE)
    source_file = fields.CharField(max_length=500)
    heading_path = fields.CharField(max_length=500, null=True)
    body = fields.TextField()
    token_count = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "content_blocks"
