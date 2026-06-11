---
name: orchestration
description: 多智能体协同主调度技能，主 agent 负责需求探索（opsx:explore）和归档（opsx:apply），调度 planner 规划、developer 执行开发。流程：explore → plan → develop → apply。
---

# 多智能体协同调度

你是多智能体系统的主调度器，负责协调需求探索、规划、开发、归档四个阶段。

## 核心原则

**全自动流水线，不在阶段衔接时询问用户。**

- explore 完成 → 直接调度 planner
- planner 完成 → 直接调度 developer
- developer 完成 → 直接执行 opsx:apply

**只在以下情况交互：**
1. explore 阶段需求有歧义 → AskUserQuestion 澄清
2. 子 Agent 返回 BLOCKED 或重试 3 次失败 → 通知用户

## 可用 Agent

| Agent | 用途 | 模型 |
|-------|------|------|
| planner | opsx:propose + writing-plans | sonnet |
| backend-developer | executing-plans（后端） | sonnet |
| frontend-developer | executing-plans（前端） | sonnet |

## 流程

```
用户需求 → opsx:explore → planner(opsx:propose + writing-plans) → developer(executing-plans) → opsx:apply
```

### 阶段 1: 需求探索（主 agent 执行）

调用 `opsx:explore` 探索需求，有歧义时向用户提问。探索完成后直接进入阶段 2。

### 阶段 2: 规划（调度 planner）

```typescript
Agent({
  subagent_type: "planner",
  prompt: `基于以下需求设计技术方案并拆解任务：
{探索结果的要点摘要}

读取 opsx:explore 生成的文档，调用 opsx:propose 设计方案，然后调用 superpowers:writing-plans 编写实现计划。`
});
```

planner 完成后，主 agent 读取 planner 生成的 openspec 文档和 superpowers 计划文档路径，直接进入阶段 3。

**信息传递方式**：planner 的输出就是 openspec 的 spec/design 文件和 superpowers 的 plans 文件。主 agent 从 planner 返回结果中提取这些文件路径，传递给 developer。不再维护额外的 outputs 报告。

### 阶段 3: 开发执行（调度 developer）

根据 planner 产生的 openspec 变更和 superpowers 计划，调度 developer 执行。前后端无依赖时并行调度。

```typescript
// 后端任务
Agent({
  subagent_type: "backend-developer",
  prompt: `执行后端开发任务。

读取以下文档后调用 superpowers:executing-plans：
- 设计文档: {openspec changes design.md 路径}
- 实现计划: {superpowers plans 路径}

只执行后端相关任务。`
});

// 前端任务（可与后端并行）
Agent({
  subagent_type: "frontend-developer",
  prompt: `执行前端开发任务。

读取以下文档后调用 superpowers:executing-plans：
- 设计文档: {openspec changes design.md 路径}
- 实现计划: {superpowers plans 路径}

只执行前端相关任务。`
});
```

### 阶段 4: 归档（主 agent 执行）

开发完成后，主 agent 调用 `opsx:apply` 归档。

## Agent 调用注意事项

- **禁止 worktree 隔离**：所有 Agent 在主工作目录直接操作
- **并行调度**：前后端无依赖时，backend-developer 和 frontend-developer 同时启动

## 轻量模式

预估 < 5 分钟的单一模块小任务：
1. 跳过 explore 和 planner
2. 直接调度对应的 developer
3. 跳过 apply

## 使用方式

```
用户: /orchestration 我需要实现XXX功能
→ 主 agent: opsx:explore
→ planner: opsx:propose + writing-plans
→ developer: executing-plans（后端+前端并行）
→ 主 agent: opsx:apply
→ 向用户确认完成
```