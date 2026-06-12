---
name: mysql-async-driver-compat
description: MySQL async driver version compatibility issues with tortoise-orm on Python 3.11
metadata:
  type: project
---

The project uses tortoise-orm with MySQL. Default `aiomysql` driver is abandoned (latest 0.2.0, 2021) and incompatible with Python 3.11. Must use `asyncmy` instead.

**Working combination (verified 2026-06-11):**
- `tortoise-orm[asyncmy]==0.24.2`
- Do NOT include nested `pool` dict in `config.py` credentials — `{"pool": {"minsize": 2, "maxsize": 20}}` gets passed through to `asyncmy.connect()` causing `TypeError: connect() got an unexpected keyword argument 'pool'`. Remove it entirely, let tortoise-orm use defaults.

**Failed combinations (do not use):**
- `tortoise-orm[aiomysql]>=0.20.0` + `aiomysql` latest → pool kwarg error on Python 3.11
- `tortoise-orm[asyncmy]==0.22.0` with nested pool config → same error
