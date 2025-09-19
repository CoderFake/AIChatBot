import type { Department } from "@/types"

export class DocumentsAPI {
  private baseURL: string

  constructor(baseURL: string = "/api/v1") {
    this.baseURL = baseURL
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<any> {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null

    const config = {
      ...options,
      headers: {
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
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

  list = async (tenant_id: string): Promise<{ documents: any[] }> => {
    return this.request(`/tenants/${tenant_id}/documents`)
  }

  upload = async (
    file: File,
    options: { collection_name: string; access_level: "public" | "private"; folder_id?: string }
  ): Promise<any> => {
    const formData = new FormData()
    formData.append("file", file)
    formData.append("collection_name", options.collection_name)
    formData.append("access_level", options.access_level)
    if (options.folder_id) {
      formData.append("folder_id", options.folder_id)
    }
    return this.request(`/documents/upload`, {
      method: "POST",
      body: formData,
    })
  }

  delete = async (document_id: string): Promise<void> => {
    return this.request(`/documents/${document_id}`, { method: "DELETE" })
  }

  createFolder = async (folder_name: string, parent_folder_id?: string): Promise<any> => {
    const formData = new FormData()
    formData.append("folder_name", folder_name)
    if (parent_folder_id) {
      formData.append("parent_folder_id", parent_folder_id)
    }
    return this.request(`/documents/folders`, {
      method: "POST",
      body: formData,
    })
  }

  getTree = async (
    access_level: "public" | "private" = "private",
    folder_id?: string
  ): Promise<any> => {
    const params = new URLSearchParams()
    if (folder_id) params.append("folder_id", folder_id)
    if (access_level) params.append("access_level", access_level)
    return this.request(`/documents/tree${params.toString() ? `?${params.toString()}` : ""}`)
  }
}

