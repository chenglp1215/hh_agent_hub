---
name: orchestration
description: 多智能体协同主调度技能，主 agent 负责需求探索（opsx:explore）和归档（opsx:apply），调度开发代表规划、后端开发/前端开发执行、接口测试验证API。支持顺序模式和监督者模式双模调度。
---

# 多智能体协同调度

你是多智能体系统的主调度器，同时承担需求探索和归档职责。你负责协调需求探索、规划、开发、验证、API测试、归档六个阶段的工作流程，并支持**顺序模式**和**监督者模式**两种调度策略。

## 关键执行原则

**自动推进流程，不要在每个阶段结束后询问用户是否执行下一步。** orchestration 是全自动流水线，各阶段之间必须无缝衔接：

- 需求探索完成 → 直接进入模式选择 + 调度，不要问"是否创建提案"
- 规划完成 → 直接调度开发 agent，不要问"是否开始开发"
- 开发完成 → 直接调度代码审计师，不要问"是否验证"
- 验证通过 → 直接调度接口测试，不要问"是否测试 API"
- API测试通过 → 直接执行 opsx:apply 归档，不要问"是否归档"

**只在以下情况与用户交互：**
1. 需求探索阶段：opsx:explore 发现需求有歧义 → 使用 AskUserQuestion 澄清
2. 子 Agent 返回 NEEDS_CLARIFICATION → 向用户提问
3. 子 Agent 返回 BLOCKED 或重试 3 次失败 → 通知用户
4. 整个流水线完成 → 向用户确认最终结果

**不要做的事：**
- 不要在阶段衔接时暂停等待用户确认
- 不要问"是否继续"、"是否执行下一步"、"是否创建提案"
- 不要把 opsx:explore 的"建议下一步"当作需要用户确认的信号

## 核心职责

1. **需求探索**: 调用 opsx:explore 探索需求，与用户交互澄清疑点
2. **模式选择**: 根据探索结果判断任务复杂度，选择顺序模式或监督者模式
3. **任务分配**: 根据任务阶段和调度模式调度合适的 Agent 执行
4. **状态管理**: 创建和更新任务状态文件
5. **结果聚合**: 收集各 Agent 输出，生成最终报告
6. **归档验收**: 调用 opsx:apply 归档验收成果
7. **日志管理**: 创建和更新统一的过程日志文件
8. **信息传递**: 在各阶段之间传递文档路径和关键信息

## 可用 Agent

| Agent | 用途 | 模型 |
|-------|------|------|
| 开发代表 | 方案设计、任务拆解 | sonnet |
| 后端开发 | Python 后端开发 | sonnet |
| 前端开发 | Vue 前端开发 | sonnet |
| 代码审计师 | 编译/构建验证 | haiku |
| 接口测试 | API 自动化测试 | sonnet |
| 整体测试 | 全量测试用例编写与执行 | haiku |

---

## 调度模式

探索阶段完成后，主 agent 根据任务特征自动选择调度模式。

### 模式选择决策树

```
探索完成
    │
    ├── 单一模块 + 简单改动（< 5 分钟预估）
    │       → 轻量模式：直接调度开发 agent，跳过其他阶段
    │
    ├── 明确需求 + 线性依赖 + 模块数 ≤ 2
    │       → 顺序模式：固定流水线 explore → plan → develop → verify → api-test → archive
    │
    └── 复杂需求 / 多模块并行 / 跨领域协同 / 不确定性强
            → 监督者模式：动态调度，主 agent 全程监督协调
```

### 顺序模式（固定流水线）

适用于需求明确、依赖关系清晰的线性任务。流程固定：

```
需求探索 → 开发代表规划 → 后端/前端开发（并行） → 代码审计师验证 → 接口测试 → 归档
```

详见下方「阶段 1 ~ 阶段 6」。

### 监督者模式（动态调度）

适用于复杂、多模块、跨领域或不确定性强的任务。**主 agent 作为监督者**，不再按固定流水线执行，而是：

#### 核心机制

1. **动态任务拆解**：探索阶段产出高层任务图（而非线性流水线），标注每个子任务的类型、依赖、预估复杂度
2. **按需调度**：监督者根据任务图实时决策下一步调度哪个 Agent，而非固定顺序
3. **并行执行**：无依赖的子任务同时分派给多个 Agent 并行执行
4. **Agent 间直接通信**：Agent 之间可以互相请求协助（如后端开发可以请求接口测试验证某个接口）
5. **动态重规划**：某个子任务的结果可能影响后续任务的形态，监督者据此调整任务图
6. **增量验证**：每完成一个子任务立即验证，而非等所有开发完成后统一验证

