import client from './client'

export const claudeSettingsApi = {
  list: (params?: { search?: string }) => client.get('/claude-settings', { params }),
  get: (id: number) => client.get(`/claude-settings/${id}`),
  create: (data: any) => client.post('/claude-settings', data),
  update: (id: number, data: any) => client.put(`/claude-settings/${id}`, data),
  delete: (id: number) => client.delete(`/claude-settings/${id}`),
}
