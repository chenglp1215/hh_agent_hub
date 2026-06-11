---
name: my-agents-info
description: 一键部署多智能体体系并同步项目信息：创建 agents/skills/目录结构等完整配置，然后扫描项目文档更新 Agent 配置使其贴合当前项目。
---

# 多智能体体系部署与同步技能

当显式调用 `/my-agents-info` 时触发。分两个阶段执行：

1. **部署阶段**：在当前项目中创建完整的多智能体协同开发体系（Agent 配置、调度技能、目录结构等）
2. **同步阶段**：扫描项目文档和代码，将项目实际的技术栈、架构、业务规则等信息同步到 Agent 配置中，使其贴合当前项目

## 触发方式

仅通过 `/my-agents-info` 显式触发，不要自动触发。

## 第一阶段：部署（创建/补齐体系结构）

### Step 1: 检查 Skills 引用可用性

Agent 配置中引用了以下 skills，需要逐一检查它们是否已安装：

**必须检查的 skills**：
- `opsx:explore` — 主 agent (orchestration) 需求探索阶段引用
- `opsx:propose` — planner 引用
- `superpowers:writing-plans` — planner 引用
- `superpowers:executing-plans` — backend-developer、frontend-developer 引用
- `superpowers:test-driven-development` — backend-developer、tester 引用
- `superpowers:systematic-debugging` — backend-developer、verifier、tester 引用
- `vue-skills-bundle:vue-best-practices` — frontend-developer 引用
- `vue-skills-bundle:vue-pinia-best-practices` — frontend-developer 引用
- `frontend-design:frontend-design` — frontend-developer 引用

**检查方法**：
使用 Glob 搜索 `.claude/skills/*/SKILL.md`，查看项目中已安装的 skill 列表。对比上述引用列表，找出缺失的 skills。

**处理策略——缺失的 skill 必须安装后才能继续**：

1. 逐一检查每个 skill 是否存在
2. 如果有缺失的 skill，**立即使用 AskUserQuestion 向用户报告缺失列表，并要求用户安装后再继续**
3. 询问格式示例：
   ```
   缺失的 Skills:
   - opsx:explore (orchestration 主 agent 需要用于需求探索)
   - opsx:propose (planner 需要)
   - superpowers:executing-plans (backend/frontend developer 需要)

   这些 skills 未安装，Agent 运行时会调用失败。
   请安装对应的 Claude Code 插件后再重新执行 /my-agents-info。

   安装方式：
   - opsx:* 系列 → 安装 OpenSpec 插件
   - superpowers:* 系列 → 通常已内置，如缺失请检查 Claude Code 插件设置
   - vue-skills-bundle:* 系列 → 安装 Vue Skills 插件
   - frontend-design:frontend-design → 通常已内置，如缺失请检查 Claude Code 插件设置
   ```
4. 用户确认安装完成后，重新执行 `/my-agents-info`，此时 Step 1 检查通过后继续后续步骤
5. **不允许跳过缺失的 skill 直接继续**——缺失 skill 会导致 Agent 调用时报错，必须在部署阶段就解决

### Step 2: 创建目录结构

使用 Bash 工具创建所有必需的目录。**目录已存在时不报错、不破坏已有内容，仅补齐缺失的目录**：

```bash
mkdir -p .claude/agents .claude/skills/orchestration .claude/skills/evolve-agents .claude/skills/my-agents-info tasks outputs/architecture outputs/plans outputs/backend outputs/frontend outputs/verify outputs/testing
```

> `mkdir -p` 在所有平台（Linux/macOS/Windows Git Bash）上都具备"已存在则静默跳过"的行为，不会失败也不会覆盖已有内容。

然后补齐 `.gitkeep` 文件——**仅在文件不存在时才创建**，避免覆盖已有 `.gitkeep`：

```bash
for dir in tasks outputs/architecture outputs/plans outputs/backend outputs/frontend outputs/verify outputs/testing; do
  [ ! -f "$dir/.gitkeep" ] && touch "$dir/.gitkeep"
done
```

### Step 3: 拷贝 Agent 配置文件

从本技能的 `_agents/` 目录拷贝 5 个 Agent 配置文件到 `.claude/agents/`。

**定位源文件**：使用 Glob 搜索 `.claude/skills/my-agents-info/_agents/*.md` 获取所有 agent 模板文件列表。

