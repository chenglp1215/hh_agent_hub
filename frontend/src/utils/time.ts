/**
 * 格式化时间为北京时间 (Asia/Shanghai, UTC+8)
 *
 * 后端 API 返回 ISO 8601 格式时间字符串（带 +08:00 后缀），
 * 此函数统一解析并格式化为 "YYYY-MM-DD HH:mm:ss" 显示。
 */

export function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  // 使用 Asia/Shanghai 时区格式化
  return d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).replace(/\//g, '-')
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
