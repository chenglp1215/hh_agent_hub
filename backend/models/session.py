from tortoise import fields, Model


class Session(Model):
    id = fields.CharField(max_length=36, pk=True)
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    user_id = fields.CharField(max_length=100, null=True)
    messages = fields.JSONField(default=list)
    thread_state = fields.JSONField(null=True)
    workspace_path = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)
    expired_at = fields.DatetimeField(null=True)

    class Meta:
        table = "sessions"
