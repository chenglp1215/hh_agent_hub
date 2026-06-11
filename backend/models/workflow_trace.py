from tortoise import fields, Model


class WorkflowTrace(Model):
    id = fields.IntField(pk=True)
    execution_id = fields.CharField(max_length=36, unique=True)
    workflow = fields.ForeignKeyField("models.Workflow", null=True, on_delete=fields.SET_NULL)
    app = fields.ForeignKeyField("models.App", null=True, on_delete=fields.SET_NULL)
    status = fields.CharField(max_length=20)
    agent_count = fields.IntField(default=0)
    total_duration_ms = fields.IntField(null=True)
    error_agent = fields.CharField(max_length=100, null=True)
    error_summary = fields.TextField(null=True)
    trace_file_path = fields.CharField(max_length=500)
    started_at = fields.DatetimeField(null=True)
    completed_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "workflow_traces"
