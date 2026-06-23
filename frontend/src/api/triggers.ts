import client from './client'

export const triggersApi = {
  list: () => client.get('/triggers'),
  get: (id: number) => client.get(`/triggers/${id}`),
  create: (data: any) => client.post('/triggers', data),
  update: (id: number, data: any) => client.put(`/triggers/${id}`, data),
  delete: (id: number) => client.delete(`/triggers/${id}`),
  execute: (id: number) => client.post(`/triggers/${id}/execute`),
}
