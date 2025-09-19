import type {
  WorkflowAgent,
  TenantSettings,
  Department,
  Agent,
  Tool
} from "@/types"

interface WorkflowAgentConfigRequest {
  provider_name: string
  model_name: string
  model_configuration?: Record<string, any>
  max_iterations?: number
  timeout_seconds?: number
  confidence_threshold?: number
}

interface CreateDepartmentRequest {
  department_name: string
  description?: string
  agent_name: string
  agent_description: string
  provider_id: string
  model_id?: string 
  provider_config?: Record<string, any>
  tool_ids?: string[]
}

interface CreateAgentRequest {
  agent_name: string
  description: string
  department_id: string
  provider_id?: string
  model_id?: string
}

interface UpdateTenantSettingsRequest {
  tenant_name?: string
  description?: string
  timezone?: string
  locale?: string
  chatbot_name?: string
  logo_url?: string
}

export class TenantAdminAPI {
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

  // ==================== WORKFLOW AGENT ====================

  async getWorkflowAgent(): Promise<WorkflowAgent> {
    return this.request('/tenant-admin/workflow-agent')
  }

  async createOrUpdateWorkflowAgent(request: WorkflowAgentConfigRequest): Promise<WorkflowAgent> {
    return this.request('/tenant-admin/workflow-agent', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // ==================== TENANT SETTINGS ====================

  async getTenantSettings(): Promise<TenantSettings> {
    return this.request('/tenant-admin/settings')
  }

  async updateTenantSettings(request: UpdateTenantSettingsRequest): Promise<TenantSettings> {
    return this.request('/tenant-admin/settings', {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  // ==================== DEPARTMENTS ====================

  async listDepartments(): Promise<Department[]> {
    return this.request('/tenant-admin/departments')
  }

  async createDepartment(request: CreateDepartmentRequest): Promise<Department> {
    return this.request('/tenant-admin/departments', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getDepartment(departmentId: string): Promise<Department> {
    return this.request(`/tenant-admin/departments/${departmentId}`)
  }

  async updateDepartment(departmentId: string, request: CreateDepartmentRequest): Promise<Department> {
    return this.request(`/tenant-admin/departments/${departmentId}`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  async deleteDepartment(departmentId: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/tenant-admin/departments/${departmentId}`, {
      method: 'DELETE',
    })
  }

  // ==================== AGENTS ====================

  async listAgents(departmentId?: string): Promise<Agent[]> {
    const params = departmentId ? `?department_id=${departmentId}` : ''
    return this.request(`/tenant-admin/agents${params}`)
  }

  async createAgent(request: CreateAgentRequest): Promise<Agent> {
    return this.request('/tenant-admin/agents', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getAgent(agentId: string): Promise<Agent> {
    return this.request(`/tenant-admin/agents/${agentId}`)
  }

  async updateAgent(agentId: string, request: CreateAgentRequest): Promise<Agent> {
    return this.request(`/tenant-admin/agents/${agentId}`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  async deleteAgent(agentId: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/tenant-admin/agents/${agentId}`, {
      method: 'DELETE',
    })
  }

  // ==================== TOOLS ====================

  async listTenantTools(): Promise<Tool[]> {
    return this.request('/tenant-admin/tools')
  }

  async enableTenantTool(toolId: string, isEnabled: boolean = true): Promise<{ success: boolean; message: string }> {
    const params = `?is_enabled=${isEnabled}`
    return this.request(`/tenant-admin/tools/${toolId}/enable${params}`, {
      method: 'POST',
    })
  }

  async enableDepartmentTool(
    departmentId: string,
    toolId: string,
    isEnabled: boolean = true,
    accessLevelOverride?: string
  ): Promise<{ success: boolean; message: string }> {
    let params = `?is_enabled=${isEnabled}`
    if (accessLevelOverride) {
      params += `&access_level_override=${accessLevelOverride}`
    }
    return this.request(`/tenant-admin/departments/${departmentId}/tools/${toolId}/enable${params}`, {
      method: 'POST',
    })
  }

  // ==================== DYNAMIC DATA ====================

  async getDynamicData(): Promise<{
    providers: any[]
    tools: any[]
    timezones: any[]
    locales: any[]
  }> {
    return this.request('/tenant-admin/dynamic-data')
  }

  // ==================== PROVIDERS ====================

  async getProviderApiKeys(providerName: string): Promise<{ api_keys: string[] }> {
    return this.request(`/tenant-admin/providers/${providerName}/api-keys`)
  }

  async updateProviderApiKeys(
    providerName: string,
    apiKeys: string[]
  ): Promise<{ success: boolean; message: string }> {
    return this.request(`/tenant-admin/providers/${providerName}/api-keys`, {
      method: 'PUT',
      body: JSON.stringify({ api_keys: apiKeys }),
    })
  }
}
