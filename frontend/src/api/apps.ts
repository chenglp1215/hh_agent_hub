import client from './client'

export const appsApi = {
  list: () => client.get('/apps'),
  get: (id: number) => client.get(`/apps/${id}`),
  create: (data: any) => client.post('/apps', data),
  update: (id: number, data: any) => client.put(`/apps/${id}`, data),
  delete: (id: number) => client.delete(`/apps/${id}`),
  rotateKey: (id: number) => client.post(`/apps/${id}/rotate-key`),
  stats: (id: number) => client.get(`/apps/${id}/stats`),
}
