from tortoise import fields, Model


class Workflow(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    flow_type = fields.CharField(max_length=20)
    supervisor_agent = fields.ForeignKeyField("models.Agent", null=True, on_delete=fields.SET_NULL)
    worker_agent_ids = fields.JSONField(default=list)
    edges = fields.JSONField(default=list)
    parallel_groups = fields.JSONField(default=list)
    human_interrupts = fields.JSONField(default=list)
    error_strategy = fields.CharField(max_length=20, default="fail_fast")
    agent_timeout_seconds = fields.IntField(default=60)
    workflow_timeout_seconds = fields.IntField(default=300)
    max_retries = fields.IntField(default=2)
    status = fields.CharField(max_length=20, default="draft")
    version = fields.IntField(default=1)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "workflows"
