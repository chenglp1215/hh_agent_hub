from tortoise import fields, Model


class AuditLog(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    action = fields.CharField(max_length=50)
    target_type = fields.CharField(max_length=50, null=True)
    target_id = fields.IntField(null=True)
    request_id = fields.CharField(max_length=36, null=True)
    ip_address = fields.CharField(max_length=45, null=True)
    details = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_logs"