**拷贝规则**：
- **目标文件不存在时**：使用 Read 工具读取源文件内容，再用 Write 工具完整写入目标路径 `.claude/agents/{agent-name}.md`
- **目标文件已存在时**：先 Read 读取已有内容，再判断差异，用 Edit 工具合并更新（保留已有项目上下文等定制内容，仅补充/更新标准模板部分）
- **禁止直接用 bash cp 拷贝**——必须通过 Read + Write/Edit 工具操作，以便在文件已存在时做智能合并

**5 个 Agent 文件对应关系**：

| 源文件 | 目标文件 | Agent | 模型 | 颜色 |
|--------|---------|-------|------|------|
| `_agents/planner.md` | `.claude/agents/planner.md` | 规划师 | sonnet | cyan |
| `_agents/backend-developer.md` | `.claude/agents/backend-developer.md` | 后端开发专家 | sonnet | green |
| `_agents/frontend-developer.md` | `.claude/agents/frontend-developer.md` | 前端开发专家 | sonnet | yellow |
| `_agents/verifier.md` | `.claude/agents/verifier.md` | 代码验证专家 | haiku | purple |
| `_agents/tester.md` | `.claude/agents/tester.md` | 测试专家 | haiku | red |

### Step 4: 拷贝 orchestration 调度技能

从本技能的 `_skills/orchestration.md` 拷贝到 `.claude/skills/orchestration/SKILL.md`。

**定位源文件**：使用 Glob 搜索 `.claude/skills/my-agents-info/_skills/orchestration.md`。

**拷贝规则**：
- **目标文件不存在时**：使用 Read 工具读取源文件内容，再用 Write 工具完整写入 `.claude/skills/orchestration/SKILL.md`
- **目标文件已存在时**：先 Read 读取已有内容，再判断差异，用 Edit 工具合并更新（保留已有定制内容，仅补充/更新标准模板部分）
- **禁止直接用 bash cp 拷贝**——必须通过 Read + Write/Edit 工具操作

### Step 5: 拷贝 evolve-agents 自进化技能

从本技能的 `_skills/evolve-agents.md` 拷贝到 `.claude/skills/evolve-agents/SKILL.md`。

**定位源文件**：使用 Glob 搜索 `.claude/skills/my-agents-info/_skills/evolve-agents.md`。

**拷贝规则**：同 Step 4，通过 Read + Write/Edit 工具操作。

## 第二阶段：同步（扫描项目信息 → 更新 Agent 配置）

部署阶段完成后，继续扫描当前项目的文档和代码，将项目实际信息同步到 Agent 配置中，使其贴合当前项目。

### Step 5: 扫描项目文档

全面搜索项目中所有可能包含规范、架构、业务说明的文件：

**搜索范围：**
- `CLAUDE.md` / `GEMINI.md` / `AGENTS.md` 等项目指令文件
- `README.md` 及 `docs/` 下的所有文档
- `*.md` 文件（设计文档、规范文档、需求文档）
- 数据库 schema / migration 文件（了解数据模型）
- API 路由定义文件（了解接口结构）
- 配置文件（`pyproject.toml`, `package.json`, `tsconfig.json` 等）
- 源代码目录结构（了解项目架构）
- `.env.example` 或类似文件（了解环境配置）
- 测试文件（了解测试规范）

**搜索方法：**
使用 Glob 和 Grep 工具系统搜索：
```
Glob: **/*.md
Glob: **/CLAUDE.md
Glob: **/schema*.sql
Glob: **/migration*/**/*
Glob: **/pyproject.toml
Glob: **/package.json
Glob: **/*.env*
Grep: 技术栈关键词（FastAPI, SQLAlchemy, Vue, Pinia, vxe-table 等）
Grep: 业务关键词（从 CLAUDE.md 或 README 中提取）
```

### Step 6: 梳理整理项目信息

将扫描到的信息分类整理为以下维度：

**1. 项目架构**
- 项目目录结构
- 模块划分和职责
- 依赖关系图

**2. 技术栈详情**
- 后端: 框架版本、ORM、数据库类型/版本、中间件
- 前端: 框架版本、UI 库、状态管理、构建工具
- 测试: 测试框架、覆盖率要求
- 其他: CI/CD、部署方式

**3. 业务规则**
- 核心业务模块
- 业务流程和数据流
- 权限和角色体系
- 特殊业务约束

