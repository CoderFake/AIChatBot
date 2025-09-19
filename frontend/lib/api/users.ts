import type { User, PaginatedResponse, InviteUsersRequest } from "@/types"

interface UsersListParams {
  page?: number
  limit?: number
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  tenant_id?: string
}

export class UsersAPI {
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

  list = async (params: UsersListParams = {}): Promise<PaginatedResponse<User>> => {
    const query = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          query.append(key, value.toString())
        }
      })
    }
    return this.request(`/users${query.toString() ? `?${query.toString()}` : ''}`)
  }

  inviteUsers = async (data: InviteUsersRequest): Promise<void> => {
    return this.request('/users/invite', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  updatePermissions = async (user_id: string, permissions: string[]): Promise<void> => {
    return this.request(`/users/${user_id}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({ permissions }),
    })
  }
}
