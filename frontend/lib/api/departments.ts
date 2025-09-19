import type { Department } from "@/types"

interface ListParams {
  page?: number
  limit?: number
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export class DepartmentsAPI {
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

  list = async (tenant_id: string, params: ListParams = {}): Promise<Department[]> => {
    const query = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          query.append(key, value.toString())
        }
      })
    }
    return this.request(`/tenant-admin/departments${query.toString() ? `?${query.toString()}` : ''}`)
  }

  create = async (data: {
    department_name: string
    description?: string
    agent_name: string
    agent_description: string
    provider_id: string
    model_name?: string
    provider_config?: Record<string, any>
    tool_ids?: string[]
  }): Promise<Department> => {
    return this.request('/tenant-admin/departments', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  update = async (id: string, data: Partial<Department>): Promise<Department> => {
    return this.request(`/tenant-admin/departments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  delete = async (id: string): Promise<void> => {
    return this.request(`/tenant-admin/departments/${id}`, {
      method: 'DELETE',
    })
  }
}
