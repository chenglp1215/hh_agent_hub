import client from './client'

export const knowledgeBasesApi = {
  list: () => client.get('/knowledge-bases'),
  get: (id: number) => client.get(`/knowledge-bases/${id}`),
  create: (data: any) => client.post('/knowledge-bases', data),
  update: (id: number, data: any) => client.put(`/knowledge-bases/${id}`, data),
  delete: (id: number) => client.delete(`/knowledge-bases/${id}`),
  sync: (id: number) => client.post(`/knowledge-bases/${id}/sync`),
  documents: (id: number) => client.get(`/knowledge-bases/${id}/documents`),
}
