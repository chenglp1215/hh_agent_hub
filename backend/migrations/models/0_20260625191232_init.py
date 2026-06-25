from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "sys_configs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "config_key" VARCHAR(100) NOT NULL UNIQUE,
    "config_value" TEXT NOT NULL,
    "config_type" VARCHAR(20) NOT NULL DEFAULT 'string',
    "description" VARCHAR(200),
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "users" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "password_hash" VARCHAR(255) NOT NULL,
    "api_key" VARCHAR(64) NOT NULL UNIQUE,
    "role" VARCHAR(20) NOT NULL DEFAULT 'user',
    "email" VARCHAR(100),
    "avatar" VARCHAR(200),
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_login" TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "llm_configs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(50) NOT NULL UNIQUE,
    "provider" VARCHAR(20) NOT NULL DEFAULT 'openai',
    "model" VARCHAR(100) NOT NULL DEFAULT 'gpt-4o-mini',
    "api_key" VARCHAR(255),
    "base_url" VARCHAR(500),
    "temperature" REAL NOT NULL DEFAULT 0.3,
    "max_tokens" INT NOT NULL DEFAULT 4096,
    "description" VARCHAR(200),
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "agents" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(50) NOT NULL UNIQUE,
    "display_name" VARCHAR(100),
    "description" TEXT,
    "role" VARCHAR(20) NOT NULL,
    "agent_type" VARCHAR(20) NOT NULL DEFAULT 'local',
    "llm_config" JSON,
    "llm_config_id" INT,
    "http_config" JSON,
    "claudecode_config" JSON,
    "a2a_config" JSON,
    "reasonix_config" JSON,
    "system_prompt" TEXT,
    "mcp_servers" JSON NOT NULL,
    "skills" JSON NOT NULL,
    "custom_tools" JSON NOT NULL,
    "knowledge_base_ids" JSON NOT NULL,
    "supervisor_prompt_template" VARCHAR(30) NOT NULL DEFAULT 'free_route',
    "custom_prompt_override" TEXT,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "workflows" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT,
    "flow_type" VARCHAR(20) NOT NULL,
    "worker_agent_ids" JSON NOT NULL,
    "edges" JSON NOT NULL,
    "parallel_groups" JSON NOT NULL,
    "human_interrupts" JSON NOT NULL,
    "error_strategy" VARCHAR(20) NOT NULL DEFAULT 'fail_fast',
    "agent_timeout_seconds" INT NOT NULL DEFAULT 60,
    "workflow_timeout_seconds" INT NOT NULL DEFAULT 300,
    "max_retries" INT NOT NULL DEFAULT 2,
    "max_supervisor_rounds" INT NOT NULL DEFAULT 5,
    "status" VARCHAR(20) NOT NULL DEFAULT 'draft',
    "version" INT NOT NULL DEFAULT 1,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
    "supervisor_agent_id" INT REFERENCES "agents" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "apps" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT,
    "workflow_version" INT NOT NULL DEFAULT 1,
    "api_key" VARCHAR(64) NOT NULL UNIQUE,
    "rate_limit" INT NOT NULL DEFAULT 60,
    "enabled" INT NOT NULL DEFAULT 1,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
    "workflow_id" INT NOT NULL REFERENCES "workflows" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "sessions" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "user_id" VARCHAR(100),
    "messages" JSON NOT NULL,
    "thread_state" JSON,
    "workspace_path" VARCHAR(500),
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "expired_at" TIMESTAMP,
    "app_id" INT NOT NULL REFERENCES "apps" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "audit_logs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "action" VARCHAR(50) NOT NULL,
    "target_type" VARCHAR(50),
    "target_id" INT,
    "request_id" VARCHAR(36),
    "ip_address" VARCHAR(45),
    "details" JSON,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "mcp_server_registry" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL UNIQUE,
    "display_name" VARCHAR(100),
    "description" TEXT,
    "base_url" VARCHAR(500) NOT NULL,
    "headers" JSON NOT NULL,
    "timeout" INT NOT NULL DEFAULT 30,
    "single_endpoint" INT NOT NULL DEFAULT 0,
    "discovered_tools" JSON NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "last_checked_at" TIMESTAMP,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "agent_mcp_links" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "enabled_tools" JSON NOT NULL,
    "enabled" INT NOT NULL DEFAULT 1,
    "agent_id" INT NOT NULL REFERENCES "agents" ("id") ON DELETE CASCADE,
    "mcp_server_id" INT NOT NULL REFERENCES "mcp_server_registry" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_agent_mcp_l_agent_i_7e870b" UNIQUE ("agent_id", "mcp_server_id")
);
CREATE TABLE IF NOT EXISTS "knowledge_bases" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL UNIQUE,
    "display_name" VARCHAR(100),
    "description" TEXT,
    "kb_type" VARCHAR(20) NOT NULL DEFAULT 'file',
    "config" JSON,
    "document_count" INT NOT NULL DEFAULT 0,
    "embedding_model" VARCHAR(100),
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "agent_kb_links" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "agent_id" INT NOT NULL REFERENCES "agents" ("id") ON DELETE CASCADE,
    "kb_id" INT NOT NULL REFERENCES "knowledge_bases" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_agent_kb_li_agent_i_e28b2e" UNIQUE ("agent_id", "kb_id")
);
CREATE TABLE IF NOT EXISTS "content_blocks" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "source_file" VARCHAR(500) NOT NULL,
    "heading_path" VARCHAR(500),
    "body" TEXT NOT NULL,
    "token_count" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "kb_id" INT NOT NULL REFERENCES "knowledge_bases" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "skills_registry" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL UNIQUE,
    "display_name" VARCHAR(100),
    "description" TEXT,
    "skill_type" VARCHAR(20) NOT NULL DEFAULT 'prompt',
    "content" JSON,
    "category" VARCHAR(50),
    "tags" JSON NOT NULL,
    "version" INT NOT NULL DEFAULT 1,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "agent_skill_links" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "agent_id" INT NOT NULL REFERENCES "agents" ("id") ON DELETE CASCADE,
    "skill_id" INT NOT NULL REFERENCES "skills_registry" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_agent_skill_agent_i_5082ab" UNIQUE ("agent_id", "skill_id")
);
CREATE TABLE IF NOT EXISTS "project_registry" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL UNIQUE,
    "display_name" VARCHAR(100),
    "description" TEXT,
    "git_repo_url" VARCHAR(500) NOT NULL,
    "git_branch" VARCHAR(100) NOT NULL DEFAULT 'main',
    "git_auth_username" VARCHAR(100),
    "git_auth_token" VARCHAR(500),
    "clone_path" VARCHAR(500),
    "system_prompt" TEXT,
    "fix_timeout_minutes" INT NOT NULL DEFAULT 30,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "agent_project_links" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "agent_id" INT NOT NULL REFERENCES "agents" ("id") ON DELETE CASCADE,
    "project_id" INT NOT NULL REFERENCES "project_registry" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_agent_proje_agent_i_0d2581" UNIQUE ("agent_id", "project_id")
);
CREATE TABLE IF NOT EXISTS "claude_settings_registry" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL UNIQUE,
    "display_name" VARCHAR(100),
    "description" TEXT,
    "model" VARCHAR(100) NOT NULL DEFAULT 'claude-sonnet-4-6',
    "max_turns" INT NOT NULL DEFAULT 25,
    "permission_mode" VARCHAR(50) NOT NULL DEFAULT 'default',
    "settings_json" TEXT,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "agent_settings_links" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "agent_id" INT NOT NULL REFERENCES "agents" ("id") ON DELETE CASCADE,
    "settings_id" INT NOT NULL REFERENCES "claude_settings_registry" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_agent_setti_agent_i_7aa1cb" UNIQUE ("agent_id", "settings_id")
);
CREATE TABLE IF NOT EXISTS "chat_logs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "task_id" VARCHAR(36),
    "user_input" TEXT NOT NULL,
    "final_answer" TEXT,
    "duration_ms" INT,
    "status" VARCHAR(20) NOT NULL DEFAULT 'success',
    "error_message" TEXT,
    "agent_count" INT NOT NULL DEFAULT 0,
    "trace_summary" JSON,
    "prompt_tokens" INT NOT NULL DEFAULT 0,
    "completion_tokens" INT NOT NULL DEFAULT 0,
    "total_tokens" INT NOT NULL DEFAULT 0,
    "model_name" VARCHAR(100),
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "app_id" INT REFERENCES "apps" ("id") ON DELETE SET NULL,
    "session_id" VARCHAR(36) REFERENCES "sessions" ("id") ON DELETE SET NULL
) /* Chat 交互日志 — 记录每次 API 调用的完整信息 */;
CREATE INDEX IF NOT EXISTS "idx_chat_logs_task_id_cc3c2b" ON "chat_logs" ("task_id");
CREATE INDEX IF NOT EXISTS "idx_chat_logs_created_5441a3" ON "chat_logs" ("created_at");
CREATE TABLE IF NOT EXISTS "workflow_traces" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "execution_id" VARCHAR(36) NOT NULL UNIQUE,
    "status" VARCHAR(20) NOT NULL,
    "agent_count" INT NOT NULL DEFAULT 0,
    "total_duration_ms" INT,
    "error_agent" VARCHAR(100),
    "error_summary" TEXT,
    "trace_file_path" VARCHAR(500) NOT NULL,
    "started_at" TIMESTAMP,
    "completed_at" TIMESTAMP,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "app_id" INT REFERENCES "apps" ("id") ON DELETE SET NULL,
    "workflow_id" INT REFERENCES "workflows" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "notification_channels" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "channel_type" VARCHAR(20) NOT NULL DEFAULT 'wecom_webhook',
    "webhook_url" VARCHAR(500) NOT NULL,
    "enabled" INT NOT NULL DEFAULT 1,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "triggers" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT,
    "trigger_type" VARCHAR(20) NOT NULL,
    "interval_value" INT,
    "interval_unit" VARCHAR(10),
    "cron_expression" VARCHAR(100),
    "wecom_chat_type" VARCHAR(10),
    "wecom_chat_id" VARCHAR(100),
    "wecom_user_id" VARCHAR(100),
    "message" TEXT NOT NULL,
    "enabled" INT NOT NULL DEFAULT 1,
    "last_fired_at" TIMESTAMP,
    "next_fire_at" TIMESTAMP,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP,
    "app_id" INT NOT NULL REFERENCES "apps" ("id") ON DELETE CASCADE,
    "created_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
    "notification_id" INT REFERENCES "notification_channels" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "trigger_executions" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "session_id" VARCHAR(100) NOT NULL,
    "task_id" VARCHAR(36),
    "source" VARCHAR(10) NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'submitted',
    "error_message" TEXT,
    "duration_ms" INT,
    "notified" INT NOT NULL DEFAULT 0,
    "started_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP,
    "trigger_id" INT NOT NULL REFERENCES "triggers" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_trigger_exe_session_ca00db" ON "trigger_executions" ("session_id");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
