class APIService {
  private baseURL: string

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1"
  }

  private async fetchAPI(endpoint: string, options: RequestInit = {}): Promise<any> {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.json()
  }

  setToken(token: string) {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token)
    }
  }

  chat = {
    createSession: async (title?: string, firstMessage?: string): Promise<{ session_id: string; title: string | null; created_at: string }> => {
      const body: any = {}
      if (title) body.title = title
      if (firstMessage) body.first_message = firstMessage
      return this.fetchAPI("/chat/create-session", {
        method: "POST",
        body: JSON.stringify(body),
      })
    },

    generateTitle: async (sessionId: string, firstMessage: string): Promise<{ title: string; session_id: string }> => {
      return this.fetchAPI("/chat/gen-title", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          first_message: firstMessage,
        }),
      })
    },

    getSessions: async (skip = 0, limit = 20): Promise<any> => {
      const query = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
      return this.fetchAPI(`/chat/sessions?${query.toString()}`)
    },

    getMessages: async (sessionId: string, skip = 0, limit = 50): Promise<any[]> => {
      const query = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
      return this.fetchAPI(`/chat/sessions/${sessionId}/messages?${query.toString()}`)
    },

    updateTitle: async (sessionId: string, title: string): Promise<{ session_id: string; title: string; updated_at: string }> => {
      return this.fetchAPI(`/chat/sessions/${sessionId}/title`, {
        method: "PUT",
        body: JSON.stringify({ title }),
      })
    },

    deleteSession: async (sessionId: string): Promise<{ success: boolean; message: string }> => {
      return this.fetchAPI(`/chat/sessions/${sessionId}`, {
        method: "DELETE",
      })
    },


    sendMessageStream: async (
      sessionId: string,
      query: string,
      onChunk: (chunk: string) => void,
      onComplete: () => void,
      onError: (error: Error) => void,
      visibility?: "public" | "private" | "both",
    ): Promise<void> => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
        const response = await fetch(`${this.baseURL}/chat/query`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token && { Authorization: `Bearer ${token}` }),
          },
          body: JSON.stringify({
            query,
            session_id: sessionId,
            access_scope: visibility ? { visibility } : { visibility: "private" },
          }),
        })

        if (!response.body) {
          throw new Error("No response body")
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n\n")
          for (const line of lines.slice(0, -1)) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6).trim()
              if (data === "[DONE]") {
                onComplete()
                return
              }
              onChunk(data)
            }
          }
          buffer = lines[lines.length - 1]
        }
        onComplete()
      } catch (error) {
        onError(error as Error)
      }
    },
  }

  documents = {
    getDocument: async (documentId: string): Promise<any> => {
      return this.fetchAPI(`/documents/${documentId}`)
    },
  }

  tenants = {
    getDetail: async (tenantId: string): Promise<any> => {
      return this.fetchAPI(`/tenants/${tenantId}`)
    },

    getTenant: async (tenantId: string): Promise<any> => {
      return this.tenants.getDetail(tenantId)
    },

    getAll: async (): Promise<any[]> => {
      return this.fetchAPI("/tenants")
    },
  }
}

export const apiService = new APIService()
export const api = apiService
