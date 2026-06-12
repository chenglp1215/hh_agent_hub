---
name: docker-compose-yaml-multiline
description: YAML multiline commands in docker-compose must use literal block scalar not folded
metadata:
  type: project
---

When writing multi-line `command:` values in `docker-compose.yml`, use `|` (literal block scalar) not `>` (folded block scalar).

- `>` folds all newlines into spaces, which concatenates Python statements into one line → `IndentationError`
- `|` preserves newlines, Python code works correctly

**Example (correct):**
```yaml
command: |
  python -c "
  import asyncio
  from module import thing

  async def main():
      ...

  asyncio.run(main())
  "
```

Also: `docker-compose.yml` file encoding must be UTF-8. Chinese comments in the file can cause decode errors on Windows GBK terminals but are fine in Docker.
