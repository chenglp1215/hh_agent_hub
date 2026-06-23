import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '主控台' } },
        // Agent management
        { path: 'agents', name: 'AgentList', component: () => import('@/views/AgentList.vue'), meta: { title: 'Agent 列表' } },
        { path: 'agents/create', name: 'AgentCreate', component: () => import('@/views/AgentEditor.vue'), meta: { title: '创建 Agent' } },
        { path: 'agents/:id/edit', name: 'AgentEdit', component: () => import('@/views/AgentEditor.vue'), meta: { title: '编辑 Agent' }, props: true },
        // Workflow orchestration
        { path: 'workflows', name: 'WorkflowList', component: () => import('@/views/WorkflowList.vue'), meta: { title: '工作流列表' } },
        { path: 'workflows/create', name: 'WorkflowCreate', component: () => import('@/views/WorkflowEditor.vue'), meta: { title: '创建工作流' } },
        { path: 'workflows/:id/edit', name: 'WorkflowEdit', component: () => import('@/views/WorkflowEditor.vue'), meta: { title: '编辑工作流' }, props: true },
        // Application management
        { path: 'apps', name: 'AppList', component: () => import('@/views/AppList.vue'), meta: { title: '应用列表' } },
        { path: 'apps/create', name: 'AppCreate', component: () => import('@/views/AppEditor.vue'), meta: { title: '创建应用' } },
        { path: 'apps/:id/edit', name: 'AppEdit', component: () => import('@/views/AppEditor.vue'), meta: { title: '编辑应用' }, props: true },
        // Trigger management
        { path: 'triggers', name: 'TriggerList', component: () => import('@/views/TriggerList.vue'), meta: { title: '触发器管理' } },
        { path: 'triggers/create', name: 'TriggerCreate', component: () => import('@/views/TriggerEditor.vue'), meta: { title: '创建触发器' } },
        { path: 'triggers/create-wecom-bot', name: 'WecomBotTriggerCreate', component: () => import('@/views/WecomBotTriggerCreate.vue'), meta: { title: '创建企微机器人触发器' } },
        { path: 'triggers/:id/edit', name: 'TriggerEdit', component: () => import('@/views/TriggerEditor.vue'), meta: { title: '编辑触发器' }, props: true },
        // Notification channels
        { path: 'notifications', name: 'NotificationList', component: () => import('@/views/NotificationList.vue'), meta: { title: '通知管理' } },
        { path: 'notifications/create', name: 'NotificationCreate', component: () => import('@/views/NotificationEditor.vue'), meta: { title: '创建通知渠道' } },
        { path: 'notifications/:id/edit', name: 'NotificationEdit', component: () => import('@/views/NotificationEditor.vue'), meta: { title: '编辑通知渠道' }, props: true },
        // Resource directory - MCP Servers
        { path: 'resources/mcp-servers', name: 'McpServerList', component: () => import('@/views/McpServerList.vue'), meta: { title: 'MCP Server 管理' } },
        { path: 'resources/mcp-servers/create', name: 'McpServerCreate', component: () => import('@/views/McpServerEditor.vue'), meta: { title: '注册 MCP Server' } },
        { path: 'resources/mcp-servers/:id/edit', name: 'McpServerEdit', component: () => import('@/views/McpServerEditor.vue'), meta: { title: '编辑 MCP Server' }, props: true },
        // Resource directory - Knowledge Bases
        { path: 'resources/knowledge-bases', name: 'KnowledgeBaseList', component: () => import('@/views/KnowledgeBaseList.vue'), meta: { title: '知识库管理' } },
        { path: 'resources/knowledge-bases/create', name: 'KnowledgeBaseCreate', component: () => import('@/views/KnowledgeBaseEditor.vue'), meta: { title: '创建知识库' } },
        { path: 'resources/knowledge-bases/:id/edit', name: 'KnowledgeBaseEdit', component: () => import('@/views/KnowledgeBaseEditor.vue'), meta: { title: '编辑知识库' }, props: true },
        // Resource directory - Skills
        { path: 'resources/skills', name: 'SkillList', component: () => import('@/views/SkillList.vue'), meta: { title: 'Skill 管理' } },
        { path: 'resources/skills/create', name: 'SkillCreate', component: () => import('@/views/SkillEditor.vue'), meta: { title: '创建 Skill' } },
        { path: 'resources/skills/:id/edit', name: 'SkillEdit', component: () => import('@/views/SkillEditor.vue'), meta: { title: '编辑 Skill' }, props: true },
        // Project Registry
        { path: 'projects', name: 'ProjectList', component: () => import('@/views/ProjectList.vue'), meta: { title: '项目管理' } },
        { path: 'projects/create', name: 'ProjectCreate', component: () => import('@/views/ProjectEditor.vue'), meta: { title: '新建项目' } },
        { path: 'projects/:id/edit', name: 'ProjectEdit', component: () => import('@/views/ProjectEditor.vue'), meta: { title: '编辑项目' }, props: true },
        // Claude Settings
        { path: 'claude-settings', name: 'ClaudeSettingsList', component: () => import('@/views/ClaudeSettingsList.vue'), meta: { title: 'Claude Settings' } },
        { path: 'claude-settings/create', name: 'ClaudeSettingsCreate', component: () => import('@/views/ClaudeSettingsEditor.vue'), meta: { title: '新建 Claude Settings' } },
        { path: 'claude-settings/:id/edit', name: 'ClaudeSettingsEdit', component: () => import('@/views/ClaudeSettingsEditor.vue'), meta: { title: '编辑 Claude Settings' }, props: true },
        // Monitoring
        { path: 'monitor/traces', name: 'ExecutionTraceList', component: () => import('@/views/ExecutionTraceList.vue'), meta: { title: '执行追踪' } },
        { path: 'monitor/traces/:executionId', name: 'ExecutionTraceDetail', component: () => import('@/views/ExecutionTrace.vue'), meta: { title: '追踪详情' }, props: true },
        { path: 'monitor/chat-test', name: 'ChatTest', component: () => import('@/views/ChatTest.vue'), meta: { title: '对话测试' } },
        { path: 'monitor/chat-logs', name: 'ChatLogList', component: () => import('@/views/ChatLogList.vue'), meta: { title: '对话日志' } },
        // System settings
        { path: 'settings', name: 'SystemConfig', component: () => import('@/views/SystemConfig.vue'), meta: { title: '系统配置', requireAdmin: true } },
        { path: 'settings/llm-configs', name: 'LlmConfigList', component: () => import('@/views/LlmConfigList.vue'), meta: { title: 'LLM 配置', requireAdmin: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFound.vue') },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