#### 监督者模式工作流程

```
                    ┌─────────────────────────────────┐
                    │       主 agent（监督者）          │
                    │   · 持有全局任务图               │
                    │   · 监控各 Agent 状态            │
                    │   · 动态决策下一步调度           │
                    │   · 处理 Agent 间协调请求        │
                    └──────────┬──────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  开发代表     │   │  后端开发     │   │  前端开发     │
    │  方案设计     │   │  API/Model   │   │  组件/页面    │
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  代码审计师   │   │  接口测试     │   │  整体测试     │
    │  编译/构建    │   │  API 验证    │   │  全量测试    │
    └──────────────┘   └──────────────┘   └──────────────┘
```

#### 监督者调度策略

| 场景 | 调度决策 |
|------|---------|
| 多个后端子任务无依赖 | 并行调度多个后端开发实例 |
| 前后端子任务无依赖 | 同时调度后端开发和前端开发 |
| 某子任务涉及新表设计 | 先调度开发代表做局部方案，再调度后端开发实现 |
| 后端完成一个子任务 | 立即调度代码审计师增量验证该子任务 |
| 代码审计师发现错误 | 直接通知对应开发 agent 修复，不等待全部完成 |
| Agent 请求协助 | 评估请求合理性，调度对应 Agent 响应 |
| 某子任务结果改变后续计划 | 更新任务图，重新评估后续调度顺序 |

#### 监督者模式下的调用方式

```typescript
// 监督者持有全局状态
const supervisorState = {
  taskGraph: [],        // 任务图（节点+依赖边）
  agentStatus: {},      // 各 Agent 状态 { agentName: 'idle' | 'running' | 'done' | 'blocked' }
  completedTasks: [],   // 已完成子任务
  activeAgents: [],     // 当前活跃的 Agent
  pendingDecisions: [], // 待监督者决策的事项
};

// 监督者主循环（伪代码）
while (supervisorState.taskGraph.hasPendingTasks()) {
  // 1. 检查已完成任务，更新任务图
  checkCompletedTasks(supervisorState);

  // 2. 找出所有依赖已满足的就绪任务
  const readyTasks = getReadyTasks(supervisorState.taskGraph);

  // 3. 对每个就绪任务，决策调度策略
  for (const task of readyTasks) {
    const agentType = mapTaskToAgent(task);
    const canParallel = !hasConflict(task, supervisorState.activeAgents);

    if (canParallel) {
      // 并行分派
      dispatchAgent(agentType, task);
    } else {
      // 加入待调度队列
      supervisorState.pendingDecisions.push({ task, agentType });
    }
  }

  // 4. 处理 Agent 间通信请求
  handleAgentRequests(supervisorState);

  // 5. 等待任一 Agent 完成
  await waitForAnyAgent(supervisorState.activeAgents);

  // 6. 收集结果，更新状态
  collectResults(supervisorState);
}

// 全部子任务完成后，统一归档
await Skill("opsx:apply", args: "归档验收成果");
```

#### 监督者模式的日志格式

监督者模式下日志增加调度决策记录：

```
[时间] [orchestration] 📊 任务图更新: 3/7 已完成，2 进行中，2 待调度
[时间] [orchestration] 🚀 并行调度: 后端开发(B2) + 前端开发(F1)
[时间] [orchestration] 📡 Agent 通信: 后端开发 → 接口测试，请求验证 POST /api/v1/xxx/
[时间] [orchestration] 🔄 重规划: 前端开发(F2) 因 B3 变更需调整，已更新任务描述
[时间] [orchestration] ✅ 子任务完成: B2 (后端开发), 耗时 4 分钟
```

---

## 顺序模式详细流程

以下为顺序模式的固定阶段流程。监督者模式下跳过这些固定阶段，改用上述动态调度策略。

### 工作流程总图

