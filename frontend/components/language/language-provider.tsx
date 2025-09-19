"use client"

import type React from "react"
import { createContext, useContext, useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import i18n from "@/lib/i18n"
import { languageApi, type TenantLanguageResponse } from "@/lib/api/language"
import { useTenant } from "@/lib/tenant-context"
import { useAuth } from "@/lib/auth-context"

interface LanguageContextType {
  currentLanguage: string
  tenantSettings: TenantLanguageResponse | null
  changeLanguage: (language: string) => void
  isLoading: boolean
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  let tenantContext
  let user

  try {
    tenantContext = useTenant()
  } catch {
    tenantContext = null
  }

  try {
    const authContext = useAuth()
    user = authContext.user
  } catch {
    user = null
  }

  const [tenantSettings, setTenantSettings] = useState<TenantLanguageResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentLanguage, setCurrentLanguage] = useState(i18n.language || 'en')

  useEffect(() => {
    const loadTenantLanguage = async () => {
      if (tenantContext && tenantContext.tenant?.id && user?.role !== "MAINTAINER") {
        setIsLoading(true)
        try {
          const settings = await languageApi.getTenantLanguage(tenantContext.tenant.id)
          setTenantSettings(settings)

          if (settings.language !== i18n.language) {
            await i18n.changeLanguage(settings.language)
            setCurrentLanguage(settings.language)
          }
        } catch (error) {
          console.warn("Failed to load tenant language settings:", error)
        } finally {
          setIsLoading(false)
        }
      }
    }

    loadTenantLanguage()
  }, [tenantContext?.tenant?.id, user?.role])

  const changeLanguage = async (language: string) => {
    try {
      await i18n.changeLanguage(language)
      setCurrentLanguage(language)

      if (user?.role === "MAINTAINER") {
        localStorage.setItem("admin-language", language)
      }

    } catch (error) {
      console.error("changeLanguage - Error:", error)
    }
  }

  useEffect(() => {
    if (user?.role === "MAINTAINER") {
      const savedLanguage = localStorage.getItem("admin-language")
      if (savedLanguage && savedLanguage !== i18n.language) {
        changeLanguage(savedLanguage)
      }
    }
  }, [user?.role])

  useEffect(() => {
    document.documentElement.lang = i18n.language
    setCurrentLanguage(i18n.language)
  }, [i18n.language])

  const value: LanguageContextType = {
    currentLanguage,
    tenantSettings,
    changeLanguage,
    isLoading,
  }

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (context === undefined) {
    throw new Error("useLanguage must be used within a LanguageProvider")
  }
  return context
}
