from tortoise import fields, Model


class SysConfig(Model):
    id = fields.IntField(pk=True)
    config_key = fields.CharField(max_length=100, unique=True)
    config_value = fields.TextField()
    config_type = fields.CharField(max_length=20, default="string")
    description = fields.CharField(max_length=200, null=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sys_configs"
