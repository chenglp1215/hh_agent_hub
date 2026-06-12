import client from './client'

export const llmConfigsApi = {
  list: () => client.get('/llm-configs'),
  create: (data: any) => client.post('/llm-configs', data),
  update: (id: number, data: any) => client.put(`/llm-configs/${id}`, data),
  delete: (id: number) => client.delete(`/llm-configs/${id}`),
}