```mermaid
flowchart TD
    A[接收用户需求] --> B[创建任务状态文件 + 初始化日志]
    B --> C[主 agent: opsx:explore]
    C --> D{探索结果}
    D -->|DONE| E[追加日志 + 保存探索结果]
    D -->|NEEDS_CLARIFICATION| F[追加日志 + 向用户提问]
    F --> C
    E --> M{模式选择}
    M -->|轻量| LITE[轻量模式：直接调度开发 agent]
    M -->|顺序| G[调度开发代表]
    M -->|监督者| SUP[进入监督者模式动态调度]
    G --> H{规划结果}
    H -->|DONE| I[追加日志 + 读取任务拆解]
    H -->|NEEDS_CLARIFICATION| J[追加日志 + 向用户提问]
    J --> G
    I --> K{任务类型}
    K -->|backend| L[调度后端开发]
    K -->|frontend| L2[调度前端开发]
    K -->|mixed| N[并行调度后端开发 + 前端开发]
    L --> O[追加日志 + 调度代码审计师]
    L2 --> O
    N --> O
    O --> P{验证结果}
    P -->|通过| Q[追加日志 + 调度接口测试]
    P -->|有错误| R2[追加日志 + 返回开发 agent 修复]
    R2 --> O
    Q --> P2{API测试结果}
    P2 -->|全部通过| S2[追加日志 + opsx:apply 归档]
    P2 -->|有失败| R[追加日志 + 接口测试自行修复并重跑]
    R --> Q
    S2 --> S[追加日志 + 标记任务完成]
    SUP --> S
    LITE --> S
```

---

## 阶段 1: 需求探索（主 agent 执行）

主 agent 直接执行需求探索，不调度子 Agent。可多次与用户交互。

### 执行方式

调用 `opsx:explore` 技能探索需求：

```
Skill("opsx:explore", args: "用户需求描述")
```

### 探索过程

1. 调用 opsx:explore，分析用户需求
2. 如果发现需求有歧义或缺失，使用 AskUserQuestion 向用户提问
3. 用户回答后，继续探索或重新调用 opsx:explore
4. 探索完成后，将结果保存到 `outputs/architecture/task-{id}-explore.md`
5. **评估任务复杂度，选择调度模式**（轻量/顺序/监督者）
6. **立即进入下一阶段**——不要询问用户"是否创建提案"

### 探索结果文件格式

```markdown
# 需求探索结果

## 任务ID: task-{id}
## 探索时间: {YYYY-MM-DD HH:MM:SS}

## 需求概述
{用户需求的核心描述}

## 业务目标
{要达成的业务目标}

## 关键发现
- {发现 1}
- {发现 2}

## 约束条件
- {约束 1}
- {约束 2}

## 涉及模块
| 模块 | 影响范围 |
|------|---------|
| {模块名} | {影响描述} |

## 用户澄清记录
| 问题 | 用户回答 |
|------|---------|
| {问题} | {回答} |

## 调度建议
- 推荐模式: {轻量/顺序/监督者}
- 理由: {简述判断依据}
- 预估复杂度: {低/中/高}
- 并行机会: {可并行的子任务列表}
```

---

## 阶段 2: 规划（调度开发代表）

将探索结果传递给开发代表，执行方案设计和任务拆解。

### 调用方式

```typescript
const plannerResult = await Agent({
  subagent_type: "开发代表",
  prompt: `
## 任务ID: task-{id}

## 输入文档（必须读取）
- 需求探索结果: outputs/architecture/task-{id}-explore.md

## 任务
基于探索结果设计技术方案并拆解为可执行任务。

### 必须产出

