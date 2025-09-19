"use client"

import type React from "react"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useTenant } from "@/lib/tenant-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { useTranslation } from "react-i18next"

interface TenantLayoutProps {
  children: React.ReactNode
  requireValidTenant?: boolean
}

export function TenantLayout({ children, requireValidTenant = true }: TenantLayoutProps) {
  const { tenant, tenantId, isLoading, error, refreshTenant } = useTenant()
  const router = useRouter()
  const { t } = useTranslation()

  useEffect(() => {
    if (!tenantId && requireValidTenant) {
      router.push("/")
      return
    }

    if (tenant && tenant.status !== "active") {
      console.warn("Tenant is inactive:", tenant.tenant_name)
    }
  }, [tenant, tenantId, requireValidTenant, router])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4 overflow-y-auto">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
              <div>
                <h3 className="font-semibold font-sans">{t("common.loading")}</h3>
                <p className="text-sm text-muted-foreground font-serif">{t("common.pleaseWait")}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4 overflow-y-auto">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-destructive" />
            </div>
            <CardTitle className="font-sans">{t("common.workspaceNotFound")}</CardTitle>
            <CardDescription className="font-serif">
              {error || "The requested workspace could not be found or is not accessible."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={refreshTenant} variant="outline" className="w-full font-sans bg-transparent">
              <RefreshCw className="w-4 h-4 mr-2" />
              {t("common.tryAgain")}
            </Button>
            <Button onClick={() => router.push("/")} className="w-full font-sans">
              {t("common.returnToHome")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Inactive tenant state
  if (tenant && tenant.status !== "active") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4 overflow-y-auto">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-muted-foreground" />
            </div>
            <CardTitle className="font-sans">{t("common.workspaceInactive")}</CardTitle>
            <CardDescription className="font-serif">
              {t("common.workspaceInactiveDescription", { tenantName: tenant.tenant_name })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push("/")} className="w-full font-sans">
              {t("common.returnToHome")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
