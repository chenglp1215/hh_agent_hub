from tortoise import fields, Model


class ClaudeSettingsRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    model = fields.CharField(max_length=100, default="claude-sonnet-4-6")
    max_turns = fields.IntField(default=25)
    permission_mode = fields.CharField(max_length=50, default="bypassPermissions")
    settings_json = fields.TextField(null=True)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "claude_settings_registry"


class AgentSettingsLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    settings = fields.ForeignKeyField("models.ClaudeSettingsRegistry", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_settings_links"
        unique_together = [("agent_id", "settings_id")]
