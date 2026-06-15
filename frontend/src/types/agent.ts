export interface ClaudeCodeConfig {
  settings_json: string
  model: string
  max_turns: number
  work_dir: string
  permission_mode: 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan'
}
