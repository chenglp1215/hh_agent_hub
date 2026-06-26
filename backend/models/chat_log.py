from tortoise import fields, Model


class ChatLog(Model):
    """Chat 交互日志 — 记录每次 API 调用的完整信息

    每条记录对应一次 POST /chat 请求的完整生命周期。
    """
    id = fields.IntField(pk=True)
    app = fields.ForeignKeyField("models.App", null=True, on_delete=fields.SET_NULL)
    session = fields.ForeignKeyField("models.Session", null=True, on_delete=fields.SET_NULL)
    task_id = fields.CharField(max_length=36, null=True, index=True)
    user_input = fields.TextField()
    final_answer = fields.TextField(null=True)
    duration_ms = fields.IntField(null=True)
    status = fields.CharField(max_length=20, default="success")  # success / error
    error_message = fields.TextField(null=True)
    agent_count = fields.IntField(default=0)
    trace_summary = fields.JSONField(null=True)
    # Token 消耗
    prompt_tokens = fields.IntField(default=0)
    completion_tokens = fields.IntField(default=0)
    total_tokens = fields.IntField(default=0)
    model_name = fields.CharField(max_length=100, null=True)
    token_by_model = fields.JSONField(null=True)  # {model_name: {prompt, completion, total}}
    created_at = fields.DatetimeField(auto_now_add=True, index=True)

    class Meta:
        table = "chat_logs"
