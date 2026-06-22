from tortoise import fields, Model


class Agent(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    role = fields.CharField(max_length=20)
    agent_type = fields.CharField(max_length=20, default="local")
    llm_config = fields.JSONField(null=True)
    llm_config_id = fields.IntField(null=True)
    http_config = fields.JSONField(null=True)
    claudecode_config = fields.JSONField(null=True)
    a2a_config = fields.JSONField(null=True)
    system_prompt = fields.TextField(null=True)
    mcp_servers = fields.JSONField(default=list)
    skills = fields.JSONField(default=list)
    custom_tools = fields.JSONField(default=list)
    knowledge_base_ids = fields.JSONField(default=list)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "agents"
