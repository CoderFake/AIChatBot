"use client"

import type React from "react"
import { createContext, useContext, useReducer, useEffect } from "react"
import type { User, Tenant, Permission } from "@/types"
import { apiService } from "@/lib/api/index"

interface AuthContextType {
  user: User | null
  tenant: Tenant | null
  permissions: Permission[]
  is_authenticated: boolean
  loading: boolean
  login: (username: string, password: string, tenantId?: string) => Promise<void>
  logout: () => Promise<void>
  setCurrentTenant: (tenant: Tenant | null) => void
  requestPasswordReset: (email: string) => Promise<void>
  resetPassword: (token: string, newPassword: string) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

type AuthAction =
  | { type: "LOGIN_START" }
  | { type: "LOGIN_SUCCESS"; payload: { user: User; tenant?: Tenant; permissions: Permission[] } }
  | { type: "LOGIN_ERROR"; payload: string }
  | { type: "LOGOUT" }
  | { type: "SET_TENANT"; payload: Tenant | null }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "INIT_SUCCESS"; payload: { user: User; tenant?: Tenant; permissions: Permission[] } }
  | { type: "INIT_FAILED" }

type AuthState = {
  user: User | null
  tenant: Tenant | null
  permissions: Permission[]
  is_authenticated: boolean
  loading: boolean
}

