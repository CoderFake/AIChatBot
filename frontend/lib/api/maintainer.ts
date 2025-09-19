import type { AxiosInstance } from "axios"

// ==================== MAINTAINER API TYPES ====================

interface CreateToolRequest {
  tool_name: string
  description: string
  tool_type: string
  config_schema?: Record<string, any>
  is_system?: boolean
}

interface UpdateToolRequest {
  tool_name?: string
  description?: string
  tool_type?: string
  config_schema?: Record<string, any>
  is_enabled?: boolean
}

interface CreateAgentRequest {
  agent_name: string
  provider_id: string
  model_name: string
  description?: string
  config?: Record<string, any>
}

interface UpdateAgentRequest {
  agent_name?: string
  provider_id?: string
  model_name?: string
  description?: string
  config?: Record<string, any>
}

interface ToolConfigRequest {
  is_enabled: boolean
  config_data?: Record<string, any>
}

interface InviteResponse {
  links: string[]
}

interface InviteRequest {
  tenant_id: string
  emails: string[]
}

// ==================== MAINTAINER API CLASS ====================

export class MaintainerAPI {
  constructor(private client: AxiosInstance) {}

  // ==================== TOOL MANAGEMENT ====================

  createTool = async (data: CreateToolRequest): Promise<{ tool: any; status: string }> => {
    const response = await this.client.post('/tools/maintainer', data)
    return response.data
  }

  updateTool = async (toolId: string, data: UpdateToolRequest): Promise<{ status: string; tool_id: string }> => {
    const response = await this.client.put(`/tools/maintainer/${toolId}`, data)
    return response.data
  }

  deleteTool = async (toolId: string): Promise<{ status: string; tool_id: string; message: string }> => {
    const response = await this.client.delete(`/tools/maintainer/${toolId}`)
    return response.data
  }

  listAllTools = async (): Promise<{ tools: any[]; total: number }> => {
    const response = await this.client.get('/tools/maintainer/all')
    return response.data
  }

  enableToolForTenant = async (toolId: string, tenantId: string, data: ToolConfigRequest): Promise<{ status: string; tool_id: string; tenant_id: string }> => {
    const response = await this.client.post(`/tools/maintainer/${toolId}/tenants/${tenantId}/enable`, data)
    return response.data
  }

  removeToolFromTenant = async (toolId: string, tenantId: string): Promise<{ status: string; tool_id: string; tenant_id: string }> => {
    const response = await this.client.delete(`/tools/maintainer/${toolId}/tenants/${tenantId}`)
    return response.data
  }

  // ==================== AGENT MANAGEMENT ====================

  listAllAgents = async (): Promise<{ agents: any[]; total: number }> => {
    const response = await this.client.get('/agents')
    return response.data
  }

  createAgent = async (data: CreateAgentRequest): Promise<{ agent: any }> => {
    const response = await this.client.post('/agents', data)
    return response.data
  }

  updateAgent = async (agentId: string, data: UpdateAgentRequest): Promise<{ success: boolean; message: string }> => {
    const response = await this.client.put(`/agents/${agentId}`, data)
    return response.data
  }

  deleteAgent = async (agentId: string): Promise<{ success: boolean; message: string }> => {
    const response = await this.client.delete(`/agents/${agentId}`)
    return response.data
  }

  assignAgentToTenant = async (agentId: string, tenantId: string): Promise<{ success: boolean; message: string }> => {
    const response = await this.client.post(`/agents/${agentId}/tenants/${tenantId}`)
    return response.data
  }

  removeAgentFromTenant = async (agentId: string, tenantId: string): Promise<{ success: boolean; message: string }> => {
    const response = await this.client.delete(`/agents/${agentId}/tenants/${tenantId}`)
    return response.data
  }

  // ==================== INVITE MANAGEMENT ====================

  inviteAdmins = async (data: InviteRequest): Promise<InviteResponse> => {
    const response = await this.client.post('/auth/maintainer/invite', data)
    return response.data
  }

  acceptInvite = async (token: string, newPassword: string): Promise<{ success: boolean; message: string }> => {
    const response = await this.client.post('/auth/invite/accept', { token, new_password: newPassword })
    return response.data
  }

  // ==================== PROVIDER MANAGEMENT ====================

  listProviders = async (): Promise<{ providers: any[] }> => {
    const response = await this.client.get('/providers')
    return response.data
  }

  listProviderModels = async (providerId: string): Promise<{ models: any[] }> => {
    const response = await this.client.get(`/providers/${providerId}/models`)
    return response.data
  }

  // ==================== SYSTEM HEALTH ====================

  getSystemStats = async (): Promise<{
    total_tenants: number
    total_users: number
    total_agents: number
    total_tools: number
    active_sessions: number
    system_health: 'healthy' | 'warning' | 'critical'
  }> => {
    const response = await this.client.get('/maintainer/stats')
    return response.data
  }

  // ==================== AUDIT LOGS ====================

  getAuditLogs = async (params?: {
    tenant_id?: string
    user_id?: string
    action?: string
    limit?: number
    offset?: number
  }): Promise<{ logs: any[]; total: number }> => {
    const response = await this.client.get('/maintainer/audit-logs', { params })
    return response.data
  }
}
