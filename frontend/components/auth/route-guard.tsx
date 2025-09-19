"use client"

import type React from "react"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth, getPostLoginRedirectPath } from "@/lib/auth-context"
import { hasRole, hasPermission } from "@/lib/tenant-utils"
import type { UserRole } from "@/types"
import { useTranslation } from "react-i18next"

interface RouteGuardProps {
  children: React.ReactNode
  requireAuth?: boolean
  requiredRoles?: UserRole[]
  requiredPermissions?: string[]
  fallbackPath?: string
  loadingComponent?: React.ReactNode
  unauthorizedComponent?: React.ReactNode
}

export function RouteGuard({
  children,
  requireAuth = true,
  requiredRoles = [],
  requiredPermissions = [],
  fallbackPath,
  loadingComponent,
  unauthorizedComponent,
}: RouteGuardProps) {
  const { user, is_authenticated, loading } = useAuth()
  const router = useRouter()
  const [isAuthorized, setIsAuthorized] = useState(false)
  const [authCheckComplete, setAuthCheckComplete] = useState(false)
  const { t } = useTranslation()


  useEffect(() => {
    if (loading) {
      setAuthCheckComplete(false)
      return
    }

    setAuthCheckComplete(true)

    const isLoginPage = window.location.pathname.includes('/login')
    if (is_authenticated && isLoginPage) {
      const redirectPath = getPostLoginRedirectPath(user)
      router.push(redirectPath)
      setIsAuthorized(false)
      return
    }

    if (requireAuth && !is_authenticated) {
      const loginPath = fallbackPath || getCorrectLoginPath(window.location.pathname)
      router.push(loginPath)
      setIsAuthorized(false)
      return
    }

    if (!requireAuth && !is_authenticated) {
      setIsAuthorized(true)
      return
    }

    if (is_authenticated && user) {
      
      if (requiredRoles.length > 0) {
        const hasRequiredRole = hasRole(user.role, requiredRoles)
        
        if (!hasRequiredRole) {
          router.push("/unauthorized")
          setIsAuthorized(false)
          return
        }
      }

      if (requiredPermissions.length > 0) {
        const userPermissions = user.permissions?.map((p) => p.name) || []
        const hasRequiredPermissions = requiredPermissions.every((permission) =>
          hasPermission(userPermissions, permission),
        )
        
        if (!hasRequiredPermissions) {
          router.push("/unauthorized")
          setIsAuthorized(false)
          return
        }
      }
      setIsAuthorized(true)
    } else if (requireAuth) {
      setIsAuthorized(false)
    }
  }, [user, is_authenticated, loading, requireAuth, requiredRoles, requiredPermissions, router, fallbackPath])

  if (loading || !authCheckComplete) {
    return (
      loadingComponent || (
        <div className="min-h-screen bg-background flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
            <div className="space-y-2">
              <p className="text-lg font-medium text-foreground">Checking access...</p>
              <p className="text-sm text-muted-foreground">Please wait</p>
            </div>
          </div>
        </div>
      )
    )
  }

  if (!isAuthorized && authCheckComplete && unauthorizedComponent) {
    return unauthorizedComponent
  }

  if (!isAuthorized) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
            <div className="space-y-2">
              <p className="text-lg font-medium text-foreground">Redirecting...</p>
              <p className="text-sm text-muted-foreground">Please wait</p>
            </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

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

export { getCorrectLoginPath }