import client from './client'

export const skillsApi = {
  list: (params?: any) => client.get('/skills', { params }),
  get: (id: number) => client.get(`/skills/${id}`),
  create: (data: any) => client.post('/skills', data),
  update: (id: number, data: any) => client.put(`/skills/${id}`, data),
  delete: (id: number) => client.delete(`/skills/${id}`),
}
