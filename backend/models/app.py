from tortoise import fields, Model


class App(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    workflow = fields.ForeignKeyField("models.Workflow", on_delete=fields.CASCADE)
    workflow_version = fields.IntField(default=1)
    api_key = fields.CharField(max_length=64, unique=True)
    rate_limit = fields.IntField(default=60)
    enabled = fields.BooleanField(default=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "apps"
