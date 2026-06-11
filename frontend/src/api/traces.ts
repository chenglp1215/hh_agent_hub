import client from './client'

export const tracesApi = {
  list: (params?: any) => client.get('/traces', { params }),
  get: (executionId: string) => client.get(`/traces/${executionId}`),
}
