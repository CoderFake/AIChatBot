import type { Tenant, PublicTenant, CreateTenantRequest, UpdateTenantRequest, UpdateTenantResponse, PaginatedResponse } from "@/types"

interface ListParams {
  page?: number
  limit?: number
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  is_active?: boolean
}

export class TenantsAPI {
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

  list = async (params: ListParams = {}): Promise<PaginatedResponse<Tenant>> => {
    const query = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          query.append(key, value.toString())
        }
      })
    }
    return this.request(`/tenants${query.toString() ? `?${query.toString()}` : ''}`)
  }

  create = async (data: CreateTenantRequest): Promise<Tenant> => {
    return this.request('/tenants', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  update = async (id: string, data: UpdateTenantRequest): Promise<UpdateTenantResponse> => {
    return this.request(`/tenants/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  delete = async (id: string): Promise<void> => {
    return this.request(`/tenants/${id}`, {
      method: 'DELETE',
    })
  }

  getDetail = async (id: string): Promise<Tenant> => {
    return this.request(`/tenants/${id}`)
  }

  getPublicInfo = async (id: string): Promise<{ id: string, tenant_name: string, locale: string, is_active: boolean, description?: string, sub_domain?: string, logo_url?: string, primary_color?: string }> => {
    return this.request(`/tenants/${id}/public-info`)
  }

  getTimezones = async (): Promise<any> => {
    return this.request('/others/timezones')
  }

  getLocales = async (): Promise<any> => {
    return this.request('/others/locales')
  }

  getAvailableTools = async (): Promise<{ tools: any[] }> => {
    return this.request('/tools/available')
  }

  getAvailableProviders = async (): Promise<{ providers: any[] }> => {
    return this.request('/providers/available')
  }

  getTenantProviders = async (tenantId: string): Promise<{ providers: any[] }> => {
    return this.request(`/providers/tenants/${tenantId}`)
  }

  getTenantTools = async (tenantId: string): Promise<{ tools: any[] }> => {
    return this.request(`/tools/tenants/${tenantId}`)
  }


  listDepartments = async (tenantId: string): Promise<any[]> => {
    return this.request('/tenant-admin/departments')
  }

  inviteDepartmentAdmins = async (departmentId: string, emails: string[]): Promise<{ success: boolean; message: string; invite_links: string[] }> => {
    return this.request('/tenants/invite-department-admins', {
      method: 'POST',
      body: JSON.stringify({ department_id: departmentId, emails }),
    })
  }

  inviteDepartmentManagers = async (departmentId: string, emails: string[]): Promise<{ success: boolean; message: string; invite_links: string[] }> => {
    return this.request('/tenants/invite-department-managers', {
      method: 'POST',
      body: JSON.stringify({ department_id: departmentId, emails }),
    })
  }

  inviteUsers = async (departmentId: string, emails: string[]): Promise<{ success: boolean; message: string; invite_links: string[] }> => {
    return this.request('/tenants/invite-users', {
      method: 'POST',
      body: JSON.stringify({ department_id: departmentId, emails }),
    })
  }

  configureProvider = async (
    tenantId: string,
    data: { provider_name: string; model_name: string; api_keys: string[]; provider_model_config?: Record<string, any> }
  ): Promise<any> => {
    return this.request(`/tenants/${tenantId}/configure-provider`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  setupWorkflowAgent = async (
    tenantId: string,
    data: { provider_name: string; model_name: string; provider_model_config?: Record<string, any> }
  ): Promise<any> => {
    return this.request(`/tenants/${tenantId}/setup-workflow-agent`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  enableTools = async (tenantId: string, toolIds: string[]): Promise<any> => {
    return this.request(`/tenants/${tenantId}/enable-tools`, {
      method: 'POST',
      body: JSON.stringify({ tool_ids: toolIds }),
    })
  }

  completeSetup = async (
    data: { tenant_id: string; provider_name: string; model_name: string; api_keys: string[]; provider_model_config?: Record<string, any> }
  ): Promise<any> => {
    return this.request('/tenants/complete-setup', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
}
