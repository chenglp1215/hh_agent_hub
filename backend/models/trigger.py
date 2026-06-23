from tortoise import fields, Model


class Trigger(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    trigger_type = fields.CharField(max_length=20)  # "interval" | "cron"
    interval_value = fields.IntField(null=True)
    interval_unit = fields.CharField(max_length=10, null=True)  # "minutes" | "hours" | "days"
    cron_expression = fields.CharField(max_length=100, null=True)
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    message = fields.TextField()
    enabled = fields.BooleanField(default=True)
    last_fired_at = fields.DatetimeField(null=True)
    next_fire_at = fields.DatetimeField(null=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "triggers"
