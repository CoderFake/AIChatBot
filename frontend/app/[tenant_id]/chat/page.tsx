"use client"

import type React from "react"
import { useTranslation } from "react-i18next"
import { useState, useRef, useEffect } from "react"
import {
  Send,
  Plus,
  Search,
  Settings,
  MessageCircle,
  ThumbsUp,
  ThumbsDown,
  Copy,
  MoreHorizontal,
  RotateCcw,
  ArrowLeft,
  Globe,
  Lock,
  Users,
  LogOut,
  User,
  ChevronDown
} from "lucide-react"
import { useTenant } from "@/lib/tenant-context"
import { useAuth, getCorrectLoginPath } from "@/lib/auth-context"
import { RouteGuard } from "@/components/auth/route-guard"
import { DocumentPreview } from "@/components/chat/document-preview"
import { StreamingMessage } from "@/components/chat/streaming-message"
import { apiService } from "@/lib/api"
import { ChatAPI } from "@/lib/api/chat"
import { Button } from "@/components/ui/button"
import { useTenantSettings } from "@/lib/tenant-context"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from "@/components/ui/dropdown-menu"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"

interface Message {
  id: string
  content: string
  isUser: boolean
  timestamp: Date
  query?: string
  documentId?: string
  documentUrl?: string
  documentType?: string
  documentTitle?: string
  isStreaming?: boolean
  planningData?: any
  executionData?: any
  progress?: number
  status?: string
}

