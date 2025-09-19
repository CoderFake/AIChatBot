import type {
  LoginRequest,
  LoginResponse,
  RefreshTokenRequest,
  RefreshTokenResponse,
  UserProfileResponse,
  InviteTokenValidationResponse
} from "@/types/auth"

interface InviteResponse {
  links: string[]
}

interface OperationResult {
  success: boolean
  detail: string
}

export class AuthAPI {
  private baseURL: string

  constructor(baseURL: string = "/api/v1") {
    this.baseURL = baseURL
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<any> {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null

    const config = {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    }
    const response = await fetch(`${this.baseURL}${endpoint}`, config)

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorData.message || errorMessage
      } catch {
        errorMessage = response.statusText || errorMessage
      }
      throw new Error(errorMessage)
    }

    const contentType = response.headers.get("content-type")
    if (contentType && contentType.includes("application/json")) {
      return response.json()
    }

    return response.text()
  }

  login = async (data: LoginRequest): Promise<LoginResponse> => {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  logout = async (): Promise<void> => {
    return this.request('/auth/logout', {
      method: 'POST',
    })
  }

  refreshToken = async (refreshToken: string): Promise<RefreshTokenResponse> => {
    return this.request('/auth/refresh-token', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
      headers: {
        "Content-Type": "application/json",
      },
    })
  }

  getProfile = async (): Promise<UserProfileResponse> => {
    return this.request('/auth/me')
  }

  requestPasswordReset = async (email: string, tenantId?: string): Promise<void> => {
    return this.request('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ username_or_email: email, tenant_id: tenantId }),
    })
  }

  resetPassword = async (token: string, newPassword: string): Promise<void> => {
    return this.request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    })
  }

  maintainerInvite = async (tenantId: string, emails: string[]): Promise<InviteResponse> => {
    const response = await this.request('/auth/maintainer/invite', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: tenantId,
        emails: emails
      }),
    })
    return response
  }

  validateInviteToken = async (token: string): Promise<InviteTokenValidationResponse> => {

    const response = await this.request('/auth/validate-invite-token', {
      method: 'POST',
      body: JSON.stringify({ token }),
    })

    return response
  }

  acceptInvite = async (token: string, newPassword: string): Promise<OperationResult> => {
    const result = await this.request('/auth/accept-invite', {
      method: 'POST',
      body: JSON.stringify({
        token: token,
        new_password: newPassword
      }),
    })

    return result
  }

  forgotPassword = async (usernameOrEmail: string): Promise<OperationResult> => {
    return this.request('/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ username_or_email: usernameOrEmail }),
    })
  }
}
