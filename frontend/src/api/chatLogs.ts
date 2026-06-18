import client from './client'

export const chatLogsApi = {
  list: (params?: any) => client.get('/chat-logs', { params }),
  get: (id: number) => client.get(`/chat-logs/${id}`),
}
