import client from './client'

export const reasonixSettingsApi = {
  list: (params?: { search?: string }) => client.get('/reasonix-settings', { params }),
  get: (id: number) => client.get(`/reasonix-settings/${id}`),
  create: (data: any) => client.post('/reasonix-settings', data),
  update: (id: number, data: any) => client.put(`/reasonix-settings/${id}`, data),
  delete: (id: number) => client.delete(`/reasonix-settings/${id}`),
}