const initialState: AuthState = {
  user: null,
  tenant: null,
  permissions: [],
  is_authenticated: false,
  loading: true,
}

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case "LOGIN_START":
      return { ...state, loading: true }
    case "LOGIN_SUCCESS":
      return {
        ...state,
        user: action.payload.user,
        tenant: action.payload.tenant || null,
        permissions: action.payload.permissions,
        is_authenticated: true,
        loading: false,
      }
    case "LOGIN_ERROR":
      return {
        ...state,
        loading: false,
        is_authenticated: false,
      }
    case "INIT_SUCCESS":
      return {
        ...state,
        user: action.payload.user,
        tenant: action.payload.tenant || null,
        permissions: action.payload.permissions,
        is_authenticated: true,
        loading: false,
      }
    case "INIT_FAILED":
      return {
        ...initialState,
        loading: false,
      }
    case "LOGOUT":
      return {
        ...initialState,
        loading: false,
      }
    case "SET_TENANT":
      return { ...state, tenant: action.payload }
    case "SET_LOADING":
      return { ...state, loading: action.payload }
    default:
      return state
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState)

  useEffect(() => {
    initializeAuth()
  }, [])

  const initializeAuth = async () => {
    const token = localStorage.getItem("access_token")
    const refreshToken = localStorage.getItem("refresh_token")
    
    if (!token) {
      dispatch({ type: "INIT_FAILED" })
      return
    }

    try {
      apiService.setToken(token)

      const userProfile = await apiService.auth.getProfile()
      
      dispatch({
        type: "INIT_SUCCESS",
        payload: {
          user: {
            id: userProfile.user_id,
            username: userProfile.username,
            email: userProfile.email,
            first_name: userProfile.full_name?.split(' ')[0] || '',
            last_name: userProfile.full_name?.split(' ').slice(1).join(' ') || '',
            is_active: true,
            role: userProfile.role as any,
            tenant_id: userProfile.tenant_id,
            department_id: userProfile.department_id,
            permissions: [],
            force_password_change: userProfile.force_password_change || false,
            created_at: userProfile.created_at || new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          permissions: [],
        },
      })
    } catch (error) {
      
      if (refreshToken) {
        try {
          const refreshResponse = await apiService.auth.refreshToken(refreshToken)
          localStorage.setItem("access_token", refreshResponse.access_token)
          apiService.setToken(refreshResponse.access_token)
          
          const userProfile = await apiService.auth.getProfile()
          dispatch({
            type: "INIT_SUCCESS",
            payload: {
              user: {
                id: userProfile.user_id,
                username: userProfile.username,
                email: userProfile.email,
                first_name: userProfile.full_name?.split(' ')[0] || '',
                last_name: userProfile.full_name?.split(' ').slice(1).join(' ') || '',
                is_active: true,
                role: userProfile.role as any,
                tenant_id: userProfile.tenant_id,
                department_id: userProfile.department_id,
                permissions: [],
                force_password_change: userProfile.force_password_change || false,
                created_at: userProfile.created_at || new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
              permissions: [],
            },
          })
        } catch (refreshError) {
          localStorage.removeItem("access_token")
          localStorage.removeItem("refresh_token")
          dispatch({ type: "INIT_FAILED" })

          const currentPath = window.location.pathname
          if (!currentPath.includes('/login') && !currentPath.includes('/forgot-password')) {
            const loginPath = getCorrectLoginPath(currentPath)
            window.location.href = loginPath
          }
        }
      } else {
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        dispatch({ type: "INIT_FAILED" })

        const currentPath = window.location.pathname
        if (!currentPath.includes('/login') && !currentPath.includes('/forgot-password')) {
          const loginPath = getCorrectLoginPath(currentPath)
          window.location.href = loginPath
        }
      }
    }
  }

  const login = async (username: string, password: string, tenantId?: string) => {
    dispatch({ type: "LOGIN_START" })
    try {
      const response = await apiService.auth.login({ username, password, tenant_id: tenantId })

      localStorage.setItem("access_token", response.access_token)
      localStorage.setItem("refresh_token", response.refresh_token)
      apiService.setToken(response.access_token)

      dispatch({
        type: "LOGIN_SUCCESS",
        payload: {
          user: {
            id: response.user_id,
            username: response.username,
            email: response.email,
            first_name: response.full_name?.split(' ')[0] || '',
            last_name: response.full_name?.split(' ').slice(1).join(' ') || '',
            is_active: true,
            role: response.role as any,
            tenant_id: response.tenant_id,
            department_id: response.department_id,
            permissions: [],
            force_password_change: response.force_password_change || false,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          permissions: [],
        },
      })
    } catch (error) {
      dispatch({ type: "LOGIN_ERROR", payload: error instanceof Error ? error.message : "Login failed" })
      throw error
    }
  }

  const logout = async () => {
    try {
      await apiService.auth.logout()
    } catch (error) {
      console.error("Logout API call failed:", error)
    } finally {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      dispatch({ type: "LOGOUT" })
    }
  }

  const setCurrentTenant = (tenant: Tenant | null) => {
    dispatch({ type: "SET_TENANT", payload: tenant })
  }

  const requestPasswordReset = async (email: string) => {
    await apiService.auth.requestPasswordReset(email)
  }

  const resetPassword = async (token: string, newPassword: string) => {
    await apiService.auth.resetPassword(token, newPassword)
  }

  const value: AuthContextType = {
    ...state,
    login,
    logout,
    setCurrentTenant,
    requestPasswordReset,
    resetPassword,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

// Export helper functions for external use
export { getPostLoginRedirectPath, getCorrectLoginPath }

const getCorrectLoginPath = (currentPath: string): string => {
  if (currentPath.startsWith('/system-admin') || currentPath === '/') {
    return '/system-admin/login'
  }

  const tenantMatch = currentPath.match(/^\/([^\/]+)/)
  if (tenantMatch && tenantMatch[1] && tenantMatch[1] !== 'system-admin') {
    return `/${tenantMatch[1]}/login`
  }

  return '/system-admin/login'
}

const getPostLoginRedirectPath = (user: User | null): string => {
  if (!user) return '/system-admin/login'

  if (user.role === 'MAINTAINER') {
    return '/system-admin/dashboard'
  }

  if (user.tenant_id) {

    const adminRoles = ['TENANT_ADMIN', 'DEPARTMENT_ADMIN']
    if (adminRoles.includes(user.role as string)) {
      return `/${user.tenant_id}/admin`
    }
    
    return `/${user.tenant_id}/chat`
  }

  return '/system-admin/login'
}