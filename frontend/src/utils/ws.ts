export function createWSConnection(
  executionId: string,
  onEvent: (event: any) => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(
    `${protocol}//${window.location.host}/api/v1/ws/execution/${executionId}/live`
  )

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      onEvent(data)
    } catch {
      // ignore malformed messages
    }
  }
  ws.onclose = () => {}
  ws.onerror = () => {}
  return ws
}
