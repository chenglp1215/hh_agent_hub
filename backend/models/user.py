from tortoise import fields, Model


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password_hash = fields.CharField(max_length=255)
    api_key = fields.CharField(max_length=64, unique=True)
    role = fields.CharField(max_length=20, default="user")
    email = fields.CharField(max_length=100, null=True)
    avatar = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(null=True)

    class Meta:
        table = "users"
