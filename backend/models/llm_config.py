from tortoise import fields, Model


class LlmConfig(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    provider = fields.CharField(max_length=20, default="openai")
    model = fields.CharField(max_length=100, default="gpt-4o-mini")
    api_key = fields.CharField(max_length=255, null=True)
    base_url = fields.CharField(max_length=500, null=True)
    temperature = fields.FloatField(default=0.3)
    max_tokens = fields.IntField(default=4096)
    description = fields.CharField(max_length=200, null=True)
    status = fields.CharField(max_length=20, default="active")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(null=True)

    class Meta:
        table = "llm_configs"
