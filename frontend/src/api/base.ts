import axios, { AxiosError } from 'axios'
import { useAuthStore } from '@/store'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown,
  ) {
    super(message)
  }
}

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
})

// Attach JWT from store on every request.
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401: clear auth and redirect to /login.
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    const message =
      (error.response?.data as { message?: string })?.message ??
      error.message ??
      'Unknown error'
    throw new ApiError(error.response?.status ?? 0, message, error.response?.data)
  },
)

export default api
