export interface ClaudeCodeConfig {
  settings_json: string
  model: string
  max_turns: number
  work_dir: string
  permission_mode: 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan'
}

/** A2A 对端 Agent 配置 */
export interface A2AConfig {
  /** 对端 Agent Card 发现地址（完整的 agent-card.json URL） */
  agent_card_url: string
  /** 请求头，用于认证等 */
  headers: Record<string, string>
  /** 请求超时时间（秒），默认 30 */
  timeout: number
}
