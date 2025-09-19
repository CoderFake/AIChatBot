export class TenantSettingsAPI {
  private baseURL: string

  constructor(baseURL: string = "/api/v1/tenant-admin") {
    if (!baseURL.includes("/tenant-admin")) {
      this.baseURL = `${baseURL}/tenant-admin`
    } else {
      this.baseURL = baseURL
    }
  }

  private async request(endpoint: string, options: RequestInit = {}, customBaseURL?: string): Promise<any> {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const config: RequestInit = {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...(options.headers || {}),
      },
    }

    const baseURL = customBaseURL || this.baseURL
    const response = await fetch(`${baseURL}${endpoint}`, config)

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(errorText || `HTTP ${response.status}`)
    }

    const contentType = response.headers.get("content-type")
    if (contentType && contentType.includes("application/json")) {
      return response.json()
    }
    return response.text()
  }

  // Settings management
  getSettings = async (): Promise<any> => {
    return await this.request("/settings")
  }

  updateSettings = async (settings: any): Promise<any> => {
    return await this.request("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    })
  }

  getWorkflowAgent = async (): Promise<any> => {
    return await this.request("/workflow-agent")
  }

  updateWorkflowAgent = async (config: any): Promise<any> => {
    return await this.request("/workflow-agent", {
      method: "POST",
      body: JSON.stringify(config),
    })
  }

  getDynamicData = async (): Promise<any> => {
    return await this.request("/dynamic-data")
  }

  getProviderApiKeys = async (providerName: string): Promise<any> => {
    return await this.request(`/providers/${providerName}/api-keys`)
  }

  updateProviderApiKeys = async (data: { provider_name: string; api_keys: string[] }): Promise<any> => {
    return await this.request(`/providers/${data.provider_name}/api-keys`, {
      method: "PUT",
      body: JSON.stringify({ api_keys: data.api_keys }),
    })
  }

  getTimezones = async (): Promise<any> => {
    return await this.request("/timezones", {}, "/api/v1")
  }

  getLocales = async (): Promise<any> => {
    return await this.request("/locales", {}, "/api/v1")
  }

  getProviders = async (): Promise<any> => {
    return await this.request("/", {}, "/api/v1/tenant-admin/providers")
  }

  getProviderModels = async (providerId: string): Promise<any> => {
    return await this.request(`/providers/${providerId}/models`, {}, "/api/v1/tenant-admin")
  }
}
