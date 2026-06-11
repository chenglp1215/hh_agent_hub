import client from './client'

export const mcpServersApi = {
  list: () => client.get('/mcp-servers'),
  get: (id: number) => client.get(`/mcp-servers/${id}`),
  create: (data: any) => client.post('/mcp-servers', data),
  update: (id: number, data: any) => client.put(`/mcp-servers/${id}`, data),
  delete: (id: number) => client.delete(`/mcp-servers/${id}`),
  discover: (id: number) => client.post(`/mcp-servers/${id}/discover`),
  test: (id: number) => client.post(`/mcp-servers/${id}/test`),
}
