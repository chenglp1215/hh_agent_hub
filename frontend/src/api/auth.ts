import client from './client'

export const authApi = {
  login: (data: { username: string; password: string }) => client.post('/auth/login', data),
  register: (data: { username: string; password: string; email?: string }) => client.post('/auth/register', data),
  refresh: () => client.post('/auth/refresh'),
  me: () => client.get('/auth/me'),
}
