import client from './client'

export const workflowsApi = {
  list: (params?: any) => client.get('/workflows', { params }),
  get: (id: number) => client.get(`/workflows/${id}`),
  create: (data: any) => client.post('/workflows', data),
  update: (id: number, data: any) => client.put(`/workflows/${id}`, data),
  delete: (id: number) => client.delete(`/workflows/${id}`),
  publish: (id: number) => client.post(`/workflows/${id}/publish`),
  archive: (id: number) => client.post(`/workflows/${id}/archive`),
  validate: (id: number) => client.post(`/workflows/${id}/validate`),
  graph: (id: number) => client.get(`/workflows/${id}/graph`),
}
