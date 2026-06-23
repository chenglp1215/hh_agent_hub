import client from './client'

export const notificationsApi = {
  list: () => client.get('/notifications'),
  get: (id: number) => client.get(`/notifications/${id}`),
  create: (data: any) => client.post('/notifications', data),
  update: (id: number, data: any) => client.put(`/notifications/${id}`, data),
  delete: (id: number) => client.delete(`/notifications/${id}`),
}
