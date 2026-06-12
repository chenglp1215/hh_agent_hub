---
name: chat-test
description: 测试本项目的 Chat API。用户让你"测试chat"、"对话测试"、"验证工作流"时调用。需用户提供 API Key 和 App ID。
---

# Chat API 测试

## 前置条件

测试前确认 `test_chat.py` 顶部的配置正确：

```python
BASE_URL = "http://<host>:<port>"
HEADERS = {"Content-Type": "application/json", "X-API-Key": "<用户提供的API Key>"}
COOKIES = {"auth_token": "<用户提供的token>"}
DEFAULT_APP_ID = <用户提供的App ID>
```

**如果用户提供了新的 API Key / App ID / URL，先更新 `test_chat.py` 再测试。**

## 测试流程

### 1. 非流式测试（默认，推荐）

```bash
python test_chat.py "<用户消息>" --app-id <id>
```

输出包含：最终回复、执行追踪（trace）、中间结果、耗时。

### 2. 流式测试

```bash
python test_chat.py "<用户消息>" --app-id <id> --stream
```

实时展示 SSE 事件：thinking → agent_call → agent_result → done。

### 3. 续接会话

```bash
python test_chat.py "<追问>" --session-id <上次返回的session_id>
```

## 结果解读

### trace 字段说明

| type | 含义 |
|---|---|
| `supervisor_start` | Supervisor 开始新一轮调度 |
| `supervisor_route` | 路由到目标 worker（target: worker名 / end） |
| `supervisor_end` | 未找到 NEXT_AGENT 标记，工作流结束 |
| `supervisor_force_end` | 达到最大轮次(5)强制结束 |
| `agent_start` | Agent 开始执行 |
| `agent_end` | Agent 执行完成（含 output_len, elapsed_ms） |

### 异常判断

| 现象 | 可能原因 |
|---|---|
| trace 只有 supervisor → end | Supervisor 未找到 NEXT_AGENT 标记 |
| trace 反复 route 同一 worker | Supervisor 未看到 worker 结果就再次路由（消息传递问题） |
| supervisor_force_end | 超过 5 轮循环，检查路由指令是否生效 |
| agent_end output_len 很小（<50） | Agent 工具调用失败或能力不足 |
| 请求超时 | LLM API 超时（120s），检查 LLM 服务可用性 |

## 常见问题

1. **消息乱码**：确保 shell 支持 UTF-8，或使用英文消息测试
2. **连接拒绝**：检查 `BASE_URL` 和网络可达性
3. **401/403**：API Key 过期或无效，请用户重新提供
4. **应用不存在**：检查 `--app-id` 是否正确
