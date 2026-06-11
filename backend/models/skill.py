from tortoise import fields, Model


class SkillRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    skill_type = fields.CharField(max_length=20, default="prompt")
    content = fields.JSONField(null=True)
    category = fields.CharField(max_length=50, null=True)
    tags = fields.JSONField(default=list)
    version = fields.IntField(default=1)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "skills_registry"


class AgentSkillLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    skill = fields.ForeignKeyField("models.SkillRegistry", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_skill_links"
        unique_together = [("agent_id", "skill_id")]
