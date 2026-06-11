## 文档版本
| 版本 | 日期 | 作者 | 说明 |

---

## 十、端到端研发流程 (SDLC Pipeline)

### 10.1 设计理念

平台不仅是"运维助手"，而是面向**完整研发生命周期**的自动化编排引擎。通过配置不同角色的 Agent 和编排工作流，实现从需求到交付的全流程自动化。

```
需求提出 ──▶ 需求分析Agent ──▶ 方案设计Agent ──▶ 编码开发Agent
                  │                    │               │
                  ▼                    ▼               ▼
             生成需求文档        生成技术方案      生成代码/PR
                                                       │
                                                       ▼
部署上线 ◀── CI/CD部署Agent ◀── 质量验证Agent ◀── 代码审查Agent
   │               │                  │               │
   ▼               ▼                  ▼               ▼
生产环境      自动构建发布        自动化测试      代码Review
```

### 10.2 研发流程中的 Agent 角色

| 阶段 | Agent 角色 | Agent 类型 | 环境/工具 |
|------|-----------|-----------|----------|
| **需求分析** | `requirement_analyst` | local | TAPD/Jira MCP, 文档 Skills |
| **方案设计** | `solution_designer` | claudecode | 架构文档 Skills, 设计模式库 |
| **编码开发** | `developer` | claudecode | 代码仓库工作目录, IDE MCP |
| **代码审查** | `code_reviewer` | claudecode | 代码仓库, Linter MCP |
| **质量验证** | `qa_tester` | claudecode | 测试框架, 测试用例库 |
| **CI/CD 部署** | `cicd_deployer` | local / http | K8s MCP, Docker MCP, Jenkins API |
| **运维监控** | `ops_monitor` | local | Prometheus MCP, 日志 MCP, 告警 MCP |

### 10.3 Agent 工作目录与工作流工作空间

SDLC 流程同时使用两层工作空间，详见 [5.10 工作流执行工作空间](#510-工作流执行工作空间)：

| 层 | 路径 | 用途 |
|----|------|------|
| Agent 个人工作目录 | `/data/agent_workspaces/agent_{id}/` | CLAUDE.md、Skills、个人配置 |
| 工作流执行工作空间 | `/data/workflow_workspaces/{exec_id}/` | repos/（clone 的代码）+ artifacts/（各阶段产物） |

工作流 Engine 启动时自动 clone 代码仓库到 workspace 的 `repos/` 目录，各阶段 Agent 在同一份代码上接力——designer 读代码写设计，developer 在同一份代码上开发，tester 在同一份代码上跑测试。

### 10.4 典型 SDLC 工作流示例

#### 需求到交付全流程

```json
{
  "name": "需求到交付-标准流程",
  "flow_type": "sequential",
  "worker_agent_ids": [1, 2, 3, 4, 5],
  "parallel_groups": [
    {
      "group_id": "review_and_test",
      "agents": [3, 4],
      "merge_strategy": "concat"
    }
  ],
  "human_interrupts": [
    {
      "interrupt_id": "confirm_deploy",
      "agent_id": 5,
      "trigger_on": "before_execute",
      "message_template": "即将部署到生产环境，变更内容：{{params.changes}}，是否确认部署？"
    }
  ],
  "error_strategy": "skip_continue",
  "agent_timeout_seconds": 600,
  "workflow_timeout_seconds": 3600
}
```

**执行流程**：
```
Step 1: requirement_analyst ──▶ 生成需求文档/用户故事
                                    │
Step 2: solution_designer  ◀────────┘ 生成技术方案/API设计
                                    │
Step 3: developer + code_reviewer ◀─┘ 并行：编码 + 审查
    (parallel_group: review_and_test)   │
                                    │
Step 4: qa_tester ◀──────────────────┘ 自动化测试
                                    │
Step 5: cicd_deployer ◀─────────────┘ CI/CD部署
         │
    [human_interrupt: confirm_deploy]  ← 人工确认
         │
         ▼
      部署到生产
```

### 10.5 Agent 间数据传递

SDLC 流程中，上游 Agent 的输出是下游 Agent 的输入：

```python
# 工作流执行时，自动构建上下文传递给下游 Agent
def build_agent_context(state: dict, agent_config: dict) -> dict:
    """构建传递给当前 Agent 的上下文"""
    
    # 上游所有 Agent 的输出
    upstream_results = state.get("intermediate_results", {})
    
    # 当前 Agent 需要的特定上下文
    context_map = {
        "developer": {
            "requirements": upstream_results.get("requirement_analyst", ""),
            "design": upstream_results.get("solution_designer", "")
        },
        "qa_tester": {
            "source_code_changes": upstream_results.get("developer", ""),
            "requirements": upstream_results.get("requirement_analyst", "")
        },
        "cicd_deployer": {
            "test_results": upstream_results.get("qa_tester", ""),
            "code_review": upstream_results.get("code_reviewer", "")
        }
    }
    
    return {
        "user_input": state.get("user_input", ""),
        "upstream_context": context_map.get(agent_config.get("name"), upstream_results),
        "session_id": state.get("session_id", "")
    }
```

### 10.6 工作流模板库

预置常用 SDLC 流程模板：

| 模板名称 | 类型 | Agent 配置 | 描述 |
|---------|------|-----------|------|
| 需求到交付（完整） | sequential | 5 Agents | 全流程 |
| 快速需求分析 | single | requirement_analyst | 只做需求分析 |
| 代码审查+测试 | parallel | reviewer + tester | 并行审查和测试 |
| 部署流水线 | sequential | builder + deployer | 构建+部署 |
| Bug 修复流程 | supervisor | analyst + developer + tester | 分析和修复 Bug |


