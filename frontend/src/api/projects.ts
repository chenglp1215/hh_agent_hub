import client from './client'

export const projectsApi = {
  list: (params?: { status?: string; search?: string }) => client.get('/projects', { params }),
  get: (id: number) => client.get(`/projects/${id}`),
  create: (data: any) => client.post('/projects', data),
  update: (id: number, data: any) => client.put(`/projects/${id}`, data),
  delete: (id: number) => client.delete(`/projects/${id}`),
}