1. **API 契约文件** \`outputs/contracts/task-{id}-api-contract.md\`（核心，最先产出）：
   - 这是后端、前端、接口测试三个 agent 的共同契约，三个 agent 各自读取同一份文件
   - 格式要求：每个接口一张表，逐字段列出 后端字段名、类型、前端字段名、前端类型、枚举值
   - 特别注意蛇形/驼峰命名映射：后端 \`customer_name\` ↔ 前端 \`customerName\`
   - 特别注意枚举值：后端 \`CharEnumField.to_dict()\` 返回字符串，前端必须用相同字符串值

2. **OpenSpec 设计文档**：调用 opsx:propose 生成
3. **Superpowers 实现计划**：调用 superpowers:writing-plans 生成

调用顺序：先 opsx:propose 设计方案 → 然后生成 API 契约文件 → 再 superpowers:writing-plans 编写实现计划。
`
});
```

### 开发代表返回信息提取

开发代表完成后，主 agent 从其返回中提取以下信息，用于传递给下游 agent：

```json
{
  "status": "DONE",
  "outputFile": "outputs/plans/task-{id}.md",
  "generatedFiles": {
    "contractFile": "outputs/contracts/task-{id}-api-contract.md",
    "specs": ["openspec/specs/{spec}/spec.md"],
    "changes": ["openspec/changes/{change}/design.md"],
    "superpowersPlan": "docs/superpowers/plans/{date}-{name}.md",
    "taskPlan": "outputs/plans/task-{id}.md"
  },
  "tasks": {
    "backend": [{"id": "B1", "title": "...", "priority": "high"}],
    "frontend": [{"id": "F1", "title": "...", "priority": "high"}],
    "apiTest": [{"id": "A1", "title": "...", "priority": "medium"}]
  },
  "apiContracts": {
    "newRoutes": [{"method": "POST", "path": "/api/v1/xxx/", "description": "..."}],
    "modifiedRoutes": [{"method": "PUT", "path": "/api/v1/xxx/{id}", "changes": "新增字段 yyy"}]
  },
  "summary": "...",
  "concerns": []
}
```

---

## 阶段 3: 开发执行（调度后端开发/前端开发）

根据开发代表的任务拆解，调度后端开发和/或前端开发。

### 调用方式

```typescript
// 读取开发代表返回结果
const planData = ...;  // 开发代表返回的 JSON

// 构建开发 agent 共享上下文
const contractFile = planData.generatedFiles.contractFile || `outputs/contracts/task-{id}-api-contract.md`;

const devContext = `
## 任务ID: task-{id}

## 输入文档（必须读取，按优先级排序）
1. **API 契约文件（优先读取）**: ${contractFile}
   - 这是开发代表制定的前后端共同契约，定义了每个接口的精确字段名、类型、枚举值
   - 后端开发：to_dict() 返回的字段名必须与契约中的"后端字段名"一致
   - 前端开发：TypeScript interface 属性名必须与契约中的"前端字段名"一致
2. 设计文档: ${planData.generatedFiles.changes?.[0] || 'openspec/changes/{change-name}/design.md'}
3. 实现计划: ${planData.generatedFiles.superpowersPlan || ''}
4. 规划报告: ${planData.outputFile}
`;

// 后端任务
if (planData.tasks?.backend?.length > 0) {
  const backendPrompt = devContext + `
## 后端任务列表
${formatTasks(planData.tasks.backend)}

## 重要：输出 API 变更报告

完成开发后，必须在开发报告中包含 **API 变更明细**，供下游接口测试使用：

### 必须包含的内容：
1. **变更的 API 接口清单**：每个接口的方法、完整路径、变更类型（新增/修改/删除）
2. **请求参数明细**：参数名、类型、必填/可选、默认值、说明
3. **响应 result 字段明细**：每个字段名、类型、含义（特别注意枚举字段的值）
4. **新增/变更的枚举值**：所有枚举值和含义
5. **认证要求**：是否需要登录、是否需要特定权限
6. **关联依赖**：接口间的调用依赖关系（如：先创建A才能创建B）

### API 变更报告格式：
\`\`\`markdown
## API 变更明细

### 新增接口
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/v1/xxx/ | 创建XXX | 需要登录 |

#### POST /api/v1/xxx/ 详细说明
- **请求体**:
  - name (string, 必填) - 名称
  - type (string, 可选, 默认 "default") - 类型，枚举值: default/advanced/custom
- **响应 result**:
  - id (int) - 记录ID
  - name (string) - 名称
  - type (string) - 类型
  - created_at (string) - 创建时间

### 修改接口
| 方法 | 路径 | 变更内容 |
|------|------|---------|
| PUT | /api/v1/xxx/{id} | 新增字段 yyy |

### 新增枚举值
| 字段 | 枚举值 | 含义 |
|------|--------|------|
| type | default | 默认类型 |
| type | advanced | 高级类型 |
| type | custom | 自定义类型 |
\`\`\`

## 任务
调用 superpowers:executing-plans 执行以上后端开发任务。
完成后输出开发报告到 outputs/backend/task-{id}.md，**必须包含上述 API 变更明细**。
`;

  const backendResult = await Agent({
    subagent_type: "后端开发",
    prompt: backendPrompt
  });
}

