"use client"

import type React from "react"
import { createContext, useContext, useEffect, useState } from "react"
import { usePathname } from "next/navigation"
import { useTranslation } from "react-i18next"
import type { Tenant } from "@/types"
import { tenantDetector } from "@/lib/tenant-utils"
import { apiService } from "@/lib/api/index"
import { extractLanguageCode } from "@/lib/api/language"
import { useAuth } from "@/lib/auth-context"

interface TenantContextType {
  tenant: Tenant | null
  tenantId: string | null
  isLoading: boolean
  error: string | null
  refreshTenant: () => Promise<void>
}

const TenantContext = createContext<TenantContextType | undefined>(undefined)

interface TenantProviderProps {
  children: React.ReactNode
  initialTenantId?: string
}

export function TenantProvider({ children, initialTenantId }: TenantProviderProps) {
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [tenantId, setTenantId] = useState<string | null>(initialTenantId || null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pathname = usePathname()
  const { i18n } = useTranslation()
  const { is_authenticated: isAuthenticated } = useAuth()

  useEffect(() => {
    if (typeof window === "undefined") return

    const detectedTenantId = tenantDetector.extractTenantFromUrl(window.location.href)

    if (detectedTenantId !== tenantId) {
      setTenantId(detectedTenantId)
      setTenant(null)
    }
  }, [pathname, tenantId])

  useEffect(() => {
    if (!tenantId) {
      setTenant(null)
      setError(null)
      return
    }

    if (pathname?.includes('/invite') || pathname?.includes('/login') ||
        pathname?.includes('/forgot-password') || pathname?.includes('/reset-password')) {
      setTenant(null)
      setError(null)
      setIsLoading(false)
      return
    }

    fetchTenantDetails(tenantId)
  }, [tenantId, pathname, isAuthenticated])

  const fetchTenantDetails = async (id: string) => {
    if (pathname?.includes('/invite') || pathname?.includes('/login') ||
        pathname?.includes('/forgot-password') || pathname?.includes('/reset-password')) {
      setTenant(null)
      setError(null)
      setIsLoading(false)
      return
    }

    // Skip if not authenticated
    if (!isAuthenticated) {
      console.log("⏳ Skipping tenant fetch - not authenticated")
      setTenant(null)
      setError(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      console.log("🔍 Fetching tenant details for authenticated user")
      const tenantData = await apiService.tenants.getDetail(id)
      setTenant(tenantData)

      if (tenantData.locale) {
        const targetLang = extractLanguageCode(tenantData.locale)
        if (i18n.language !== targetLang) {
          await i18n.changeLanguage(targetLang)
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load tenant"
      setError(errorMessage)
      console.error("Failed to fetch tenant details:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const refreshTenant = async () => {
    if (tenantId) {
      await fetchTenantDetails(tenantId)
    }
  }

  const value: TenantContextType = {
    tenant,
    tenantId,
    isLoading,
    error,
    refreshTenant,
  }

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useTenant() {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider")
  }
  return context
}

/**
 * Hook to check if current route is tenant-specific
 */
export function useIsTenantRoute(): boolean {
  const { tenantId } = useTenant()
  return tenantId !== null
}

/**
 * Hook to generate tenant-specific URLs
 */
export function useTenantUrl() {
  const { tenantId } = useTenant()

  const generateUrl = (path = ""): string => {
    if (!tenantId) return path

    return tenantDetector.generateTenantUrl(tenantId, path)
  }

  return { generateUrl, tenantId }
}

/**
 * Hook to get tenant settings including branding
 */
export function useTenantSettings() {
  const [settings, setSettings] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const { tenantId } = useTenant()
  const { is_authenticated } = useAuth()

  useEffect(() => {
    if (!tenantId || !is_authenticated) {
      setSettings(null)
      return
    }

    fetchSettings()
  }, [tenantId, is_authenticated])

  const fetchSettings = async () => {
    if (!tenantId) return

    setIsLoading(true)
    try {
      const settingsData = await apiService.tenantSettings.getSettings()
      setSettings(settingsData)
    } catch (error) {
      setSettings(null)
    } finally {
      setIsLoading(false)
    }
  }

  const getLogoUrl = (): string | null => {
    if (!settings?.branding?.logo_url) {
      return null
    }
    return settings.branding.logo_url
  }

  const getBotName = (): string => {
    return settings?.bot_name || "AI Assistant"
  }

  return {
    settings,
    isLoading,
    getLogoUrl,
    getBotName,
    refreshSettings: fetchSettings
  }
}
