from tortoise import fields, Model


class McpServerRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    base_url = fields.CharField(max_length=500)
    headers = fields.JSONField(default=dict)
    timeout = fields.IntField(default=30)
    single_endpoint = fields.BooleanField(default=False)
    discovered_tools = fields.JSONField(default=list)
    status = fields.CharField(max_length=20, default="active")
    last_checked_at = fields.DatetimeField(null=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "mcp_server_registry"


class AgentMcpLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    mcp_server = fields.ForeignKeyField("models.McpServerRegistry", on_delete=fields.CASCADE)
    enabled_tools = fields.JSONField(default=list)
    enabled = fields.BooleanField(default=True)

    class Meta:
        table = "agent_mcp_links"
        unique_together = [("agent_id", "mcp_server_id")]