// 前端任务（可与后端并行）
if (planData.tasks?.frontend?.length > 0) {
  const frontendPrompt = devContext + `
## 前端任务列表
${formatTasks(planData.tasks.frontend)}

## 重要：输出前端变更报告

完成开发后，必须在开发报告中包含以下内容：

### 必须包含的内容：
1. **变更的组件/页面清单**：文件路径、变更类型
2. **对接的 API 接口**：每个接口的方法、路径、用途
3. **新增/变更的 TypeScript 类型**：interface/enum 定义
4. **路由变更**（如有）：新增/修改的路由路径

## 任务
调用 superpowers:executing-plans 执行以上前端开发任务。
完成后输出开发报告到 outputs/frontend/task-{id}.md。
`;

  const frontendResult = await Agent({
    subagent_type: "前端开发",
    prompt: frontendPrompt
  });
}
```

### 并行调度

前后端任务无依赖时并行执行：

```typescript
const [backendResult, frontendResult] = await Promise.all([
  Agent({ subagent_type: "后端开发", prompt: backendPrompt }),
  Agent({ subagent_type: "前端开发", prompt: frontendPrompt })
]);
```

---

## 阶段 4: 编译/构建验证（调度代码审计师）

开发完成后，调度代码审计师进行编译和构建检查。

### 调用方式

```typescript
await Agent({
  subagent_type: "代码审计师",
  prompt: `
## 任务ID: task-{id}

## 输入文档（必须读取）
- 后端开发报告: outputs/backend/task-{id}.md
- 前端开发报告: outputs/frontend/task-{id}.md
- 规划报告: ${planData.outputFile}

## 任务
对本次变更的代码进行编译检查和构建验证。
`
});
```

### 处理验证失败

如果代码审计师返回 BLOCKED（编译/构建失败），调度对应的开发 agent 修复错误，然后重新验证：

```typescript
if (verifyResult.status === "BLOCKED") {
  await Agent({ subagent_type: "后端开发", prompt: fixPrompt });
  await Agent({ subagent_type: "代码审计师", prompt: reVerifyPrompt });
}
```

---

## 阶段 5: API 测试（调度接口测试）

验证通过后，调度接口测试对后端 API 变更进行自动化测试。

### 调用方式

```typescript
await Agent({
  subagent_type: "接口测试",
  prompt: `
## 任务ID: task-{id}

## 输入文档（必须读取，按优先级排序）
1. **API 契约文件（优先读取）**: ${contractFile}
   - 开发代表制定的前后端共同契约，逐字段定义了每个接口的请求参数和响应字段
   - 这是契约验证的基准
2. 后端变更报告: outputs/backend/task-{id}.md
3. 规划报告: outputs/plans/task-{id}.md

## 变更的 API 摘要
${summarizeApiChanges(planData.apiContracts)}

## 任务
1. 读取 API 契约文件和后端变更报告
2. 确认后端服务运行中（如未运行则启动，记录 PID）
3. 登录获取 JWT Token
4. 调用 Skill("api-testing") 执行 API 测试
5. **契约验证（核心）**：
   - 逐字段对比实际 API 响应与契约文件中的定义
   - 检查：字段名、类型、枚举值、分页格式
   - 🚨 字段名不一致 → 直接修复（通常是后端 to_dict() 忘记更新）
   - 生成契约合规报告
6. 发现问题时：简单 Bug 直接修复并重跑，复杂问题记录到报告
7. 测试完成后清理测试数据和测试进程
8. 输出测试报告（含契约合规报告）到 outputs/testing/task-{id}.md
`
});
```

### 处理 API 测试失败

```typescript
if (apiTestResult.status === "DONE_WITH_CONCERNS") {
  // 接口测试已自行修复可修复的 Bug 并重跑
  // 仍有失败项时，记录到日志，继续归档（不阻塞流程）
  logConcerns(apiTestResult.concerns);
}

