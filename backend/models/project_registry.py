from tortoise import fields, Model


class ProjectRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    git_repo_url = fields.CharField(max_length=500)
    git_branch = fields.CharField(max_length=100, default="main")
    git_auth_username = fields.CharField(max_length=100, null=True)
    git_auth_token = fields.CharField(max_length=500, null=True)
    clone_path = fields.CharField(max_length=500, null=True)
    system_prompt = fields.TextField(null=True)
    fix_timeout_minutes = fields.IntField(default=30)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "project_registry"


class AgentProjectLink(Model):
    id = fields.IntField(pk=True)
    agent = fields.ForeignKeyField("models.Agent", on_delete=fields.CASCADE)
    project = fields.ForeignKeyField("models.ProjectRegistry", on_delete=fields.CASCADE)

    class Meta:
        table = "agent_project_links"
        unique_together = [("agent_id", "project_id")]
