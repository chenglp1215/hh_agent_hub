from tortoise import fields, Model


class ReasonixSettingsRegistry(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    model = fields.CharField(max_length=100, default="deepseek-v4-pro")
    api_key = fields.CharField(max_length=255, null=True)
    base_url = fields.CharField(max_length=500, null=True)
    temperature = fields.FloatField(default=0.0)
    max_turns = fields.IntField(default=25)
    reasoning_language = fields.CharField(max_length=10, default="zh")
    auto_plan = fields.CharField(max_length=10, default="off")
    compact_ratio = fields.FloatField(default=0.8)
    extra_json = fields.JSONField(null=True)
    status = fields.CharField(max_length=20, default="active")
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "reasonix_settings_registry"