if (apiTestResult.status === "BLOCKED") {
  // 服务无法启动或登录失败，通知用户
  notifyUser("API 测试阻塞: " + apiTestResult.reason);
}
```

### 只有前端变更时跳过

如果开发代表返回的 tasks 中只有前端任务（无 backend 任务），跳过接口测试阶段，直接从代码审计师进入归档。

---

## 阶段 6: 归档验收（主 agent 执行）

主 agent 直接执行归档，调用 opsx:apply。

### 执行方式

```
Skill("opsx:apply", args: "归档验收成果")
```

### 归档内容

1. 读取 API 测试报告
2. 调用 opsx:apply 归档规格文档、变更文档、实现计划
3. 更新任务状态文件为 `completed`
4. 向用户确认完成

---

## 过程日志

每个任务有一个统一的过程日志文件 `outputs/task-{id}.log`，所有 Agent 的执行过程都追加写入同一个文件。**所有日志写入必须使用 Bash 工具执行 `echo >>` 命令追加，不要用 Write 工具（Write 会覆盖整个文件）**：

```bash
echo "[{时间}] [{Agent名称}] {事件描述}" >> outputs/task-{id}.log
```

### 日志格式

```
[{时间}] [{Agent名称}] {事件描述}
```

### 日志事件类型

| 事件 | 格式示例 |
|------|----------|
| 任务创建 | `[2026-06-13 18:00:00] [orchestration] ===== 任务创建: task-001 - 用户登录功能 =====` |
| 需求探索 | `[2026-06-13 18:00:00] [orchestration] 调用 opsx:explore` |
| 模式选择 | `[2026-06-13 18:02:00] [orchestration] 模式选择: 监督者模式（多模块并行，复杂度高）` |
| 调度 Agent | `[2026-06-13 18:05:00] [orchestration] 调度 → 开发代表` |
| 并行调度 | `[2026-06-13 18:20:00] [orchestration] 🚀 并行调度: 后端开发(B2) + 前端开发(F1)` |
| 重规划 | `[2026-06-13 18:30:00] [orchestration] 🔄 重规划: B3 结果改变后续任务，更新任务图` |
| 开始执行 | `[2026-06-13 18:05:00] [开发代表] ===== 开始执行 =====` |
| 关键步骤 | `[2026-06-13 18:10:00] [开发代表] 完成方案设计 (opsx:propose)` |
| 输出文件 | `[2026-06-13 18:15:00] [开发代表] 输出计划: outputs/plans/task-001.md` |
| 需要澄清 | `[2026-06-13 18:08:00] [开发代表] NEEDS_CLARIFICATION: {问题}` |
| 执行完成 | `[2026-06-13 18:30:00] [后端开发] ===== 完成 (DONE) =====` |
| 有疑虑 | `[2026-06-13 18:30:00] [后端开发] ===== 完成 (DONE_WITH_CONCERNS) =====` |
| 阻塞 | `[2026-06-13 18:10:00] [接口测试] ===== 阻塞 (BLOCKED) =====` |
| 归档 | `[2026-06-13 19:00:00] [orchestration] 调用 opsx:apply 归档` |
| 任务结束 | `[2026-06-13 19:00:00] [orchestration] ===== 任务完成 =====` |

---

## 上下文传递链（信息流）

各阶段之间的信息传递遵循以下链路。**核心：API 契约文件是开发代表产出的共享文件，后端、前端、接口测试三个 agent 各自读取同一份文件。**

```
explore 产出            开发代表 产出                     开发 agent 消费                 接口测试 消费
┌────────────────┐    ┌──────────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ 需求探索结果    │    │ API 契约文件（共享文件）   │    │ 后端开发              │    │ 接口测试              │
│ - 需求概述      │    │ outputs/contracts/       │    │ → 读取契约文件        │    │ → 读取契约文件        │
│ - 业务目标      │──→│   task-{id}-api-contract  │──→│ → to_dict()字段名     │──→│ → 逐字段对比实际响应  │
│ - 涉及模块      │    │                          │    │   必须与契约一致       │    │   与契约定义是否一致  │
│ - 约束条件      │    │ 每个接口：               │    │                       │    │                       │
│ - 调度建议      │    │ - 后端字段名 ↔ 前端字段名 │    │ 前端开发              │    │ 发现不一致 → 直接修复 │
└────────────────┘    │ - 类型、枚举值            │    │ → 读取契约文件        │    │ 输出契约合规报告     │
                      │ - 请求参数表              │    │ → interface属性名     │    └──────────────────────┘
                      │ - 响应字段表              │──→│   必须与契约一致       │
                      │                          │    └──────────────────────┘
                      │ OpenSpec 设计文档         │
                      │ Superpowers 实现计划      │
                      └──────────────────────────┘
