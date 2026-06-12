---
name: deploy-and-test
description: 代码改动推送到Git后自动部署到开发环境并测试验证。用户说"部署测试"、"deploy and test"、代码push后要求验证时调用。需要先有chat-test skill。
---

# 部署与测试

**前置：** 代码已 commit 并 push 到 master。

## 部署环境

| 项目 | 值 |
|---|---|
| 主机 | 10.5.30.227 |
| 用户 | root |
| SSH 私钥 | dev_env/mykey |
| 代码目录 | /opt/hh_agent_hub |
| 服务管理 | docker compose |

## 部署流程

### 1. 拉取代码并重启服务

```bash
ssh -i dev_env/mykey -o StrictHostKeyChecking=no root@10.5.30.227 \
  "cd /opt/hh_agent_hub && git pull && docker compose up -d --build main worker"
```

**注意：** 只重启有代码变动的服务（main + worker），不动 frontend/mysql/redis。

### 2. 等待服务就绪

```bash
# 等待 main 服务健康检查通过
ssh -i dev_env/mykey -o StrictHostKeyChecking=no root@10.5.30.227 \
  "sleep 5 && docker compose ps --format json 2>/dev/null || docker-compose ps"
```

确认 `main` 和 `worker` 状态为 `Up` 或 `running`。

### 3. 验证代码版本

```bash
ssh -i dev_env/mykey -o StrictHostKeyChecking=no root@10.5.30.227 \
  "cd /opt/hh_agent_hub && git log --oneline -3"
```

确认最新 commit 已部署。

### 4. 查看启动日志（可选，排查启动失败时）

```bash
ssh -i dev_env/mykey -o StrictHostKeyChecking=no root@10.5.30.227 \
  "docker compose logs --tail 30 main 2>/dev/null || docker-compose logs --tail 30 main"
```

## 测试流程

### 优先：使用 chat-test skill 进行对话测试

调用 `/chat-test` skill，发送测试消息验证工作流端到端功能。

典型测试用例：
- "给我查一下线上这个事件的详情：1cc6dd40a5cbd2d196a3efb248dfd039"
- "你好，请介绍一下你的能力"

### 备选：直接 curl API 测试

```bash
curl -s "http://10.5.30.227:9020/api/v1/chat" \
  -H "Content-Type: application/json" \
  -b "auth_token=test123" \
  -H "X-API-Key: ak-VvVxOzYWM8WCFM1E3lXIhZfTwFWa2Y6N" \
  -d '{"app_id":1,"message":"测试消息","stream":false}' \
  --max-time 300
```

检查响应：
- `code` 应为 0
- `data.trace` 应包含完整的执行链路
- 无 `supervisor_force_end`、无连续同一 worker 的 route

## 测试验证检查清单

- [ ] 服务启动成功（docker compose ps 状态正常）
- [ ] 最新 commit 已生效
- [ ] Chat API 返回 code=0
- [ ] trace 显示 supervisor → worker → end（正常流程）
- [ ] 无 `supervisor_force_end`（正常结束 vs 强制终止）
- [ ] agent_end 的 elapsed_ms 在合理范围
- [ ] Agent 返回内容有意义（output_len > 20）
- [ ] 启动日志无 ERROR

## 遇到问题

| 症状 | 排查 |
|---|---|
| 服务未启动 | `docker compose logs main` 查看启动报错 |
| 503/502 | 等待 10s 后重试，可能服务还在启动中 |
| 路由无限循环 | 检查 `_available_workers` 是否正确传递 |
| MCP 工具调用失败 | 查看 worker 日志：`docker compose logs worker \| grep "MCP Tool"` |
| 超时 | 检查 LLM API 可用性（glm-5.1 服务状态） |
