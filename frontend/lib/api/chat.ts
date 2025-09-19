interface ChatAPISession {
  session_id: string;
  title: string | null;
  created_at: string;
}

interface ChatAPITitleUpdate {
  session_id: string;
  title: string;
  updated_at: string;
}

interface ChatAPIDeleteResponse {
  success: boolean;
  message: string;
}

export class ChatAPI {
  private baseURL: string

  constructor(baseURL: string = "/api/v1") {
    this.baseURL = baseURL
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<any> {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const config: RequestInit = {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...(options.headers || {}),
      },
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, config)

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

  createSession = async (title?: string, firstMessage?: string): Promise<ChatAPISession> => {
    const body: any = {}
    if (title) body.title = title
    if (firstMessage) body.first_message = firstMessage

    return this.request("/chat/create-session", {
      method: "POST",
      body: JSON.stringify(body),
    })
  }

  generateTitle = async (sessionId: string, firstMessage: string): Promise<{ title: string; session_id: string }> => {
    return this.request("/chat/gen-title", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        first_message: firstMessage,
      }),
    })
  }

  getSessions = async (skip = 0, limit = 20): Promise<any> => {
    const query = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
    return this.request(`/chat/sessions?${query.toString()}`)
  }

  getMessages = async (sessionId: string, skip = 0, limit = 50): Promise<any[]> => {
    const query = new URLSearchParams({ skip: skip.toString(), limit: limit.toString() })
    return this.request(`/chat/sessions/${sessionId}/messages?${query.toString()}`)
  }

  updateTitle = async (sessionId: string, title: string): Promise<ChatAPITitleUpdate> => {
    return this.request(`/chat/sessions/${sessionId}/title`, {
      method: "PUT",
      body: JSON.stringify({ title }),
    })
  }

  deleteSession = async (sessionId: string): Promise<ChatAPIDeleteResponse> => {
    return this.request(`/chat/sessions/${sessionId}`, {
      method: "DELETE",
    })
  }

  sendMessageStream = async (
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

      if (!response.ok) {
        // Handle authentication errors
        if (response.status === 401) {
          const errorText = await response.text()
          let errorMessage = "Authentication failed"

          try {
            const errorData = JSON.parse(errorText)
            errorMessage = errorData.error?.message || errorMessage
          } catch {
            if (errorText) errorMessage = errorText
          }

          const authError = new Error(`Authentication Error: ${errorMessage}`)
          ;(authError as any).statusCode = 401
          ;(authError as any).isAuthError = true
          throw authError
        }

        // Handle other HTTP errors
        const errorText = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`)
      }

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
        const lines = buffer.split("\n")
        for (const line of lines.slice(0, -1)) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6)
            onChunk(data)
          }
        }
        buffer = lines[lines.length - 1]
      }
      onComplete()
    } catch (error) {
      onError(error as Error)
    }
  }
}