```

**关键信息要求：**

| 传递环节 | 必须包含的信息 | 用途 |
|---------|--------------|------|
| 开发代表 → 契约文件 | 每个接口逐字段的后端字段名、前端字段名、类型、枚举值 | **前后端和测试的共同基准** |
| 契约文件 → 后端开发 | 后端字段名必须与契约一致，枚举值必须匹配 | 确保 to_dict() 返回正确 |
| 契约文件 → 前端开发 | 前端字段名必须与契约一致，蛇形→驼峰映射 | 确保 interface 定义正确 |
| 契约文件 + 后端报告 → 接口测试 | 对比实际响应与契约，逐字段验证 | 发现并修复前后端不一致 |
| 后端开发 → 代码审计师 | 变更文件列表 | 确定编译检查范围 |

---

## 执行阶段总览

| 阶段 | 执行者 | 输入 | 输出 |
|------|--------|------|------|
| 需求探索 | 主 agent (opsx:explore) | 用户需求 | `outputs/architecture/task-{id}-explore.md` |
| 模式选择 | 主 agent | 探索结果 | 调度模式决策 |
| 规划 | 开发代表 | 探索结果 | `outputs/plans/task-{id}.md` + openspec 文档 |
| 后端开发 | 后端开发 | 设计文档 + 实现计划 | `outputs/backend/task-{id}.md`（含 API 变更明细） |
| 前端开发 | 前端开发 | 设计文档 + 实现计划 | `outputs/frontend/task-{id}.md` |
| 编译验证 | 代码审计师 | 开发报告 | `outputs/verify/task-{id}.md` |
| API 测试 | 接口测试 | 后端变更报告 + 规划报告 | `outputs/testing/task-{id}.md` + 测试脚本 |
| 归档验收 | 主 agent (opsx:apply) | 所有报告 | 归档完成 |

---

## 处理 Agent 返回状态

| 状态 | 处理方式 |
|------|----------|
| DONE | 继续下一步流程 |
| DONE_WITH_CONCERNS | 记录疑虑，继续流程（接口测试的 DONE_WITH_CONCERNS 不阻塞归档） |
| NEEDS_CLARIFICATION | 使用 AskUserQuestion 向用户提问 |
| BLOCKED | 记录阻塞原因，通知用户（接口测试的 BLOCKED 需要用户介入） |

## 重试与回滚策略

1. **最大重试次数**: 3 次
2. **重试间隔**: 指数退避
3. **超过重试次数**: 标记任务为 `FAILED`，通知用户
4. **失败快照**: 保存当前代码状态到 `outputs/{agent}/task-{id}-retry-{n}.md`
5. **紧急回滚**: 连续 3 次重试失败，使用 `git checkout` 回退

## 错误处理

1. Agent 执行失败：记录错误，标记任务为 blocked，通知用户
2. 验证失败：返回开发 Agent 修复，最多重试 3 次
3. API 测试失败：接口测试自行修复简单 Bug 并重跑；复杂问题记录不阻塞流程
4. 依赖阻塞：等待依赖任务完成后再执行

## Agent 调用注意事项

**禁止使用 worktree 隔离模式**：调用 Agent 时不要传 `isolation: "worktree"` 参数。所有 Agent 必须在主工作目录中直接操作。

## 轻量模式

对于预估 < 5 分钟的单一模块小任务，自动进入轻量模式：

**触发条件**: 任务类型为单一模块且预估工作量小

**轻量流程**:
1. 跳过 opsx:explore 和开发代表
2. 直接调度对应的开发 agent 执行
3. 跳过代码审计师、接口测试和 opsx:apply
4. 完成后简要说明变更内容

**示例**:
```
用户: 修复登录页面的样式问题
→ 触发 orchestration skill
→ 识别为轻量任务（单一前端模块，小改动）
→ 直接调度前端开发修复
→ 完成后简要汇报变更
```

## 使用方式

```
用户: /orchestration 我需要实现XXX功能
→ 主 agent: opsx:explore 探索需求（如有歧义向用户提问）
→ 探索完成 → 模式选择（轻量/顺序/监督者）
→ [顺序模式] 自动调度开发代表 → 后端开发 + 前端开发（并行） → 代码审计师 → 接口测试 → opsx:apply 归档
→ [监督者模式] 构建任务图 → 动态并行调度 → 增量验证 → 动态重规划 → 全部完成 → opsx:apply 归档
→ [轻量模式] 直接调度开发 agent → 完成汇报
→ 向用户确认最终结果
```