export default function ChatPage() {
  const { t } = useTranslation()
  const { tenant } = useTenant()
  const { user, logout } = useAuth()
  const { getLogoUrl, getBotName } = useTenantSettings()

  const logoUrl = getLogoUrl()
  const chatbotName = getBotName()
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [documentPreview, setDocumentPreview] = useState<{
    isOpen: boolean
    documentId: string
    url: string
    title?: string
  }>({
    isOpen: false,
    documentId: "",
    url: "",
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<any[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [scope, setScope] = useState<"private" | "public" | "both">("private")
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [sessionToDelete, setSessionToDelete] = useState<{ id: string; title: string } | null>(null)
  const [editingSession, setEditingSession] = useState<{ id: string; title: string } | null>(null)
  const [editTitleValue, setEditTitleValue] = useState("")
  const [currentPlanningData, setCurrentPlanningData] = useState<any>(null)
  const [streamBuffer, setStreamBuffer] = useState<Record<string, string>>({})
  const isManager = user && ["DEPT_MANAGER", "DEPT_ADMIN", "TENANT_ADMIN", "ADMIN", "MAINTAINER"].includes(user.role)
  const isDeptManager = user && user.role === "DEPT_MANAGER"

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const handleGoToAdmin = () => {
    if (user?.tenant_id) {
      window.location.href = `/${user.tenant_id}/admin`
    }
  }

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      // Logout failed
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const loadMessages = async (sessionId: string) => {
    try {
      const response: any = await apiService.chat.getMessages(sessionId)
      const data = response.messages || response || []
      const msgs: Message[] = []

      data.forEach((m: any) => {
        if (m.role === "assistant" && m.query) {
          // Tạo user message từ query của assistant message
          msgs.push({
            id: `${m.id}_user`,
            content: m.query,
            isUser: true,
            timestamp: new Date(m.created_at),
          })
          // Tạo assistant message từ content
          msgs.push({
            id: m.id,
            content: m.content,
            isUser: false,
            timestamp: new Date(m.created_at),
          })
        } else if (m.role === "user") {
          // User message bình thường
          msgs.push({
            id: m.id,
            content: m.content,
            isUser: true,
            timestamp: new Date(m.created_at),
          })
        }
      })

      setMessages(msgs)
    } catch (error) {
      setMessages([{
        id: "error",
        content: t("chat.failedToLoadMessages"),
        isUser: false,
        timestamp: new Date(),
      }])
    }
  }

  useEffect(() => {
    const init = async () => {
      try {
        const response: any = await apiService.chat.getSessions()
        const sess = Array.isArray(response) ? response : (response.sessions || response || [])
        setSessions(sess)
        if (sess.length > 0) {
          setCurrentSessionId(sess[0].session_id || sess[0].id)
          await loadMessages(sess[0].session_id || sess[0].id)
        } else {
          try {
            const sessionResult = await apiService.chat.createSession()
            setCurrentSessionId(sessionResult.session_id)
            setMessages([])
          } catch (error) {
            setCurrentSessionId(null)
            setMessages([
              {
                id: "error",
                content: t("chat.failedToCreateSession"),
                isUser: false,
                timestamp: new Date(),
              },
            ])
          }
        }
      } catch (error) {
        setSessions([])
        setCurrentSessionId(null)
        setMessages([
          {
            id: "error",
            content: t("chat.failedToLoadChatData"),
            isUser: false,
            timestamp: new Date(),
          },
        ])
      }
    }
    init()
  }, [user?.tenant_id, t])

  const handleNewChat = async () => {
    try {
      const sessionResult = await apiService.chat.createSession()
      const sessionId = sessionResult.session_id

      setCurrentSessionId(sessionId)
      setMessages([])

      const response = await apiService.chat.getSessions()
      const sess = Array.isArray(response) ? response : (response.sessions || response || [])
      setSessions(sess)
    } catch (error) {
      setMessages([
        {
          id: "error",
          content: t("chat.failedToCreateSession"),
          isUser: false,
          timestamp: new Date(),
        },
      ])
    }
  }

  const handleSelectSession = async (id: string) => {
    setCurrentSessionId(id)
    await loadMessages(id)
  }

  const handleDeleteSession = async (sessionId: string, sessionTitle: string) => {
    setSessionToDelete({ id: sessionId, title: sessionTitle })
    setDeleteConfirmOpen(true)
  }

  const confirmDeleteSession = async () => {
    if (!sessionToDelete) return

    try {
      await apiService.chat.deleteSession(sessionToDelete.id)

      // Update sessions list
      const response: any = await apiService.chat.getSessions()
      const updatedSessions = Array.isArray(response) ? response : (response.sessions || response || [])
      setSessions(updatedSessions)

      // If current session is deleted, reset to first session or create new
      if (currentSessionId === sessionToDelete.id) {
        if (updatedSessions.length > 0) {
          const firstSession = updatedSessions[0]
          setCurrentSessionId(firstSession.session_id || firstSession.id)
          await loadMessages(firstSession.session_id || firstSession.id)
        } else {
          // No sessions left, create new one
          try {
            const sessionResult = await apiService.chat.createSession()
            setCurrentSessionId(sessionResult.session_id)
            setMessages([])
          } catch (error) {
            setCurrentSessionId(null)
            setMessages([])
          }
        }
      }

    } catch (error) {
    } finally {
      setDeleteConfirmOpen(false)
      setSessionToDelete(null)
    }
  }

  const handleEditTitle = (sessionId: string, currentTitle: string) => {
    setEditingSession({ id: sessionId, title: currentTitle })
    setEditTitleValue(currentTitle)
  }

  const saveTitleEdit = async () => {
    if (!editingSession || !editTitleValue.trim()) return

    try {
      await apiService.chat.updateTitle(editingSession.id, editTitleValue.trim())

      // Update sessions list
      const response: any = await apiService.chat.getSessions()
      const updatedSessions = Array.isArray(response) ? response : (response.sessions || response || [])
      setSessions(updatedSessions)

    } catch (error) {
    } finally {
      setEditingSession(null)
      setEditTitleValue("")
    }
  }

  const cancelTitleEdit = () => {
    setEditingSession(null)
    setEditTitleValue("")
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading || !currentSessionId) return

    const currentInput = inputValue
    const isFirstMessageOfNewSession = messages.length === 0

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      isUser: true,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue("")
    setIsLoading(true)
    setCurrentPlanningData(null)  // Clear previous planning data

    let actualSessionId = currentSessionId

    // Title generation is now handled automatically by backend in /chat/query
    // No need for separate generateTitle() call

    const streamingId = (Date.now() + 1).toString()
    setStreamingMessageId(streamingId)
    setStreamBuffer((prev) => ({ ...prev, [streamingId]: "" }))

    const initialAiMessage: Message = {
      id: streamingId,
      content: "",
      isUser: false,
      timestamp: new Date(),
      isStreaming: true,
      planningData: null,  
      executionData: null,
    }

    setMessages((prev) => [...prev, initialAiMessage])

    try {
      await apiService.chat.sendMessageStream(
        actualSessionId,
        currentInput,
        (chunk: string) => {
          try {
            const eventData = JSON.parse(chunk)

            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id === streamingId) {
                  let updatedMsg = { ...msg, isStreaming: true }

                  const sseType = eventData.sse_type || eventData.type

                  switch (sseType) {
                    case 1:
                    case 'start':
                      updatedMsg.isStreaming = true
                      
                      if (eventData.session_title && isFirstMessageOfNewSession) {
                        setSessions(prevSessions => 
                          prevSessions.map(session => 
                            (session.session_id === actualSessionId || session.id === actualSessionId) 
                              ? { ...session, title: eventData.session_title, display_title: eventData.session_title }
                              : session
                          )
                        )
                      } 
                      break
                    case 2:
                    case 'plan_execution':
                    case 'plan':
                      setCurrentPlanningData({
                        semantic_routing: eventData.semantic_routing,
                        execution_plan: eventData.execution_plan,
                        progress: eventData.progress || 0,
                        status: eventData.status || 'running',
                        message: eventData.message || 'Planning execution...',
                        ...eventData.planningData
                      })

                      updatedMsg.isStreaming = true
                      updatedMsg.progress = eventData.progress || 0
                      updatedMsg.status = eventData.status || 'running'
                      break

                    case 3:
                    case 'response':
                      if (eventData.content && eventData.type !== 'executeplan') {
                        const nextContent = (updatedMsg.content || "") + eventData.content
                        updatedMsg.content = nextContent
                        updatedMsg.isStreaming = true
                      } else if (eventData.content) {
                        setCurrentPlanningData((prev: any) => ({
                          ...prev,
                          execution_details: eventData.content
                        }))
                      }

                      if (eventData.is_complete) {
                        updatedMsg.isStreaming = false
                      }
                      break

                    case 4:
                    case 'end':
                      updatedMsg.progress = 100
                      updatedMsg.status = eventData.status || 'completed'
                      updatedMsg.isStreaming = false

                      // Chỉ override bằng final_response nếu chưa có nội dung stream
                      if (eventData.final_response && (!updatedMsg.content || !updatedMsg.content.trim())) {
                        updatedMsg.content = eventData.final_response
                      }

                      // Store final planning data if available
                      if (eventData.execution_plan || eventData.execution_metadata) {
                        setCurrentPlanningData((prev: any) => ({
                          ...prev,
                          final_execution_plan: eventData.execution_plan,
                          execution_metadata: eventData.execution_metadata,
                          final_sources: eventData.sources
                        }))
                      }

                      break

                    default:
                      if (eventData.content && !eventData.type?.includes('plan')) {
                        updatedMsg.content = eventData.content
                      }
                      break
                  }

                  return updatedMsg
                }
                return msg
              })
            )
          } catch (e) {
            // Not JSON, treat as text chunk
            setMessages((prev) =>
              prev.map((msg) => (msg.id === streamingId ? { ...msg, content: chunk, isStreaming: true } : msg))
            )
          }
        },
        () => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === streamingId ? { ...msg, isStreaming: false } : msg))
          )
          setStreamingMessageId(null)
          setIsLoading(false)
          // Keep planning data for potential display, don't clear it here
        },
        (error: Error) => {
          if ((error as any).isAuthError || error.message.includes('Authentication Error')) {
            localStorage.removeItem("access_token")
            localStorage.removeItem("refresh_token")
            const currentPath = window.location.pathname
            const loginPath = getCorrectLoginPath(currentPath)
            window.location.href = loginPath
            return
          }

          setMessages((prev) =>
            prev.map((msg) => (msg.id === streamingId ? { ...msg, isStreaming: false, status: 'error', content: `Error: ${error.message}` } : msg))
          )
          setStreamingMessageId(null)
          setIsLoading(false)
          setCurrentPlanningData(null) 
         }
      )
    } catch (error) {
      setStreamingMessageId(null)
      setIsLoading(false)
      setCurrentPlanningData(null)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleDocumentClick = (documentId: string, url: string, title?: string) => {
    setDocumentPreview({ isOpen: true, documentId, url, title })
  }

  return (
    <RouteGuard requireAuth>
      <div className="flex h-screen bg-white">
      {/* Sidebar */}
      <div className="w-80 bg-gray-50 border-r border-gray-200 flex flex-col">
        <div className="p-6 flex items-center gap-2 border-b border-gray-200">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt="Logo"
              className="w-5 h-5 rounded object-cover"
              onError={(e) => {
                const target = e.target as HTMLImageElement
                target.style.display = "none"
                target.parentElement!.innerHTML = `
                  <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
                  </svg>
                `
              }}
            />
          ) : (
            <MessageCircle size={50} className="text-blue-600" />
          )}
          <h1 className="text-lg font-semibold">{chatbotName || t("chat.title")}</h1>
        </div>

        <div className="p-4">
          <button
            onClick={handleNewChat}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg flex items-center gap-2 hover:bg-blue-700"
          >
            <Plus size={16} />
            {t("chat.newChat")}
          </button>
        </div>

        <div className="px-4">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-3 text-gray-400" />
            <input
              type="text"
              placeholder={t("chat.searchPlaceholder", "Search")}
              className="w-full pl-9 pr-4 py-2 bg-gray-100 rounded-lg text-sm"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {sessions.map((sess) => (
            <div
              key={sess.session_id || sess.id}
              className={`p-3 rounded-lg hover:bg-gray-100 text-sm flex items-center gap-3 group ${currentSessionId === (sess.session_id || sess.id) ? 'bg-gray-100' : ''}`}
            >
              <MessageCircle size={16} className="text-gray-400" />
              {editingSession?.id === (sess.session_id || sess.id) ? (
                <input
                  type="text"
                  value={editTitleValue}
                  onChange={(e) => setEditTitleValue(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      saveTitleEdit()
                    } else if (e.key === 'Escape') {
                      cancelTitleEdit()
                    }
                  }}
                  onBlur={saveTitleEdit}
                  className="flex-1 px-2 py-1 text-sm bg-white border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                  autoFocus
                />
              ) : (
                <span
                  className="truncate flex-1 cursor-pointer"
                  onClick={() => handleSelectSession(sess.session_id || sess.id)}
                >
                  {sess.display_title || sess.title ||
                    (sess.message_count > 0 ? t("chat.newChat") : t("chat.untitledChat"))
                  }
                </span>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-200 transition-opacity">
                    <MoreHorizontal size={14} className="text-gray-400" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem
                    onClick={() => handleEditTitle(
                      sess.session_id || sess.id,
                      sess.display_title || sess.title || t("chat.untitledChat")
                    )}
                    className="cursor-pointer"
                  >
                    <span>{t("chat.editTitle") || "Edit Title"}</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => handleDeleteSession(
                      sess.session_id || sess.id,
                      sess.display_title || sess.title || t("chat.untitledChat")
                    )}
                    className="cursor-pointer text-red-600 focus:text-red-600"
                  >
                    <span>Delete Chat</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-gray-200 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
                {user?.first_name?.charAt(0) || user?.email?.charAt(0) || "U"}
              </div>
              <div>
                <span className="text-sm font-medium block">{user?.first_name && user?.last_name ? `${user.first_name} ${user.last_name}` : user?.email || "User"}</span>
                <span className="text-xs text-gray-500">{user?.role?.replace('_', ' ') || ""}</span>
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="p-2 rounded-lg hover:bg-gray-100">
                  <Settings size={16} className="text-gray-600" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <div className="px-2 py-1.5 text-sm text-gray-900">
                  <div className="font-medium">{user?.first_name && user?.last_name ? `${user.first_name} ${user.last_name}` : user?.email || "User"}</div>
                  <div className="text-xs text-gray-500">{user?.role?.replace('_', ' ') || ""}</div>
                </div>
                <DropdownMenuSeparator />
                {isManager && (
                  <>
                    <DropdownMenuItem onClick={handleGoToAdmin} className="cursor-pointer">
                      <User className="mr-2 h-4 w-4" />
                      <span>{t("admin.dashboard")}</span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-red-600">
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>{t("common.logout")}</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {isDeptManager && (
            <Button
              onClick={handleGoToAdmin}
              className="w-full bg-green-600 hover:bg-green-700 text-white"
              size="sm"
            >
              <ArrowLeft size={16} className="mr-2" />
              Go to Admin Panel
            </Button>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">{chatbotName}</p>
            {isManager && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">{t("chat.accessScope")}</span>
                <Select value={scope} onValueChange={(value) => setScope(value as any)}>
                  <SelectTrigger className="w-40 border-gray-300">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="private">
                      <div className="flex items-center gap-2">
                        <Lock size={16} className="text-blue-600" />
                        <span>{t("chat.private")}</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="public">
                      <div className="flex items-center gap-2">
                        <Globe size={16} className="text-green-600" />
                        <span>{t("chat.public")}</span>
                      </div>
                    </SelectItem>
                    <SelectItem value="both">
                      <div className="flex items-center gap-2">
                        <Users size={16} className="text-purple-600" />
                        <span>{t("chat.both")}</span>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="max-w-4xl mx-auto px-4 py-6 space-y-4 min-h-full flex flex-col pb-20">
            {messages.length === 0 && (
              <div className="text-center py-12 flex-grow flex items-center justify-center">
                <div>
                  <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center">
                    <MessageCircle size={32} className="text-blue-600" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    {t("chat.welcomeTitle", "Welcome to Chat")}
                  </h3>
                  <p className="text-gray-500 mb-6">
                    {t("chat.welcomeMessage", "Start a conversation by typing your message below")}
                  </p>
                </div>
              </div>
            )}
            {messages.map((message) => (
              <div key={message.id} className={`flex w-full ${message.isUser ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] ${message.isUser ? "text-right" : "text-left"}`}>
                  {message.isUser ? (
                    <div className="bg-[#f4f4f4] px-4 py-3 rounded-2xl rounded-br-md inline-block">
                      <p className="whitespace-pre-wrap m-0 text-gray-900">{message.content}</p>
                    </div>
                  ) : (
                    <div className="relative">
                      <StreamingMessage
                        content={message.content}
                        isStreaming={message.isStreaming || false}
                        progress={message.progress}
                        status={message.status}
                        onDocumentClick={handleDocumentClick}
                      />
                      {/* Show planning indicator if planning data exists */}
                      {currentPlanningData && !message.isStreaming && (
                        <div className="mt-2 text-xs text-gray-500 flex items-center gap-1">
                          <span>🤖</span>
                          <span>{chatbotName}</span>
                        </div>
                      )}
                    </div>
                  )}
                  {!message.isUser && !message.isStreaming && (
                    <div className="flex items-center gap-2 mt-3">
                      <button className="p-1 rounded hover:bg-gray-100">
                        <ThumbsUp size={16} className="text-gray-500" />
                      </button>
                      <button className="p-1 rounded hover:bg-gray-100">
                        <ThumbsDown size={16} className="text-gray-500" />
                      </button>
                      <button className="p-1 rounded hover:bg-gray-100">
                        <Copy size={16} className="text-gray-500" />
                      </button>
                      <button className="p-1 rounded hover:bg-gray-100">
                        <MoreHorizontal size={16} className="text-gray-500" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Fixed Input Box */}
        <div className="bg-white p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center gap-3 bg-white border border-gray-200 rounded-full p-4 shadow-sm">
              <div className="w-6 h-6 rounded-full bg-red-400 flex items-center justify-center text-white text-xs">❤️</div>
              <input
                type="text"
                placeholder={t("chat.inputPlaceholder", "What's in your mind...?")}
                className="flex-1 outline-none"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
              />
              <button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isLoading}
                className="p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <DocumentPreview
        documentId={documentPreview.documentId}
        url={documentPreview.url}
        isOpen={documentPreview.isOpen}
        onClose={() => setDocumentPreview({ isOpen: false, documentId: "", url: "" })}
      />

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("chat.deleteChat") || "Delete Chat"}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("chat.deleteChatConfirm", {
                title: sessionToDelete?.title || t("chat.untitledChat"),
                defaultValue: `Are you sure you want to delete "${sessionToDelete?.title || t("chat.untitledChat")}"? This action cannot be undone and all messages will be permanently deleted.`
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel") || "Cancel"}</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteSession}
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
            >
              {t("common.delete") || "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
    </RouteGuard>
  )
}