**4. 开发规范**
- 代码风格要求（命名、格式、注释）
- 分支和提交规范
- API 设计规范（RESTful、版本管理）
- 数据库规范（命名、索引、迁移）

**5. 已有模式**
- 代码中已形成的惯例和模式
- 常用工具函数和组件
- 错误处理方式
- 日志和监控方式

### Step 7: 对比现有 Agent 配置

读取 `.claude/agents/` 下的 5 个文件（第一阶段已确保它们存在），对比梳理出的信息与现有 Agent 配置的差异：
- 技术栈是否与项目实际一致？
- 代码规范是否涵盖了项目已有的惯例？
- 业务场景是否已体现在 Agent prompt 中？
- 可用 Skills 是否需要调整？

### Step 8: 更新 Agent 配置

根据梳理结果，使用 Edit 工具更新每个 Agent 的 `.md` 文件。更新时遵循以下原则：

**更新内容：**
- 在 Agent prompt 中增加或更新「项目上下文」章节，写入项目实际架构、技术栈版本、业务规则
- 在「技术栈」章节中细化到具体版本和配置
- 在「代码规范」章节中补充项目已有的惯例和模式
- 在「可用 Skills」中根据项目需要增删
- 在「工作流程」中补充项目特有的步骤（如特定的部署流程、审批流程等）

**不更新的内容：**
- Agent 的 name、model、color 不变
- Agent 的工具权限不变
- 返回状态定义不变
- 过程日志格式不变

**项目上下文章节示例：**

```markdown
## 项目上下文

### 项目架构
- 后端: FastAPI 应用，入口 `backend/main.py`
- 前端: Vue 3 SPA，入口 `frontend/src/App.vue`
- 数据库: MySQL 8.0，迁移使用 Alembic

### 核心业务模块
- 用户管理: 注册、登录、权限
- 数据看板: 统计、报表

### 项目特有规范
- API 返回统一格式: `{ "code": int, "data": any, "msg": string }`
- 数据库表命名: `t_{module}_{entity}`
- 前端路由: 使用动态路由加载
```

## 执行注意事项

### 通用原则
1. **合并策略核心原则**：文件不存在 → Write 写入完整内容；文件已存在 → 先 Read 读取，再判断差异，用 Edit 合理合并（保留已有定制内容，仅补充/更新标准模板部分），不破坏项目已有配置
2. **禁止使用 worktree 隔离模式**：调用 Agent 时不要传 `isolation: "worktree"` 参数。worktree 模式会导致子 Agent 在隔离副本中工作，完成后通过 git patch 合合回主目录，如果主目录在此期间发生了变化，patch 会冲突失败。多 Agent 协同场景中，所有 Agent 必须在主工作目录中直接操作

### 第一阶段（部署）
2. **Step 1 Skills 引用检查**：必须逐一检查 Agent 引用的 skills 是否可用，缺失的 skill **必须要求用户安装后再继续**，不允许跳过缺失 skill 直接往下执行
3. **Step 3、Step 4、Step 5 使用文件拷贝**：从 `_agents/` 和 `_skills/` 目录拷贝模板文件到目标位置，通过 Read + Write/Edit 工具操作，不要用 bash cp 命令
4. **拷贝时必须完整写入**——Read 读取源文件的完整内容后，Write 写入目标路径，不要省略任何内容
5. **文件已存在时做智能合并**——保留项目已有的定制内容（如项目上下文），仅更新标准模板部分

### 第二阶段（同步）
9. 扫描项目文档时使用 Glob 和 Grep，确保覆盖所有可能的配置文件
10. 更新 Agent 配置时使用 Edit 工具精确修改，不要覆盖整个文件
11. 如果项目还没有实际代码（如新项目），主要基于 CLAUDE.md、README.md 等文档更新
12. 每次执行后应该可以看到 Agent 配置的变化，不要做无效更新
13. 如果扫描后发现项目信息与现有 Agent 配置完全一致，则报告「无需更新」即可
14. **项目上下文章节**：如果 Agent 中已有此章节，更新其内容；如果没有，新增此章节
15. 不更新 Agent 的 name、model、color、工具权限、返回状态定义、过程日志格式

### 完成确认
16. 执行完毕后向用户确认：体系已就绪，Agent 配置已同步项目信息，可以通过提出开发需求来触发 orchestration 技能