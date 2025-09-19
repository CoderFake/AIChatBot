import type { RefreshTokenResponse } from "@/types/auth"

export class APIInterceptor {
  private baseURL: string
  private refreshPromise: Promise<RefreshTokenResponse> | null = null

  constructor(baseURL: string = "/api/v1") {
    this.baseURL = baseURL
  }

  setupInterceptors() {
    if (typeof window === 'undefined') return

    const originalFetch = window.fetch

    window.fetch = async (...args: Parameters<typeof fetch>) => {
      const [url, options = {}] = args

      const token = localStorage.getItem("access_token")
      if (token && !(options.headers as any)?.['Authorization']) {
        options.headers = {
          ...(options.headers as any),
          'Authorization': `Bearer ${token}`
        }
      }

      const response = await originalFetch(url, options)

      if (response.status === 401 && !url.toString().includes('/auth/refresh-token')) {
        const currentPath = window.location.pathname
        const refreshToken = localStorage.getItem("refresh_token")

        if (refreshToken) {
          try {
            if (!this.refreshPromise) {
              this.refreshPromise = this.refreshAccessToken(refreshToken)
            }

            const refreshResponse = await this.refreshPromise
            this.refreshPromise = null

            localStorage.setItem("access_token", refreshResponse.access_token)

            if (refreshResponse.refresh_token) {
              localStorage.setItem("refresh_token", refreshResponse.refresh_token)
            }

            // Retry the original request with new token
            const newOptions = {
              ...options,
              headers: {
                ...(options.headers as any),
                'Authorization': `Bearer ${refreshResponse.access_token}`
              }
            }

            return originalFetch(url, newOptions)
          } catch (refreshError) {
            console.error("Token refresh failed:", refreshError)
            this.refreshPromise = null
            this.clearTokens()
            if (!currentPath.includes('/login')) {
              const loginPath = this.getCorrectLoginPath(currentPath)
              window.location.href = loginPath
            }
          }
        } else {
          this.clearTokens()
          if (!currentPath.includes('/login')) {
            const loginPath = this.getCorrectLoginPath(currentPath)
            window.location.href = loginPath
          }
        }
      }

      return response
    }
  }

  private async refreshAccessToken(refreshToken: string): Promise<RefreshTokenResponse> {
    const response = await fetch(`${this.baseURL}/auth/refresh-token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      throw new Error('Token refresh failed')
    }

    return response.json()
  }

  private getCorrectLoginPath = (currentPath: string): string => {
    if (currentPath.startsWith('/system-admin') || currentPath === '/') {
      return '/system-admin/login'
    }

    const tenantMatch = currentPath.match(/^\/([^\/]+)/)
    if (tenantMatch && tenantMatch[1] && tenantMatch[1] !== 'system-admin') {
      return `/${tenantMatch[1]}/login`
    }

    return '/system-admin/login'
  }

  private clearTokens() {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
  }

  setToken(token: string) {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token)
    }
  }

  removeToken() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
    }
  }
}
