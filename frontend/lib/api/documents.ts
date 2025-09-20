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

  list = async (tenant_id?: string): Promise<any> => {
    return this.request(`/documents`)
  }

  upload = async (
    file: File,
    options: { folder_id?: string; title?: string; description?: string }
  ): Promise<any> => {
    const formData = new FormData()
    formData.append("file", file)
    if (options.folder_id) {
      formData.append("folder_id", options.folder_id)
    }
    if (options.title) {
      formData.append("title", options.title)
    }
    if (options.description) {
      formData.append("description", options.description)
    }
    return this.request(`/documents/upload`, {
      method: "POST",
      body: formData,
    })
  }

  uploadBatch = async (
    files: File[],
    options: { folder_id?: string }
  ): Promise<any> => {
    const formData = new FormData()
    files.forEach((file, index) => {
      formData.append("files", file)
    })
    if (options.folder_id) {
      formData.append("folder_id", options.folder_id)
    }
    return this.request(`/documents/upload/batch`, {
      method: "POST",
      body: formData,
    })
  }

  delete = async (document_id: string): Promise<void> => {
    return this.request(`/documents/${document_id}`, { method: "DELETE" })
  }

  createFolder = async (
    folder_name: string,
    parent_folder_id?: string,
    department_id?: string
  ): Promise<any> => {
    const formData = new FormData()
    formData.append("folder_name", folder_name)
    if (parent_folder_id) {
      formData.append("parent_folder_id", parent_folder_id)
    }
    if (department_id) {
      formData.append("department_id", department_id)
    }
    return this.request(`/documents/folders`, {
      method: "POST",
      body: formData,
    })
  }

  getAccessLevels = async (departmentId: string): Promise<string[]> => {
    return this.request(`/documents/departments/${departmentId}/access-levels`)
  }

  getDepartmentFolders = async (departmentId: string): Promise<any> => {
    return this.request(`/documents/departments/${departmentId}/folders`)
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

  deleteFolder = async (folder_id: string): Promise<void> => {
    return this.request(`/documents/folders/${folder_id}`, { method: "DELETE" })
  }

  updateFolder = async (
    folder_id: string,
    updates: { folder_name?: string; access_level?: "public" | "private" }
  ): Promise<any> => {
    return this.request(`/documents/folders/${folder_id}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    })
  }

  moveFolder = async (
    folder_id: string,
    target_parent_id: string
  ): Promise<any> => {
    return this.request(`/documents/folders/${folder_id}/move`, {
      method: "PUT",
      body: JSON.stringify({ target_parent_id }),
    })
  }

  updateDocument = async (
    document_id: string,
    updates: { title?: string; description?: string; access_level?: "public" | "private" }
  ): Promise<any> => {
    return this.request(`/documents/${document_id}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    })
  }

  moveDocument = async (
    document_id: string,
    target_folder_id?: string
  ): Promise<any> => {
    return this.request(`/documents/${document_id}/move`, {
      method: "PUT",
      body: JSON.stringify({ target_folder_id }),
    })
  }

  getFolderContents = async (folder_id: string): Promise<any> => {
    return this.request(`/documents/folders/${folder_id}`)
  }

  downloadDocument = async (document_id: string): Promise<Blob> => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null

    const response = await fetch(`${this.baseURL}/documents/${document_id}/download`, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    return response.blob()
  }

  getDocumentDetail = async (document_id: string): Promise<any> => {
    return this.request(`/documents/${document_id}`)
  }

  getCollections = async (department_name: string): Promise<any> => {
    return this.request(`/documents/collections?department_name=${encodeURIComponent(department_name)}`)
  }

  getPublicTree = async (folder_id?: string): Promise<any> => {
    const params = new URLSearchParams()
    if (folder_id) params.append("folder_id", folder_id)
    return this.request(`/documents/tree/public${params.toString() ? `?${params.toString()}` : ""}`)
  }

  getPrivateTree = async (folder_id?: string): Promise<any> => {
    const params = new URLSearchParams()
    if (folder_id) params.append("folder_id", folder_id)
    return this.request(`/documents/tree/private${params.toString() ? `?${params.toString()}` : ""}`)
  }

  getTreeFiltered = async (
    folder_id?: string,
    access_level?: "public" | "private"
  ): Promise<any> => {
    const params = new URLSearchParams()
    if (folder_id) params.append("folder_id", folder_id)
    if (access_level) params.append("access_level", access_level)
    return this.request(`/documents/tree${params.toString() ? `?${params.toString()}` : ""}`)
  }

  getDocumentsByDepartmentAndAccessLevel = async (
    departmentId: string,
    accessLevel: "public" | "private"
  ): Promise<any> => {
    return this.request(`/documents/departments/${departmentId}/access-level/${accessLevel}`)
  }

  getFolderContentsWithContext = async (folderId: string): Promise<any> => {
    return this.request(`/documents/folders/${folderId}/contents`)
  }

  getFolderDetails = async (folderId: string): Promise<any> => {
    return this.request(`/documents/folder/${folderId}`)
  }

  getFolders = async (folderId?: string): Promise<any> => {
    const params = new URLSearchParams()
    if (folderId) params.append("folder_id", folderId)
    return this.request(`/documents/folders${params.toString() ? `?${params.toString()}` : ""}`)
  }

  renameDocument = async (
    documentId: string,
    newName: string
  ): Promise<any> => {
    return this.request(`/documents/${documentId}/rename`, {
      method: "PUT",
      body: JSON.stringify({ new_name: newName }),
    })
  }

  // Rename folder
  renameFolder = async (
    folderId: string,
    newName: string
  ): Promise<any> => {
    return this.request(`/documents/folders/${folderId}/rename`, {
      method: "PUT",
      body: JSON.stringify({ new_name: newName }),
    })
  }
}

