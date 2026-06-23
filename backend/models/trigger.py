from tortoise import fields, Model


class Trigger(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(null=True)
    trigger_type = fields.CharField(max_length=20)  # "interval" | "cron"
    interval_value = fields.IntField(null=True)
    interval_unit = fields.CharField(max_length=10, null=True)  # "minutes" | "hours" | "days"
    cron_expression = fields.CharField(max_length=100, null=True)
    # --- wecom_bot fields ---
    wecom_chat_type = fields.CharField(max_length=10, null=True)  # "group" | "user"
    wecom_chat_id = fields.CharField(max_length=100, null=True)
    wecom_user_id = fields.CharField(max_length=100, null=True)
    # --- end wecom_bot fields ---
    app = fields.ForeignKeyField("models.App", on_delete=fields.CASCADE)
    message = fields.TextField()
    enabled = fields.BooleanField(default=True)
    notification = fields.ForeignKeyField("models.NotificationChannel", null=True, on_delete=fields.SET_NULL)
    last_fired_at = fields.DatetimeField(null=True)
    next_fire_at = fields.DatetimeField(null=True)
    created_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "triggers"


class NotificationChannel(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    channel_type = fields.CharField(max_length=20, default="wecom_webhook")
    webhook_url = fields.CharField(max_length=500)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "notification_channels"


class TriggerExecution(Model):
    id = fields.IntField(pk=True)
    trigger = fields.ForeignKeyField("models.Trigger", on_delete=fields.CASCADE)
    session_id = fields.CharField(max_length=100, index=True)
    task_id = fields.CharField(max_length=36, null=True)
    source = fields.CharField(max_length=10)  # "auto" | "manual"
    status = fields.CharField(max_length=20, default="submitted")
    error_message = fields.TextField(null=True)
    duration_ms = fields.IntField(null=True)
    notified = fields.BooleanField(default=False)
    started_at = fields.DatetimeField(auto_now_add=True)
    completed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "trigger_executions"
